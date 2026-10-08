"""Rapat Direksi meetings on the server: the Corsec's Notulen, saved whole (D27 step 1).

A meeting is one document, the shape the Notulen screens already hold (nine record collections, the
live session, the plan, the notes). The server checks its structure with the same rules the client
applies when it reads one back (`parseMeeting` in `src/lib/notulen/repo.ts`) and refuses anything
else, so a malformed document never reaches another machine.

**Revisions.** Every stored meeting carries a revision, starting at 1. A save names the revision it
was based on and lands only if that is still the stored one; the update is conditional in SQL, so
two instances racing on the same meeting cannot both win. A stale save is refused with the current
revision and nothing is written: no last-writer-wins.

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
    session = document.get('session')
    if not isinstance(session, dict):
        raise MalformedMeeting('the meeting has no session')
    if not _is_int(session.get('currentAgenda')) or not isinstance(session.get('doneAgendas'), list):
        raise MalformedMeeting('the session needs a current agenda and its done agendas')
    try:
        text = json.dumps(document, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise MalformedMeeting('the meeting is not plain JSON') from error
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise MalformedMeeting('the meeting is too large')
    return text


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
                    closed_at=None,
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


def save_meeting(connection: Any, meeting_id: str, document: Any, *, base_revision: int, author: str) -> StoredMeeting:
    """Replace the meeting if `base_revision` is still the stored one; StaleRevision otherwise."""
    text = validate_document(document, meeting_id)
    result = connection.execute(
        update(meeting_table)
        .where(meeting_table.c.id == meeting_id, meeting_table.c.revision == base_revision)
        .values(document=text, revision=base_revision + 1, updated_by=author, updated_at=_now_ms())
    )
    if result.rowcount != 1:
        current = read_meeting(connection, meeting_id)
        if current is None:
            raise MeetingNotFound(meeting_id)
        raise StaleRevision(current.revision)
    stored = read_meeting(connection, meeting_id)
    assert stored is not None
    return stored


def _now_ms() -> int:
    return time.time_ns() // 1_000_000
