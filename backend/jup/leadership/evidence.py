"""The PIC's side of an action: progress and evidence (P2 T3, ACT-02's PIC half).

Only the action's recorded PIC submits, and only with the `actions.submit` capability; the
capability is the router's check, and the PIC check is here, against the action's current row.
An action with no recorded PIC user has no submitter at all. Admin, a BOC observer and every
other reader are refused whatever else they hold.

Evidence is versioned: each submission is a new `leadership_evidence` row at the next revision,
tied to the event that recorded it, and nothing is ever replaced. A submission can also request
closure, bound to that exact evidence revision, which moves the action to awaiting BOD closure:

- `completed` (the `completion` flag), from in progress only;
- `cancelled`, with a reason, from any open state (not started, in progress, blocked);
- `superseded`, naming the replacement action, from any open state.

**It never closes the action.** Closing is a BOD decision (T4), and all three kinds pass the same
gate. The evidence of a cancellation or a supersession is whatever records it: the memo, the
minutes, the replacement's charter.

The evidence row, the event, the version bump and any closure request commit in one
`unit_of_work()`. The file itself is stored first, under a content-addressed key, so a transaction
that rolls back leaves at most an unreferenced object, never a row pointing at nothing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select

from jup.leadership import actions
from jup.leadership.evidence_store import CheckedFile
from jup.leadership.models import action, closure_request, evidence
from jup.leadership.repository import ActionNotFound, AppendResult, UnitOfWork


class NotThePic(PermissionError):
    """The caller is not this action's recorded PIC; nothing was written."""


@dataclass(frozen=True)
class Submission:
    event: AppendResult
    evidence: dict[str, Any]
    closure_request_id: str | None

    @property
    def replayed(self) -> bool:
        return self.event.replayed


def ensure_pic(connection: Any, action_id: str, actor: str) -> dict[str, Any]:
    """The action's row, if `actor` is its recorded PIC."""
    row = connection.execute(select(action).where(action.c.id == action_id)).mappings().first()
    if row is None:
        raise ActionNotFound(f'no action {action_id!r}')
    if row['pic_user_id'] is None or row['pic_user_id'] != actor:
        raise NotThePic(f'only the recorded PIC submits on action {action_id!r}')
    return dict(row)


def submit_progress(uow: UnitOfWork, *, action_id: str, actor: str, **command: Any) -> AppendResult:
    """An owner update, from the PIC only. See `actions.record_progress` for the fields."""
    ensure_pic(uow.connection, action_id, actor)
    return actions.record_progress(uow, action_id=action_id, author=actor, **command)


def link_evidence(url: str) -> dict[str, Any]:
    """Evidence that is a link: https only, with a host."""
    parts = urlsplit((url or '').strip())
    if parts.scheme != 'https' or not parts.netloc:
        raise actions.CommandRefused('link evidence must be an https URL')
    return {'kind': 'link', 'url': parts.geturl()}


def file_evidence(checked: CheckedFile) -> dict[str, Any]:
    """Evidence that is a stored file. The key is the server's; the filename is metadata."""
    return {
        'kind': 'file',
        'storage_key': checked.key,
        'filename': checked.filename,
        'content_type': checked.content_type,
        'size_bytes': checked.size,
        'sha256': checked.sha256,
    }


