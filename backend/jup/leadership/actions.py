"""The board action: its lifecycle, its due dates, and the flags derived beside them (P2 T2, ACT-03).

Every command here is an event appended through `repository.UnitOfWork`, so each one takes the
caller's `expected_version` and an optional idempotency key, and a stale version is a
`VersionConflict` that writes nothing.

The lifecycle is the approved design's: **Not started → In progress → Awaiting BOD closure →
Closed**, with **Blocked** as an explicit open state. This module lets the owner move only between
not started, in progress and blocked. Awaiting BOD closure is reached by submitting completion
evidence (T3), and closing, returning and reopening are BOD decisions (T4); `TRANSITIONS` records
the whole graph so those modules check against the same table.

A command's event holds only what the command was given, never what it read, so a double
submission compares equal and replays. Rules that depend on the current state (a closed action
takes no owner command, a transition must be legal) are judged only when the caller's version is
current; with a stale version the append conflicts instead, and nobody is refused on the basis of
state they never saw.

Overdue, due before the next meeting and stale are derived flags, never states. Each is None,
with a reason, when the data cannot support it: an overdue count needs a day-precise due date, and
staleness needs a threshold the company has recorded. Nothing here invents a date or a percentage.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    # Imported for annotations only, so `Due` and `derive_flags` stay usable (and tested) without
    # the database runtime installed.
    from jup.leadership.repository import AppendResult, Event, UnitOfWork

NOT_STARTED = 'not_started'
IN_PROGRESS = 'in_progress'
BLOCKED = 'blocked'
AWAITING_BOD_CLOSURE = 'awaiting_bod_closure'
CLOSED = 'closed'
STATES = (NOT_STARTED, IN_PROGRESS, BLOCKED, AWAITING_BOD_CLOSURE, CLOSED)

# Closure records what it means; cancellation needs a reason and supersession links the
# replacement. All three pass the BOD closure gate (T4).
CLOSURE_KINDS = ('completed', 'cancelled', 'superseded')

TRANSITIONS: dict[str, frozenset[str]] = {
    # Awaiting closure is reachable from any open state, because cancellation and supersession
    # are requested without completion evidence. Which request may come from where is T3/T4's.
    NOT_STARTED: frozenset({IN_PROGRESS, BLOCKED, AWAITING_BOD_CLOSURE}),
    IN_PROGRESS: frozenset({BLOCKED, AWAITING_BOD_CLOSURE}),
    BLOCKED: frozenset({IN_PROGRESS, AWAITING_BOD_CLOSURE}),
    # Close, or return to in progress or blocked with a reason.
    AWAITING_BOD_CLOSURE: frozenset({CLOSED, IN_PROGRESS, BLOCKED}),
    # Reopening: a BOD decision and a new event; the previous closure stays in the history.
    CLOSED: frozenset({IN_PROGRESS}),
}

# The part of the graph the owner walks with `change_state`.
OWNER_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {(NOT_STARTED, IN_PROGRESS), (NOT_STARTED, BLOCKED), (IN_PROGRESS, BLOCKED), (BLOCKED, IN_PROGRESS)}
)

# JUP reports in WIB; a timestamp becomes a calendar day there, not in UTC.
REPORTING_TZ = ZoneInfo('Asia/Jakarta')

# ASCII digits only: `\d` would accept any Unicode digit.
_DUE_PATTERNS = {
    'date': re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}'),
    'month': re.compile(r'[0-9]{4}-[0-9]{2}'),
    'year': re.compile(r'[0-9]{4}'),
    'year_range': re.compile(r'[0-9]{4}/[0-9]{4}'),
}


class CommandRefused(ValueError):
    """The command is not allowed for this action as it stands; nothing was written."""


@dataclass(frozen=True)
class Due:
    """A due date at the precision the source gave: 'date', 'month', 'year' or 'year_range'.

    Stored as text: '2026-11-30', '2026-11', '2027' or '2026/2027'. A source that said
    "2026–2027" stays a range; it never becomes an invented day.
    """

    precision: str
    value: str

    def __post_init__(self) -> None:
        pattern = _DUE_PATTERNS.get(self.precision)
        if pattern is None:
            raise ValueError(f'due precision must be one of {", ".join(_DUE_PATTERNS)}, not {self.precision!r}')
        if not isinstance(self.value, str) or not pattern.fullmatch(self.value):
            raise ValueError(f'{self.value!r} is not a {self.precision} due date')
        if self.precision == 'date':
            dt.date.fromisoformat(self.value)  # refuses 2026-02-30
        elif self.precision == 'month' and not 1 <= int(self.value[5:]) <= 12:
            raise ValueError(f'{self.value!r} has no month {self.value[5:]}')
        elif self.precision == 'year_range':
            start, end = self.value.split('/')
            if int(start) > int(end):
                raise ValueError(f'{self.value!r} ends before it starts')

    def as_dict(self) -> dict[str, str]:
        return {'precision': self.precision, 'value': self.value}


# --- commands -------------------------------------------------------------------------------


def create_action(
    uow: UnitOfWork,
    *,
    action_id: str,
    title: str,
    pic_label: str,
    author: str,
    pic_user_id: str | None = None,
    due: Due | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> AppendResult:
    """A new action, not started. Its due date, if known, is both the original and the current one."""
    _require_text(title, 'title')
    _require_text(pic_label, 'pic_label')
    fields = {
        'title': title,
        'pic_user_id': pic_user_id,
        'pic_label': pic_label,
        'state': NOT_STARTED,
        'original_due': due.value if due else None,
        'original_due_precision': due.precision if due else None,
        'current_due': due.value if due else None,
        'current_due_precision': due.precision if due else None,
    }
    return uow.create_action(
        action_id=action_id, fields=fields, author=author, reason=reason, idempotency_key=idempotency_key
    )


def change_state(
    uow: UnitOfWork,
    *,
    action_id: str,
    expected_version: int,
    to_state: str,
    author: str,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> AppendResult:
    """The owner's moves: start, block (with a reason) and unblock. Nothing here closes."""
    if to_state not in {IN_PROGRESS, BLOCKED}:
        raise CommandRefused(
            f'an owner cannot move an action to {to_state!r}; closure is requested with evidence and decided by the BOD'
        )
    if to_state == BLOCKED:
        _require_text(reason, 'reason', refusal=True)
    current = _current_if_fresh(uow, action_id, expected_version)
    if current is not None:
        _refuse_if_closed(current)
        if (current['state'], to_state) not in OWNER_TRANSITIONS:
            raise CommandRefused(f'an owner cannot move an action from {current["state"]!r} to {to_state!r}')
    return uow.append_event(
        action_id=action_id,
        expected_version=expected_version,
        kind='state_changed',
        payload={'to': to_state},
        changes={'state': to_state},
        author=author,
        reason=reason,
        idempotency_key=idempotency_key,
    )


