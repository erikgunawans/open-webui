"""Meeting snapshots and RKA baselines: what the board saw, and what it approved (P2 T5, SNAP-01).

**A snapshot** freezes one view (Board or RKA) for one meeting: its context, metrics, assumptions,
module states, the actions at their current event versions, and the sources it cites, as canonical
JSON with a SHA-256 over those exact bytes. It is then a sequence of versions, each immutable:

- `draft`: the first version, or a later draft that replaces an earlier draft.
- `publication`: repeats the draft it publishes, byte for byte and hash for hash. It needs a
  configured publication policy (`JUP_LEADERSHIP_PUBLICATION_POLICY`); unset means everything stays
  draft. The router also requires the `snapshots.publish` capability.
- `correction`: a new draft linked to the published version it would replace. The meeting record
  stays the earlier publication until the correction is itself published, and the replaced version
  is kept.

Nothing here serves a draft as an approved record. Reading verifies every version: its hash
against its bytes, and a published version against the draft it claims to publish. A row that
fails (a state flipped outside this module, content edited in the database) is an
`IntegrityFailure`, never a quietly served record.

**An RKA record** is one immutable row with an effective period: an approved `baseline`, an
approved `revision` that supersedes a baseline or an earlier revision, or a `forecast`, which is
never approved and never supersedes approved RKA. A new figure is always a new record.

The publication policy is `{"four_eyes": true | false}`. With four eyes, the author of a draft
cannot publish it.

Only the policy parser is importable without the database runtime; the rest imports it where used,
as `actions.py` does, so CI's `--only-group dev` job still runs the pure tests.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any

from jup.leadership.actions import CommandRefused

PUBLICATION_POLICY_ENV = 'JUP_LEADERSHIP_PUBLICATION_POLICY'
VIEWS = ('board', 'rka')
RKA_KINDS = ('baseline', 'revision', 'forecast')

_ISO_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


@dataclass(frozen=True)
class PublicationPolicy:
    four_eyes: bool


class PublicationNotConfigured(Exception):
    """No publication policy is configured: every snapshot stays a draft."""


class SnapshotNotFound(LookupError):
    """No snapshot has this id."""


class SnapshotRefused(CommandRefused):
    """The snapshot or RKA command is not allowed as things stand; nothing was written."""


class SnapshotConflict(Exception):
    """The snapshot moved on, or its content is not the content the caller reviewed; nothing was written."""

    def __init__(self, message: str, latest_version: int | None = None) -> None:
        super().__init__(message)
        self.latest_version = latest_version


class IntegrityFailure(Exception):
    """A stored version does not verify; it is refused rather than served."""


@dataclass(frozen=True)
class SnapshotVersion:
    id: str
    snapshot_id: str
    view: str
    meeting_label: str
    meeting_date: str | None
    version: int
    state: str  # 'draft' or 'published'
    change_kind: str  # 'draft', 'publication' or 'correction'
    previous_version_id: str | None
    content_bytes: bytes
    content_hash: str
    created_by: str
    created_at: int

    def summary(self) -> dict[str, Any]:
        """Everything but the content."""
        return {
            'id': self.id,
            'snapshot_id': self.snapshot_id,
            'view': self.view,
            'meeting_label': self.meeting_label,
            'meeting_date': self.meeting_date,
            'version': self.version,
            'state': self.state,
            'change_kind': self.change_kind,
            'previous_version_id': self.previous_version_id,
            'content_hash': self.content_hash,
            'created_by': self.created_by,
            'created_at': self.created_at,
        }


@dataclass(frozen=True)
class RkaRecord:
    id: str
    kind: str
    content_hash: str


# --- the publication policy -----------------------------------------------------------------


def parse_publication_policy(raw: str | None) -> PublicationPolicy | None:
    """The policy, or None when it is unset or anything about it is off."""
    if not raw or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {'four_eyes'} or type(value['four_eyes']) is not bool:
        return None
    return PublicationPolicy(four_eyes=value['four_eyes'])


def configured_publication_policy() -> PublicationPolicy | None:
    """Read per request, so a restarted container or a test needs no reimport."""
    return parse_publication_policy(os.environ.get(PUBLICATION_POLICY_ENV, ''))


# --- freezing a view ------------------------------------------------------------------------


def view_content(connection: Any, dataset: dict[str, Any], view: str, actions_source: str = 'sample') -> dict[str, Any]:
    """One view as it stands: the reader's overview, each action's recorded state, and its sources.

    With the `records` actions source, the actions are the recorded register, each already carrying
    its record. With `sample`, an action with a record in the store is frozen at its current event
    version, and one that exists only in the dataset says so (`record: None`) instead of borrowing a
    state it does not have.
    """
    from sqlalchemy import select

    from jup.leadership.models import action
    from jup.leadership.reader import read_overview, recorded_actions

    if actions_source == 'records':
        overview = read_overview(dataset, view, recorded_actions(connection))
        return {'view': view, **overview, 'sources': _cited_sources(dataset, overview)}
    overview = read_overview(dataset, view)
    ids = [item['id'] for item in overview['actions']]
    rows = {row['id']: row for row in connection.execute(select(action).where(action.c.id.in_(ids))).mappings()}
    for item in overview['actions']:
        row = rows.get(item['id'])
        item['record'] = (
            None
            if row is None
            else {
                key: row[key]
                for key in ('version', 'state', 'pic_label', 'current_due', 'current_due_precision', 'updated_at')
            }
        )
    return {'view': view, **overview, 'sources': _cited_sources(dataset, overview)}


def _cited_sources(dataset: dict[str, Any], overview: dict[str, Any]) -> list[dict[str, Any]]:
    cited = set(overview['context']['source_ids'])
    for item in overview['actions']:
        cited.update(item.get('source_ids', ()))
    return [source for source in dataset['sources'] if source['id'] in cited]


# --- snapshot commands ----------------------------------------------------------------------


def create_draft(
    connection: Any,
    *,
    view: str,
    meeting_label: str,
    meeting_date: str | None,
    content: dict[str, Any],
    author: str,
) -> SnapshotVersion:
    """A new snapshot for one meeting, at version 1, as a draft."""
    from jup.leadership.models import snapshot

    if view not in VIEWS:
        raise ValueError(f'a snapshot is of one view, {" or ".join(VIEWS)}, not {view!r}')
    if not isinstance(meeting_label, str) or not meeting_label.strip():
        raise ValueError('meeting_label is required')
    if meeting_date is not None:
        _date(meeting_date, 'meeting_date')
    body = _freeze(content)
    snapshot_id = uuid.uuid4().hex
    now = _now_ms()
    connection.execute(
        snapshot.insert().values(
            id=snapshot_id,
            view_key=view,
            meeting_label=meeting_label,
            meeting_date=meeting_date,
            created_by=author,
            created_at=now,
        )
    )
    return _insert_version(connection, snapshot_id, 1, 'draft', 'draft', None, body, author, now)


def publish(
    connection: Any,
    *,
    snapshot_id: str,
    expected_version: int,
    content_hash: str,
    publisher: str,
    policy: PublicationPolicy | None,
) -> SnapshotVersion:
    """Publish the latest version, which must be a draft whose hash is the one the publisher reviewed."""
    if policy is None:
        raise PublicationNotConfigured('publication is not configured; every snapshot stays a draft')
    latest = _latest(connection, snapshot_id, expected_version)
    if latest.content_hash != content_hash:
        raise SnapshotConflict('the draft is not the content you reviewed', latest.version)
    if latest.state != 'draft':
        raise SnapshotRefused('only a draft is published; this version already is')
    if policy.four_eyes and latest.created_by == publisher:
        raise SnapshotRefused('four-eyes publication: the author of a draft cannot publish it')
    return _insert_version(
        connection,
        snapshot_id,
        latest.version + 1,
        'published',
        'publication',
        latest.id,
        latest.content_bytes.decode('utf-8'),
        publisher,
        _now_ms(),
    )


def revise(
    connection: Any, *, snapshot_id: str, expected_version: int, content: dict[str, Any], author: str
) -> SnapshotVersion:
    """A new draft: replacing an earlier draft, or correcting a published version (then linked to it)."""
    latest = _latest(connection, snapshot_id, expected_version)
    kind = 'correction' if latest.state == 'published' else 'draft'
    return _insert_version(
        connection, snapshot_id, latest.version + 1, 'draft', kind, latest.id, _freeze(content), author, _now_ms()
    )


# --- reading --------------------------------------------------------------------------------


def read_versions(connection: Any, snapshot_id: str) -> list[SnapshotVersion]:
    """Every version of one snapshot, in order, each verified. Raises `IntegrityFailure` on any that fails."""
    from sqlalchemy import select

    from jup.leadership.models import snapshot, snapshot_version

    head = connection.execute(select(snapshot).where(snapshot.c.id == snapshot_id)).mappings().first()
    if head is None:
        raise SnapshotNotFound(f'no snapshot {snapshot_id!r}')
    rows = connection.execute(
        select(snapshot_version)
        .where(snapshot_version.c.snapshot_id == snapshot_id)
        .order_by(snapshot_version.c.version)
    ).mappings()
    versions = [_version(head, row) for row in rows]
    _verify(versions)
    return versions


def latest_published(connection: Any, snapshot_id: str) -> SnapshotVersion | None:
    """The meeting record: the latest published version, or None while everything is draft."""
    published = [version for version in read_versions(connection, snapshot_id) if version.state == 'published']
    return published[-1] if published else None


def list_snapshots(connection: Any, view: str) -> list[dict[str, Any]]:
    """Each snapshot of one view, newest meeting first, with its latest version's summary."""
    from sqlalchemy import select

    from jup.leadership.models import snapshot

    heads = connection.execute(
        select(snapshot.c.id).where(snapshot.c.view_key == view).order_by(snapshot.c.created_at.desc())
    ).scalars()
    listed = []
    for snapshot_id in heads:
        versions = read_versions(connection, snapshot_id)
        published = [v for v in versions if v.state == 'published']
        listed.append(
            {
                'latest': versions[-1].summary(),
                'published': published[-1].summary() if published else None,
            }
        )
    return listed


