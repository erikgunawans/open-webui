"""Fail-closed governance: no model call leaves this deployment ungoverned.

ADR-0002 settled *where* enforcement attaches and why every extension point fails. This
module is *what* it enforces, and the policy is deliberately narrow: **a governed turn must
carry the JUP operating contract in its system message, or it is refused.** Erik settled that
shape on 2026-09-21 over two alternatives, and the reasoning is worth keeping because it is
not obvious.

`~/jup/kb/serve.ts` implements the sibling guard, and D13 records it being ported verbatim
into the Cloudflare Worker. Porting it a third time into this tree is impossible as written:
`serve.ts` inspects the model's *answer* (`violatesTierDiscipline(r.text)`) and refuses to
ship it. It can do that because it is non-streaming — it holds the whole answer before
responding. ADR-0002's attachment points are all inlets; they see the request and never the
answer, and the ADR's own Consequences section says there is no way to block a
websocket-streamed response once the first token has shipped. So this guard does the
inlet-shaped thing instead: rather than catching a bad answer, it refuses to let an
ungoverned request reach a provider at all. The contract it attaches carries D11's
revenue-not-margin rule into the model's context, which is where that rule can still change
an answer.

**Why the contract is attached here and not once at the edge.** `utils/chat.py`'s
`generate_chat_completion` is reached on *every* turn, including the tool loop's second and
later turns (`utils/middleware.py:5994`, `:6214`). That matters because the loop can strip the
system message outright before re-entering — `middleware.py:5873` calls
`replace_system_message_content('', ...)` — so a contract attached once at turn one is gone by
turn two. Attaching on every pass through the funnel is self-healing: whatever the loop
stripped, the next turn restores.

**Why the admission stamp lives on `request.state` and not in `form_data`.** The two provider
routes are mounted directly and reachable with nothing but a verified user's API key, so
anything inside `form_data` is attacker-controlled there. The vendor learned this about
`bypass_filter` and fixed it the same way (`routers/openai.py:1478-1481`): the flag travels on
`request.state`, which no HTTP client can set. The task exemption below is only honoured for a
stamped, internally-originated turn for exactly this reason — otherwise a direct caller would
exempt itself by sending `metadata: {'task': 'title_generation'}`.

**`bypass_filter` is ignored by design.** It is a model-access-control flag, and
`generate_chat_completion` sets it to `True` unconditionally when `BYPASS_MODEL_ACCESS_CONTROL`
is on. A guard that honoured it would be off by default in exactly the deployments that most
need it. Governance is not an access-control decision and does not share its switch.

Every turn is appended to the audit trail — admitted, exempt and refused alike. "Every turn
audited, success and refusal" is the whole governance claim, and a refusal that leaves no
trace is indistinguishable from a call that never happened.
"""

import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

AUDIT_ENV = 'JUP_GOVERNANCE_AUDIT'

#: Set on `request.state` once a turn has been through `admit()`. Unforgeable from HTTP.
ADMITTED_STATE_ATTR = 'jup_governance_admitted'

#: Set on a subagent's synthetic `request.state` by `utils/subagents.py`: the chat that delegated.
#: `request.state` rather than `form_data` for the same reason as the admission stamp — a direct
#: caller can put anything in `form_data`, and a forged parent would mislabel the trail.
PARENT_CHAT_STATE_ATTR = 'jup_parent_chat_id'

#: The marker the contract opens with, so a human reading a provider-side log can see the
#: turn was governed. Presence of this alone is *not* sufficient — see `carries_contract`.
CONTRACT_SENTINEL = '[JUP-GOVERNED]'

#: The operating contract. Carried into the model's context on every governed turn.
#:
#: Rules 2 and 3 are D11's three-tier certainty discipline, which is the single
#: highest-consequence fabrication risk in this material: the gas figures are potential
#: top-line revenue, and B-to-G tariffs are government-set, so presenting them as profit or
#: margin misstates the business to whoever is reading. Rule 4 keeps G1 honest — the 5 mmscfd
#: allocation is not secured, and an answer that implies otherwise is the same failure in a
#: different place.
CONTRACT_TEXT = '\n'.join(
    [
        CONTRACT_SENTINEL + ' JUP operating contract — these rules bind this turn.',
        '1. Never invent a number, name, date, or claim. If you do not have it, say so plainly.',
        '2. Never blend certainty tiers. Gas rupiah figures are potential REVENUE (top-line), NOT '
        'margin, NOT profit, NOT NPV — B-to-G tariffs are government-set. Whenever you cite a gas '
        'rupiah figure you MUST state that it is revenue, not margin.',
        '3. Whenever the gas pillar comes up, state that the 5 mmscfd allocation is NOT yet secured '
        '(Gate G1). Whenever WTP comes up, state that the fold-out is pending, not final.',
        '4. Never speculate about whether a partner (SKK Migas, PGN, PLN, Pelindo) will agree.',
        '5. Reply in the user language. Keep technical and business terms in English even in '
        'Indonesian text (capex, OPEX, NPV, IRR, offtake, stage-gate, fold-out, hedge, B-to-G).',
        '6. A refusal is a feature, not a failure. Saying "that is not something I have" is the '
        'governance guarantee working.',
    ]
)

