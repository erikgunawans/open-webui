"""JUP's decisions register, read from `DECISIONS.md`: Decisions and the open items behind them.

A5 + E5, ticket 5/7. A Decision (glossary: `CONTEXT.md`) can already be found through the
Strategy KB, but only by similarity search, which returns fragments and sometimes loses the
status that says whether the Decision still stands. This reads the register whole, so a
question about D20 gets D20, and "D18 was reversed" is itself an answer.

**Served as written.** A reversed or superseded Decision is not filtered out or rewritten: its
status is part of the answer. Only the Markdown bold markers are removed.

**A register that cannot be read is an error, never an empty result.** "Nothing found" and
"could not read the register" must not look alike to the model, or it will tell a director
that JUP never decided something it did.

Pure: standard library only, no network, no database (see `jup/__init__.py`). The MCP server in
`jup_mcp/decisions.py` is a thin wrapper over `load_register` and the two `render_*` functions.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = '/srv/jup/DECISIONS.md'  # the read-only records mount (deploy/gcp/deploy.sh)

_DECISION_HEADER = ['#', 'Decision', 'Status', 'Why', 'Date']
_OPEN_ITEM_HEADER = ['Item', 'Blocks', 'Counterparty']
_NON_COVERAGE = re.compile(r'\s*named non-coverage\s*:\s*', re.IGNORECASE)
_NUMBER = re.compile(r'^D(\d+)$')
_CELL_SPLIT = re.compile(r'(?<!\\)\|')
_WORD = re.compile(r'\w+', re.UNICODE)
_ONE_LINE_MAX = 240


class DecisionsError(Exception):
    """The register is missing or cannot be read as a register. Never means 'no results'."""


@dataclass(frozen=True)
class Decision:
    number: str
    decision: str
    status: str
    reasoning: str
    non_coverage: str
    date: str

    @property
    def one_line(self) -> str:
        first = re.split(r'(?<=[.!?])\s+', self.decision, maxsplit=1)[0]
        return first if len(first) <= _ONE_LINE_MAX else first[: _ONE_LINE_MAX - 1].rstrip() + '…'


@dataclass(frozen=True)
class OpenItem:
    item: str
    blocks: str
    counterparty: str

    def blocks_decision(self, number: str) -> bool:
        return re.search(rf'\b{re.escape(number)}\b', self.blocks) is not None


@dataclass(frozen=True)
class Register:
    decisions: tuple[Decision, ...]
    open_items: tuple[OpenItem, ...]

    def get(self, number: str) -> Decision | None:
        wanted = _normalise_number(number)
        return next((d for d in self.decisions if d.number == wanted), None)

    def search(self, query: str) -> list[Decision]:
        """Decisions ranked by how many query words they hold, then by where they hold them."""
        if _normalise_number(query) and self.get(query):
            return [self.get(query)]
        words = _words(query)
        scored = []
        for order, d in enumerate(self.decisions):
            headline = d.decision.lower()
            rest = ' '.join((d.status, d.reasoning, d.non_coverage)).lower()
            hits = [w for w in words if w in headline or w in rest]
            if hits:
                weight = sum(3 if w in headline else 1 for w in hits)
                scored.append((-len(hits), -weight, order, d))
        return [d for *_, d in sorted(scored, key=lambda s: s[:3])]

    def search_open_items(self, query: str) -> list[OpenItem]:
        words = _words(query)
        return [
            i for i in self.open_items if any(w in ' '.join((i.item, i.blocks, i.counterparty)).lower() for w in words)
        ]


def default_path() -> Path:
    return Path(os.environ.get('JUP_DECISIONS_FILE', '').strip() or DEFAULT_PATH)


def load_register(path: Path | None) -> Register:
    """Read the register at `path`. Raises `DecisionsError` for anything short of a real register."""
    if path is None:
        raise DecisionsError('the decisions register path is not configured')
    try:
        text = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        raise DecisionsError(f'the decisions register was not found at {path}') from None
    except (OSError, UnicodeDecodeError) as error:
        raise DecisionsError(f'the decisions register at {path} could not be read: {error}') from None

    rows = _table(text, _DECISION_HEADER)
    if rows is None:
        raise DecisionsError(f'{path} has no decisions table (a "| # | Decision | Status | Why | Date |" header)')
    if not rows:
        raise DecisionsError(f'{path} has a decisions table with no decisions in it')
    decisions = tuple(_decision(cells, n, path) for n, cells in enumerate(rows, start=1))

    items = _table(text, _OPEN_ITEM_HEADER) or []
    open_items = tuple(_open_item(cells, n, path) for n, cells in enumerate(items, start=1))
    return Register(decisions=decisions, open_items=open_items)


def render_search(register: Register, query: str) -> str:
    """The `search_decisions` answer: number, one-line decision and status for each match."""
    decisions = register.search(query)
    items = register.search_open_items(query)
    if not decisions and not items:
        return (
            f'No decision or open item matches {query!r}. This is a real absence in the register, not a '
            f'read failure. Decisions on record: {_numbers(register)}. Use get_decision for one by number.'
        )
    lines = []
    if decisions:
        lines += [f'Decisions matching {query!r} (use get_decision for the full text):', '']
        lines += [f'- **{d.number}** [{d.status}] {d.one_line}' for d in decisions]
    if items:
        lines += ['', 'Open items waiting on someone else:', '']
        lines += [_open_item_line(i) for i in items]
    lines += ['', _SOURCE]
    return '\n'.join(lines).strip()


def render_decision(register: Register, number: str) -> str:
    """The `get_decision` answer: the whole Decision, with what it does not cover."""
    d = register.get(number)
    if d is None:
        return f'No decision {number.strip()} in the register. Decisions on record: {_numbers(register)}.'
    blocking = [i for i in register.open_items if i.blocks_decision(d.number)]
    lines = [
        f'# {d.number}: {d.decision}',
        '',
        f'- Status: {d.status}',
        f'- Date: {d.date}',
        '',
        '## Why',
        '',
        d.reasoning or 'No reasoning recorded.',
        '',
        '## Named non-coverage (what this decision does not cover)',
        '',
        d.non_coverage or 'none named in the register.',
    ]
    if blocking:
        lines += ['', '## Open items blocking it', '']
        lines += [_open_item_line(i) for i in blocking]
    lines += ['', _SOURCE]
    return '\n'.join(lines)


_SOURCE = (
    "Source: JUP's decision register (DECISIONS.md), served as written. "
    'A reversed or superseded status is part of the answer; report it.'
)


def _table(text: str, header: list[str]) -> list[list[str]] | None:
    """The body rows of the first table whose header is `header`, or None when there is none."""
    lines = text.splitlines()
    for at, line in enumerate(lines):
        if _cells(line) == header:
            rows = []
            for row in lines[at + 2 :]:  # skip the |---| separator
                if not row.strip().startswith('|'):
                    break
                rows.append(_cells(row))
            return rows
    return None


def _cells(line: str) -> list[str] | None:
    line = line.strip()
    if not line.startswith('|'):
        return None
    parts = _CELL_SPLIT.split(line)
    return [_plain(p) for p in parts[1:-1]] if line.endswith('|') else [_plain(p) for p in parts[1:]]


def _plain(cell: str) -> str:
    return cell.replace('\\|', '|').replace('**', '').strip()


def _decision(cells: list[str], n: int, path: Path) -> Decision:
    if len(cells) != len(_DECISION_HEADER):
        raise DecisionsError(f'{path}: row {n} of the decisions table has {len(cells)} cells, expected 5')
    number, decision, status, why, date = cells
    if not _NUMBER.match(number):
        raise DecisionsError(f'{path}: row {n} of the decisions table has no decision number (got {number!r})')
    reasoning, non_coverage = _split_why(why)
    return Decision(
        number=number,
        decision=decision,
        status=status,
        reasoning=reasoning,
        non_coverage=non_coverage,
        date=date,
    )


def _split_why(why: str) -> tuple[str, str]:
    """The register's convention: a Why cell names what the decision does not cover after a marker."""
    reasoning, non_coverage = (*_NON_COVERAGE.split(why, maxsplit=1), '')[:2]
    return reasoning.strip(), non_coverage.strip()


def _open_item(cells: list[str], n: int, path: Path) -> OpenItem:
    if len(cells) != len(_OPEN_ITEM_HEADER):
        raise DecisionsError(f'{path}: row {n} of the open-items table has {len(cells)} cells, expected 3')
    return OpenItem(*cells)


def _open_item_line(i: OpenItem) -> str:
    return f'- {i.item}. Blocks: {i.blocks}. Waiting on: {i.counterparty}.'


def _normalise_number(value: str) -> str:
    value = value.strip().upper()
    if value.isdigit():
        value = f'D{value}'
    return value if _NUMBER.match(value) else ''


def _words(query: str) -> list[str]:
    return list(dict.fromkeys(w for w in _WORD.findall(query.lower()) if len(w) >= 3 or w.isdigit()))


def _numbers(register: Register) -> str:
    return ', '.join(d.number for d in register.decisions)


__all__ = [
    'DEFAULT_PATH',
    'Decision',
    'DecisionsError',
    'OpenItem',
    'Register',
    'default_path',
    'load_register',
    'render_decision',
    'render_search',
]