def revise_due(
    uow: UnitOfWork,
    *,
    action_id: str,
    expected_version: int,
    due: Due,
    reason: str,
    author: str,
    idempotency_key: str | None = None,
) -> AppendResult:
    """Move the current due date, with a reason. The original due date is never touched."""
    _require_text(reason, 'reason', refusal=True)
    current = _current_if_fresh(uow, action_id, expected_version)
    if current is not None:
        _refuse_if_closed(current)
        if (current['current_due'], current['current_due_precision']) == (due.value, due.precision):
            raise CommandRefused('the due date is unchanged; a revision must move it')
    return uow.append_event(
        action_id=action_id,
        expected_version=expected_version,
        kind='due_revised',
        payload={'due': due.as_dict()},
        changes={'current_due': due.value, 'current_due_precision': due.precision},
        author=author,
        reason=reason,
        idempotency_key=idempotency_key,
    )


def record_progress(
    uow: UnitOfWork,
    *,
    action_id: str,
    expected_version: int,
    narrative: str,
    author: str,
    milestones_completed: Iterable[str] = (),
    remaining_work: str | None = None,
    blocker: str | None = None,
    next_step: str | None = None,
    reported_at: str | None = None,
    idempotency_key: str | None = None,
) -> AppendResult:
    """An owner update. It changes no state and carries no percentage.

    `reported_at` is the client's own clock, kept for display. It orders nothing: events are
    ordered by version, so a late-arriving older update conflicts rather than overwrites.
    """
    _require_text(narrative, 'narrative', refusal=True)
    current = _current_if_fresh(uow, action_id, expected_version)
    if current is not None:
        _refuse_if_closed(current)
    payload = {
        'owner_update': True,
        'narrative': narrative,
        'milestones_completed': list(milestones_completed),
        'remaining_work': remaining_work,
        'blocker': blocker,
        'next_step': next_step,
        'reported_at': reported_at,
    }
    return uow.append_event(
        action_id=action_id,
        expected_version=expected_version,
        kind='progress_submitted',
        payload=payload,
        author=author,
        idempotency_key=idempotency_key,
    )


# --- reading --------------------------------------------------------------------------------


