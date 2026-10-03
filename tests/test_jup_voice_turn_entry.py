"""#27: the completion entry's question "is this a voice chat?" (`routers/jup_voice.enforce_voice_turn`).

Faked: the chat row (through `VoiceStore.chat`) and the server secret. The real signed mark from
`jup.voice` and the real `jup.voice_turn.rewrite` run on every call.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the other endpoint
tests. A skip here is not a pass. The rewrite itself is covered without a server in
test_jup_voice_turn.py.
"""

import ast
import asyncio
import importlib.util
from types import SimpleNamespace

import pytest

from jup import voice

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt', 'sqlalchemy')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The rewrite is covered without a server in test_jup_voice_turn.py.'
    ),
)

SECRET = 'test-secret'
ERIK = 'user-erik'
ADMIN = 'user-admin'
CHAT = 'chat-voice'


class _Store:
    def __init__(self) -> None:
        self.chats: dict[str, SimpleNamespace] = {}

    async def get_chat(self, chat_id: str):
        return self.chats.get(chat_id)

    def add(self, chat_id: str, owner: str, meta: dict) -> None:
        self.chats[chat_id] = SimpleNamespace(id=chat_id, user_id=owner, meta=meta)


def _mark(chat_id: str = CHAT, owner: str = ERIK) -> dict:
    return {voice.CHAT_KEY: voice.voice_mark(chat_id, owner, at=1, secret=SECRET)}


def _forged(chat_id: str = CHAT) -> dict:
    return {
        'model': 'xiaomi/mimo-v2.6-pro-ultraspeed',
        'chat_id': chat_id,
        'tool_ids': ['gate_probe'],
        'features': {'web_search': True},
        'messages': [],
    }


def _enforce(form: dict, store: _Store, *, user: str = ERIK, secret: str = SECRET) -> bool:
    from open_webui.routers import jup_voice

    return asyncio.run(jup_voice.enforce_voice_turn(form, SimpleNamespace(id=user), store=store, secret=secret))


def _turn_lines(caplog) -> list[dict]:
    lines = []
    for record in caplog.records:
        message = record.getMessage()
        if message.startswith('jup.governance') and "'event': 'voice_turn'" in message:
            line = ast.literal_eval(message[message.index('{') :])
            line.pop('ts', None)
            lines.append(line)
    return lines


@pytest.fixture(autouse=True)
def _audit(caplog: pytest.LogCaptureFixture) -> None:
    # Imported first: the vendor's import configures logging, which would drop the capture.
    from open_webui.routers import jup_voice  # noqa: F401

    caplog.set_level('INFO', logger='jup.governance')


def test_a_voice_chat_turn_is_forced_onto_the_voice_model(caplog) -> None:
    store = _Store()
    store.add(CHAT, ERIK, _mark())
    form = _forged()
    assert _enforce(form, store) is True
    assert form['model'] == voice.VOICE_MODEL_ID
    assert form['tool_ids'] == ['portfolio_status', 'jup_contracts', 'jup_leadership']
    assert form['features'] == {}
    assert _turn_lines(caplog) == [
        {'event': 'voice_turn', 'user': ERIK, 'chat': CHAT, 'changed': ['model', 'tool_ids', 'features']}
    ]


def test_an_admin_turn_in_someone_elses_voice_chat_is_forced_too() -> None:
    """The mark is checked against the chat's owner, not the caller."""
    store = _Store()
    store.add(CHAT, ERIK, _mark())
    form = _forged()
    assert _enforce(form, store, user=ADMIN) is True
    assert form['model'] == voice.VOICE_MODEL_ID


def test_an_ordinary_chat_is_left_alone(caplog) -> None:
    store = _Store()
    store.add(CHAT, ERIK, {})
    form = _forged()
    assert _enforce(form, store) is False
    assert form == _forged()
    assert _turn_lines(caplog) == []


def test_a_copied_mark_does_not_make_a_voice_chat() -> None:
    """A mark signed for another chat id (an import or a fork) is not a voice chat."""
    store = _Store()
    store.add('chat-copy', ERIK, _mark(CHAT))
    form = _forged('chat-copy')
    assert _enforce(form, store) is False
    assert form['model'] == 'xiaomi/mimo-v2.6-pro-ultraspeed'


@pytest.mark.parametrize('chat_id', [None, '', 'local:abc', 'channel:abc', 'missing'])
def test_no_saved_chat_means_no_voice_turn(chat_id) -> None:
    store = _Store()
    form = _forged()
    form['chat_id'] = chat_id
    assert _enforce(form, store) is False


def test_without_the_server_secret_no_chat_is_voice() -> None:
    store = _Store()
    store.add(CHAT, ERIK, _mark())
    assert _enforce(_forged(), store, secret='') is False