def submit_evidence(
    uow: UnitOfWork,
    *,
    action_id: str,
    expected_version: int,
    actor: str,
    item: dict[str, Any],
    completion: bool = False,
    note: str | None = None,
    idempotency_key: str | None = None,
    closure_kind: str | None = None,
    reason: str | None = None,
    replacement_action_id: str | None = None,
) -> Submission:
    """Record one evidence revision; with a closure kind (or `completion`), also request BOD closure."""
    closure_kind = _closure_kind(completion, closure_kind, reason, replacement_action_id, action_id)
    row = ensure_pic(uow.connection, action_id, actor)
    if row['version'] == expected_version:
        _check_request_state(row['state'], closure_kind)
        if replacement_action_id is not None:
            if uow.connection.execute(select(action.c.id).where(action.c.id == replacement_action_id)).scalar() is None:
                raise actions.CommandRefused(f'no replacement action {replacement_action_id!r}')

    result = uow.append_event(
        action_id=action_id,
        expected_version=expected_version,
        kind='evidence_submitted',
        payload={
            'evidence': item,
            'completion': closure_kind == 'completed',
            'closure_kind': closure_kind,
            'replacement_action_id': replacement_action_id,
            'note': note,
        },
        changes={'state': actions.AWAITING_BOD_CLOSURE} if closure_kind else {},
        author=actor,
        reason=reason,
        idempotency_key=idempotency_key,
    )
    connection = uow.connection
    if result.replayed:
        stored = connection.execute(select(evidence).where(evidence.c.event_id == result.event.id)).mappings().one()
        request_id = connection.execute(
            select(closure_request.c.id).where(closure_request.c.event_id == result.event.id)
        ).scalar()
        return Submission(result, dict(stored), request_id)

    # The UPDATE inside append_event holds this action's row, so the next revision is ours alone;
    # the unique (action_id, revision) constraint backs that up.
    revision = (
        connection.execute(
            select(func.coalesce(func.max(evidence.c.revision), 0)).where(evidence.c.action_id == action_id)
        ).scalar()
        + 1
    )
    stored = {
        'id': uuid.uuid4().hex,
        'action_id': action_id,
        'revision': revision,
        'event_id': result.event.id,
        'kind': item['kind'],
        'storage_key': item.get('storage_key'),
        'url': item.get('url'),
        'filename': item.get('filename'),
        'content_type': item.get('content_type'),
        'size_bytes': item.get('size_bytes'),
        'sha256': item.get('sha256'),
        'submitted_by': actor,
        'created_at': result.event.created_at,
    }
    connection.execute(evidence.insert().values(**stored))

    request_id = None
    if closure_kind:
        request_id = uuid.uuid4().hex
        connection.execute(
            closure_request.insert().values(
                id=request_id,
                action_id=action_id,
                evidence_id=stored['id'],
                event_id=result.event.id,
                closure_kind=closure_kind,
                replacement_action_id=replacement_action_id,
                status='open',
                requested_by=actor,
                created_at=result.event.created_at,
                resolved_at=None,
            )
        )
    return Submission(result, stored, request_id)


def _closure_kind(
    completion: bool, kind: str | None, reason: str | None, replacement: str | None, action_id: str
) -> str | None:
    """The closure this submission requests, if any, with what each kind must carry."""
    if completion:
        if kind not in (None, 'completed'):
            raise actions.CommandRefused(f'completion evidence cannot also request {kind!r}')
        kind = 'completed'
    if kind is not None and kind not in actions.CLOSURE_KINDS:
        raise actions.CommandRefused(f'a closure request is one of {", ".join(actions.CLOSURE_KINDS)}, not {kind!r}')
    if kind == 'cancelled' and (not isinstance(reason, str) or not reason.strip()):
        raise actions.CommandRefused('a cancellation request needs a reason')
    if (kind == 'superseded') != (replacement is not None):
        raise actions.CommandRefused('a supersession request, and only one, names its replacement action')
    if replacement == action_id:
        raise actions.CommandRefused('an action cannot supersede itself')
    return kind


def _check_request_state(state: str, kind: str | None) -> None:
    if state == actions.CLOSED:
        raise actions.CommandRefused('the action is closed; only a BOD decision can reopen it')
    if kind == 'completed' and state != actions.IN_PROGRESS:
        raise actions.CommandRefused(
            f'completion evidence is submitted on an action in progress, not one that is {state!r}'
        )
    if kind is not None and state == actions.AWAITING_BOD_CLOSURE:
        raise actions.CommandRefused('a closure request is already open on this action')


def read_evidence(connection: Any, evidence_id: str) -> dict[str, Any] | None:
    row = connection.execute(select(evidence).where(evidence.c.id == evidence_id)).mappings().first()
    return dict(row) if row is not None else None
