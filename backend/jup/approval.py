"""The approval step for an attended External Call (ADR-0013 §3, A5 + E5 ticket 3/7).

`jup.tool_policy` decides *whether* a call needs a person. This module is what happens while it
waits for one: the vendor's pause-and-resume machinery (`pause_for_tool_approval`,
`resolve_tool_call_output`, `drain_approved_tool_calls`) moves the call through the chat's stored
`output`, and these functions are the JUP rules applied at each step. They are pure, so every rule
is tested here; the vendor patches stay one call each (`deploy/gcp/VENDOR-PATCHES.md`).

**The life of a gated call.** It is *armed* when its card is shown (`arm`): the call item gains a
`jup_gate` entry with the moment it was shown, and its 10-minute clock starts then, not when the
model produced it, because a call queued behind another card has not been shown to anyone yet.
The asking user then approves or rejects it (`resolve`), or nobody answers and the server times it
out (`time_out`). A decision after the deadline is a timeout, whatever the button said.

**Why an approval is signed.** The stored `output` lives in the user's chat, which the chat's
owner can rewrite through the chats API. An approval is therefore an HMAC over exactly the call
that was shown (chat, message, call id, tool name, argument text), who approved it and when, keyed
with the server secret. `verified` recomputes it at the moment the call runs: an edited argument,
another user, another message or a hand-set `approved: true` all fail, and the call is refused.
What the signature cannot stop is the owner replaying their own approved call by deleting its
result from the stored chat; that would need a server-side ledger, and it only ever re-runs a call
that same person approved.

The approval never reaches the model or the audit line as content: the audit line gets
`approval`, `approved_by` and `approval_wait_ms` (`jup.governance.audit_tool_call`).
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from jup.tool_policy import EXTERNAL, classify

#: How long a shown card waits for an answer before the call is refused as `timed_out`.
TIMEOUT_MS = 10 * 60 * 1000

#: The key this module owns on a stored `function_call` item.
GATE_KEY = 'jup_gate'


class AlreadyResolved(Exception):
    """The gated call already has a decision; a second one must not replace it."""


@dataclass(frozen=True)
class Approval:
    """A verified approval, as `jup.tool_policy.decide` takes it."""

    approved_by: str
    wait_ms: int


@dataclass(frozen=True)
class Resolution:
    """What one decision on a gated call came to, for the model and for the audit line.

    `message` is the refusal the model is given when the call will not run; `None` on approval.
    """

    approval: str
    approved_by: str | None
    wait_ms: int
    tool_id: str | None
    message: str | None = None


def is_gated(item: Any) -> bool:
    return isinstance(item, dict) and isinstance(item.get(GATE_KEY), dict)


def arm(item: dict, tool: Any, *, now_ms: int) -> bool:
    """Start the clock on a call whose card is being shown. True only when it was newly armed.

    Only an `external` call is armed. Arming is idempotent: the vendor re-pauses a message after
    each drained call, and a re-pause must not give the call a fresh ten minutes.
    """
    if is_gated(item) or classify(tool) != EXTERNAL:
        return False
    item[GATE_KEY] = {'paused_at': int(now_ms), 'tool_id': (tool or {}).get('tool_id')}
    return True


def resolve(
    item: dict, action: str, *, chat_id: str, message_id: str, user_id: str, now_ms: int, secret: str
) -> Resolution:
    """Apply the asking user's `approve` or `reject` to an armed call, mutating the stored item.

    The caller has already checked that `user_id` is the chat's owner. Past the deadline both
    actions become `timed_out`. Raises `AlreadyResolved` for a call that already has a decision,
    and `ValueError` for any other action.
    """
    if action not in ('approve', 'reject'):
        raise ValueError(f'a gated call is approved or rejected, not {action!r}')
    gate = item[GATE_KEY]
    if 'decision' in gate:
        raise AlreadyResolved(item.get('call_id'))
    wait_ms = max(0, int(now_ms) - int(gate.get('paused_at', now_ms)))
    if wait_ms > TIMEOUT_MS:
        return _refuse(item, 'timed_out', None, wait_ms)
    if action == 'reject':
        return _refuse(item, 'rejected', user_id, wait_ms)

    gate.update(decision='approved', approved_by=user_id, decided_at=int(now_ms))
    gate['sig'] = _signature(item, chat_id=chat_id, message_id=message_id, secret=secret)
    item['status'] = 'queued'
    item['approved'] = True
    return Resolution('approved', user_id, wait_ms, gate.get('tool_id'))


def time_out(item: Any, *, now_ms: int) -> Resolution | None:
    """The server-side timer's decision: refuse an armed, undecided call once its deadline passed.

    `None` when there is nothing to do: not gated, already decided, or not yet due.
    """
    if not is_gated(item) or 'decision' in item[GATE_KEY]:
        return None
    wait_ms = int(now_ms) - int(item[GATE_KEY].get('paused_at', now_ms))
    if wait_ms < TIMEOUT_MS:
        return None
    return _refuse(item, 'timed_out', None, wait_ms)


def verified(item: Any, *, chat_id: str, message_id: str, user_id: str | None, secret: str) -> Approval | None:
    """The approval on a stored call, if it is genuine and belongs to `user_id`; else `None`."""
    if not is_gated(item):
        return None
    gate = item[GATE_KEY]
    if gate.get('decision') != 'approved' or not user_id or gate.get('approved_by') != user_id:
        return None
    signature = gate.get('sig')
    if not isinstance(signature, str):
        return None
    expected = _signature(item, chat_id=chat_id, message_id=message_id, secret=secret)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        wait_ms = max(0, int(gate['decided_at']) - int(gate['paused_at']))
    except (KeyError, TypeError, ValueError):
        return None
    return Approval(approved_by=user_id, wait_ms=wait_ms)


def _refuse(item: dict, approval: str, decided_by: str | None, wait_ms: int) -> Resolution:
    gate = item[GATE_KEY]
    gate.update(decision=approval, approved_by=decided_by)
    item['status'] = 'rejected'
    item.pop('approved', None)
    name = item.get('name', '')
    message = _timed_out(name) if approval == 'timed_out' else _rejected(name)
    return Resolution(approval, decided_by, wait_ms, gate.get('tool_id'), message)


def _signature(item: dict, *, chat_id: str, message_id: str, secret: str) -> str:
    gate = item.get(GATE_KEY) or {}
    signed = [
        chat_id,
        message_id,
        item.get('call_id') or item.get('id'),
        item.get('name'),
        item.get('arguments'),
        gate.get('approved_by'),
        gate.get('paused_at'),
        gate.get('decided_at'),
    ]
    payload = json.dumps(signed, separators=(',', ':'), ensure_ascii=False, default=str).encode('utf-8')
    return hmac.new(str(secret).encode('utf-8'), payload, hashlib.sha256).hexdigest()


# Worded for the model to relay, like the other gate refusals in `jup.tool_policy`.


def _rejected(name: str) -> str:
    return (
        f'Rejected by the user: `{name}` is an External Call (risk class `external`), and the user '
        'rejected it on the approval card. The tool did not run. Acknowledge this plainly; do not '
        'attempt it another way, and do not ask again unless the user asks you to.'
    )


def _timed_out(name: str) -> str:
    return (
        f"Refused by JUP's approval gate: `{name}` is an External Call (risk class `external`), and "
        'nobody approved it within 10 minutes (reason: `timed_out`). The tool did not run. Tell the '
        'user plainly that the step was refused because it was not approved in time; they can ask '
        'again if they still want it.'
    )


__all__ = [
    'GATE_KEY',
    'TIMEOUT_MS',
    'AlreadyResolved',
    'Approval',
    'Resolution',
    'arm',
    'is_gated',
    'resolve',
    'time_out',
    'verified',
]
