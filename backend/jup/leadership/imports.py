"""Reviewed imports: a meeting deck's actions arrive as candidates, never as records (P2 T6).

P2 does not parse PPTX. Extraction stays outside the app, and what arrives is a structured candidate
file (`schema_version` 1):

    {"schema_version": 1, "source_document": "BOD-2026-09.pptx", "meeting_date": "2026-09-28",
     "candidates": [{"key", "slide", "external_id", "title", "owner_label", "due", "state",
                     "progress_summary", "source_metadata", "missing"}]}

- `owner_label`, `due`, `state` and `progress_summary` may be null, but only with a reason under
  `missing`. A missing value stays null with that reason; nothing fills it in.
- `source_metadata` is kept verbatim: a hidden slide, a draft note or an old slide number survives.
- A malformed file is refused whole. There are no floats anywhere (figures are decimal strings).

**Matching** is only ever through a reviewed `leadership_external_ref`: an owner-confirmed id,
first recorded against a deck and slide. A candidate whose id has such a reference is matched to
that action; otherwise it is a new-action candidate. A matched candidate whose title, owner or due
date differs from the record is a conflict: both values are stored and shown, and nothing is
resolved automatically. The deck's reported state is kept in the payload but never compared, since
the lifecycle moves only through the action's own commands.

**Review** needs `imports.review` (the router's check) and happens once per candidate:

- `accept` on a new candidate creates the action (not started, no PIC user until the identity
  mapping is decided) and records the reference. If the id gained a reference meanwhile, it is
  refused: link instead, so recurrence never duplicates.
- `link` ties a new candidate to an existing action by recording the reference; the action is
  unchanged.
- `accept` on a matched candidate confirms the reference for this deck; on a conflict it is
  recorded as `acknowledged` and the recorded values stay. A change goes through the action's
  commands (a reasoned due revision, for example).
- `reject` records the decision and writes nothing else.

Nothing is labelled `verified` until it is accepted or linked. Ingesting the same file bytes again
is a no-op. An action absent from a later deck is simply not mentioned; nothing closes it.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from jup.leadership.actions import STATES, CommandRefused, Due

MAX_BYTES = 5 * 1024 * 1024
DECISIONS = ('accept', 'link', 'reject')
_NULLABLE = ('owner_label', 'due', 'state', 'progress_summary')
_FIELDS = {'key', 'slide', 'external_id', 'title', 'source_metadata', 'missing', *_NULLABLE}
_ISO_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


class InvalidCandidates(ValueError):
    """The candidate file cannot be ingested; the message names the offending path."""


class ImportRefused(CommandRefused):
    """The review is not allowed as things stand; nothing was written."""


class AlreadyReviewed(Exception):
    """The candidate was reviewed already; nothing was written."""


class BatchNotFound(LookupError):
    """No import batch or candidate has this id."""


@dataclass(frozen=True)
class ParsedFile:
    source_document: str
    meeting_date: str | None
    candidates: list[dict[str, Any]]


@dataclass(frozen=True)
class Batch:
    id: str
    created: bool


# --- the file -------------------------------------------------------------------------------


def parse_candidates(raw: bytes) -> ParsedFile:
    """The file, fully checked, or `InvalidCandidates`."""
    try:
        data = json.loads(raw.decode('utf-8'), parse_float=_no_float)
    except (UnicodeDecodeError, ValueError) as error:
        raise InvalidCandidates(f'the file is not UTF-8 JSON without floats: {error}') from error
    if not isinstance(data, dict) or set(data) != {'schema_version', 'source_document', 'meeting_date', 'candidates'}:
        raise InvalidCandidates('$: expected exactly schema_version, source_document, meeting_date, candidates')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise InvalidCandidates('$.schema_version: must be integer 1')
    document = _text(data['source_document'], '$.source_document')
    meeting_date = data['meeting_date']
    if meeting_date is not None and (not isinstance(meeting_date, str) or not _ISO_DATE.fullmatch(meeting_date)):
        raise InvalidCandidates('$.meeting_date: must be a YYYY-MM-DD date or null')
    if not isinstance(data['candidates'], list):
        raise InvalidCandidates('$.candidates: must be a list')

    keys: set[str] = set()
    external_ids: set[str] = set()
    for index, candidate in enumerate(data['candidates']):
        path = f'$.candidates[{index}]'
        _check_candidate(candidate, path)
        if candidate['key'] in keys:
            raise InvalidCandidates(f'{path}.key: {candidate["key"]!r} appears twice')
        if candidate['external_id'] in external_ids:
            raise InvalidCandidates(f'{path}.external_id: {candidate["external_id"]!r} appears twice in one deck')
        keys.add(candidate['key'])
        external_ids.add(candidate['external_id'])
    return ParsedFile(document, meeting_date, data['candidates'])


def _check_candidate(candidate: Any, path: str) -> None:
    if not isinstance(candidate, dict) or set(candidate) != _FIELDS:
        raise InvalidCandidates(f'{path}: expected exactly {", ".join(sorted(_FIELDS))}')
    for name in ('key', 'slide', 'external_id', 'title'):
        _text(candidate[name], f'{path}.{name}')
    if not isinstance(candidate['source_metadata'], dict):
        raise InvalidCandidates(f'{path}.source_metadata: must be an object')
    _check_missing(candidate, path)
    _check_values(candidate, path)


def _check_missing(candidate: dict[str, Any], path: str) -> None:
    """Each nullable value is present, or null with a reason; nothing else may be missing."""
    missing = candidate['missing']
    if not isinstance(missing, dict):
        raise InvalidCandidates(f'{path}.missing: must be an object')
    for name in _NULLABLE:
        if candidate[name] is None:
            if not isinstance(missing.get(name), str) or not missing[name].strip():
                raise InvalidCandidates(f'{path}.{name}: null needs a reason under missing.{name}')
        elif name in missing:
            raise InvalidCandidates(f'{path}.missing.{name}: the value is present')
    extra = set(missing) - set(_NULLABLE)
    if extra:
        raise InvalidCandidates(f'{path}.missing: {", ".join(sorted(extra))} cannot be missing')


def _check_values(candidate: dict[str, Any], path: str) -> None:
    """The values that are present: text, the lifecycle vocabulary, a due date at its precision."""
    for name in ('owner_label', 'progress_summary'):
        if candidate[name] is not None:
            _text(candidate[name], f'{path}.{name}')
    if candidate['state'] is not None and candidate['state'] not in STATES:
        raise InvalidCandidates(f'{path}.state: must be one of {", ".join(STATES)}')
    due = candidate['due']
    if due is not None:
        if not isinstance(due, dict) or set(due) != {'precision', 'value'}:
            raise InvalidCandidates(f'{path}.due: expected precision and value')
        try:
            Due(due['precision'], due['value'])
        except ValueError as error:
            raise InvalidCandidates(f'{path}.due: {error}') from error


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidCandidates(f'{path}: must be non-empty text')
    return value


def _no_float(text: str) -> Any:
    raise ValueError(f'{text} is a float; figures travel as decimal strings')


# --- ingestion ------------------------------------------------------------------------------


def ingest(connection: Any, raw: bytes, *, filename: str, uploader: str) -> Batch:
    """Store a file's candidates for review. The same bytes again return the first batch."""
    from sqlalchemy import select

    from jup.leadership.models import import_batch, import_candidate
    from jup.leadership.repository import canonical_json

    digest = hashlib.sha256(raw).hexdigest()
    existing = connection.execute(select(import_batch.c.id).where(import_batch.c.source_sha256 == digest)).scalar()
    if existing is not None:
        return Batch(existing, created=False)

    parsed = parse_candidates(raw)
    batch_id = uuid.uuid4().hex
    now = _now_ms()
    connection.execute(
        import_batch.insert().values(
            id=batch_id,
            source_filename=filename or parsed.source_document,
            source_sha256=digest,
            meeting_date=parsed.meeting_date,
            status='open',
            uploaded_by=uploader,
            created_at=now,
        )
    )
    for candidate in parsed.candidates:
        payload = candidate | {'source_document': parsed.source_document}
        matched, kind, conflict = _match(connection, candidate)
        connection.execute(
            import_candidate.insert().values(
                id=uuid.uuid4().hex,
                batch_id=batch_id,
                candidate_key=candidate['key'],
                payload=canonical_json(payload),
                matched_action_id=matched,
                match_kind=kind,
                conflict=canonical_json(conflict) if conflict else None,
                review_state='pending',
                reviewed_by=None,
                reviewed_at=None,
            )
        )
    return Batch(batch_id, created=True)


