"""Ruang Pimpinan's persistence adapter: one transaction per command, events appended, never edited.

ADR-0014 puts the section's workflow records in the app database as an append-only event log. This
module is the only place that writes them, and it offers exactly one way to change an action: an
event appended inside `unit_of_work()`, which in the same transaction

- bumps the action's optimistic version, but only if the caller's `expected_version` is still
  current (a stale one raises `VersionConflict` and writes nothing),
- applies the aggregate columns that event changes, and
- records the idempotency key, so a double-clicked submission returns the first result instead of
  appending twice.

Either all of that commits or none of it does. Anything else the command writes inside the same
`unit_of_work()` (evidence, a closure request) shares the transaction.

What an event *means* (which states follow which, who may do what) belongs to the domain modules
that call this one; the adapter only guarantees the write is atomic, ordered and never repeated.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from jup.leadership.models import action, action_event

# The aggregate columns an event may change. Identity, the version, the creation record and the
# original due date are absent on purpose: the version moves only through an append, and an
# original due date is kept when the current one is revised (ACT-03).
MUTABLE_ACTION_COLUMNS = frozenset(
    {'title', 'pic_user_id', 'pic_label', 'state', 'current_due', 'current_due_precision'}
)
_CREATE_COLUMNS = MUTABLE_ACTION_COLUMNS | {'original_due', 'original_due_precision'}


class VersionConflict(Exception):
    """The action moved on since the caller read it; nothing was written."""

    def __init__(self, action_id: str, expected: int, actual: int) -> None:
        super().__init__(f'action {action_id!r} is at version {actual}, not {expected}')
        self.action_id = action_id
        self.expected = expected
        self.actual = actual


class IdempotencyKeyReused(Exception):
    """A key already used for this action arrived with a different event; nothing was written."""


class ActionNotFound(LookupError):
    """No action has this id."""


class ActionExists(Exception):
    """An action with this id already exists; ids are stable and never reissued."""


@dataclass(frozen=True)
class Event:
    """One appended change to an action, as stored."""

    id: str
    action_id: str
    version: int
    kind: str
    payload: dict[str, Any]
    changes: dict[str, Any]
    reason: str | None
    author: str
    created_at: int
    idempotency_key: str | None


@dataclass(frozen=True)
class AppendResult:
    event: Event
    # True when an idempotency key matched an earlier submission and that event was returned.
    replayed: bool


@contextmanager
def unit_of_work(engine: Engine) -> Iterator[UnitOfWork]:
    """One transaction: everything done through the yielded object commits together or not at all."""
    with engine.begin() as connection:
        yield UnitOfWork(connection)


class UnitOfWork:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create_action(
        self,
        *,
        action_id: str,
        fields: dict[str, Any],
        author: str,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AppendResult:
        """Insert an action at version 1 together with its `created` event, which carries every field."""
        _check_columns(fields, _CREATE_COLUMNS)
        body = _canonical_json({'data': {}, 'changes': fields})
        if self._current_version(action_id) is not None:
            raise ActionExists(f'action {action_id!r} already exists')
        now = _now_ms()
        try:
            self.connection.execute(
                action.insert().values(
                    id=action_id, version=1, created_by=author, created_at=now, updated_at=now, **fields
                )
            )
        except IntegrityError as error:
            # A concurrent create of the same id got there first.
            raise ActionExists(f'action {action_id!r} already exists') from error
        event = self._insert_event(action_id, 1, 'created', body, reason, author, now, idempotency_key)
        return AppendResult(event, replayed=False)

    def append_event(
        self,
        *,
        action_id: str,
        expected_version: int,
        kind: str,
        payload: dict[str, Any],
        author: str,
        reason: str | None = None,
        changes: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> AppendResult:
        """Append one event at `expected_version + 1`, applying `changes` to the action in the same write.

        Raises:
            ValueError: `changes` names a column an event may not touch, or the payload holds a float.
            IdempotencyKeyReused: the key was used for this action with a different event.
            ActionNotFound: no such action.
            VersionConflict: the action is no longer at `expected_version`.
        """
        changes = dict(changes or {})
        _check_columns(changes, MUTABLE_ACTION_COLUMNS)
        body = _canonical_json({'data': payload, 'changes': changes})

        if idempotency_key is not None:
            earlier = self._replay(action_id, idempotency_key, kind, body)
            if earlier is not None:
                return earlier

        now = _now_ms()
        # The version check and the bump are one conditional UPDATE. On Postgres a second writer
        # blocks on this row until the first commits, then finds the version moved and matches
        # nothing, so two writers can never both append at the same version.
        moved = self.connection.execute(
            update(action)
            .where(action.c.id == action_id, action.c.version == expected_version)
            .values(version=expected_version + 1, updated_at=now, **changes)
        )
        if moved.rowcount != 1:
            current = self._current_version(action_id)
            if current is None:
                raise ActionNotFound(f'no action {action_id!r}')
            if idempotency_key is not None:
                # The writer we lost to may have been this same submission, committed meanwhile.
                earlier = self._replay(action_id, idempotency_key, kind, body)
                if earlier is not None:
                    return earlier
            raise VersionConflict(action_id, expected_version, current)

        event = self._insert_event(action_id, expected_version + 1, kind, body, reason, author, now, idempotency_key)
        return AppendResult(event, replayed=False)

    def _insert_event(
        self,
        action_id: str,
        version: int,
        kind: str,
        body: str,
        reason: str | None,
        author: str,
        now: int,
        idempotency_key: str | None,
    ) -> Event:
        row = {
            'id': uuid.uuid4().hex,
            'action_id': action_id,
            'version': version,
            'kind': kind,
            'payload': body,
            'reason': reason,
            'author_user_id': author,
            'created_at': now,
            'idempotency_key': idempotency_key,
        }
        self.connection.execute(action_event.insert().values(**row))
        return _event(row)

    def event_for_key(self, action_id: str, key: str) -> Event | None:
        """The event an idempotency key already recorded on this action, if any.

        For commands whose event depends on what they read (a BOD vote's count), so a replay has
        to be recognised by the command before anything is recomputed.
        """
        row = (
            self.connection.execute(
                select(action_event).where(action_event.c.action_id == action_id, action_event.c.idempotency_key == key)
            )
            .mappings()
            .first()
        )
        return _event(row) if row is not None else None

    def _replay(self, action_id: str, key: str, kind: str, body: str) -> AppendResult | None:
        row = (
            self.connection.execute(
                select(action_event).where(action_event.c.action_id == action_id, action_event.c.idempotency_key == key)
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        if row['kind'] != kind or row['payload'] != body:
            raise IdempotencyKeyReused(
                f'idempotency key {key!r} was already used on action {action_id!r} for a different event'
            )
        return AppendResult(_event(row), replayed=True)

    def _current_version(self, action_id: str) -> int | None:
        return self.connection.execute(select(action.c.version).where(action.c.id == action_id)).scalar()


def read_action(engine: Engine, action_id: str) -> dict[str, Any] | None:
    """The action's current row, or None."""
    with engine.connect() as connection:
        row = connection.execute(select(action).where(action.c.id == action_id)).mappings().first()
    return dict(row) if row is not None else None


def read_events(engine: Engine, action_id: str) -> list[Event]:
    """Every event of one action, in version order (never client time)."""
    with engine.connect() as connection:
        rows = connection.execute(
            select(action_event).where(action_event.c.action_id == action_id).order_by(action_event.c.version)
        ).mappings()
        return [_event(row) for row in rows]


def _event(row: Any) -> Event:
    body = json.loads(row['payload'])
    return Event(
        id=row['id'],
        action_id=row['action_id'],
        version=row['version'],
        kind=row['kind'],
        payload=body['data'],
        changes=body['changes'],
        reason=row['reason'],
        author=row['author_user_id'],
        created_at=row['created_at'],
        idempotency_key=row['idempotency_key'],
    )


def _check_columns(values: dict[str, Any], allowed: frozenset[str]) -> None:
    refused = sorted(set(values) - allowed)
    if refused:
        raise ValueError(f'an event may not set {", ".join(refused)} on an action')


def _canonical_json(value: Any) -> str:
    """Stable bytes for stored content, refusing any float (money travels as decimal strings)."""
    _refuse_floats(value, '$')
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except TypeError as error:
        raise ValueError(f'event content must be plain JSON: {error}') from error


def _refuse_floats(value: Any, path: str) -> None:
    if isinstance(value, float):
        raise ValueError(f'{path} is a float; figures travel as decimal strings')
    if isinstance(value, dict):
        for key, item in value.items():
            _refuse_floats(item, f'{path}.{key}')
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _refuse_floats(item, f'{path}[{index}]')


def _now_ms() -> int:
    return time.time_ns() // 1_000_000