# --- RKA records ----------------------------------------------------------------------------


def record_rka(
    connection: Any,
    *,
    kind: str,
    label: str,
    period_start: str,
    period_end: str,
    content: dict[str, Any],
    author: str,
    approved_by: str | None = None,
    approved_at: int | None = None,
    supersedes_id: str | None = None,
) -> RkaRecord:
    """One new RKA record. Nothing here updates an existing one."""
    from jup.leadership.models import rka_baseline

    _check_rka(connection, kind, label, period_start, period_end, approved_by, approved_at, supersedes_id)
    body = _freeze(content)
    record_id = uuid.uuid4().hex
    digest = _sha256(body)
    connection.execute(
        rka_baseline.insert().values(
            id=record_id,
            record_kind=kind,
            label=label,
            period_start=period_start,
            period_end=period_end,
            supersedes_id=supersedes_id,
            content=body,
            content_hash=digest,
            approved_by=approved_by,
            approved_at=approved_at,
            created_by=author,
            created_at=_now_ms(),
        )
    )
    return RkaRecord(record_id, kind, digest)


def _check_rka(
    connection: Any,
    kind: str,
    label: str,
    period_start: str,
    period_end: str,
    approved_by: str | None,
    approved_at: int | None,
    supersedes_id: str | None,
) -> None:
    """What an RKA record must say about itself: its kind, period, approval and what it supersedes."""
    if kind not in RKA_KINDS:
        raise SnapshotRefused(f'an RKA record is one of {", ".join(RKA_KINDS)}, not {kind!r}')
    if not isinstance(label, str) or not label.strip():
        raise ValueError('label is required')
    if _date(period_start, 'period_start') > _date(period_end, 'period_end'):
        raise ValueError('the period ends before it starts')

    approved = approved_by is not None or approved_at is not None
    if kind == 'forecast':
        if approved:
            raise SnapshotRefused('a forecast is never approved RKA')
    elif not (isinstance(approved_by, str) and approved_by.strip() and type(approved_at) is int):
        raise SnapshotRefused(f'an approved {kind} names who approved it and when')

    _check_supersedes(connection, kind, supersedes_id)


