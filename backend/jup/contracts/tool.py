"""The `jup_contracts` tool's logic: search, one card, OCR pages. `tools/jup_contracts.py` only wraps it.

Every call resolves the caller's grants itself (a tool receives the user, not their permissions), and
filters and masks before returning a word: the model reads only what this reader may see, with every
individual party as a code. Each contract is cited by its reference (the run number, e.g. `0042`) and
its card state (D1). Source folder and file names are never returned: they often carry the partner's
name, which for an individual is the person.

Each call writes one `jup.governance` line with the user, the operation and the references returned.

**Restricted reads mark the chat** (`jup.office_floor`): a card shown with its money fields, or
contract page text, makes every file later created in that chat at least TERBATAS. If the mark
cannot be written the read is refused, so no restricted text reaches a chat without its label.
"""

import asyncio
import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import or_, select

from jup import office_floor
from jup.contracts import access, cards
from jup.contracts.access import Access, Withheld
from jup.contracts.models import contract, party, party_link
from jup.governance import audit

MAX_RESULTS = 10
MAX_PAGES = 5
MAX_PAGE_CHARS = 12000
MAIN_RUN = 'full'

UNAVAILABLE = 'Basis kontrak belum tersedia: skema basis datanya belum siap. Laporkan ke admin.'
MARK_FAILED = 'Kontrak tidak dapat ditampilkan saat ini: server gagal mencatat klasifikasi percakapan. Coba lagi.'

log = logging.getLogger(__name__)

# (chat_id, source, message_id) -> None; raises when the mark cannot be written.
Marker = Callable[[str, str, str | None], Any]

LABELS: dict[str, str] = {
    'mitra': 'Mitra',
    'nomor_pks': 'Nomor',
    'judul': 'Judul',
    'tanggal_tanda_tangan': 'Tanggal tanda tangan',
    'jenis_dokumen': 'Jenis dokumen',
    'hak_kewajiban_lingkup': 'Hak, kewajiban dan lingkup',
    'nilai_dan_pembayaran': 'Nilai dan pembayaran',
    'jangka_waktu_perpanjangan': 'Jangka waktu dan perpanjangan',
    'pengakhiran': 'Pengakhiran',
    'wanprestasi_ganti_rugi': 'Wanprestasi dan ganti rugi',
    'kerahasiaan_hki': 'Kerahasiaan dan HKI',
    'keadaan_kahar': 'Keadaan kahar',
    'penyelesaian_sengketa': 'Penyelesaian sengketa',
    'keabsahan': 'Keabsahan',
    'hubungan_dokumen': 'Hubungan dengan dokumen lain',
}


class Source:
    """Where the tool reads from. Production values; tests pass their own."""

    def __init__(
        self,
        engine: Any = None,
        root: Path | str | None = None,
        permissions: Callable[[str], Any] | None = None,
        ready: Callable[[], bool] | None = None,
        today: Callable[[], dt.date] | None = None,
    ) -> None:
        self._engine = engine
        self._root = root
        self._permissions = permissions
        self._ready = ready
        self._today = today or dt.date.today

    @property
    def engine(self) -> Any:
        if self._engine is None:
            from open_webui.internal.db import engine

            self._engine = engine
        return self._engine

    @property
    def root(self) -> Path | None:
        if self._root is None:
            import os

            configured = (os.environ.get('JUP_CONTRACTS_DIR') or '').strip()
            return Path(configured) if configured else None
        return Path(self._root)

    def ready(self) -> bool:
        if self._ready is not None:
            return self._ready()
        from jup.contracts.migrate import schema_ready

        return schema_ready()

    async def reader(self, user_id: str) -> Access:
        if self._permissions is not None:
            permissions = self._permissions(user_id)
            if asyncio.iscoroutine(permissions):
                permissions = await permissions
        else:
            import copy

            from jup.contracts.titles import DEFAULT_PERMISSIONS
            from open_webui.utils.access_control import get_permissions

            permissions = await get_permissions(user_id, copy.deepcopy(DEFAULT_PERMISSIONS))
        return Access.from_permissions(permissions)

    def today(self) -> dt.date:
        return self._today()


def reference(row: dict[str, Any]) -> str:
    return row['number'] if row['run'] == MAIN_RUN else f'{row["run"]}-{row["number"]}'


