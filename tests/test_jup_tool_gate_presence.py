"""A5+E5 #18: the vendor inserts that make every tool dispatch ask `jup.tool_policy` first.

Losing one of these fails nothing visible: the tool simply runs, ungated, and the answer still
arrives. So a lost patch must break this test instead (ADR-0007, `deploy/gcp/VENDOR-PATCHES.md`).
Each test checks that the gate is consulted, and that a refusal returns *before* the code that
runs the tool, at each of the three places `utils/middleware.py` runs one.
"""

import re
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui' / 'utils'
MIDDLEWARE_PY = VENDOR / 'middleware.py'
TOOLS_PY = VENDOR / 'tools.py'


def _middleware() -> str:
    return MIDDLEWARE_PY.read_text(encoding='utf-8')


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def test_middleware_imports_the_policy():
    assert 'from jup import tool_policy as jup_tool_policy' in _middleware()


def test_there_is_one_gate_per_tool_execution_site():
    assert len(re.findall(r'jup_tool_policy\.decide\(', _middleware())) == 3


def test_the_native_loop_refuses_before_it_runs_the_tool():
    body = _between(_middleware(), 'async def execute_tool_call(tool_call):', 'delegate_calls = [')
    gate = body.index('jup_tool_policy.decide(\n')
    refusal = body.index('if not jup_gate.runs:', gate)
    assert refusal < body.index('return params, jup_gate.message', refusal) < body.index('await function(**params)')
    assert refusal < body.index("'type': 'execute:tool'")


def test_the_native_loop_hands_the_gates_answer_to_the_audit_line():
    source = _middleware()
    assert 'jup_gate_approvals[id(tool_call)] = jup_gate.approval' in source
    assert "approval=jup_gate_approvals.get(id(tool_call), 'not_required')" in source


def test_a_users_own_approval_does_not_get_past_the_gate():
    """`ask` mode approves through this executor; the gate still decides after the user has."""
    body = _between(_middleware(), 'async def execute_tool_call_for_output(', 'async def drain_approved_tool_calls(')
    gate = body.index('jup_gate = jup_tool_policy.decide(\n')
    early_return = body.index("'content': jup_gate.message", gate)
    assert early_return < body.index('await function(**params)')
    assert early_return < body.index("'type': 'execute:tool'")
    assert "'jup_approval': jup_gate.approval" in body[body.index('tool_result_content(result)') - 200 :]


def test_the_approval_drain_audits_the_gates_answer():
    body = _between(_middleware(), 'async def drain_approved_tool_calls(', 'async def pause_for_tool_approval(')
    assert "approval=result.get('jup_approval', 'not_required')" in body


def test_the_prompt_based_handler_refuses_before_it_runs_the_tool():
    body = _between(_middleware(), 'async def tool_call_handler(tool_call):', 'jup_governance.audit_tool_call(')
    gate = body.index('jup_gate = jup_tool_policy.decide(\n')
    refusal = body.index('if not jup_gate.runs:', gate)
    assert refusal < body.index('tool_result = jup_gate.message', refusal) < body.index('elif tool.get(')
    assert refusal < body.index('await tool_function(**tool_function_params)')


def test_the_stored_tools_declared_class_reaches_the_tool_entry():
    body = _between(TOOLS_PY.read_text(encoding='utf-8'), 'async def get_tools(', 'async def get_builtin_tools(')
    assert "'risk_class': ((tool.meta.manifest if tool.meta else None) or {}).get('risk_class')" in body


# --- #20: unattended paths fail closed ------------------------------------------------------------

PATH_ARG = 'path=jup_tool_policy.path_of(metadata, request.state)'


def test_every_gate_is_told_the_path_the_call_arrived_on():
    """The unattended override: without the path, an automation's forced `full` mode would pass as
    an attended chat. `decide` takes `path` as a required keyword, so a site that drops it raises;
    this test says which site and why."""
    source = _middleware()
    assert source.count(PATH_ARG) == 3
    for start, end in [
        ('async def tool_call_handler(tool_call):', 'jup_governance.audit_tool_call('),
        ('async def execute_tool_call_for_output(', 'async def drain_approved_tool_calls('),
        ('async def execute_tool_call(tool_call):', 'delegate_calls = ['),
    ]:
        body = _between(source, start, end)
        gate = body.index('jup_tool_policy.decide(')
        assert PATH_ARG in body[gate : body.index('if not jup_gate.runs:', gate)], start


