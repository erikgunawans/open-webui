"""Rapat Direksi meetings on the server: the Corsec's Notulen, saved whole (D27 step 1).

A meeting is one document, the shape the Notulen screens already hold (nine record collections, the
live session, the plan, the notes). The server checks its structure with the same rules the client
applies when it reads one back (`parseMeeting` in `src/lib/notulen/repo.ts`) and refuses anything
else, so a malformed document never reaches another machine.

**Revisions.** Every stored meeting carries a revision, starting at 1. A save names the revision it
was based on and lands only if that is still the stored one; the update is conditional in SQL, so
two instances racing on the same meeting cannot both win. A stale save is refused with the current
revision and nothing is written: no last-writer-wins.

**Tutup rapat.** A meeting is closed on the server (`close_meeting`), and from then on every save is
refused, from any machine, until it is reopened (`reopen_meeting`) with a written reason. The
reopening (when, why, who) is kept beside the document; the document carries the reason too, so the
Risalah prints it. Closing again freezes it again. A plain save never opens or closes a meeting.

**Pindahkan ke server.** Meetings a browser kept before the server did are moved once
(`move_meeting`): created if absent, never written over. The answer says whether the stored meeting
is exactly the one sent, because only then may the browser drop its own copy.

Who may read and write is the router's check (`policy.py`); this module decides only what is stored.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from jup.leadership.models import meeting as meeting_table

# A meeting is a few hundred kilobytes at most; this bounds a runaway client, not a real one.
MAX_BYTES = 2 * 1024 * 1024
AGENDA_COLLECTIONS = 9
# The ids the client makes (`rd-2026-10-08-ab12`) and anything a URL can carry safely.
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')


class MalformedMeeting(ValueError):
    """The document is not a meeting; the message says what is wrong, never what it contains."""


class MeetingNotFound(LookupError):
    pass


class MeetingExists(Exception):
    def __init__(self, revision: int) -> None:
        super().__init__('a meeting with this id is already stored')
        self.revision = revision


class MeetingClosed(Exception):
    """The meeting is closed: nothing changes it until it is reopened with a reason."""

    def __init__(self, revision: int) -> None:
        super().__init__('the meeting is closed')
        self.revision = revision


class MeetingOpen(Exception):
    """Reopening a meeting that is not closed."""

    def __init__(self, revision: int) -> None:
        super().__init__('the meeting is not closed')
        self.revision = revision


class MissingReason(ValueError):
    """A reopening without a written reason."""


class StaleRevision(Exception):
    """The save was based on a revision that is no longer the stored one."""

    def __init__(self, actual: int) -> None:
        super().__init__(f'the stored revision is {actual}')
        self.actual = actual


@dataclass(frozen=True)
class StoredMeeting:
    id: str
    owner_user_id: str
    document: dict[str, Any]
    revision: int
    closed_at: int | None
    reopenings: list[Any]
    created_by: str
    created_at: int
    updated_by: str
    updated_at: int

    def view(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'revision': self.revision,
            'document': self.document,
            'owner_user_id': self.owner_user_id,
            'closed_at': self.closed_at,
            'reopenings': self.reopenings,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at,
        }


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_document(document: Any, meeting_id: str | None = None) -> str:
    """The document as stored text, or MalformedMeeting.

    The rules are the client's `isMeeting`: an id, nine record collections that are each a list, and
    a session with a numeric current agenda and a list of done agendas. The id must also be one a URL
    carries, and match the meeting it is saved under.
    """
    if not isinstance(document, dict):
        raise MalformedMeeting('a meeting is a JSON object')
    doc_id = document.get('id')
    if not isinstance(doc_id, str) or not _ID.fullmatch(doc_id):
        raise MalformedMeeting('the meeting id is missing or not a valid id')
    if meeting_id is not None and doc_id != meeting_id:
        raise MalformedMeeting('the document belongs to a different meeting')
    records = document.get('records')
    if not isinstance(records, list) or len(records) != AGENDA_COLLECTIONS:
        raise MalformedMeeting(f'a meeting holds exactly {AGENDA_COLLECTIONS} record collections')
    if not all(isinstance(collection, list) for collection in records):
        raise MalformedMeeting('every record collection is a list')
    _validate_session(document.get('session'))
    try:
        text = json.dumps(document, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise MalformedMeeting('the meeting is not plain JSON') from error
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise MalformedMeeting('the meeting is too large')
    return text


def _validate_session(session: Any) -> None:
    """A current agenda and its done agendas; a closing time and reopenings only in their shape."""
    if not isinstance(session, dict):
        raise MalformedMeeting('the meeting has no session')
    if not _is_int(session.get('currentAgenda')) or not isinstance(session.get('doneAgendas'), list):
        raise MalformedMeeting('the session needs a current agenda and its done agendas')
    if session.get('closedAt') is not None and not _is_int(session.get('closedAt')):
        raise MalformedMeeting('the closing time is not a time')
    if session.get('reopenings') is not None and not isinstance(session.get('reopenings'), list):
        raise MalformedMeeting('the reopenings are a list')


def _closed(document: dict[str, Any]) -> bool:
    """The document says the meeting is closed (the client's `session.closedAt`)."""
    return document['session'].get('closedAt') is not None


def _stored(row: Any) -> StoredMeeting:
    return StoredMeeting(
        id=row.id,
        owner_user_id=row.owner_user_id,
        document=json.loads(row.document),
        revision=row.revision,
        closed_at=row.closed_at,
        reopenings=json.loads(row.reopenings),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def list_meetings(connection: Any) -> list[StoredMeeting]:
    """Every stored meeting, oldest first."""
    rows = connection.execute(select(meeting_table).order_by(meeting_table.c.created_at, meeting_table.c.id))
    return [_stored(row) for row in rows]


def read_meeting(connection: Any, meeting_id: str) -> StoredMeeting | None:
    row = connection.execute(select(meeting_table).where(meeting_table.c.id == meeting_id)).first()
    return None if row is None else _stored(row)


def create_meeting(connection: Any, document: Any, *, author: str) -> StoredMeeting:
    """Store a new meeting at revision 1, owned by its author. An id already stored is MeetingExists."""
    text = validate_document(document)
    meeting_id = document['id']
    existing = read_meeting(connection, meeting_id)
    if existing is not None:
        raise MeetingExists(existing.revision)
    now = _now_ms()
    try:
        with connection.begin_nested():
            connection.execute(
                insert(meeting_table).values(
                    id=meeting_id,
                    owner_user_id=author,
                    document=text,
                    revision=1,
                    # A meeting that arrives closed (one moved from a browser) is closed here too.
                    closed_at=now if _closed(document) else None,
                    reopenings='[]',
                    created_by=author,
                    created_at=now,
                    updated_by=author,
                    updated_at=now,
                )
            )
    except IntegrityError as error:
        # Another instance created it between the read and the insert.
        raced = read_meeting(connection, meeting_id)
        raise MeetingExists(raced.revision if raced else 1) from error
    stored = read_meeting(connection, meeting_id)
    assert stored is not None
    return stored


@dataclass(frozen=True)
class MoveResult:
    """What became of one meeting a browser moved: `moved`, `on_server` or `refused`."""

    id: str | None
    result: str
    revision: int | None = None
    # The server now holds exactly the document sent: the browser's copy is safe to remove.
    confirmed: bool = False
    # Why it was refused; says what is wrong, never what the meeting contains.
    reason: str | None = None

    def view(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'result': self.result,
            'revision': self.revision,
            'confirmed': self.confirmed,
            'reason': self.reason,
        }


def move_meeting(connection: Any, document: Any, *, author: str) -> MoveResult:
    """Create the meeting if no meeting has its id; an existing one is never touched.

    A meeting already on the server is `on_server`, confirmed only when the stored document is the
    one sent (an earlier move whose browser copy was not removed). A malformed one is `refused`.
    """
    doc_id = document.get('id') if isinstance(document, dict) else None
    doc_id = doc_id if isinstance(doc_id, str) and _ID.fullmatch(doc_id) else None
    try:
        stored = create_meeting(connection, document, author=author)
    except MalformedMeeting as error:
        return MoveResult(id=doc_id, result='refused', reason=str(error))
    except MeetingExists as error:
        existing = read_meeting(connection, document['id'])
        return MoveResult(
            id=doc_id,
            result='on_server',
            revision=existing.revision if existing else error.revision,
            confirmed=existing is not None and existing.document == document,
        )
    return MoveResult(id=stored.id, result='moved', revision=stored.revision, confirmed=True)


def save_meeting(connection: Any, meeting_id: str, document: Any, *, base_revision: int, author: str) -> StoredMeeting:
    """Replace the meeting if `base_revision` is still the stored one and it is open.

    StaleRevision when the revision moved, MeetingClosed when the meeting is closed. A save that
    would close the meeting is malformed: closing is `close_meeting`, so it is always audited.
    """
    text = validate_document(document, meeting_id)
    if _closed(document):
        raise MalformedMeeting('a meeting is closed with Tutup rapat, not by saving it')
    result = connection.execute(
        update(meeting_table)
        .where(
            meeting_table.c.id == meeting_id,
            meeting_table.c.revision == base_revision,
            meeting_table.c.closed_at.is_(None),
        )
        .values(document=text, revision=base_revision + 1, updated_by=author, updated_at=_now_ms())
    )
    return _written(connection, meeting_id, result)


def close_meeting(connection: Any, meeting_id: str, document: Any, *, base_revision: int, author: str) -> StoredMeeting:
    """Tutup rapat: store the closing document and freeze the meeting.

    The document is the meeting as the Corsec closed it (its `session.closedAt` set, the closing time
    stamped). Refused like a save when the revision moved or the meeting is already closed.
    """
    text = validate_document(document, meeting_id)
    if not _closed(document):
        raise MalformedMeeting('the closing document carries no closing time')
    now = _now_ms()
    result = connection.execute(
        update(meeting_table)
        .where(
            meeting_table.c.id == meeting_id,
            meeting_table.c.revision == base_revision,
            meeting_table.c.closed_at.is_(None),
        )
        .values(document=text, revision=base_revision + 1, closed_at=now, updated_by=author, updated_at=now)
    )
    return _written(connection, meeting_id, result)


def reopen_meeting(
    connection: Any, meeting_id: str, document: Any, *, base_revision: int, reason: str, author: str
) -> StoredMeeting:
    """Buka kembali: open a closed meeting again, keeping when, why and who.

    The reason must be written, and the document must carry it as its last reopening (that is what
    the Risalah prints). MeetingOpen when the meeting is not closed.
    """
    reason = reason.strip()
    if not reason:
        raise MissingReason('a meeting is reopened only with a written reason')
    text = validate_document(document, meeting_id)
    if _closed(document):
        raise MalformedMeeting('the reopened document is still closed')
    written = document['session'].get('reopenings') or []
    last = written[-1] if written else None
    if not isinstance(last, dict) or not isinstance(last.get('reason'), str) or last['reason'].strip() != reason:
        raise MalformedMeeting('the reopened document does not carry this reason')
    current = read_meeting(connection, meeting_id)
    if current is None:
        raise MeetingNotFound(meeting_id)
    now = _now_ms()
    kept = [*current.reopenings, {'at': now, 'reason': reason, 'by': author}]
    # The revision guard makes the read above safe: if anything wrote in between, nothing is written.
    result = connection.execute(
        update(meeting_table)
        .where(
            meeting_table.c.id == meeting_id,
            meeting_table.c.revision == base_revision,
            meeting_table.c.closed_at.is_not(None),
        )
        .values(
            document=text,
            revision=base_revision + 1,
            closed_at=None,
            reopenings=json.dumps(kept, ensure_ascii=False),
            updated_by=author,
            updated_at=now,
        )
    )
    return _written(connection, meeting_id, result, reopening=True)


def _written(connection: Any, meeting_id: str, result: Any, *, reopening: bool = False) -> StoredMeeting:
    """The stored meeting after a conditional update, or why the update matched nothing."""
    if result.rowcount != 1:
        current = read_meeting(connection, meeting_id)
        if current is None:
            raise MeetingNotFound(meeting_id)
        if reopening and current.closed_at is None:
            raise MeetingOpen(current.revision)
        if not reopening and current.closed_at is not None:
            raise MeetingClosed(current.revision)
        raise StaleRevision(current.revision)
    stored = read_meeting(connection, meeting_id)
    assert stored is not None
    return stored


def _now_ms() -> int:
    return time.time_ns() // 1_000_000