def _parse_reference(ref: str) -> tuple[str, str] | None:
    ref = (ref or '').strip().lstrip('#').upper().removeprefix('K').removeprefix('-').strip()
    match = re.fullmatch(r'(?:([a-z0-9_]+)-)?(\d{1,6})', ref.lower())
    if not match:
        return None
    run, number = match.group(1) or MAIN_RUN, match.group(2)
    return run, number


def _parties_by_contract(connection: Any, ids: list[str]) -> dict[str, list[dict[str, str]]]:
    found: dict[str, list[dict[str, str]]] = {contract_id: [] for contract_id in ids}
    if not ids:
        return found
    rows = connection.execute(
        select(party_link.c.contract_id, party.c.code, party.c.name)
        .join(party, party.c.id == party_link.c.party_id)
        .where(party_link.c.contract_id.in_(ids))
    ).mappings()
    for row in rows:
        found[row['contract_id']].append({'code': row['code'], 'name': row['name']})
    return found


def _visible_text(view: dict[str, Any] | None) -> str:
    if not view:
        return ''
    parts = [value.get('isi', '') for value in view.values() if isinstance(value, dict)]
    parts.extend(view.get(cards.INDIVIDUALS) or [])
    return ' '.join(parts).casefold()


def _summary_line(row: dict[str, Any], view: dict[str, Any] | None) -> str:
    def field(name: str) -> str:
        value = (view or {}).get(name)
        text = value.get('isi') if isinstance(value, dict) else None
        return text if text and text.strip().lower() != 'tidak tercantum' else '—'

    line = f'[{reference(row)}] {field("judul")} | mitra: {field("mitra")} | nomor: {field("nomor_pks")} | jenis: {field("jenis_dokumen")}'
    if row.get('end_date'):
        line += f' | berakhir: {row["end_date"]}'
    line += f' | status kartu: {access.STATE_LABELS.get(row["state"], row["state"])}'
    if view is None:
        line += ' | tanpa kartu (pindaian tanpa teks)'
    return line


def _footer(reader: Access) -> str:
    notes = access.withheld_notes(reader)
    lines = [
        'Sebutkan status kartu di jawaban: kartu berstatus draf belum ditinjau Tim Legal.',
        'Nama perorangan ditampilkan sebagai kode "Perorangan X"; jangan menebak namanya.',
    ]
    return '\n'.join(lines + notes)


def _search(
    source: Source, reader: Access, query: str, ends_within_days: int | None, state: str | None
) -> tuple[str, list[str]]:
    terms = [term for term in re.split(r'\s+', (query or '').strip()) if term]
    statement = select(contract)
    if state:
        if state not in access.STATE_LABELS:
            return f'Status "{state}" tidak dikenal. Pilihan: draft, approved, returned.', []
        statement = statement.where(contract.c.state == state)
    if ends_within_days is not None:
        today = source.today()
        statement = statement.where(
            contract.c.end_date.is_not(None),
            contract.c.end_date >= today.isoformat(),
            contract.c.end_date <= (today + dt.timedelta(days=int(ends_within_days))).isoformat(),
        )
    for term in terms:
        like = f'%{term}%'
        statement = statement.where(
            or_(
                contract.c.partner.ilike(like),
                contract.c.contract_number.ilike(like),
                contract.c.title.ilike(like),
                contract.c.doc_type.ilike(like),
                contract.c.current_card.ilike(like),
            )
        )
    with source.engine.connect() as connection:
        rows = [
            dict(row) for row in connection.execute(statement.order_by(contract.c.run, contract.c.number)).mappings()
        ]
        parties = _parties_by_contract(connection, [row['id'] for row in rows])
        dated = None
        if ends_within_days is not None:
            dated = connection.execute(select(contract.c.id).where(contract.c.end_date.is_not(None)).limit(1)).first()

    hits = []
    for row in rows:
        view = access.card_view(
            json.loads(row['current_card']) if row['current_card'] else None, reader, parties[row['id']]
        )
        # The SQL match ran on the unfiltered card; a term counts only where this reader can see it.
        visible = _visible_text(view) + ' ' + reference(row)
        if all(term.casefold() in visible for term in terms):
            hits.append((row, view))

    if ends_within_days is not None and dated is None:
        return (
            'Tanggal berakhir kontrak belum diekstrak ke basis kontrak, jadi pencarian berdasarkan tanggal '
            'belum bisa dijawab. Cari dengan kata kunci lalu baca isian "Jangka waktu dan perpanjangan".',
            [],
        )
    if not hits:
        return 'Tidak ada kartu kontrak yang cocok.\n' + _footer(reader), []
    shown = hits[:MAX_RESULTS]
    lines = [
        f'{len(hits)} kartu kontrak cocok' + (f'; {len(shown)} pertama ditampilkan.' if len(hits) > len(shown) else '.')
    ]
    lines.extend(_summary_line(row, view) for row, view in shown)
    lines.append('Baca satu kartu dengan get_contract memakai nomor di dalam kurung siku.')
    lines.append(_footer(reader))
    return '\n'.join(lines), [reference(row) for row, _ in shown]


