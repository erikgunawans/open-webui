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
    gate = body.index('jup_tool_policy.decide(name, tool)')
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
    gate = body.index('jup_gate = jup_tool_policy.decide(name, tool)')
    early_return = body.index("'content': jup_gate.message", gate)
    assert early_return < body.index('await function(**params)')
    assert early_return < body.index("'type': 'execute:tool'")
    assert "'jup_approval': jup_gate.approval" in body[body.index('tool_result_content(result)') - 200 :]


def test_the_approval_drain_audits_the_gates_answer():
    body = _between(_middleware(), 'async def drain_approved_tool_calls(', 'async def pause_for_tool_approval(')
    assert "approval=result.get('jup_approval', 'not_required')" in body


def test_the_prompt_based_handler_refuses_before_it_runs_the_tool():
    body = _between(_middleware(), 'async def tool_call_handler(tool_call):', 'jup_governance.audit_tool_call(')
    gate = body.index('jup_gate = jup_tool_policy.decide(tool_function_name, tools[tool_function_name])')
    refusal = body.index('if not jup_gate.runs:', gate)
    assert refusal < body.index('tool_result = jup_gate.message', refusal) < body.index('elif tool.get(')
    assert refusal < body.index('await tool_function(**tool_function_params)')


def test_the_stored_tools_declared_class_reaches_the_tool_entry():
    body = _between(TOOLS_PY.read_text(encoding='utf-8'), 'async def get_tools(', 'async def get_builtin_tools(')
    assert "'risk_class': ((tool.meta.manifest if tool.meta else None) or {}).get('risk_class')" in body