def _referenced_actions(connection: Any, external_id: str) -> set[str]:
    from sqlalchemy import select

    from jup.leadership.models import external_ref

    return set(
        connection.execute(select(external_ref.c.action_id).where(external_ref.c.external_id == external_id)).scalars()
    )


def _match(connection: Any, candidate: dict[str, Any]) -> tuple[str | None, str, dict[str, Any] | None]:
    """(matched action, match kind, conflict) through reviewed references only."""
    from sqlalchemy import select

    from jup.leadership.models import action

    actions = _referenced_actions(connection, candidate['external_id'])
    if not actions:
        return None, 'new', None
    if len(actions) > 1:
        return None, 'conflict', {'external_id': {'recorded': sorted(actions), 'candidate': candidate['external_id']}}
    (action_id,) = actions
    row = connection.execute(select(action).where(action.c.id == action_id)).mappings().one()
    recorded = {
        'title': row['title'],
        'owner_label': row['pic_label'],
        'due': None
        if row['current_due'] is None
        else {'precision': row['current_due_precision'], 'value': row['current_due']},
    }
    conflict = {
        name: {'recorded': recorded[name], 'candidate': candidate[name]}
        for name in ('title', 'owner_label', 'due')
        # A value the deck does not give is missing, not different.
        if candidate[name] is not None and candidate[name] != recorded[name]
    }
    return action_id, ('conflict' if conflict else 'external_ref'), conflict or None