#: Named internal generations that do not carry the contract, and do not need to.
#:
#: These never answer a person about JUP material — they title a chat, pick an emoji, expand a
#: search query. Governing them would refuse them, because nothing attaches a contract to a
#: title-generation call, and the app would fail to boot into a usable state rather than fail
#: closed in any useful sense.
#:
#: `function_calling` belongs here, and the distinction is subtle enough to be worth stating:
#: it is `middleware.py:1318`'s *native tool-selection* call, which sets
#: `metadata={'task': 'function_calling'}`. It is NOT the tool loop's continuation turns at
#: `:5994` and `:6214` — those set no task at all and so remain governed, which is what issue
#: #16 requires when it asks for a refusal proven on turn two.
EXEMPT_TASKS = frozenset(
    {
        'title_generation',
        'follow_up_generation',
        'tags_generation',
        'emoji_generation',
        'query_generation',
        'image_prompt_generation',
        'autocomplete_generation',
        'function_calling',
    }
)
# `moa_response_generation` was on this list until 2026-09-23 and was removed on purpose.
# `routers/tasks.py`'s MoA route takes the caller's `prompt` and `responses` verbatim and sets
# the task name itself, so the funnel stamp could not tell it apart from a genuine internal
# generation: any verified user had an exempt, contract-free completion on their own text. JUP
# never uses MoA, so it is now governed like any other turn and carries the contract.


class GovernanceRefusal(Exception):
    """A turn refused before it reached a provider.

    Carries an HTTP shape because both refusal sites are request handlers, and a governance
    refusal is a deliberate answer to the caller rather than a server fault. 403 rather than
    400: the request is well-formed and the caller is authenticated; what is missing is
    authority to make an ungoverned model call.
    """

    status_code = 403

    def __init__(self, reason: str, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail or (
            'Refused by JUP governance: this request would have reached a model provider without '
            'the JUP operating contract attached. The contract is not optional and cannot be '
            'bypassed. Send the request through the chat interface, or attach the contract to a '
            'system message.'
        )
        super().__init__(f'{reason}: {self.detail}')


def audit_path(env: dict[str, str] | None = None) -> Path | None:
    """Where the trail is written, or `None` when no location is configured.

    `JUP_GOVERNANCE_AUDIT` wins. Otherwise the trail sits beside the rest of the deployment's
    state in `DATA_DIR`, which is read from the environment rather than imported from
    `open_webui.env` so that this package keeps its promise not to reach into the vendor tree.
    With neither set there is no file trail and every entry still reaches the logger, which is
    the right behaviour for a test process and for a first boot before any volume is mounted.
    """
    source = os.environ if env is None else env
    configured = (source.get(AUDIT_ENV) or '').strip()
    if configured:
        return Path(configured)
    data_dir = (source.get('DATA_DIR') or '').strip()
    if data_dir:
        return Path(data_dir) / 'jup-governance-audit.jsonl'
    return None


def audit(event: str, *, path: Path | None = None, **fields: Any) -> None:
    """Append one JSONL entry. One turn, one entry.

    Never raises. An audit trail that can fail a turn is a liability rather than a control —
    the turn has already been decided by the time we get here, and turning a full disk into a
    500 helps nobody. The failure is logged loudly instead, because a silently missing trail
    is the one outcome worse than a noisy one.
    """
    entry = {'ts': dt.datetime.now(dt.UTC).isoformat(), 'event': event, **fields}
    log.info('jup.governance %s', entry)
    target = audit_path() if path is None else path
    if target is None:
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, default=str) + '\n')
    except Exception:
        log.exception('jup.governance could not append to the audit trail at %s', target)


def task_of(form_data: dict) -> str | None:
    """The named internal task behind this call, if it declares one."""
    metadata = form_data.get('metadata')
    if not isinstance(metadata, dict):
        return None
    task = metadata.get('task')
    return task if isinstance(task, str) and task else None


def _chat_fields(form_data: dict, state: Any) -> dict:
    """The chat a funnel turn belongs to, as audit fields: `chat`, and `parent_chat` for a subagent.

    Read at the funnel only, where `utils/chat.py` has already merged `request.state.metadata`
    over the payload's own, so the id is the one the app assigned. Absent keys are left out
    rather than written as null: a task call with no chat is not a turn that lost its chat.
    """
    metadata = form_data.get('metadata')
    chat = metadata.get('chat_id') if isinstance(metadata, dict) else None
    parent = getattr(state, PARENT_CHAT_STATE_ATTR, None) if state is not None else None
    fields = {}
    if isinstance(chat, str) and chat:
        fields['chat'] = chat
    if parent:
        fields['parent_chat'] = parent
    return fields