def load_contract(source: Source, ref: str) -> tuple[dict[str, Any], list[dict[str, str]]] | None:
    parsed = _parse_reference(ref)
    if parsed is None:
        return None
    run, number = parsed
    with source.engine.connect() as connection:
        row = (
            connection.execute(
                select(contract).where(contract.c.run == run, contract.c.number.in_([number, number.zfill(4)]))
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        row = dict(row)
        return row, _parties_by_contract(connection, [row['id']])[row['id']]


def _card_text(source: Source, reader: Access, ref: str) -> tuple[str, list[str]]:
    loaded = load_contract(source, ref)
    if loaded is None:
        return f'Kartu kontrak "{ref}" tidak ditemukan. Cari dulu dengan search_contracts.', []
    row, parties = loaded
    view = access.card_view(json.loads(row['current_card']) if row['current_card'] else None, reader, parties)
    lines = [
        f'Kartu kontrak [{reference(row)}] — status kartu: {access.STATE_LABELS.get(row["state"], row["state"])}',
        f'Jumlah halaman: {row["page_count"]}',
    ]
    if row.get('start_date') or row.get('end_date'):
        renewal = {True: 'ya', False: 'tidak'}.get(row.get('auto_renewal'), 'tidak jelas')
        lines.append(
            f'Tanggal terstruktur (hasil ekstraksi, periksa isian jangka waktu): mulai {row.get("start_date") or "—"}, '
            f'berakhir {row.get("end_date") or "—"}, perpanjangan otomatis: {renewal}'
        )
    if view is None:
        lines.append('Pindaian ini tidak memiliki teks OCR, jadi kartunya tidak dibuat. Tim Legal perlu memeriksanya.')
    else:
        for name in cards.FIELDS:
            value = view.get(name) or {}
            pages = ', '.join(str(n) for n in value.get('halaman') or [])
            lines.append(f'- {LABELS[name]}: {value.get("isi", "—")}' + (f' (hal. {pages})' if pages else ''))
        if view.get(cards.INDIVIDUALS):
            lines.append('- Pihak perorangan: ' + ', '.join(view[cards.INDIVIDUALS]))
    manual = json.loads(row['manual_check_pages'] or '[]')
    low = json.loads(row['low_confidence_pages'] or '[]')
    if manual:
        lines.append('Halaman yang perlu diperiksa manual: ' + ', '.join(map(str, manual)))
    if low:
        lines.append('Halaman dengan OCR berkeyakinan rendah: ' + ', '.join(map(str, low)))
    if reader.fulltext:
        lines.append(f'PDF: /api/v1/contracts/{reference(row)}/pdf')
    lines.append(_footer(reader))
    return '\n'.join(lines), [reference(row)]


def _parse_pages(spec: str) -> list[int]:
    found: list[int] = []
    for part in re.split(r'[,\s]+', (spec or '').strip()):
        if not part:
            continue
        match = re.fullmatch(r'(\d+)(?:-(\d+))?', part)
        if not match:
            raise ValueError(part)
        start = int(match.group(1))
        end = int(match.group(2) or start)
        found.extend(range(start, min(end, start + MAX_PAGES) + 1))
    return sorted(set(found))[:MAX_PAGES]


def _pages_text(source: Source, reader: Access, ref: str, spec: str) -> tuple[str, list[str]]:
    if not reader.fulltext:
        raise Withheld(access.WITHHELD_FULLTEXT)
    try:
        wanted = _parse_pages(spec)
    except ValueError:
        return f'Halaman "{spec}" tidak dapat dibaca. Contoh: "3" atau "3-5".', []
    if not wanted:
        return 'Sebutkan halaman yang ingin dibaca, misalnya "3" atau "3-5".', []
    loaded = load_contract(source, ref)
    if loaded is None:
        return f'Kartu kontrak "{ref}" tidak ditemukan.', []
    row, parties = loaded
    root = source.root
    if root is None:
        return 'Teks lengkap kontrak belum tersedia di server ini. Laporkan ke admin.', []
    path = root / row['run'] / 'ocr-text' / f'{row["number"]}.json'
    try:
        pages = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 'Teks OCR kontrak ini tidak dapat dibaca. Laporkan ke admin.', [reference(row)]
    shown = access.pages_view(pages, wanted, reader, parties)
    lines = [f'Kontrak [{reference(row)}] — status kartu: {access.STATE_LABELS.get(row["state"], row["state"])}']
    budget = MAX_PAGE_CHARS
    for page in shown:
        text = page['teks'][:budget]
        budget -= len(text)
        note = ' (OCR berkeyakinan rendah; periksa PDF)' if page['ocr_rendah'] else ''
        lines.append(f'=== Halaman {page["halaman"]}{note} ===\n{text}')
        if budget <= 0:
            lines.append('[dipotong: batas panjang tercapai]')
            break
    if not shown:
        lines.append(f'Halaman tersebut tidak ada; kontrak ini {row["page_count"]} halaman.')
    lines.append('Kutip nomor halaman di jawaban. Nama perorangan tetap berupa kode.')
    return '\n'.join(lines), [reference(row)]


async def _run(
    operation: str,
    user: dict | None,
    source: Source | None,
    work: Callable[[Source, Access], tuple[str, list[str]]],
    *,
    chat_id: str | None = None,
    message_id: str | None = None,
    restricted: Callable[[Access], bool] | None = None,
    marker: Marker | None = None,
) -> str:
    source = source or Source()
    user_id = (user or {}).get('id')
    if not user_id:
        return 'Pengguna tidak dikenali.'
    if not source.ready():
        audit('contract_read', user=user_id, operation=operation, result='unavailable')
        return UNAVAILABLE
    reader = await source.reader(user_id)
    if not reader.cards:
        audit('contract_read', user=user_id, operation=operation, result='withheld')
        return access.NO_CARDS
    try:
        text, refs = await asyncio.to_thread(work, source, reader)
    except Withheld as refused:
        audit('contract_read', user=user_id, operation=operation, result='withheld')
        return str(refused)
    if chat_id and refs and restricted is not None and restricted(reader):
        try:
            await (marker or office_floor.mark_restricted)(chat_id, 'contracts', message_id=message_id)
        except Exception:
            log.exception('contract_read: marking chat %s restricted failed', chat_id)
            audit('contract_read', user=user_id, operation=operation, result='mark_failed')
            return MARK_FAILED
    audit('contract_read', user=user_id, operation=operation, result='ok', refs=refs)
    return text


async def search_contracts(
    user: dict | None,
    query: str = '',
    ends_within_days: int | None = None,
    state: str | None = None,
    source: Source | None = None,
) -> str:
    return await _run('search', user, source, lambda s, r: _search(s, r, query, ends_within_days, state or None))


async def get_contract(
    user: dict | None,
    ref: str,
    source: Source | None = None,
    chat_id: str | None = None,
    marker: Marker | None = None,
    message_id: str | None = None,
) -> str:
    # A card shows its money fields only to a reader holding `money`.
    return await _run(
        'card',
        user,
        source,
        lambda s, r: _card_text(s, r, ref),
        chat_id=chat_id,
        message_id=message_id,
        restricted=lambda reader: reader.money,
        marker=marker,
    )


async def read_contract_pages(
    user: dict | None,
    ref: str,
    pages: str,
    source: Source | None = None,
    chat_id: str | None = None,
    marker: Marker | None = None,
    message_id: str | None = None,
) -> str:
    # Page text is contract full text, which is TERBATAS for every reader.
    return await _run(
        'pages',
        user,
        source,
        lambda s, r: _pages_text(s, r, ref, pages),
        chat_id=chat_id,
        message_id=message_id,
        restricted=lambda reader: True,
        marker=marker,
    )