# --- review ---------------------------------------------------------------------------------


def review_candidate(
    engine: Any, *, candidate_id: str, decision: str, reviewer: str, action_id: str | None = None
) -> dict[str, Any]:
    """Review one candidate; the action, the reference and the candidate's state commit together."""
    from sqlalchemy import select, update

    from jup.leadership.models import import_batch, import_candidate
    from jup.leadership.repository import unit_of_work

    if decision not in DECISIONS:
        raise ImportRefused(f'a review decision is one of {", ".join(DECISIONS)}, not {decision!r}')
    with unit_of_work(engine) as uow:
        connection = uow.connection
        row = (
            connection.execute(select(import_candidate).where(import_candidate.c.id == candidate_id)).mappings().first()
        )
        if row is None:
            raise BatchNotFound(f'no candidate {candidate_id!r}')
        payload = json.loads(row['payload'])
        now = _now_ms()

        if decision == 'reject':
            state, result_action = 'rejected', None
        elif decision == 'link':
            state, result_action = 'linked', _link(connection, row, payload, action_id, reviewer, now)
        else:
            state, result_action = _accept(uow, row, payload, reviewer, now)

        # Conditional on still pending, so two reviewers cannot both decide.
        moved = connection.execute(
            update(import_candidate)
            .where(import_candidate.c.id == candidate_id, import_candidate.c.review_state == 'pending')
            .values(review_state=state, reviewed_by=reviewer, reviewed_at=now)
        )
        if moved.rowcount != 1:
            raise AlreadyReviewed(f'candidate {candidate_id!r} was already reviewed')
        pending = connection.execute(
            select(import_candidate.c.id).where(
                import_candidate.c.batch_id == row['batch_id'], import_candidate.c.review_state == 'pending'
            )
        ).first()
        if pending is None:
            connection.execute(
                update(import_batch).where(import_batch.c.id == row['batch_id']).values(status='reviewed')
            )
    return {'candidate_id': candidate_id, 'review_state': state, 'action_id': result_action}


def _require_pending(row: Any) -> None:
    if row['review_state'] != 'pending':
        raise AlreadyReviewed(f'candidate {row["id"]!r} was already reviewed')


