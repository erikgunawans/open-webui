"""The BOD's side of an action: closing, returning and reopening (P2 T4, ACT-02's BOD half, ACT-03).

Only the BOD closes. The capability (`bod.review`) is the router's check; everything else is here:

- **A configured policy.** `JUP_LEADERSHIP_BOD_POLICY` is deployment configuration, so every change
  to it is a reviewed commit: `{"mode": "individual"}` or `{"mode": "collective", "quorum": N}` with
  N ≥ 2. Unset or invalid means there is no closure path for anyone, and the router answers 503.
- **Never the owner.** The action's recorded PIC does not review it, whatever grants they hold.
- **The exact evidence.** A decision names the evidence revision the reviewer looked at. If the PIC
  has submitted a newer one since, the decision is refused as stale and the reviewer looks again.
  In collective mode, only close votes on the latest revision count toward the quorum, so a
  revision that lands mid-review sets the count back.

A close in individual mode, or the vote that reaches the quorum in collective mode, closes the
action and resolves its request. A vote short of the quorum is recorded as an event and changes no
state. A return sends the action back to in progress or blocked with a reason and resolves the
request as returned; the PIC's next completion evidence opens a new one. A reopen moves a closed
action back to in progress with a reason, as a new event: the closure it undoes stays in the record.

Return and reopen are single-reviewer decisions in both modes; only closing counts a quorum.

Each decision is one `bod_decision` event plus one `leadership_closure_decision` row, committed in
the same `unit_of_work()` as the request's status and the action's version.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update

from jup.leadership import actions
from jup.leadership.actions import CommandRefused
from jup.leadership.models import action, closure_decision, closure_request, evidence
from jup.leadership.repository import (
    ActionNotFound,
    AppendResult,
    IdempotencyKeyReused,
    UnitOfWork,
    VersionConflict,
)

log = logging.getLogger(__name__)

POLICY_ENV = 'JUP_LEADERSHIP_BOD_POLICY'
DECISIONS = ('close', 'return', 'reopen')
RETURN_STATES = (actions.IN_PROGRESS, actions.BLOCKED)
EVENT_KIND = 'bod_decision'


@dataclass(frozen=True)
class BodPolicy:
    mode: str  # 'individual' or 'collective'
    quorum: int


class OwnerCannotReview(PermissionError):
    """The reviewer is this action's recorded PIC; nothing was written."""


class StaleEvidence(CommandRefused):
    """The PIC submitted a newer evidence revision than the one reviewed; nothing was written."""

    def __init__(self, reviewed: str | None, latest: str) -> None:
        super().__init__('the evidence changed since it was reviewed; review the latest revision')
        self.reviewed = reviewed
        self.latest = latest


@dataclass(frozen=True)
class Decision:
    event: AppendResult
    decision_id: str
    outcome: str  # 'closed', 'vote_recorded', 'returned' or 'reopened'
    close_votes: int | None
    quorum: int | None

    @property
    def replayed(self) -> bool:
        return self.event.replayed


def parse_policy(raw: str | None) -> BodPolicy | None:
    """The BOD policy, or None when it is unset or anything about it is off."""
    if not raw or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(value, dict) or not set(value) <= {'mode', 'quorum'}:
        return None
    mode, quorum = value.get('mode'), value.get('quorum')
    # bool is an int in Python; a quorum of `true` must not read as one.
    if quorum is not None and (type(quorum) is not int):
        return None
    if mode == 'individual' and quorum in (None, 1):
        return BodPolicy('individual', 1)
    if mode == 'collective' and quorum is not None and quorum >= 2:
        return BodPolicy('collective', quorum)
    return None


def configured_policy() -> BodPolicy | None:
    """Read per request, so a restarted container or a test needs no reimport."""
    raw = os.environ.get(POLICY_ENV, '')
    policy = parse_policy(raw)
    if policy is None and raw.strip():
        log.warning('%s is set but invalid; BOD closure stays disabled', POLICY_ENV)
    return policy


