"""ADR-0002's fail-closed enforcement, and the three vendor lines that carry it.

Two kinds of test here, deliberately different in what they protect:

- **Behaviour** of `jup.governance` itself, which needs no runtime and so runs in CI's
  `--only-group dev` job.
- **Presence** of the three vendor inserts, following the `test_jup_iap_registration.py`
  precedent and issue #15's rule: *a lost patch must break a test, not production.* The
  failure being guarded is a quarterly rebase (ADR-0007) resolving a conflict in
  `utils/chat.py`, `routers/openai.py` or `routers/ollama.py` by taking upstream's side. Nothing
  else would notice — the app boots, chat works, and the only symptom is that model calls are
  ungoverned again, which looks exactly like a working deployment.
"""

import ast
import json
from pathlib import Path

import pytest

from jup.governance import (
    ADMITTED_STATE_ATTR,
    CONTRACT_SENTINEL,
    CONTRACT_TEXT,
    EXEMPT_TASKS,
    GovernanceRefusal,
    admit,
    assert_governed,
    attach_contract,
    audit,
    audit_path,
    carries_contract,
    refuse_if_ungoverned,
    refuse_passthrough,
    task_of,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent / 'backend'
CHAT_PY = BACKEND_DIR / 'open_webui' / 'utils' / 'chat.py'
OPENAI_PY = BACKEND_DIR / 'open_webui' / 'routers' / 'openai.py'
OLLAMA_PY = BACKEND_DIR / 'open_webui' / 'routers' / 'ollama.py'
RETRIEVAL_PY = BACKEND_DIR / 'open_webui' / 'routers' / 'retrieval.py'

#: Raw provider passthroughs that nothing in the app calls. Each must refuse before it can
#: dispatch, because their payloads carry instructions outside `messages` (2026-09-23).
PASSTHROUGH_ROUTES = [
    (OPENAI_PY, 'responses'),
    (OLLAMA_PY, 'generate_completion'),
    (OLLAMA_PY, 'generate_openai_completion'),
    (OLLAMA_PY, 'generate_openai_chat_completion'),
    (OLLAMA_PY, 'generate_anthropic_messages'),
    (OLLAMA_PY, 'generate_responses'),
]

_LOST_PATCH = (
    'ADR-0002 attaches fail-closed enforcement at exactly three points. Losing one on an '
    'upstream rebase is silent: the app boots, chat works, and model calls simply stop being '
    'governed. Restore the insert rather than moving enforcement elsewhere — the ADR records '
    'why every extension point fails.'
)


class _State:
    """Stands in for `request.state`, which is an arbitrary attribute bag."""


def _turn(*, system: str | None = None, task: str | None = None, model: str = 'gpt-4o') -> dict:
    messages: list[dict] = []
    if system is not None:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': 'Berapa potensi revenue gas 5 mmscfd?'})
    form_data: dict = {'model': model, 'messages': messages}
    if task is not None:
        form_data['metadata'] = {'task': task}
    return form_data


# ── The contract itself ─────────────────────────────────────────────────────────────────


def test_contract_carries_the_revenue_not_margin_rule():
    """D11's tier discipline is the whole point of the contract, so assert it is in there.

    `kb/serve.ts` enforces this by inspecting the answer; here it can only be enforced by
    putting the rule in front of the model. If this text ever drifts out, the guard still
    refuses ungoverned calls but no longer governs anything in particular.
    """
    assert CONTRACT_TEXT.startswith(CONTRACT_SENTINEL)
    assert 'revenue, not margin' in CONTRACT_TEXT
    assert 'NOT margin' in CONTRACT_TEXT and 'NOT profit' in CONTRACT_TEXT
    assert '5 mmscfd' in CONTRACT_TEXT and 'G1' in CONTRACT_TEXT


def test_the_sentinel_alone_does_not_satisfy_the_check():
    """A direct caller must paste the real rules, not just the marker.

    If the sentinel were sufficient, the guard would be a password check, and the password is
    printed in this repository.
    """
    assert not carries_contract(_turn(system=f'{CONTRACT_SENTINEL} trust me, I am governed'))
    assert carries_contract(_turn(system=CONTRACT_TEXT))


def test_attach_is_idempotent_and_preserves_an_existing_system_prompt():
    form_data = _turn(system='You are a helpful assistant.')
    attach_contract(form_data)
    once = form_data['messages'][0]['content']
    assert 'You are a helpful assistant.' in once
    assert CONTRACT_TEXT in once

    attach_contract(form_data)
    assert form_data['messages'][0]['content'] == once, 'the contract was attached twice'


def test_attach_inserts_a_system_message_when_there_is_none():
    form_data = _turn()
    assert form_data['messages'][0]['role'] == 'user'
    attach_contract(form_data)
    assert form_data['messages'][0] == {'role': 'system', 'content': CONTRACT_TEXT}
    assert form_data['messages'][1]['role'] == 'user'


def test_attach_handles_block_style_content():
    """Vendor stages hand system content over as typed blocks as well as plain strings."""
    form_data = {
        'model': 'gpt-4o',
        'messages': [
            {'role': 'system', 'content': [{'type': 'text', 'text': 'Be brief.'}]},
            {'role': 'user', 'content': 'hi'},
        ],
    }
    attach_contract(form_data)
    assert carries_contract(form_data)
    assert attach_contract(form_data) is form_data
    assert len(form_data['messages'][0]['content']) == 2, 'block content was appended to twice'


# ── The funnel: utils/chat.py ───────────────────────────────────────────────────────────


def test_a_user_turn_is_governed_and_stamped():
    state = _State()
    form_data = _turn()
    assert admit(form_data, state=state, user_id='u1') is None
    assert carries_contract(form_data)
    assert getattr(state, ADMITTED_STATE_ATTR) is True


def test_the_funnel_refuses_a_payload_it_cannot_govern():
    """The funnel must be able to refuse, not merely observe — issue #16's first criterion.

    It is load-bearing rather than ceremonial: `generate_direct_chat_completion` (direct
    connection) and `generate_function_chat_completion` (pipe model) are dispatched from the
    funnel and never reach a router guard, so for those two branches this is the only control in
    the path. A payload whose `messages` is not a list has nowhere to attach the contract, and a
    turn that cannot be governed is refused rather than forwarded.
    """
    state = _State()
    form_data = {'model': 'gpt-4o', 'messages': 'not a list'}
    refusal = admit(form_data, state=state, user_id='u1')
    assert isinstance(refusal, GovernanceRefusal)
    assert refusal.status_code == 403
    assert 'could not be governed' in refusal.detail
    assert not hasattr(state, ADMITTED_STATE_ATTR), 'an ungovernable turn was stamped as admitted'
    assert form_data['messages'] == 'not a list', 'the malformed payload was silently rewritten'


def test_an_unstamped_turn_is_still_refused_downstream():
    """The funnel refusing without stamping is what makes the router guard the backstop."""
    state = _State()
    form_data = {'model': 'gpt-4o', 'messages': 'not a list'}
    assert isinstance(admit(form_data, state=state, user_id='u1'), GovernanceRefusal)
    assert isinstance(refuse_if_ungoverned(form_data, state=state, user_id='u1'), GovernanceRefusal)


def test_an_exempt_task_is_stamped_but_not_governed():
    """Title generation never answers anyone about JUP material and must not be refused."""
    state = _State()
    form_data = _turn(task='title_generation')
    assert admit(form_data, state=state, user_id='u1') is None
    assert not carries_contract(form_data), 'the contract was attached to a title generation'
    assert getattr(state, ADMITTED_STATE_ATTR) is True
    assert refuse_if_ungoverned(form_data, state=state, user_id='u1', route='openai') is None


def test_the_tool_loop_second_turn_is_governed_after_the_system_message_is_stripped():
    """The turn-two case issue #16 asks for by name.

    `middleware.py:5873` calls `replace_system_message_content('', ...)` before re-entering
    `generate_chat_completion` at `:5994`, so turn two can arrive with the system content
    emptied. The loop sets no `metadata.task`, so it is a governed turn, and the funnel has to
    put the contract back rather than wave it through.
    """
    state = _State()
    form_data = _turn(system=CONTRACT_TEXT)
    assert admit(form_data, state=state, user_id='u1') is None
    assert carries_contract(form_data)

    # What the tool loop does to the payload between turns.
    form_data['messages'][0]['content'] = ''
    assert not carries_contract(form_data)

    assert admit(form_data, state=state, user_id='u1') is None
    assert carries_contract(form_data), 'turn two reached the provider ungoverned'


def test_the_tool_loop_turn_carries_no_task_and_so_is_never_exempt():
    """Guards the distinction between `:1318`'s function_calling task and the loop's turns."""
    assert task_of(_turn()) is None
    assert 'function_calling' in EXEMPT_TASKS
    assert task_of(_turn(task='function_calling')) == 'function_calling'


# ── The two direct routes ───────────────────────────────────────────────────────────────


def test_a_direct_unstamped_turn_is_refused():
    refusal = refuse_if_ungoverned(_turn(), state=_State(), user_id='u1', route='openai')
    assert isinstance(refusal, GovernanceRefusal)
    assert refusal.status_code == 403
    assert 'cannot be bypassed' in refusal.detail


def test_a_direct_turn_that_really_carries_the_contract_proceeds():
    assert refuse_if_ungoverned(_turn(system=CONTRACT_TEXT), state=_State(), user_id='u1') is None


def test_a_forged_task_does_not_exempt_a_direct_turn():
    """The metadata is attacker-controlled on a directly-mounted route.

    This is the hole that closes by honouring the exemption only for a turn `admit()` stamped:
    a caller can claim any task they like, and on the direct route the claim buys nothing.
    """
    for task in sorted(EXEMPT_TASKS):
        refusal = refuse_if_ungoverned(_turn(task=task), state=_State(), user_id='attacker', route='openai')
        assert isinstance(refusal, GovernanceRefusal), f'{task} exempted a direct turn'


def test_bypass_filter_cannot_turn_the_guard_off():
    """`bypass_filter` is an access-control flag and is ignored by design.

    `generate_chat_completion` sets it to `True` unconditionally under
    `BYPASS_MODEL_ACCESS_CONTROL`, so a guard that honoured it would be off in exactly the
    deployments that most need it. The guard reads one attribute only, and this proves no other
    attribute on the state bag can stand in for it.
    """
    state = _State()
    state.bypass_filter = True
    state.bypass_system_prompt = True
    assert isinstance(refuse_if_ungoverned(_turn(), state=state, user_id='u1'), GovernanceRefusal)

    setattr(state, ADMITTED_STATE_ATTR, True)
    assert refuse_if_ungoverned(_turn(), state=state, user_id='u1') is None


def test_assert_governed_raises_for_callers_without_a_framework():
    with pytest.raises(GovernanceRefusal):
        assert_governed(_turn(), state=_State())


# ── The audit trail ─────────────────────────────────────────────────────────────────────


def test_audit_records_admitted_exempt_and_refused(tmp_path, monkeypatch):
    trail = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(trail))

    admit(_turn(), state=_State(), user_id='u1')
    admit(_turn(task='title_generation'), state=_State(), user_id='u1')
    refuse_if_ungoverned(_turn(), state=_State(), user_id='u2', route='openai')

    events = [json.loads(line) for line in trail.read_text().splitlines()]
    assert [e['event'] for e in events] == ['admitted', 'exempt', 'refused']
    assert all('ts' in e for e in events)
    assert events[-1]['route'] == 'openai' and events[-1]['user'] == 'u2'