def _accept(uow: Any, row: Any, payload: dict[str, Any], reviewer: str, now: int) -> tuple[str, str]:
    from jup.leadership import actions

    _require_pending(row)
    connection = uow.connection
    if row['match_kind'] == 'new':
        if _referenced_actions(connection, payload['external_id']):
            raise ImportRefused(
                f'{payload["external_id"]!r} has been recorded against an action since this deck was imported; link it'
            )
        if payload['owner_label'] is None:
            raise ImportRefused('a new action needs its owner label; this candidate has none (link or reject it)')
        action_id = f'act-{uuid.uuid4().hex}'
        due = payload['due']
        actions.create_action(
            uow,
            action_id=action_id,
            title=payload['title'],
            pic_label=payload['owner_label'],
            author=reviewer,
            due=Due(due['precision'], due['value']) if due else None,
            reason=f'imported from {payload["source_document"]}, slide {payload["slide"]}',
        )
        _reference(connection, action_id, payload, reviewer, now)
        return 'accepted', action_id
    if row['matched_action_id'] is None:
        raise ImportRefused('this candidate matches several actions; link it to the right one or reject it')
    _reference(connection, row['matched_action_id'], payload, reviewer, now)
    return ('acknowledged' if row['match_kind'] == 'conflict' else 'accepted'), row['matched_action_id']


def _link(connection: Any, row: Any, payload: dict[str, Any], action_id: str | None, reviewer: str, now: int) -> str:
    from sqlalchemy import select

    from jup.leadership.models import action

    _require_pending(row)
    if row['match_kind'] == 'external_ref':
        raise ImportRefused('this candidate is already matched; accept or reject it')
    if not action_id or connection.execute(select(action.c.id).where(action.c.id == action_id)).scalar() is None:
        raise ImportRefused('link names an existing action')
    if _referenced_actions(connection, payload['external_id']) - {action_id}:
        raise ImportRefused(f'{payload["external_id"]!r} already refers to another action')
    _reference(connection, action_id, payload, reviewer, now)
    return action_id


def _reference(connection: Any, action_id: str, payload: dict[str, Any], reviewer: str, now: int) -> None:
    from sqlalchemy import select

    from jup.leadership.models import external_ref

    exists = connection.execute(
        select(external_ref.c.id).where(
            external_ref.c.source_document == payload['source_document'],
            external_ref.c.slide == payload['slide'],
            external_ref.c.external_id == payload['external_id'],
        )
    ).scalar()
    if exists is None:
        connection.execute(
            external_ref.insert().values(
                id=uuid.uuid4().hex,
                action_id=action_id,
                source_document=payload['source_document'],
                slide=payload['slide'],
                external_id=payload['external_id'],
                confirmed_by=reviewer,
                confirmed_at=now,
            )
        )


# --- reading --------------------------------------------------------------------------------


def list_batches(connection: Any) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from jup.leadership.models import import_batch

    rows = connection.execute(select(import_batch).order_by(import_batch.c.created_at.desc())).mappings()
    return [dict(row) for row in rows]


def read_batch(connection: Any, batch_id: str) -> dict[str, Any]:
    """One batch and its candidates, each labelled verified only once accepted or linked."""
    from sqlalchemy import select

    from jup.leadership.models import import_batch, import_candidate

    batch = connection.execute(select(import_batch).where(import_batch.c.id == batch_id)).mappings().first()
    if batch is None:
        raise BatchNotFound(f'no import batch {batch_id!r}')
    rows = connection.execute(
        select(import_candidate)
        .where(import_candidate.c.batch_id == batch_id)
        .order_by(import_candidate.c.candidate_key)
    ).mappings()
    candidates = [
        {
            'id': row['id'],
            'candidate_key': row['candidate_key'],
            'match_kind': row['match_kind'],
            'matched_action_id': row['matched_action_id'],
            'conflict': json.loads(row['conflict']) if row['conflict'] else None,
            'review_state': row['review_state'],
            'reviewed_by': row['reviewed_by'],
            'reviewed_at': row['reviewed_at'],
            # A claim inside the file is never the label; only a review makes a record verified.
            'verification': 'verified' if row['review_state'] in ('accepted', 'linked') else 'unverified',
            'payload': json.loads(row['payload']),
        }
        for row in rows
    ]
    return dict(batch) | {'candidates': candidates}


def _now_ms() -> int:
    import time

    return time.time_ns() // 1_000_000
