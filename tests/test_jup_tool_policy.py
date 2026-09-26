"""A5+E5 #18: every tool has a Risk Class, and every `external` call is refused for now.

Behaviour of `jup.tool_policy` through its public interface: what class a tool resolves to, and
whether a call runs or is refused, with what the model is told and what the audit line says.
The dispatch inserts that consult it are guarded separately in `test_jup_tool_gate_presence.py`.
"""

import pytest

from jup.tool_policy import BUILTIN_CLASSES, EXTERNAL, READ, WRITE_OWN, classify, decide


def builtin(name: str) -> dict:
    """The shape `utils/tools.py:get_builtin_tools` gives every vendor built-in."""
    return {'tool_id': f'builtin:{name}', 'type': 'builtin', 'spec': {'name': name}}


def native(tool_id: str, risk_class=None) -> dict:
    """The shape `utils/tools.py:get_tools` gives a DB tool, with the class its source declared."""
    return {'tool_id': tool_id, 'spec': {'name': tool_id}, 'risk_class': risk_class}


# --- the built-in table ---------------------------------------------------------------------------

READ_BUILTINS = [
    'get_current_timestamp',
    'calculate_timestamp',
    'search_web',
    'ask_user',
    'execute_code',
    'list_memory_paths',
    'read_memory_path',
    'search_memories',
    'list_memories',
    'search_notes',
    'view_note',
    'search_chats',
    'view_chat',
    'search_channels',
    'search_channel_messages',
    'view_channel_message',
    'view_channel_thread',
    'list_knowledge_bases',
    'search_knowledge_bases',
    'query_knowledge_bases',
    'list_knowledge',
    'search_knowledge_files',
    'grep_knowledge_files',
    'query_knowledge_files',
    'view_knowledge_file',
    'list_chat_files',
    'grep_chat_files',
    'query_chat_files',
    'view_file',
    'view_skill',
    'list_automations',
    'search_calendar_events',
    'notify',
    'delegate_task',
    'timer',
]
WRITE_OWN_BUILTINS = [
    'add_memory',
    'update_memory',
    'replace_memory_content',
    'delete_memory',
    'create_tasks',
    'update_task',
    'create_automation',
    'update_automation',
    'toggle_automation',
    'delete_automation',
]
EXTERNAL_BUILTINS = [
    'fetch_url',
    'generate_image',
    'edit_image',
    'write_note',
    'replace_note_content',
    'create_calendar_event',
    'update_calendar_event',
    'delete_calendar_event',
]


@pytest.mark.parametrize('name', READ_BUILTINS)
def test_read_builtins_run_without_approval(name):
    assert classify(builtin(name)) == READ
    decision = decide(name, builtin(name))
    assert decision.runs and decision.approval == 'not_required'


@pytest.mark.parametrize('name', WRITE_OWN_BUILTINS)
def test_write_own_builtins_run_without_approval(name):
    assert classify(builtin(name)) == WRITE_OWN
    decision = decide(name, builtin(name))
    assert decision.runs and decision.approval == 'not_required'


@pytest.mark.parametrize('name', EXTERNAL_BUILTINS)
def test_external_builtins_are_refused(name):
    assert classify(builtin(name)) == EXTERNAL
    decision = decide(name, builtin(name))
    assert not decision.runs and decision.approval == 'rejected'


def test_the_table_is_exactly_the_reviewed_rows():
    """A row added or dropped without updating this list is a class change nobody reviewed."""
    reviewed = {**dict.fromkeys(READ_BUILTINS, READ), **dict.fromkeys(WRITE_OWN_BUILTINS, WRITE_OWN)}
    reviewed |= dict.fromkeys(EXTERNAL_BUILTINS, EXTERNAL)
    assert reviewed == BUILTIN_CLASSES


def test_search_web_is_the_named_exception_and_fetch_url_is_not():
    """ADR-0013 amendment §1: only the query leaves on a search; a fetch reaches any URL."""
    assert decide('search_web', builtin('search_web')).runs
    assert not decide('fetch_url', builtin('fetch_url')).runs


# --- anything unclassified is external ------------------------------------------------------------


@pytest.mark.parametrize(
    'tool',
    [
        builtin('kb_exec'),  # a real vendor built-in that is off here and not yet in the table
        builtin('some_tool_from_the_next_vendor_release'),
        native('an_undeclared_native_tool'),
        native('a_misdeclared_native_tool', 'READ-ONLY'),
        {'tool_id': 'server:mcp:decisions', 'type': 'mcp'},
        {'tool_id': 'server:0', 'type': 'external'},
        {'tool_id': 'terminal:t1', 'type': 'terminal'},
        {'type': 'builtin'},  # no id at all
        {},
    ],
)
def test_a_tool_the_policy_cannot_classify_is_external(tool):
    assert classify(tool) == EXTERNAL
    assert not decide('whatever', tool).runs


def test_a_builtin_is_looked_up_by_its_id_not_the_name_the_model_used():
    """The vendor prefixes a colliding name with its tool id; the id is what identifies it."""
    assert decide('portfolio_status_fetch_url', builtin('fetch_url')).approval == 'rejected'


def test_a_builtin_cannot_claim_a_class_of_its_own():
    """A declared class is honoured for native tools only; the table is the authority for built-ins."""
    assert classify({**builtin('fetch_url'), 'risk_class': READ}) == EXTERNAL


# --- native JUP tools declare their class ---------------------------------------------------------


@pytest.mark.parametrize('declared', [READ, WRITE_OWN, EXTERNAL])
def test_a_native_tool_resolves_to_the_class_its_source_declares(declared):
    assert classify(native('some_jup_tool', declared)) == declared


def test_portfolio_status_runs_and_gate_probe_is_refused():
    assert decide('portfolio_status', native('portfolio_status', READ)).approval == 'not_required'
    probe = decide('gate_probe', native('gate_probe', EXTERNAL))
    assert not probe.runs
    assert probe.approval == 'rejected'


# --- what the model is told -----------------------------------------------------------------------


def test_a_refusal_tells_the_model_what_was_refused_and_why():
    message = decide('gate_probe', native('gate_probe', EXTERNAL)).message
    assert 'gate_probe' in message
    assert 'external' in message
    assert 'did not run' in message
    assert 'approval' in message.lower()


def test_a_call_that_runs_carries_no_message():
    assert decide('search_web', builtin('search_web')).message is None