def test_funnel_audit_lines_carry_the_chat(tmp_path, monkeypatch):
    """A turn line with no chat id cannot be joined to the chat it governed."""
    trail = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(trail))

    turn = _turn()
    turn['metadata'] = {'chat_id': 'chat-1'}
    admit(turn, state=_State(), user_id='u1')
    child = _State()
    child.jup_parent_chat_id = 'chat-1'
    sub = _turn()
    sub['metadata'] = {'chat_id': 'chat-2'}
    admit(sub, state=child, user_id='u1')
    admit(_turn(task='title_generation'), state=_State(), user_id='u1')
    bad = {'model': 'gpt-4o', 'messages': 'not a list', 'metadata': {'chat_id': 'chat-3'}}
    admit(bad, state=_State(), user_id='u1')

    events = [json.loads(line) for line in trail.read_text().splitlines()]
    assert [e['event'] for e in events] == ['admitted', 'admitted', 'exempt', 'refused']
    assert events[0]['chat'] == 'chat-1' and 'parent_chat' not in events[0]
    assert events[1]['chat'] == 'chat-2' and events[1]['parent_chat'] == 'chat-1'
    assert 'chat' not in events[2]
    assert events[3]['chat'] == 'chat-3'


def test_audit_never_raises_when_the_trail_cannot_be_written(tmp_path, monkeypatch):
    """A control that can 500 a turn by failing to log it is a liability."""
    blocker = tmp_path / 'not-a-dir'
    blocker.write_text('')
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(blocker / 'audit.jsonl'))
    audit('admitted', user='u1')  # must not raise


