"""E1: one `jup.governance` audit line per tool invocation, and the three vendor lines that write it.

`admit()` audits each *model turn*. A turn can run several tools, and the tool is where the agent
touches data, so without these lines the trail cannot say which tool ran for whom. The agent-depth
plan puts this first because every later tool is only as accountable as this line.

Same two kinds of test as `test_jup_governance.py`:

- **Behaviour** of `audit_tool_call`, including the rule that argument *content* never reaches the
  trail, only its size.
- **Presence** of the inserts at the three places `utils/middleware.py` runs a tool: the native
  tool loop, the approval drain, and the legacy prompt-based handler. Losing one fails nothing
  visible — tools still run, the answer still arrives — so a lost patch must break this test
  instead. See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import json
import re
from pathlib import Path

import pytest

from jup.governance import audit_tool_call

MIDDLEWARE_PY = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui' / 'utils' / 'middleware.py'

SECRET = 'NPWP 01.234.567.8-901.000 dan tarif rahasia'
TOOL = {'tool_id': 'portfolio_status', 'type': '', 'spec': {}}


def _trail(tmp_path, monkeypatch):
    trail = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(trail))
    return trail


def _entries(trail: Path) -> list[dict]:
    return [json.loads(line) for line in trail.read_text().splitlines()]


def _call(**overrides):
    fields = dict(
        name='portfolio_status',
        arguments=json.dumps({'query': SECRET}),
        tool=TOOL,
        result='ok',
        error=False,
        user_id='u1',
        chat_id='c1',
        mode='native',
    )
    fields.update(overrides)
    audit_tool_call(**fields)


def test_a_successful_call_writes_one_line_with_who_what_and_outcome(tmp_path, monkeypatch):
    trail = _trail(tmp_path, monkeypatch)
    _call()
    [entry] = _entries(trail)
    assert entry['event'] == 'tool_call'
    assert entry['user'] == 'u1'
    assert entry['chat'] == 'c1'
    assert entry['tool'] == 'portfolio_status'
    assert entry['tool_id'] == 'portfolio_status'
    assert entry['outcome'] == 'ok'
    assert entry['mode'] == 'native'
    assert entry['arg_bytes'] == len(json.dumps({'query': SECRET}).encode('utf-8'))


def test_argument_content_never_reaches_the_trail(tmp_path, monkeypatch):
    trail = _trail(tmp_path, monkeypatch)
    _call()
    _call(arguments={'query': SECRET}, mode='default')
    text = trail.read_text()
    assert 'NPWP' not in text and 'rahasia' not in text


def test_dict_arguments_are_sized_as_utf8_json(tmp_path, monkeypatch):
    trail = _trail(tmp_path, monkeypatch)
    _call(arguments={'q': 'é'})
    assert _entries(trail)[0]['arg_bytes'] == len(json.dumps({'q': 'é'}, ensure_ascii=False).encode('utf-8'))


@pytest.mark.parametrize(
    'overrides, outcome',
    [
        ({'error': True, 'result': {'error': 'boom'}}, 'error'),
        ({'tool': None, 'result': 'Error: Tool "x" not found.'}, 'not_found'),
        ({'tool': None, 'result': None, 'arguments': '{bad'}, 'unparsed'),
        ({'result': None}, 'ok'),  # a tool that legitimately returns nothing still ran
    ],
)
def test_outcomes(tmp_path, monkeypatch, overrides, outcome):
    trail = _trail(tmp_path, monkeypatch)
    _call(**overrides)
    assert _entries(trail)[0]['outcome'] == outcome


def test_a_builtin_tool_is_identified_by_its_builtin_id(tmp_path, monkeypatch):
    trail = _trail(tmp_path, monkeypatch)
    _call(name='query_knowledge_files', tool={'tool_id': 'builtin:query_knowledge_files'})
    assert _entries(trail)[0]['tool_id'] == 'builtin:query_knowledge_files'


def test_auditing_never_raises_into_the_tool_loop(tmp_path, monkeypatch):
    blocker = tmp_path / 'not-a-dir'
    blocker.write_text('')
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(blocker / 'audit.jsonl'))
    _call()  # unwritable trail
    _call(arguments=object())  # unserialisable to anything but its repr — still must not raise
    _call(tool='not-a-dict')  # a shape the vendor never sends


# --- presence of the vendor inserts -------------------------------------------------------------


def _source() -> str:
    return MIDDLEWARE_PY.read_text(encoding='utf-8')


def test_middleware_imports_the_governance_module():
    assert 'from jup import governance as jup_governance' in _source()


@pytest.mark.parametrize('mode', ['native', 'approved', 'default'])
def test_each_tool_execution_site_audits(mode: str):
    calls = re.findall(r'jup_governance\.audit_tool_call\((.*?)\n\s*\)', _source(), re.S)
    modes = [m for m in (re.search(r"mode='(\w+)'", c) for c in calls) if m]
    assert mode in [m.group(1) for m in modes], f'the {mode} tool-execution site lost its audit line'


def test_the_native_loop_audits_every_result_before_it_is_used():
    """The audit sits straight after the unpack, so no `continue` below it can skip a call."""
    source = _source()
    unpack = source.index('tool_type, direct_tool = tool_results[id(tool_call)]')
    audit_at = source.index('jup_governance.audit_tool_call(', unpack)
    skip = source.index('if tool_result is None:', unpack)
    assert audit_at < skip


def test_the_approval_drain_audits_after_the_status_is_decided():
    source = _source()
    drain = source[source.index('async def drain_approved_tool_calls') :]
    drain = drain[: drain.index('\nasync def ')]
    status = drain.index("item['status'] = 'failed' if _is_tool_result_error")
    assert status < drain.index('jup_governance.audit_tool_call(')