def decide(
    uow: UnitOfWork,
    *,
    action_id: str,
    expected_version: int,
    reviewer: str,
    decision: str,
    policy: BodPolicy,
    evidence_id: str | None = None,
    reason: str | None = None,
    return_to: str | None = None,
    idempotency_key: str | None = None,
) -> Decision:
    """Record one BOD decision on an action. See the module docstring for the rules."""
    if decision not in DECISIONS:
        raise CommandRefused(f'a BOD decision is one of {", ".join(DECISIONS)}, not {decision!r}')
    command = {'decision': decision, 'evidence_id': evidence_id, 'reason': reason, 'return_to': return_to}
    connection = uow.connection

    if idempotency_key is not None:
        earlier = uow.event_for_key(action_id, idempotency_key)
        if earlier is not None:
            if earlier.kind != EVENT_KIND or earlier.payload.get('command') != command:
                raise IdempotencyKeyReused(
                    f'idempotency key {idempotency_key!r} was already used on action {action_id!r} '
                    'for a different event'
                )
            return _replayed(connection, earlier)

    row = connection.execute(select(action).where(action.c.id == action_id)).mappings().first()
    if row is None:
        raise ActionNotFound(f'no action {action_id!r}')
    # Judge nothing on state the caller never saw: a stale version conflicts first.
    if row['version'] != expected_version:
        raise VersionConflict(action_id, expected_version, row['version'])
    if row['pic_user_id'] is not None and row['pic_user_id'] == reviewer:
        raise OwnerCannotReview(f'the PIC of action {action_id!r} cannot review it')

    latest = connection.execute(
        select(evidence.c.id).where(evidence.c.action_id == action_id).order_by(evidence.c.revision.desc()).limit(1)
    ).scalar()
    if decision == 'reopen':
        plan = _plan_reopen(connection, row, latest, reason)
    else:
        plan = _plan_review(connection, row, latest, reviewer, policy, decision, evidence_id, reason, return_to)

    result = uow.append_event(
        action_id=action_id,
        expected_version=expected_version,
        kind=EVENT_KIND,
        payload={
            'command': command,
            'outcome': plan.outcome,
            'request_id': plan.request_id,
            'evidence_id': plan.evidence_id,
            'mode': policy.mode,
            'close_votes': plan.close_votes,
            'quorum': plan.quorum,
        },
        changes=plan.changes,
        author=reviewer,
        reason=reason,
        idempotency_key=idempotency_key,
    )
    decision_id = uuid.uuid4().hex
    connection.execute(
        closure_decision.insert().values(
            id=decision_id,
            request_id=plan.request_id,
            evidence_id=plan.evidence_id,
            event_id=result.event.id,
            decision=decision,
            reason=reason,
            reviewer_user_id=reviewer,
            created_at=result.event.created_at,
        )
    )
    if plan.outcome in ('closed', 'returned'):
        connection.execute(
            update(closure_request)
            .where(closure_request.c.id == plan.request_id)
            .values(status=plan.outcome, resolved_at=result.event.created_at)
        )
    return Decision(result, decision_id, plan.outcome, plan.close_votes, plan.quorum)


@dataclass(frozen=True)
class _Plan:
    """What a decision will write, worked out before anything is written."""

    outcome: str
    changes: dict[str, Any]
    request_id: str
    evidence_id: str
    close_votes: int | None = None
    quorum: int | None = None


def _plan_reopen(connection: Any, row: Any, latest: str | None, reason: str | None) -> _Plan:
    _require_reason(reason, 'reopening')
    if row['state'] != actions.CLOSED:
        raise CommandRefused(f'only a closed action is reopened, not one that is {row["state"]!r}')
    request = (
        connection.execute(
            select(closure_request)
            .where(closure_request.c.action_id == row['id'], closure_request.c.status == 'closed')
            .order_by(closure_request.c.resolved_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if request is None:
        raise CommandRefused('this action has no recorded closure to reopen')
    return _Plan('reopened', {'state': actions.IN_PROGRESS}, request['id'], latest or request['evidence_id'])


def _plan_review(
    connection: Any,
    row: Any,
    latest: str | None,
    reviewer: str,
    policy: BodPolicy,
    decision: str,
    evidence_id: str | None,
    reason: str | None,
    return_to: str | None,
) -> _Plan:
    """A close or a return, on the open request and the latest evidence revision."""
    if row['state'] != actions.AWAITING_BOD_CLOSURE:
        raise CommandRefused(f'no closure request is open on an action that is {row["state"]!r}')
    request = (
        connection.execute(
            select(closure_request).where(closure_request.c.action_id == row['id'], closure_request.c.status == 'open')
        )
        .mappings()
        .first()
    )
    if request is None:
        raise CommandRefused('no closure request is open on this action')
    if evidence_id != latest:
        raise StaleEvidence(evidence_id, latest)

    if decision == 'return':
        _require_reason(reason, 'a return')
        if return_to not in RETURN_STATES:
            raise CommandRefused(f'a return goes back to {" or ".join(RETURN_STATES)}, not {return_to!r}')
        return _Plan('returned', {'state': return_to}, request['id'], latest)

    voters = set(
        connection.execute(
            select(closure_decision.c.reviewer_user_id).where(
                closure_decision.c.request_id == request['id'],
                closure_decision.c.decision == 'close',
                closure_decision.c.evidence_id == latest,
            )
        ).scalars()
    )
    if reviewer in voters:
        raise CommandRefused('this reviewer has already voted to close on this evidence')
    votes = len(voters) + 1
    if votes >= policy.quorum:
        return _Plan('closed', {'state': actions.CLOSED}, request['id'], latest, votes, policy.quorum)
    return _Plan('vote_recorded', {}, request['id'], latest, votes, policy.quorum)


def _replayed(connection: Any, event: Any) -> Decision:
    decision_id = connection.execute(
        select(closure_decision.c.id).where(closure_decision.c.event_id == event.id)
    ).scalar_one()
    payload = event.payload
    return Decision(
        AppendResult(event, replayed=True), decision_id, payload['outcome'], payload['close_votes'], payload['quorum']
    )


def _require_reason(reason: str | None, what: str) -> None:
    if not isinstance(reason, str) or not reason.strip():
        raise CommandRefused(f'{what} needs a reason')