def test_audit_path_prefers_its_own_env_then_data_dir():
    assert audit_path({'JUP_GOVERNANCE_AUDIT': '/tmp/a.jsonl'}) == Path('/tmp/a.jsonl')
    assert audit_path({'DATA_DIR': '/data'}) == Path('/data/jup-governance-audit.jsonl')
    assert audit_path({}) is None


# ── The three vendor inserts ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('source', 'call'),
    [
        (CHAT_PY, 'admit'),
        (OPENAI_PY, 'refuse_if_ungoverned'),
        (OLLAMA_PY, 'refuse_if_ungoverned'),
    ],
    ids=['utils/chat.py', 'routers/openai.py', 'routers/ollama.py'],
)
def test_the_vendor_insert_is_present(source: Path, call: str):
    text = source.read_text()
    assert 'from jup import governance as jup_governance' in text, f'{source.name}: import lost. {_LOST_PATCH}'
    assert f'jup_governance.{call}(' in text, f'{source.name}: guard call lost. {_LOST_PATCH}'


@pytest.mark.parametrize(
    'source', [CHAT_PY, OPENAI_PY, OLLAMA_PY], ids=['utils/chat.py', 'routers/openai.py', 'routers/ollama.py']
)
def test_nothing_dispatches_before_the_guard(source: Path):
    """Enforcement is inlet-only, so nothing may reach a provider ahead of the guard.

    A guard that drifted below an early `return`, an `await` on a provider call or a branch
    that raises would still satisfy a grep, which is why this parses the function instead. The
    check is deliberately about *dispatch* rather than position: in `utils/chat.py` the guard
    sits after the `request.state` and metadata assignments on purpose, because the task
    exemption cannot be read before `form_data['metadata']` is merged. Those assignments are
    pure bookkeeping. An `await`, a `return` or a `raise` is not.
    """
    tree = ast.parse(source.read_text())
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'generate_chat_completion'
    ]
    assert functions, f'{source.name}: generate_chat_completion is gone entirely. {_LOST_PATCH}'

    for function in functions:
        statements = [
            node for node in function.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        ]
        guarded = [index for index, node in enumerate(statements) if 'jup_governance.' in ast.unparse(node)]
        assert guarded, f'{source.name}: the guard is not in generate_chat_completion. {_LOST_PATCH}'

        for node in statements[: guarded[0]]:
            escapes = [
                type(inner).__name__
                for inner in ast.walk(node)
                if isinstance(inner, (ast.Await, ast.Return, ast.Raise, ast.Yield))
            ]
            assert not escapes, (
                f'{source.name}: `{ast.unparse(node).splitlines()[0]}` runs before the guard and '
                f'can {escapes[0]} — a turn could reach a provider ungoverned. {_LOST_PATCH}'
            )


