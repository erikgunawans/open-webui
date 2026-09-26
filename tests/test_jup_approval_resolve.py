"""A5+E5 #21: the vendor resolve route and the server-side timer, with the chat store in memory.

`jup.approval` holds the rules (`test_jup_approval.py`); this is the glue in
`utils/tool_approval.py` that applies them: only the asking user resolves, a gated approve is
signed and a reject reaches the model and the audit line, a late click is a timeout, and the timer
times out an unanswered call with no tab open and resumes the turn so the model is told.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the endpoint tests.
A skip here is not a pass.
"""

import importlib.util
import json
from types import SimpleNamespace

import pytest

_RUNTIME_MODULES = ('fastapi', 'sqlalchemy', 'aiosqlite', 'socketio')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The rules are covered without a server in test_jup_approval.py.'
    ),
)

CHAT_ID = 'chat-1'
MESSAGE_ID = 'msg-1'
CALL_ID = 'call-1'
OWNER = 'user-owner'
ADMIN = 'user-admin'
ARGUMENTS = json.dumps({'text': 'NPWP rahasia'})
MINUTE = 60_000


class _Chats:
    """The two chat rows the route reads and writes, in memory."""

    def __init__(self, output: list) -> None:
        self.chat = SimpleNamespace(id=CHAT_ID, user_id=OWNER, chat={}, variables={})
        self.message = {'id': MESSAGE_ID, 'output': output}

    async def get_chat_by_id(self, chat_id, db=None):
        return self.chat if chat_id == CHAT_ID else None

    async def get_message_by_id_and_message_id(self, chat_id, message_id):
        return self.message if (chat_id, message_id) == (CHAT_ID, MESSAGE_ID) else None

    async def upsert_message_to_chat_by_id_and_message_id(self, chat_id, message_id, fields, touch=True):
        self.message.update(fields)


def _gated_call(paused_at: int) -> dict:
    return {
        'type': 'function_call',
        'id': CALL_ID,
        'call_id': CALL_ID,
        'name': 'gate_probe',
        'arguments': ARGUMENTS,
        'status': 'pending',
        'jup_gate': {'paused_at': paused_at, 'tool_id': 'gate_probe'},
    }


@pytest.fixture
def glue(monkeypatch, tmp_path):
    from open_webui.utils import tool_approval

    trail = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(trail))
    monkeypatch.setattr(tool_approval, 'WEBUI_SECRET_KEY', 'test-secret')

    async def no_emitter(*args, **kwargs):
        return None

    monkeypatch.setattr(tool_approval, 'get_event_emitter', no_emitter)
    now = {'ms': 10 * MINUTE}
    monkeypatch.setattr(tool_approval.time, 'time', lambda: now['ms'] / 1000)
    return SimpleNamespace(module=tool_approval, trail=trail, now=now)


def _store(glue, monkeypatch, paused_at: int) -> _Chats:
    chats = _Chats([_gated_call(paused_at)])
    monkeypatch.setattr(glue.module, 'Chats', chats)
    return chats


async def _resolve(glue, action: str, user_id: str = OWNER, role: str = 'user'):
    form = glue.module.ResolveToolCallForm(call_id=CALL_ID, action=action)
    return await glue.module.resolve_tool_call_output(CHAT_ID, MESSAGE_ID, form, SimpleNamespace(id=user_id, role=role))


def _audit(glue) -> list[dict]:
    if not glue.trail.exists():
        return []
    return [json.loads(line) for line in glue.trail.read_text().splitlines()]


def _outputs(chats: _Chats) -> list[dict]:
    return [item for item in chats.message['output'] if item.get('type') == 'function_call_output']


async def test_an_admin_cannot_decide_another_users_call(glue, monkeypatch):
    from fastapi import HTTPException

    chats = _store(glue, monkeypatch, paused_at=glue.now['ms'])
    with pytest.raises(HTTPException) as refused:
        await _resolve(glue, 'approve', user_id=ADMIN, role='admin')
    assert refused.value.status_code == 401
    assert chats.message['output'][0]['status'] == 'pending'


