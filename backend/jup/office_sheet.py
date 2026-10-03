"""Excel workbooks for the assistant (Track O, O2 1/3).

Like `jup.office_doc`, the assistant never writes a file itself. It sends a **spec** (a title, a
classification and a list of sheets, each with typed columns and rows) and this module builds the
.xlsx on the server. No model-written code runs anywhere, so nothing needs a sandbox and nothing
leaves the server.

**Rules the model cannot override** (each tested in `tests/test_jup_office_sheet.py`):

- **No formulas.** A text cell that starts like a formula (`=`, `+`, `-`, `@`, tab, CR) is stored
  as text, never as a formula, so nothing the model writes is ever executed by Excel. Totals are
  computed here and written as values.
- **Numbers stay numbers.** `number`, `idr` and `percent` cells must be numbers (a plain numeric
  string such as "1250000" is accepted); "Rp 1.250.000" is refused rather than guessed, because
  "1.250" means different things in Indonesian and English. Dates must be ISO `YYYY-MM-DD`.
- The status is always **Draf** and the classification follows `office_doc.classification_for`:
  INTERNAL by default, never PUBLIK, never below the caller-supplied `floor`.
- The first sheet, "Info", carries the title, status and classification, and every sheet's
  printed footer repeats them.
- Limits are refused with a message, never silently truncated.

Pure: no app imports, no network, no disk writes. `jup.office_tool` stores the bytes.
"""

from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass
from typing import Any

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from jup.office_doc import MAX_TITLE, STATUS, OfficeDocError, _text, classification_for

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
JAKARTA = dt.timezone(dt.timedelta(hours=7))

MAX_SHEETS = 10
MAX_ROWS = 5_000
MAX_COLS = 50
MAX_CELL = 32_000  # Excel's own limit is 32,767 characters
MAX_CELLS = 100_000
MAX_BYTES = 5 * 1024 * 1024
MAX_SHEET_NAME = 31

COLUMN_TYPES = ('text', 'number', 'idr', 'percent', 'date')
NUMERIC = frozenset({'number', 'idr', 'percent'})
SUMMED = frozenset({'number', 'idr'})
INFO_SHEET = 'Info'

FONT = 'Space Grotesk'
GREEN = '006C34'  # JUP green-700, white text on it measures 6.9:1
_FORMULA_START = ('=', '+', '-', '@', '\t', '\r')
_SHEET_NAME_BAD = re.compile(r'[\[\]:*?/\\]')
_NUMERIC_TEXT = re.compile(r'-?\d+(\.\d+)?')
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


@dataclass
class SheetRendered:
    data: bytes
    filename: str
    title: str
    classification: str
    status: str = STATUS
    sheets: int = 0
    rows: int = 0
    cells: int = 0
    content_type: str = XLSX_MIME


@dataclass
class _Column:
    header: str
    type: str


@dataclass
class _Sheet:
    name: str
    columns: list[_Column]
    rows: list[list[Any]]
    totals: bool


# -- spec validation ---------------------------------------------------------------------------


def _sheet_name(value: Any, index: int, seen: set[str]) -> str:
    name = _text(value, f'Sheet {index} name', MAX_SHEET_NAME)
    if _SHEET_NAME_BAD.search(name):
        raise OfficeDocError(f'Sheet name "{name}" may not contain any of [ ] : * ? / \\.')
    if name.casefold() == INFO_SHEET.casefold():
        raise OfficeDocError(f'"{INFO_SHEET}" is reserved for the cover sheet; choose another sheet name.')
    if name.casefold() in seen:
        raise OfficeDocError(f'Two sheets are named "{name}"; sheet names must be unique.')
    seen.add(name.casefold())
    return name


def _number(value: Any, where: str) -> float | int:
    if isinstance(value, bool):
        raise OfficeDocError(f'{where} must be a number, not true/false.')
    if isinstance(value, (int, float)):
        if value != value or value in (float('inf'), float('-inf')):
            raise OfficeDocError(f'{where} is not a finite number.')
        return value
    if isinstance(value, str) and _NUMERIC_TEXT.fullmatch(value.strip()):
        text = value.strip()
        return float(text) if '.' in text else int(text)
    raise OfficeDocError(
        f'{where} must be a number such as 1250000 or 12.5, without "Rp", spaces or thousands separators; got {value!r}.'
    )


def _date(value: Any, where: str) -> dt.date:
    if isinstance(value, str) and _ISO_DATE.fullmatch(value.strip()):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise OfficeDocError(f'{where} must be a date written YYYY-MM-DD, for example 2026-10-03; got {value!r}.')