def _check_supersedes(connection: Any, kind: str, supersedes_id: str | None) -> None:
    """A baseline supersedes nothing, a revision an approved record, a forecast only a forecast."""
    from sqlalchemy import select

    from jup.leadership.models import rka_baseline

    if kind == 'baseline' and supersedes_id is not None:
        raise SnapshotRefused('a baseline supersedes nothing; a later approved figure is a revision')
    if kind == 'revision' and supersedes_id is None:
        raise SnapshotRefused('a revision names the record it revises')
    if supersedes_id is not None:
        superseded = connection.execute(
            select(rka_baseline.c.record_kind).where(rka_baseline.c.id == supersedes_id)
        ).scalar()
        if superseded is None:
            raise SnapshotRefused(f'no RKA record {supersedes_id!r}')
        allowed = ('forecast',) if kind == 'forecast' else ('baseline', 'revision')
        if superseded not in allowed:
            raise SnapshotRefused(f'a {kind} cannot supersede a {superseded}')


def list_rka(connection: Any) -> list[dict[str, Any]]:
    """Every RKA record, oldest first, each verified against its hash."""
    from sqlalchemy import select

    from jup.leadership.models import rka_baseline

    records = []
    for row in connection.execute(select(rka_baseline).order_by(rka_baseline.c.created_at)).mappings():
        if _sha256(row['content']) != row['content_hash']:
            raise IntegrityFailure(f'RKA record {row["id"]} does not match its hash')
        records.append(
            {key: row[key] for key in row.keys() if key != 'content'} | {'content': json.loads(row['content'])}
        )
    return records