def _system_texts(form_data: dict) -> list[str]:
    """Every scrap of system-role text in the payload, flattened.

    Content is either a string or a list of typed blocks depending on which vendor stage last
    touched it, and a contract hidden in the block form still governs the model, so both are
    read.
    """
    texts: list[str] = []
    for message in form_data.get('messages') or []:
        if not isinstance(message, dict) or message.get('role') != 'system':
            continue
        content = message.get('content')
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get('text'), str):
                    texts.append(block['text'])
    return texts


def carries_contract(form_data: dict) -> bool:
    """Whether the payload actually carries the contract.

    The whole `CONTRACT_TEXT` must be present, not merely `CONTRACT_SENTINEL`. That is the
    difference between a check a direct caller can satisfy by pasting a marker and one they can
    only satisfy by genuinely putting the governing rules in front of the model. If a caller
    does paste the real contract, the turn is governed and passing it is correct.
    """
    return any(CONTRACT_TEXT in text for text in _system_texts(form_data))


def attach_contract(form_data: dict) -> dict:
    """Put the contract in the payload's system message, idempotently.

    Appended to the existing system content rather than replacing it, because a model's own
    configured system prompt is legitimate and the contract constrains it rather than
    competing with it. The vendor's own `add_or_update_system_message` will later prepend the
    model params' `system` ahead of this without disturbing it, and
    `merge_system_messages` collapses multiple system messages by joining their content — so
    the contract survives both.

    Returns the payload whether or not it worked; the caller checks `carries_contract`. A
    payload carrying a `messages` value that is not a list is left **untouched** rather than
    repaired: replacing it would discard whatever the caller sent, and a malformed payload we
    cannot govern is a turn to refuse rather than to quietly rewrite.
    """
    if carries_contract(form_data):
        return form_data
    messages = form_data.get('messages')
    if messages is None:
        messages = []
        form_data['messages'] = messages
    elif not isinstance(messages, list):
        return form_data
    if messages and isinstance(messages[0], dict) and messages[0].get('role') == 'system':
        content = messages[0].get('content')
        if isinstance(content, str):
            messages[0]['content'] = f'{content}\n{CONTRACT_TEXT}' if content else CONTRACT_TEXT
            return form_data
        if isinstance(content, list):
            content.append({'type': 'text', 'text': CONTRACT_TEXT})
            return form_data
    messages.insert(0, {'role': 'system', 'content': CONTRACT_TEXT})
    return form_data


def admit(
    form_data: dict, *, state: Any = None, user_id: str | None = None, model: str | None = None
) -> GovernanceRefusal | None:
    """Govern one turn at the funnel. Returns a refusal, or `None` when the turn may proceed.

    Called from `utils/chat.py`'s `generate_chat_completion`, which every in-process model call
    reaches. An exempt named task passes through untouched; everything else has the contract
    attached, so in ordinary operation this does not refuse — it *makes* the turn compliant.

    **It can still refuse, and that is load-bearing.** Two branches of that function never reach
    a router guard: `generate_direct_chat_completion` for a direct connection, and
    `generate_function_chat_completion` for a pipe model. For those, this is the only control in
    the path. So the contract is attached and then *verified*, and a payload we could not govern
    is refused rather than forwarded. Fail-closed means the failure to govern is itself a
    refusal, not a shrug.

    `state` is `request.state`, injected so this is testable without a FastAPI request.
    """
    task = task_of(form_data)
    chat = _chat_fields(form_data, state)
    if task in EXEMPT_TASKS:
        audit('exempt', task=task, user=user_id, model=model or form_data.get('model'), **chat)
        if state is not None:
            setattr(state, ADMITTED_STATE_ATTR, True)
        return None

    already = carries_contract(form_data)
    attach_contract(form_data)
    if not carries_contract(form_data):
        reason = 'ungovernable payload: the operating contract could not be attached'
        audit('refused', task=task, user=user_id, model=model or form_data.get('model'), reason=reason, **chat)
        return GovernanceRefusal(
            reason,
            'Refused by JUP governance: this request could not be governed, because its '
            '`messages` payload is not a list and the operating contract has nowhere to attach. '
            'A turn that cannot be governed is refused rather than forwarded.',
        )
    audit(
        'admitted',
        task=task,
        user=user_id,
        model=model or form_data.get('model'),
        contract='carried' if already else 'attached',
        **chat,
    )
    if state is not None:
        setattr(state, ADMITTED_STATE_ATTR, True)
    return None


