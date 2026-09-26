"""A5+E5 #23: an MCP server's Risk Class, set by an admin on its connection, and its audit tool_id.

`mcp_tool_fields` is what the vendor's MCP loop adds to each MCP tool entry: `tool_id` `mcp:<id>`
(what the audit line names) and the class resolved from the connection config — the per-tool
override, then the server's class, else `external`. `classify` trusts that class for an `mcp:` id.
The vendor insert that calls it is guarded in `test_jup_tool_gate_presence.py`.
"""

import json

import pytest

from jup.governance import audit_tool_call
from jup.tool_policy import CHAT, EXTERNAL, READ, WRITE_OWN, classify, decide, mcp_tool_fields


def entry(server_id: str, tool_name: str, config) -> dict:
    """An MCP tool entry as the vendor builds it, with the JUP fields added."""
    return {
        'spec': {'name': f'{server_id}_{tool_name}'},
        'type': 'mcp',
        **mcp_tool_fields(server_id, tool_name, config),
    }


def test_an_mcp_tool_is_named_for_the_audit_line_by_its_server():
    assert mcp_tool_fields('decisions', 'get_decision', {'jup_risk_class': 'read'})['tool_id'] == 'mcp:decisions'


def test_the_servers_class_covers_all_its_tools():
    config = {'jup_risk_class': 'read'}
    for tool_name in ('search_decisions', 'get_decision'):
        tool = entry('decisions', tool_name, config)
        assert classify(tool) == READ
        ruling = decide(f'decisions_{tool_name}', tool, path=CHAT)
        assert ruling.runs and ruling.approval == 'not_required'


def test_a_per_tool_override_wins_over_the_servers_class():
    config = {'jup_risk_class': 'read', 'jup_tool_risk_classes': {'send_mail': 'external', 'save_draft': 'write_own'}}
    assert classify(entry('mail', 'send_mail', config)) == EXTERNAL
    assert classify(entry('mail', 'save_draft', config)) == WRITE_OWN
    assert classify(entry('mail', 'list_inbox', config)) == READ


@pytest.mark.parametrize('config', [None, {}, {'enable': True}, {'jup_risk_class': 'READ'}, {'jup_risk_class': 3}])
def test_a_server_nobody_classified_is_external(config):
    tool = entry('someserver', 'anything', config)
    assert classify(tool) == EXTERNAL
    assert not decide('someserver_anything', tool, path=CHAT).runs


@pytest.mark.parametrize('override', ['External', 'extern', 'readonly', None, 3])
def test_a_malformed_override_is_external_even_on_a_read_server(override):
    """An admin who meant to gate one tool and mistyped the class must not have it run ungated."""
    config = {'jup_risk_class': 'read', 'jup_tool_risk_classes': {'send_mail': override}}
    assert classify(entry('mail', 'send_mail', config)) == EXTERNAL
    assert classify(entry('mail', 'list_inbox', config)) == READ


def test_an_override_table_that_is_not_a_mapping_gates_the_whole_server():
    assert classify(entry('mail', 'list_inbox', {'jup_risk_class': 'read', 'jup_tool_risk_classes': ['x']})) == EXTERNAL


def test_a_malformed_override_never_reads_more_generously_than_the_server():
    config = {'jup_risk_class': 'external', 'jup_tool_risk_classes': {'x': 'readonly'}}
    assert classify(entry('s', 'x', config)) == EXTERNAL
    assert classify(entry('s', 'x', {'jup_risk_class': 'external', 'jup_tool_risk_classes': ['x']})) == EXTERNAL


def test_only_the_mcp_prefix_is_trusted_with_a_class_on_the_entry():
    """An OpenAPI server's entry is still `server:…` and still external, whatever it carries."""
    assert classify({'tool_id': 'server:0', 'risk_class': 'read'}) == EXTERNAL
    assert classify({'tool_id': 'mcp:', 'risk_class': 'read'}) == EXTERNAL


def test_an_mcp_call_audits_its_server(tmp_path, monkeypatch):
    trail = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(trail))
    audit_tool_call(
        name='decisions_get_decision',
        arguments=json.dumps({'id': 'D20'}),
        tool=entry('decisions', 'get_decision', {'jup_risk_class': 'read'}),
        result='D20 …',
        error=False,
        user_id='u1',
        chat_id='c1',
        mode='native',
        approval='not_required',
    )
    [line] = [json.loads(raw) for raw in trail.read_text().splitlines()]
    assert line['tool_id'] == 'mcp:decisions'
    assert line['outcome'] == 'ok'
    assert 'D20' not in trail.read_text()