# --- helpers --------------------------------------------------------------------------------


def _freeze(content: dict[str, Any]) -> str:
    from jup.leadership.repository import canonical_json

    if not isinstance(content, dict):
        raise ValueError('frozen content is a JSON object')
    return canonical_json(content)


def _sha256(body: str) -> str:
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def _latest(connection: Any, snapshot_id: str, expected_version: int) -> SnapshotVersion:
    latest = read_versions(connection, snapshot_id)[-1]
    if latest.version != expected_version:
        raise SnapshotConflict(
            f'snapshot {snapshot_id!r} is at version {latest.version}, not {expected_version}', latest.version
        )
    return latest


def _insert_version(
    connection: Any,
    snapshot_id: str,
    version: int,
    state: str,
    change_kind: str,
    previous_version_id: str | None,
    body: str,
    author: str,
    now: int,
) -> SnapshotVersion:
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from jup.leadership.models import snapshot, snapshot_version

    row = {
        'id': uuid.uuid4().hex,
        'snapshot_id': snapshot_id,
        'version': version,
        'state': state,
        'change_kind': change_kind,
        'previous_version_id': previous_version_id,
        'content': body,
        'content_hash': _sha256(body),
        'created_by': author,
        'created_at': now,
    }
    try:
        # A second writer at the same version hits the unique (snapshot_id, version) constraint;
        # raising rolls the caller's whole transaction back.
        connection.execute(snapshot_version.insert().values(**row))
    except IntegrityError as error:
        raise SnapshotConflict(f'snapshot {snapshot_id!r} moved on meanwhile') from error
    head = connection.execute(select(snapshot).where(snapshot.c.id == snapshot_id)).mappings().one()
    return _version(head, row)


def _version(head: Any, row: Any) -> SnapshotVersion:
    return SnapshotVersion(
        id=row['id'],
        snapshot_id=row['snapshot_id'],
        view=head['view_key'],
        meeting_label=head['meeting_label'],
        meeting_date=head['meeting_date'],
        version=row['version'],
        state=row['state'],
        change_kind=row['change_kind'],
        previous_version_id=row['previous_version_id'],
        content_bytes=row['content'].encode('utf-8'),
        content_hash=row['content_hash'],
        created_by=row['created_by'],
        created_at=row['created_at'],
    )


_KIND_STATE = {'draft': 'draft', 'correction': 'draft', 'publication': 'published'}


def _verify(versions: list[SnapshotVersion]) -> None:
    """Each version's bytes, its state and its link, as the commands above write them."""
    by_id = {version.id: version for version in versions}
    for index, version in enumerate(versions):
        where = f'snapshot {version.snapshot_id} version {version.version}'
        if version.version != index + 1:
            raise IntegrityFailure(f'{where} is out of sequence')
        if hashlib.sha256(version.content_bytes).hexdigest() != version.content_hash:
            raise IntegrityFailure(f'{where} does not match its hash')
        if _KIND_STATE.get(version.change_kind) != version.state:
            raise IntegrityFailure(f'{where} is {version.state!r} but was written as a {version.change_kind!r}')
        previous = by_id.get(version.previous_version_id) if version.previous_version_id else None
        _verify_link(version, previous, where)


def _verify_link(version: SnapshotVersion, previous: SnapshotVersion | None, where: str) -> None:
    """A version against the one before it: a first draft links nothing, the rest link their predecessor."""
    if version.version == 1:
        if version.change_kind != 'draft' or version.previous_version_id is not None:
            raise IntegrityFailure(f'{where} is not a plain first draft')
        return
    if previous is None or previous.version != version.version - 1:
        raise IntegrityFailure(f'{where} does not link the version before it')
    if version.change_kind == 'publication' and (
        previous.state != 'draft' or previous.content_hash != version.content_hash
    ):
        raise IntegrityFailure(f'{where} does not repeat the draft it publishes')
    if version.change_kind == 'draft' and previous.state != 'draft':
        raise IntegrityFailure(f'{where} replaces a published version without being a correction')
    if version.change_kind == 'correction' and previous.state != 'published':
        raise IntegrityFailure(f'{where} corrects a version that was never published')


def _date(value: Any, name: str) -> dt.date:
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise ValueError(f'{name} must be a YYYY-MM-DD date')
    return dt.date.fromisoformat(value)


def _now_ms() -> int:
    import time

    return time.time_ns() // 1_000_000