def latest_progress(events: Iterable[Event]) -> Event | None:
    """The owner update with the highest version, whatever its client clock said."""
    updates = [event for event in events if event.kind == 'progress_submitted']
    return max(updates, key=lambda event: event.version) if updates else None


def fold_history(events: Iterable[Event]) -> list[dict[str, Any]]:
    """Each event with the state and current due date before and after it, in version order."""
    history: list[dict[str, Any]] = []
    state: str | None = None
    due: dict[str, str] | None = None
    for event in sorted(events, key=lambda item: item.version):
        state_before, due_before = state, due
        changes = event.changes
        state = changes.get('state', state)
        if 'current_due' in changes or 'current_due_precision' in changes:
            value, precision = changes.get('current_due'), changes.get('current_due_precision')
            due = {'precision': precision, 'value': value} if value is not None else None
        history.append(
            {
                'version': event.version,
                'kind': event.kind,
                'author': event.author,
                'at': event.created_at,
                'reason': event.reason,
                'payload': event.payload,
                'state_before': state_before,
                'state_after': state,
                'due_before': due_before,
                'due_after': due,
            }
        )
    return history


@dataclass(frozen=True)
class Flags:
    """Derived beside the state, never instead of it. None means "cannot say", with a reason."""

    overdue: bool | None
    days_overdue: int | None
    due_before_next_meeting: bool | None
    stale: bool | None
    reasons: dict[str, str] = field(default_factory=dict)


def derive_flags(
    row: dict[str, Any],
    *,
    today: dt.date,
    next_meeting: dt.date | None = None,
    stale_after_days: int | None = None,
    last_update_at_ms: int | None = None,
) -> Flags:
    """Overdue, due before the next meeting, and stale, for one action's current row.

    Args:
        row: the action's current row (state and current due date are read).
        today: the reporting day, in WIB.
        next_meeting: the next BOD meeting, if one is scheduled.
        stale_after_days: the company's recorded staleness threshold. There is no default: an
            assumed threshold would quietly mark actions fresh.
        last_update_at_ms: when the owner last updated the action.
    """
    if row['state'] == CLOSED:
        closed = 'the action is closed'
        return Flags(None, None, None, None, {'overdue': closed, 'due_before_next_meeting': closed, 'stale': closed})

    reasons: dict[str, str] = {}
    due_day = _due_day(row)
    if due_day is None:
        precision = row.get('current_due_precision')
        reasons['overdue'] = (
            'no due date is known' if precision is None else f'the due date is {precision}-precise, not a day'
        )
        overdue, days_overdue = None, None
    else:
        overdue = today > due_day
        days_overdue = (today - due_day).days if overdue else None

    if due_day is None or next_meeting is None:
        reasons['due_before_next_meeting'] = (
            'no next meeting is scheduled' if due_day is not None else reasons['overdue']
        )
        before_meeting = None
    else:
        before_meeting = due_day <= next_meeting

    if stale_after_days is None:
        reasons['stale'] = 'no staleness policy is recorded'
        stale = None
    elif last_update_at_ms is None:
        reasons['stale'] = 'the owner has not updated this action'
        stale = None
    else:
        last_day = dt.datetime.fromtimestamp(last_update_at_ms / 1000, REPORTING_TZ).date()
        stale = (today - last_day).days > stale_after_days

    return Flags(overdue, days_overdue, before_meeting, stale, reasons)


# --- helpers --------------------------------------------------------------------------------


def _current_if_fresh(uow: UnitOfWork, action_id: str, expected_version: int) -> dict[str, Any] | None:
    """The action's row when the caller's version is current; None when it is stale."""
    from sqlalchemy import select

    from jup.leadership.models import action
    from jup.leadership.repository import ActionNotFound

    row = uow.connection.execute(select(action).where(action.c.id == action_id)).mappings().first()
    if row is None:
        raise ActionNotFound(f'no action {action_id!r}')
    return dict(row) if row['version'] == expected_version else None


def _refuse_if_closed(row: dict[str, Any]) -> None:
    if row['state'] == CLOSED:
        raise CommandRefused('the action is closed; only a BOD decision can reopen it')


def _due_day(row: dict[str, Any]) -> dt.date | None:
    if row.get('current_due_precision') != 'date' or row.get('current_due') is None:
        return None
    return dt.date.fromisoformat(row['current_due'])


def _require_text(value: str | None, name: str, *, refusal: bool = False) -> None:
    if not isinstance(value, str) or not value.strip():
        error = CommandRefused if refusal else ValueError
        raise error(f'{name} is required')