def test_a_subagent_is_filtered_before_its_tools_are_offered():
    body = _between(_middleware(), 'async def process_chat_payload(', 'file_context_enabled =')
    filtered = body.index(f'tools_dict = jup_tool_policy.offered_tools(tools_dict, {PATH_ARG[5:]})')
    assert body.index('builtin_tools = await get_builtin_tools(') < filtered
    assert filtered < body.index("metadata['tools'] = tools_dict")
    assert filtered < body.index("form_data['tools'] = [")


def test_the_subagent_request_still_carries_the_mark_the_path_reads():
    source = (VENDOR / 'subagents.py').read_text(encoding='utf-8')
    assert 'child_request.state.jup_parent_chat_id = parent_chat_id' in source


def test_automations_still_send_their_id_so_the_path_can_see_them():
    """`path_of` finds an automation by `metadata['automation_id']`, which main.py fills from the
    form the automation runner sends."""
    main = (VENDOR.parent / 'main.py').read_text(encoding='utf-8')
    assert "automation_id = form_data.pop('automation_id', None)" in main
    assert "'automation_id': automation_id," in main
    runner = (VENDOR / 'automations.py').read_text(encoding='utf-8')
    assert runner.count("'automation_id': automation.id,") >= 2


# --- #21: an attended External Call waits for the asking user ---------------------------------------


def _tool_approval() -> str:
    return (VENDOR / 'tool_approval.py').read_text(encoding='utf-8')


def test_the_native_loop_pauses_for_a_gated_call_whatever_the_mode():
    """The forced-pause patch: without it, `full` mode runs straight into the refusal and no card ever
    shows. The vendor paused only on `tool_approval_mode == 'ask'`."""
    body = _between(
        _middleware(),
        "tool_approval_mode = metadata.get('params', {}).get('tool_approval_mode', 'full')",
        'tools = metadata.get(',
    )
    assert 'jup_must_pause = any(' in body
    assert 'jup_tool_policy.must_pause(' in body
    condition = body[body.index('if (\n') : body.index('await pause_for_tool_approval(')]
    assert 'and jup_must_pause' in condition
    assert "and tool_approval_mode == 'ask'" not in condition, 'the vendor-only condition came back'
    assert 'jup_tool_policy.preapprove_ungated(' in condition


def test_the_drain_re_pauses_gated_calls_in_full_mode_too():
    body = _between(_middleware(), 'async def drain_approved_tool_calls(', 'async def pause_for_tool_approval(')
    assert body.count('jup_tool_policy.must_pause(') == 2
    assert "get('tool_approval_mode', 'full') == 'ask' and any(" not in body, 'the vendor-only re-pause came back'


def test_the_drain_runs_a_gated_call_only_on_a_verified_approval_and_audits_who():
    body = _between(_middleware(), 'async def drain_approved_tool_calls(', 'async def pause_for_tool_approval(')
    verify = body.index("'jup_approval': jup_approval.verified(")
    assert verify < body.index('result = await execute_tool_call_for_output(')
    assert 'secret=WEBUI_SECRET_KEY' in body
    assert "approved_by=result.get('jup_approved_by')" in body
    assert "approval_wait_ms=result.get('jup_approval_wait_ms', 0)" in body
    executor = _between(
        _middleware(), 'async def execute_tool_call_for_output(', 'async def drain_approved_tool_calls('
    )
    assert "approval=tool_call.get('jup_approval')" in executor
    assert "'jup_approved_by': jup_gate.approved_by" in executor


def test_the_card_is_never_shown_for_a_preapproved_call_and_a_gated_card_is_armed():
    body = _between(_middleware(), 'async def pause_for_tool_approval(', 'def get_response_data(')
    assert "and item.get('approved') is not True" in body
    armed = body.index('jup_approval.arm(')
    assert body.index("item['status'] = 'pending'") < armed
    assert body.index('await Chats.upsert_message_to_chat_by_id_and_message_id(') < body.index(
        'arm_jup_approval_timeout(chat_id, message_id, call_id)'
    ), 'the timer must read the stored, armed call'