async def test_the_asking_user_approves_and_the_approval_verifies_for_the_drain(glue, monkeypatch):
    from jup import approval

    chats = _store(glue, monkeypatch, paused_at=glue.now['ms'] - MINUTE)
    result = await _resolve(glue, 'approve')
    [item] = chats.message['output']
    assert item['status'] == 'queued' and item['approved'] is True
    assert result['paused'] is True  # queued until the drain runs it
    granted = approval.verified(item, chat_id=CHAT_ID, message_id=MESSAGE_ID, user_id=OWNER, secret='test-secret')
    assert granted is not None and granted.wait_ms == MINUTE
    assert _audit(glue) == [], 'an approval is audited where the call runs, with its outcome'


async def test_a_second_decision_on_an_approved_call_is_a_conflict(glue, monkeypatch):
    from fastapi import HTTPException

    _store(glue, monkeypatch, paused_at=glue.now['ms'])
    await _resolve(glue, 'approve')
    with pytest.raises(HTTPException) as conflict:
        await _resolve(glue, 'reject')
    assert conflict.value.status_code == 409


async def test_a_reject_reaches_the_model_and_the_audit_line_without_the_arguments(glue, monkeypatch):
    chats = _store(glue, monkeypatch, paused_at=glue.now['ms'] - 2 * MINUTE)
    await _resolve(glue, 'reject')
    [refusal] = _outputs(chats)
    assert refusal['status'] == 'rejected'
    assert 'rejected it on the approval card' in refusal['output'][0]['text']
    [entry] = _audit(glue)
    assert entry['approval'] == 'rejected'
    assert entry['approved_by'] == OWNER
    assert entry['approval_wait_ms'] == 2 * MINUTE
    assert entry['outcome'] == 'refused'
    assert entry['tool_id'] == 'gate_probe'
    assert 'rahasia' not in glue.trail.read_text()


async def test_an_approve_after_ten_minutes_is_refused_as_timed_out(glue, monkeypatch):
    chats = _store(glue, monkeypatch, paused_at=glue.now['ms'] - 11 * MINUTE)
    await _resolve(glue, 'approve')
    [item, refusal] = chats.message['output']
    assert item['status'] == 'rejected' and 'approved' not in item
    assert 'timed_out' in refusal['output'][0]['text']
    [entry] = _audit(glue)
    assert entry['approval'] == 'timed_out'
    assert entry['approved_by'] is None


async def test_the_timer_times_out_an_unanswered_call_and_resumes_the_turn(glue, monkeypatch):
    """No tab, no click: the server refuses the call, audits it, and runs the model to say so."""
    chats = _store(glue, monkeypatch, paused_at=glue.now['ms'])
    slept = []

    async def fast_sleep(seconds):
        slept.append(seconds)
        glue.now['ms'] += int(seconds * 1000)

    monkeypatch.setattr(glue.module.asyncio, 'sleep', fast_sleep)

    async def owner(user_id):
        return SimpleNamespace(id=user_id, role='user')

    monkeypatch.setattr(glue.module.Users, 'get_user_by_id', owner)

    async def payload(chat_id, message_id, chat=None):
        return {'chat_id': chat_id, 'id': message_id}

    monkeypatch.setattr(glue.module, 'build_tool_approval_resume_payload', payload)
    resumed = []

    async def handler(request, form_data, user):
        resumed.append((form_data, user.id))

    from open_webui.main import app

    monkeypatch.setattr(app.state, 'CHAT_COMPLETION_HANDLER', handler)

    await glue.module._jup_time_out(CHAT_ID, MESSAGE_ID, CALL_ID)

    assert slept and slept[0] * 1000 >= 10 * MINUTE
    [refusal] = _outputs(chats)
    assert 'timed_out' in refusal['output'][0]['text']
    [entry] = _audit(glue)
    assert entry['approval'] == 'timed_out' and entry['approved_by'] is None
    assert resumed == [({'chat_id': CHAT_ID, 'id': MESSAGE_ID}, OWNER)]


async def test_the_timer_does_nothing_when_the_user_answered_first(glue, monkeypatch):
    chats = _store(glue, monkeypatch, paused_at=glue.now['ms'])
    await _resolve(glue, 'approve')

    async def fast_sleep(seconds):
        glue.now['ms'] += int(seconds * 1000)

    monkeypatch.setattr(glue.module.asyncio, 'sleep', fast_sleep)
    await glue.module._jup_time_out(CHAT_ID, MESSAGE_ID, CALL_ID)
    assert chats.message['output'][0]['status'] == 'queued'
    assert _outputs(chats) == []