def _cell(value: Any, kind: str, where: str) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if kind in NUMERIC:
        number = _number(value, where)
        return number / 100 if kind == 'percent' else number
    if kind == 'date':
        return _date(value, where)
    text = value if isinstance(value, str) else str(value)
    text = ILLEGAL_CHARACTERS_RE.sub('', text)
    if len(text) > MAX_CELL:
        raise OfficeDocError(f'{where} is {len(text)} characters; the limit is {MAX_CELL}.')
    return text


def validate_sheets(sheets: Any) -> list[_Sheet]:
    if not isinstance(sheets, list) or not sheets:
        raise OfficeDocError('The workbook needs at least one sheet: a list of {"name", "columns", "rows"}.')
    if len(sheets) > MAX_SHEETS:
        raise OfficeDocError(f'The workbook has {len(sheets)} sheets; the limit is {MAX_SHEETS}.')
    seen: set[str] = set()
    out: list[_Sheet] = []
    cells = 0
    for index, sheet in enumerate(sheets, start=1):
        if not isinstance(sheet, dict):
            raise OfficeDocError(f'Sheet {index} must be an object with "name", "columns" and "rows".')
        unknown = sorted(set(sheet) - {'name', 'columns', 'rows', 'totals'})
        if unknown:
            raise OfficeDocError(f'Sheet {index} has unknown keys: {", ".join(unknown)}.')
        name = _sheet_name(sheet.get('name'), index, seen)
        raw_columns = sheet.get('columns')
        if not isinstance(raw_columns, list) or not raw_columns:
            raise OfficeDocError(f'Sheet "{name}" needs columns: a list of {{"header", "type"}}.')
        if len(raw_columns) > MAX_COLS:
            raise OfficeDocError(f'Sheet "{name}" has {len(raw_columns)} columns; the limit is {MAX_COLS}.')
        columns = []
        for c, column in enumerate(raw_columns, start=1):
            if not isinstance(column, dict):
                raise OfficeDocError(f'Sheet "{name}" column {c} must be an object with "header" and "type".')
            kind = str(column.get('type') or 'text').strip().lower()
            if kind not in COLUMN_TYPES:
                raise OfficeDocError(
                    f'Sheet "{name}" column {c} has type "{column.get("type")}"; use one of: {", ".join(COLUMN_TYPES)}.'
                )
            columns.append(_Column(_text(column.get('header'), f'Sheet "{name}" column {c} header', 200), kind))
        raw_rows = sheet.get('rows')
        if raw_rows is None:
            raw_rows = []
        if not isinstance(raw_rows, list):
            raise OfficeDocError(f'Sheet "{name}" rows must be a list of lists.')
        if len(raw_rows) > MAX_ROWS:
            raise OfficeDocError(f'Sheet "{name}" has {len(raw_rows)} rows; the limit is {MAX_ROWS}. Split it.')
        rows = []
        for r, row in enumerate(raw_rows, start=1):
            if not isinstance(row, list):
                raise OfficeDocError(f'Sheet "{name}" row {r} must be a list of cell values.')
            if len(row) > len(columns):
                raise OfficeDocError(
                    f'Sheet "{name}" row {r} has {len(row)} cells but the sheet has {len(columns)} columns.'
                )
            padded = row + [None] * (len(columns) - len(row))
            rows.append(
                [
                    _cell(value, column.type, f'Sheet "{name}" row {r}, column "{column.header}"')
                    for value, column in zip(padded, columns)
                ]
            )
        cells += len(rows) * len(columns)
        if cells > MAX_CELLS:
            raise OfficeDocError(f'The workbook has more than {MAX_CELLS} cells; split it into smaller exports.')
        out.append(_Sheet(name, columns, rows, bool(sheet.get('totals'))))
    return out


# -- rendering ---------------------------------------------------------------------------------


def _format(column: _Column, values: list[Any]) -> str | None:
    whole = all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in values if v is not None)
    if column.type == 'number':
        return '#,##0' if whole else '#,##0.00'
    if column.type == 'idr':
        return '"Rp" #,##0' if whole else '"Rp" #,##0.00'
    if column.type == 'percent':
        return '0.0%'
    if column.type == 'date':
        return 'dd/mm/yyyy'
    return None


def _as_text(cell) -> None:
    """Keep a string a string: openpyxl would otherwise store "=..." as a formula."""
    cell.data_type = 's'


def _footer(ws, title: str, level: str) -> None:
    ws.oddFooter.left.text = f'{level} · {STATUS}'
    ws.oddFooter.right.text = title[:100]


def _width(values: list[Any], header: str) -> float:
    longest = max([len(header)] + [len(str(v)) for v in values[:500] if v is not None])
    return float(min(max(longest + 2, 8), 60))