def test_only_the_chats_owner_resolves_a_call():
    body = _between(
        _tool_approval(),
        'async def resolve_tool_call_output(',
        'message = await Chats.get_message_by_id_and_message_id',
    )
    assert 'if not chat or chat.user_id != user.id:' in body
    assert "user.role != 'admin'" not in body, "the vendor's admin override came back"


def test_a_gated_call_is_decided_by_jup_approval_before_the_vendors_branches():
    body = _between(
        _tool_approval(),
        'async def resolve_tool_call_output(',
        'await Chats.upsert_message_to_chat_by_id_and_message_id(',
    )
    gated = body.index('if jup_approval.is_gated(function_call)')
    assert gated < body.index("elif form_data.action == 'approve':")
    assert 'jup_approval.resolve(' in body[gated:]
    assert '_jup_record_refusal(' in body[gated:]


def test_the_timeout_timer_is_scheduled_and_resumes_the_turn():
    source = _tool_approval()
    timer = _between(source, 'async def _jup_time_out(', 'async def build_tool_approval_resume_payload(')
    assert 'jup_approval.time_out(' in timer
    assert '_jup_record_refusal(' in timer
    assert 'CHAT_COMPLETION_HANDLER(request, payload, user=user)' in timer


def test_the_timer_the_middleware_imports_still_exists():
    assert 'def arm_jup_approval_timeout(' in _tool_approval()
    assert 'from open_webui.utils.tool_approval import arm_jup_approval_timeout' in _middleware()


def test_switching_a_chat_to_full_never_approves_a_gated_call():
    """The vendor's mode switch posts `approve` for the pending card; that must not be a gated one."""
    chat = (VENDOR.parent.parent.parent / 'src/lib/components/chat/Chat.svelte').read_text(encoding='utf-8')
    body = _between(chat, "if (tool_approval_mode === 'full') {", "'approve'")
    assert '!item?.jup_gate &&' in body


# --- #22: the approval card as ADR-0013 describes it ------------------------------------------------

SRC = VENDOR.parent.parent.parent / 'src'


def _src(path: str) -> str:
    return (SRC / path).read_text(encoding='utf-8')


def test_the_armed_calls_class_reaches_the_card():
    source = _src('lib/components/chat/Messages/structuredOutput.ts')
    assert "import { gateRiskClass } from '$lib/gate/card';" in source
    body = _between(source, 'function buildToolCallToken(', 'function buildReasoningToken(')
    assert 'risk_class: gateRiskClass(item)' in body


def test_a_gated_card_masks_secrets_labels_its_class_and_opens():
    source = _src('lib/components/common/ToolCallDisplay.svelte')
    assert "import { maskedArguments } from '$lib/gate/card';" in source
    assert '$: shownArgs = riskClass ? maskedArguments(args) : args;' in source
    assert '$: parsedArgs = parseArguments(shownArgs);' in source
    assert re.search(r'formatJSONString\(\s*shownArgs\s*\)', source), 'the raw-text view must show the masked text'
    assert not re.search(r'formatJSONString\(\s*args\s*\)', source)
    assert '$: if (riskClass && needsApproval) open = true;' in source
    assert 'class="jup-risk-label shrink-0"' in source
    assert '.jup-risk-label {' in _src('jup-skin.css')


def test_the_group_offers_no_shortcut_allow_for_a_gated_call():
    """The collapsed group's Allow/Deny approve without showing the arguments."""
    source = _src('lib/components/chat/Messages/Markdown/ConsecutiveDetailsGroup.svelte')
    assert '$: if (hasGatedPending) open = true;' in source
    assert source.count('&& !hasGatedPending}') == 2


def test_a_gated_calls_echoed_result_is_masked_too():
    source = _src('lib/components/common/ToolCallDisplay.svelte')
    assert '$: parsedResult = parseJSONString(riskClass ? maskedArguments(result) : result);' in source


def test_full_access_no_longer_claims_to_skip_every_approval():
    source = _src('lib/components/chat/MessageInput/InputMenu.svelte')
    assert "'Run tools without asking for approval, except External Calls, which always ask.'" in source
    assert re.search(
        r"mode\.value === 'full'\s*\?\s*jupFullAccessDescription\s*:\s*\$i18n\.t\(mode\.description\)", source
    )
