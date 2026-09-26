"""A5+E5 #20: where nobody is present to approve, an External Call fails closed (ADR-0013 §4).

Behaviour of `jup.tool_policy` through its public interface: which path a request is on, what an
`external` call gets there (refused as `rejected_unattended`, the model told why), that `read` and
`write_own` still run, and that a subagent is never offered an `external` tool. The vendor inserts
that pass the path and filter the subagent's tools are guarded in `test_jup_tool_gate_presence.py`.
"""

from types import SimpleNamespace

import pytest

from jup.tool_policy import (
    AUTOMATION,
    CHANNEL,
    CHAT,
    SUBAGENT,
    UNATTENDED,
    decide,
    offered_tools,
    path_of,
)


def builtin(name: str) -> dict:
    return {'tool_id': f'builtin:{name}', 'type': 'builtin', 'spec': {'name': name}}


def native(tool_id: str, risk_class=None) -> dict:
    return {'tool_id': tool_id, 'spec': {'name': tool_id}, 'risk_class': risk_class}


GATE_PROBE = native('gate_probe', 'external')


# --- which path a request is on -------------------------------------------------------------------


def test_an_ordinary_chat_is_attended():
    assert path_of({'chat_id': 'c1', 'params': {'tool_approval_mode': 'ask'}}, SimpleNamespace()) == CHAT


def test_an_automation_run_is_unattended():
    """The shape `utils/automations.py` sends: a real chat id, plus the automation's id."""
    assert path_of({'chat_id': 'c1', 'automation_id': 'a1'}, SimpleNamespace()) == AUTOMATION


def test_a_channel_chat_is_unattended():
    assert path_of({'chat_id': 'channel:ch1'}, SimpleNamespace()) == CHANNEL


def test_a_channel_automation_counts_as_an_automation():
    assert path_of({'chat_id': 'channel:ch1', 'automation_id': 'a1'}, SimpleNamespace()) == AUTOMATION


def test_a_subagent_is_marked_by_the_state_its_request_carries():
    """`utils/subagents.py` stamps `jup_parent_chat_id` on the child request (as `jup.governance` reads it)."""
    assert path_of({'chat_id': 'c2'}, SimpleNamespace(jup_parent_chat_id='c1')) == SUBAGENT


@pytest.mark.parametrize('mode', ['full', 'ask', None])
def test_the_chats_approval_mode_never_changes_the_path(mode):
    """The vendor forces `full` on automations and channels; the gate must not read it."""
    metadata = {'chat_id': 'c1', 'automation_id': 'a1', 'params': {'tool_approval_mode': mode}}
    assert path_of(metadata, SimpleNamespace()) == AUTOMATION


def test_missing_metadata_and_state_are_a_chat_not_a_crash():
    assert path_of(None, None) == CHAT


# --- what an external call gets there -------------------------------------------------------------


@pytest.mark.parametrize('path', sorted(UNATTENDED))
@pytest.mark.parametrize('tool', [GATE_PROBE, builtin('fetch_url'), {'tool_id': 'server:mcp:x'}])
def test_an_external_call_on_an_unattended_path_is_refused_as_unattended(path, tool):
    ruling = decide('gate_probe', tool, path=path)
    assert not ruling.runs
    assert ruling.approval == 'rejected_unattended'


def test_an_unknown_path_is_treated_as_unattended():
    assert decide('gate_probe', GATE_PROBE, path='webhook').approval == 'rejected_unattended'


def test_an_attended_external_call_is_still_refused_as_rejected():
    """Until the card exists (#21) the attended refusal stays `rejected`, not `rejected_unattended`."""
    assert decide('gate_probe', GATE_PROBE, path=CHAT).approval == 'rejected'


@pytest.mark.parametrize('path', sorted(UNATTENDED))
@pytest.mark.parametrize(
    'tool', [builtin('search_web'), builtin('add_memory'), builtin('create_tasks'), native('portfolio_status', 'read')]
)
def test_read_and_write_own_still_run_unattended(path, tool):
    ruling = decide('x', tool, path=path)
    assert ruling.runs
    assert ruling.approval == 'not_required'
    assert ruling.message is None


@pytest.mark.parametrize(
    ('path', 'where'),
    [(AUTOMATION, 'automation run'), (CHANNEL, 'channel conversation'), (SUBAGENT, 'subagent task')],
)
def test_the_model_is_told_why_so_the_reason_reaches_the_runs_chat(path, where):
    message = decide('gate_probe', GATE_PROBE, path=path).message
    assert 'gate_probe' in message
    assert where in message
    assert 'nobody is present to approve' in message
    assert 'rejected_unattended' in message
    assert 'did not run' in message


# --- a subagent is not offered external tools -----------------------------------------------------

TOOLS = {
    'search_web': builtin('search_web'),
    'add_memory': builtin('add_memory'),
    'fetch_url': builtin('fetch_url'),
    'write_note': builtin('write_note'),
    'portfolio_status': native('portfolio_status', 'read'),
    'gate_probe': GATE_PROBE,
    'decisions_search_decisions': {'tool_id': 'server:mcp:decisions', 'type': 'mcp'},
    'kb_exec': builtin('kb_exec'),
}


def test_a_subagents_offered_tools_exclude_every_external_tool():
    assert set(offered_tools(TOOLS, SUBAGENT)) == {'search_web', 'add_memory', 'portfolio_status'}


@pytest.mark.parametrize('path', [CHAT, AUTOMATION, CHANNEL])
def test_other_paths_are_offered_everything_and_refused_at_the_call(path):
    """Filtering there would hide the refusal from the run's chat; the call is refused instead."""
    assert offered_tools(TOOLS, path) == TOOLS