def _write_info(ws, title: str, level: str, author: str, now: dt.datetime, sheets: list[_Sheet]) -> None:
    ws.title = INFO_SHEET
    rows = [
        ('Judul', title),
        ('Status', STATUS),
        ('Klasifikasi', level),
        ('Dibuat oleh', 'Asisten JUP' + (f' untuk {author}' if author else '')),
        ('Tanggal dibuat', now.strftime('%d/%m/%Y %H:%M WIB')),
        ('Lembar', ', '.join(s.name for s in sheets)),
        ('Catatan', 'Draf untuk ditinjau sebelum digunakan. Tidak ada rumus: total dihitung saat dibuat.'),
    ]
    for r, (label, value) in enumerate(rows, start=1):
        ws.cell(row=r, column=1, value=label).font = Font(name=FONT, bold=True)
        cell = ws.cell(row=r, column=2, value=value)
        _as_text(cell)
        cell.font = Font(name=FONT, bold=label == 'Klasifikasi')
        cell.alignment = Alignment(wrap_text=True, vertical='top')
    ws.column_dimensions['A'].width = 16
    ws.column_dimensions['B'].width = 80
    _footer(ws, title, level)


def _write_sheet(ws, sheet: _Sheet, title: str, level: str) -> None:
    header_font = Font(name=FONT, bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor=GREEN)
    body_font = Font(name=FONT)
    for c, column in enumerate(sheet.columns, start=1):
        cell = ws.cell(row=1, column=c, value=column.header)
        _as_text(cell)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical='center', wrap_text=True)
    formats = [_format(column, [row[c] for row in sheet.rows]) for c, column in enumerate(sheet.columns)]
    for r, row in enumerate(sheet.rows, start=2):
        for c, (value, column) in enumerate(zip(row, sheet.columns), start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = body_font
            if column.type == 'text' and value is not None:
                _as_text(cell)
            if formats[c - 1] and value is not None:
                cell.number_format = formats[c - 1]
    last = len(sheet.rows) + 1
    if sheet.totals and sheet.rows:
        total_row = last + 1
        label_col = next((i for i, col in enumerate(sheet.columns, start=1) if col.type == 'text'), None)
        if label_col is not None:
            cell = ws.cell(row=total_row, column=label_col, value='Total')
            _as_text(cell)
            cell.font = Font(name=FONT, bold=True)
        for c, column in enumerate(sheet.columns, start=1):
            if column.type not in SUMMED:
                continue
            total = sum(row[c - 1] for row in sheet.rows if row[c - 1] is not None)
            cell = ws.cell(row=total_row, column=c, value=total)
            cell.font = Font(name=FONT, bold=True)
            cell.number_format = formats[c - 1] or '#,##0'
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{get_column_letter(len(sheet.columns))}{last}'
    for c, column in enumerate(sheet.columns, start=1):
        ws.column_dimensions[get_column_letter(c)].width = _width([row[c - 1] for row in sheet.rows], column.header)
    _footer(ws, title, level)


def filename_for(title: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '-', title).strip('-')[:60] or 'lembar-kerja'
    return f'JUP-XLS-{slug}-Draf.xlsx'


def render_sheet(
    title: Any,
    sheets: Any,
    *,
    classification: Any = None,
    floor: Any = None,
    author: str = '',
    now: dt.datetime | None = None,
) -> SheetRendered:
    """Build a workbook from a spec. Raises `OfficeDocError` for anything it will not render."""
    clean_title = _text(title, 'The title', MAX_TITLE)
    level = classification_for(classification, floor)
    clean = validate_sheets(sheets)
    moment = (now or dt.datetime.now(JAKARTA)).astimezone(JAKARTA)

    workbook = Workbook()
    _write_info(workbook.active, clean_title, level, author[:200], moment, clean)
    for sheet in clean:
        _write_sheet(workbook.create_sheet(sheet.name), sheet, clean_title, level)
    workbook.active = 0

    props = workbook.properties
    props.title = clean_title
    props.creator = author[:200] or 'Asisten JUP'
    props.lastModifiedBy = 'Asisten JUP'
    props.keywords = 'JUP-XLS'
    props.description = f'Draf dibuat oleh Asisten JUP. Klasifikasi: {level}.'

    out = io.BytesIO()
    workbook.save(out)
    data = out.getvalue()
    if len(data) > MAX_BYTES:
        raise OfficeDocError(f'The workbook would be {len(data)} bytes; the limit is {MAX_BYTES}. Split it.')
    return SheetRendered(
        data=data,
        filename=filename_for(clean_title),
        title=clean_title,
        classification=level,
        sheets=len(clean),
        rows=sum(len(s.rows) for s in clean),
        cells=sum(len(s.rows) * len(s.columns) for s in clean),
    )


__all__ = [
    'COLUMN_TYPES',
    'MAX_ROWS',
    'MAX_SHEETS',
    'SheetRendered',
    'XLSX_MIME',
    'filename_for',
    'render_sheet',
    'validate_sheets',
]
