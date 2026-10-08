"""Tindakan into the review queue at Tutup rapat (D27 step 1, #160).

Closing a meeting turns the Tindakan of its Action Plan (record collection 8) into one candidate
file in the import format (`imports.parse_candidates`, `schema_version` 1) and ingests it, so the
reviewers accept, link or reject them in the existing review queue. Nothing here writes an action.

Mapping, per Tindakan:

- title <- Tindakan / deliverable (a Tindakan without one has nothing to review and is left out);
- owner label <- PIC utama; due <- Target waktu as a date; both null with a reason when blank;
- source document <- a stable meeting label: "Rapat Direksi, <date>, <meeting id>";
- slide <- the Tindakan's agenda and its position in the Action Plan;
- external id <- ID tindakan, else the record id. An ID tindakan used twice in one meeting would
  refuse the whole file, so both fall back to their record id and keep the ID in the metadata.
- the Notulen Status is the deck's reported state (kept, never compared); Bukti progres is the
  progress summary.

The file is serialised canonically (sorted keys, no whitespace), so closing an unchanged meeting
again produces the same bytes, and `ingest` answers with the first batch instead of a new one. A
Tindakan accepted meanwhile carries a reviewed reference, so on a re-close it arrives matched to its
action, never as a new one; a changed Tindakan comes through again with its differences shown.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from jup.leadership import imports
from jup.leadership.actions import AWAITING_BOD_CLOSURE, BLOCKED, IN_PROGRESS, NOT_STARTED

ACTION_PLAN = 8
TITLE = 'Tindakan / deliverable'
PIC = 'PIC utama'
DUE = 'Target waktu'
EXTERNAL_ID = 'ID tindakan'
AGENDA = 'Agenda'
STATUS = 'Status'
PROGRESS = 'Bukti progres / hambatan / eskalasi'
MEETING_DATE = 'Tanggal & waktu'
_STATES = {
    'Belum mulai': NOT_STARTED,
    'Berjalan': IN_PROGRESS,
    'Terhambat': BLOCKED,
    # The PIC reports it done; only the Direksi close an action.
    'Selesai': AWAITING_BOD_CLOSURE,
}
_DATE_PREFIX = re.compile(r'([0-9]{4}-[0-9]{2}-[0-9]{2})')


def source_label(document: dict[str, Any]) -> str:
    """The meeting as a source document: stable for as long as its date and id are."""
    return f'Rapat Direksi, {meeting_date(document) or "tanpa tanggal"}, {document["id"]}'


def meeting_date(document: dict[str, Any]) -> str | None:
    """The meeting's date from Informasi & Ringkasan Rapat, or None."""
    info = _records(document, 0)
    return _date(_values(info[0]).get(MEETING_DATE)) if info else None


def candidate_file(document: dict[str, Any]) -> bytes | None:
    """The meeting's Tindakan as canonical candidate-file bytes, or None when it has none."""
    from jup.leadership.repository import canonical_json

    records = enumerate(_records(document, ACTION_PLAN), 1)
    tindakan = [(position, record) for position, record in records if _text(_values(record).get(TITLE))]
    if not tindakan:
        return None
    ids = [_text(_values(record).get(EXTERNAL_ID)) for _, record in tindakan]
    candidates = [
        _candidate(position, record, unique=ids.count(ids[index]) == 1)
        for index, (position, record) in enumerate(tindakan)
    ]
    return canonical_json(
        {
            'schema_version': 1,
            'source_document': source_label(document),
            'meeting_date': meeting_date(document),
            'candidates': candidates,
        }
    ).encode('utf-8')


def import_at_close(connection: Any, document: dict[str, Any], *, closer: str) -> imports.Batch | None:
    """Ingest the closed meeting's Tindakan in the caller's transaction; None when it has none."""
    raw = candidate_file(document)
    if raw is None:
        return None
    return imports.ingest(connection, raw, filename=source_label(document), uploader=closer)


def _candidate(position: int, record: dict[str, Any], *, unique: bool) -> dict[str, Any]:
    values = _values(record)
    record_id = _text(record.get('id')) or f'tindakan-{position}'
    id_tindakan = _text(values.get(EXTERNAL_ID))
    agenda = _text(values.get(AGENDA)) or '8. Action Plan'
    owner = _text(values.get(PIC)) or None
    due = _date(values.get(DUE))
    state = _STATES.get(_text(values.get(STATUS)))
    progress = _text(values.get(PROGRESS)) or None
    missing = {
        name: reason
        for name, value, reason in (
            ('owner_label', owner, 'PIC utama belum diisi di Notulen'),
            ('due', due, 'Target waktu belum diisi di Notulen'),
            ('state', state, 'Status belum diisi di Notulen'),
            ('progress_summary', progress, 'Bukti progres belum diisi di Notulen'),
        )
        if value is None
    }
    metadata: dict[str, Any] = {'record_id': record_id, 'agenda': agenda, 'position': position}
    if id_tindakan:
        metadata['id_tindakan'] = id_tindakan
        if not unique:
            metadata['id_tindakan_duplicate'] = True
    return {
        'key': record_id,
        'slide': f'{agenda} · Tindakan {position}',
        'external_id': id_tindakan if id_tindakan and unique else record_id,
        'title': _text(values.get(TITLE)),
        'owner_label': owner,
        'due': None if due is None else {'precision': 'date', 'value': due},
        'state': state,
        'progress_summary': progress,
        'source_metadata': metadata,
        'missing': missing,
    }


def _records(document: dict[str, Any], index: int) -> list[dict[str, Any]]:
    collections = document.get('records')
    if not isinstance(collections, list) or len(collections) <= index or not isinstance(collections[index], list):
        return []
    return [record for record in collections[index] if isinstance(record, dict)]


def _values(record: dict[str, Any]) -> dict[str, Any]:
    values = record.get('values')
    return values if isinstance(values, dict) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ''


def _date(value: Any) -> str | None:
    """A date value's day (`start`, read as Asia/Jakarta like the client), or None."""
    start = value.get('start') if isinstance(value, dict) else None
    match = _DATE_PREFIX.match(start) if isinstance(start, str) else None
    if match is None:
        return None
    try:
        dt.date.fromisoformat(match.group(1))
    except ValueError:
        return None
    return match.group(1)