def test_the_guard_does_not_honour_bypass_filter_in_vendor_code():
    """Issue #16's trap, checked where it would actually be introduced.

    The tempting "fix" for a noisy guard is to pass `bypass_filter` into it. A guard that
    honours `bypass_filter` is not a guard, so no vendor insert may mention it.
    """
    for source in (CHAT_PY, OPENAI_PY, OLLAMA_PY):
        for line in source.read_text().splitlines():
            if 'jup_governance.' in line:
                assert 'bypass' not in line, f'{source.name}: the guard was handed a bypass flag — {line.strip()}'


# ── Passthroughs and the MoA exemption (2026-09-23) ─────────────────────────────────────


def test_moa_is_governed_not_exempt():
    """The MoA task route takes the caller's own text, so an exemption there was a bypass."""
    assert 'moa_response_generation' not in EXEMPT_TASKS
    state = _State()
    form_data = _turn(task='moa_response_generation')
    assert admit(form_data, state=state, user_id='u1') is None
    assert carries_contract(form_data), 'a MoA turn went out without the contract'


def test_a_passthrough_is_refused_and_audited(tmp_path, monkeypatch):
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(tmp_path / 'audit.jsonl'))
    refusal = refuse_passthrough(user_id='u3', route='openai', model='m')
    assert isinstance(refusal, GovernanceRefusal) and refusal.status_code == 403
    event = json.loads((tmp_path / 'audit.jsonl').read_text().splitlines()[-1])
    assert event['event'] == 'refused' and event['user'] == 'u3' and event['route'] == 'openai'


def _function(source: Path, name: str) -> ast.AsyncFunctionDef:
    found = [
        n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n, ast.AsyncFunctionDef) and n.name == name
    ]
    assert len(found) == 1, f'{source.name}: expected one `{name}`, found {len(found)}. {_LOST_PATCH}'
    return found[0]


def _body_without_docstring(function: ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return body


@pytest.mark.parametrize(('source', 'name'), PASSTHROUGH_ROUTES, ids=[f'{s.name}:{n}' for s, n in PASSTHROUGH_ROUTES])
def test_a_passthrough_route_refuses_before_anything_else(source: Path, name: str):
    body = _body_without_docstring(_function(source, name))
    assert 'jup_governance.refuse_passthrough(' in ast.unparse(body[0]), (
        f'{source.name}:{name}: the passthrough refusal is not the first statement. {_LOST_PATCH}'
    )
    assert isinstance(body[1], ast.Raise), f'{source.name}:{name}: the refusal is computed but not raised.'


@pytest.mark.parametrize('name', ['process_url', 'process_web'])
def test_url_fetching_routes_check_web_upload_first(name: str):
    """Fetching an arbitrary URL from the backend is egress; the permission check comes first."""
    body = _body_without_docstring(_function(RETRIEVAL_PY, name))
    assert '_jup_require_web_upload(user)' in ast.unparse(body[0]), f'retrieval.py:{name}: web_upload gate lost.'