def refuse_if_ungoverned(
    form_data: dict, *, state: Any = None, user_id: str | None = None, route: str = ''
) -> GovernanceRefusal | None:
    """The refusal a turn has earned, or `None` when it may proceed. Audits either way.

    This is the three-line insert at the head of `routers/openai.py` and `routers/ollama.py`.
    A turn stamped by `admit()` came through the funnel and is already governed. An unstamped
    turn arrived directly at the mounted route, so no exemption is available to it — the task
    name in its `form_data` is attacker-controlled — and the only way through is to genuinely
    carry the contract.

    It **returns** rather than raises so the caller can raise its own framework's exception.
    This package is not allowed to import FastAPI (see `jup/__init__.py`), and a governance
    refusal that surfaced as a 500 would read as a server fault rather than the deliberate
    answer it is.
    """
    if state is not None and getattr(state, ADMITTED_STATE_ATTR, False):
        return None
    if carries_contract(form_data):
        audit('admitted', route=route, user=user_id, model=form_data.get('model'), contract='carried', direct=True)
        return None
    reason = 'ungoverned: direct provider route without the JUP operating contract'
    audit(
        'refused',
        route=route,
        user=user_id,
        model=form_data.get('model'),
        reason=reason,
        claimed_task=task_of(form_data),
    )
    return GovernanceRefusal(reason)


def refuse_passthrough(*, user_id: str | None = None, route: str = '', model: Any = None) -> GovernanceRefusal:
    """The refusal for a raw provider passthrough, which is never governable. Audits it.

    `refuse_if_ungoverned` reads the contract out of `messages`, and that is only sound for a
    chat-completions payload. The Responses, Ollama generate/completions and Anthropic Messages
    shapes carry their instructions elsewhere (`instructions`, `system`, `prompt`), so a caller
    could satisfy a `messages` check with a field the provider then ignores. Nothing inside the
    app calls these routes — the pipeline reaches `/responses` from inside
    `generate_chat_completion`, which is already governed — so they are refused outright.
    """
    reason = 'ungoverned: raw provider passthrough route'
    audit('refused', route=route, user=user_id, model=model, reason=reason)
    return GovernanceRefusal(reason)


def audit_tool_call(
    *,
    name: str,
    arguments: Any,
    tool: dict | None,
    result: Any,
    error: bool,
    user_id: str | None,
    chat_id: str | None,
    mode: str,
    state: Any = None,
) -> None:
    """Append one `tool_call` entry for one tool invocation. Never raises.

    `admit()` writes a line per *model turn*; a turn can run several tools, and the tool is where
    the agent touches data, so a trail with only turn lines cannot say which tool read what for
    whom. This is that line (agent-depth plan, E1).

    **Argument size, never argument content.** Arguments carry whatever the user asked about, and
    the trail is read far more widely than the chat it came from; the byte count is enough to
    spot a runaway or an exfiltration-shaped call without copying the payload into a second place.

    `outcome` is `unparsed` when the model's JSON could not be read (the native loop resolves no
    tool and a `None` result for that), `not_found` when it named a tool it was not offered, and
    otherwise `error`
    or `ok` per the vendor's own error test, which the caller passes in as `error` so this package
    does not re-derive — and drift from — the vendor's definition of a failed tool.
    """
    try:
        if isinstance(arguments, str):
            size = len(arguments.encode('utf-8'))
        elif arguments is None:
            size = 0
        else:
            size = len(json.dumps(arguments, default=str, ensure_ascii=False).encode('utf-8'))
        if not tool:
            outcome = 'unparsed' if result is None else 'not_found'
        else:
            outcome = 'error' if error else 'ok'
        parent = getattr(state, PARENT_CHAT_STATE_ATTR, None) if state is not None else None
        audit(
            'tool_call',
            mode=mode,
            user=user_id,
            chat=chat_id,
            tool=name,
            tool_id=(tool or {}).get('tool_id') or None,
            outcome=outcome,
            arg_bytes=size,
            **({'parent_chat': parent} if parent else {}),
        )
    except Exception:
        log.exception('jup.governance could not audit the tool call %r', name)


def assert_governed(form_data: dict, *, state: Any = None, user_id: str | None = None, route: str = '') -> None:
    """The raising form of `refuse_if_ungoverned`, for callers with no framework of their own."""
    refusal = refuse_if_ungoverned(form_data, state=state, user_id=user_id, route=route)
    if refusal is not None:
        raise refusal


__all__ = [
    'ADMITTED_STATE_ATTR',
    'AUDIT_ENV',
    'CONTRACT_SENTINEL',
    'CONTRACT_TEXT',
    'EXEMPT_TASKS',
    'GovernanceRefusal',
    'PARENT_CHAT_STATE_ATTR',
    'admit',
    'assert_governed',
    'attach_contract',
    'audit',
    'audit_path',
    'audit_tool_call',
    'carries_contract',
    'refuse_passthrough',
    'task_of',
]
