"""#28: the audio boundary's seam (`routers/jup_voice.stt_admit`, `stt_audit`, `speech_body`,
`GET /speech/parts`).

Faked: the request, the chat rows (`VoiceStore.get_chat` / `get_message`), the caller's merged
permissions and the server secret. The real signed voice mark and the real rules in
`jup.voice_audio` run on every call.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the other endpoint
tests. A skip here is not a pass. The rules are covered without a server in test_jup_voice_audio.py.
"""

import ast
import asyncio
import importlib.util
import json
from types import SimpleNamespace

import pytest

from jup import voice

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt', 'sqlalchemy')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The rules are covered without a server in test_jup_voice_audio.py.'
    ),
)

SECRET = 'test-secret'
ERIK = 'user-erik'
OTHER = 'user-other'
VOICE_CHAT = 'chat-voice'
TYPED_CHAT = 'chat-typed'
OTHERS_VOICE_CHAT = 'chat-other-voice'
ANSWER = 'a-1'
QUESTION = 'u-1'
GRANTED = {'jup': {'voice': {'call': True}}}
ANSWER_TEXT = 'Strategi JUP berfokus pada gas.'


class _Store:
    def __init__(self) -> None:
        self.chats: dict[str, SimpleNamespace] = {}
        self.messages: dict[tuple[str, str], dict] = {}

    async def get_chat(self, chat_id: str):
        return self.chats.get(chat_id)

    async def get_message(self, chat_id: str, message_id: str):
        return self.messages.get((chat_id, message_id))

    async def set_message_meta_key(self, chat_id: str, message_id: str, key: str, value) -> None:
        message = self.messages[(chat_id, message_id)]
        message['meta'] = {**(message.get('meta') or {}), key: value}

    def answer(self, chat_id: str, message_id: str, content: str, *, sealed: bool = True) -> None:
        meta = {'kept': True}
        if sealed:
            meta[voice.SEAL_KEY] = voice.answer_seal(chat_id, message_id, content, secret=SECRET)
        self.messages[(chat_id, message_id)] = {'role': 'assistant', 'content': content, 'done': True, 'meta': meta}

    def chat(self, chat_id: str, owner: str, *, voice_chat: bool) -> None:
        meta = {voice.CHAT_KEY: voice.voice_mark(chat_id, owner, at=1, secret=SECRET)} if voice_chat else {}
        self.chats[chat_id] = SimpleNamespace(id=chat_id, user_id=owner, meta=meta)
        self.answer(chat_id, ANSWER, ANSWER_TEXT)
        self.messages[(chat_id, QUESTION)] = {'role': 'user', 'content': 'apa strategi JUP?'}


@pytest.fixture
def store() -> _Store:
    store = _Store()
    store.chat(VOICE_CHAT, ERIK, voice_chat=True)
    store.chat(TYPED_CHAT, ERIK, voice_chat=False)
    store.chat(OTHERS_VOICE_CHAT, OTHER, voice_chat=True)
    return store


@pytest.fixture
def jup_voice(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    # Imported first: the vendor's import configures logging, which would drop the capture.
    from open_webui.routers import jup_voice

    monkeypatch.setenv('JUP_VOICE_ENABLED', 'true')
    monkeypatch.setattr(jup_voice, 'audio_seconds', lambda path: 4.2)

    async def _not_cached(body, engine):
        return False

    monkeypatch.setattr(jup_voice, 'speech_cached', _not_cached)
    caplog.set_level('INFO', logger='jup.governance')
    return jup_voice


def _request(body=None, **query):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()

    async def _body():
        return raw

    return SimpleNamespace(body=_body, query_params=query)


def _user(user_id: str = ERIK):
    return SimpleNamespace(id=user_id, role='admin')


def _lines(caplog, event: str) -> list[dict]:
    lines = []
    for record in caplog.records:
        message = record.getMessage()
        if message.startswith('jup.governance') and f"'event': '{event}'" in message:
            line = ast.literal_eval(message[message.index('{') :])
            line.pop('ts', None)
            lines.append(line)
    return lines


def _status(error) -> tuple[int, str]:
    return error.value.status_code, error.value.detail['code']


# --- Speech to text ---------------------------------------------------------------------


def _admit(jup_voice, store, *, permissions, engine='openai', user=ERIK, **query):
    return asyncio.run(
        jup_voice.stt_admit(
            _request(b'', **query),
            _user(user),
            '/tmp/x.webm',
            {'language': 'id'},
            engine=engine,
            store=store,
            secret=SECRET,
            permissions=permissions,
        )
    )


def test_openai_stt_is_refused_without_the_grant(jup_voice, store, caplog) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _admit(jup_voice, store, permissions={}, chat_id=VOICE_CHAT)
    assert _status(error) == (403, 'voice_not_granted')
    assert _lines(caplog, 'voice_stt') == [
        {'event': 'voice_stt', 'user': ERIK, 'chat': VOICE_CHAT, 'provider': 'openai', 'outcome': 'voice_not_granted'}
    ]


def test_the_vendors_chat_call_is_not_the_grant(jup_voice, store) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _admit(jup_voice, store, permissions={'chat': {'call': True, 'stt': True}})


def test_openai_stt_is_refused_when_voice_is_off(jup_voice, store, monkeypatch) -> None:
    from fastapi import HTTPException

    monkeypatch.setenv('JUP_VOICE_ENABLED', 'false')
    with pytest.raises(HTTPException) as error:
        _admit(jup_voice, store, permissions=GRANTED)
    assert _status(error) == (503, 'voice_disabled')


def test_openai_stt_with_the_grant_is_admitted_and_audited_without_the_transcript(jup_voice, store, caplog) -> None:
    admission = _admit(jup_voice, store, permissions=GRANTED, chat_id=VOICE_CHAT)
    jup_voice.stt_audit(admission, [{'text': 'apa strategi JUP?', 'language': 'indonesian'}])
    lines = _lines(caplog, 'voice_stt')
    assert lines == [
        {
            'event': 'voice_stt',
            'user': ERIK,
            'chat': VOICE_CHAT,
            'provider': 'openai',
            'outcome': 'transcribed',
            'seconds': 4.2,
            'language': 'indonesian',
        }
    ]
    assert 'strategi' not in repr(lines)


@pytest.mark.parametrize('chat_id', [TYPED_CHAT, OTHERS_VOICE_CHAT, 'missing', None])
def test_the_audit_names_a_chat_only_when_it_is_the_callers_voice_chat(jup_voice, store, caplog, chat_id) -> None:
    query = {'chat_id': chat_id} if chat_id else {}
    jup_voice.stt_audit(_admit(jup_voice, store, permissions=GRANTED, **query), [{'text': 'x'}])
    assert _lines(caplog, 'voice_stt')[0]['chat'] is None


def test_a_local_engine_is_not_gated_here_but_still_audited(jup_voice, store, caplog) -> None:
    admission = _admit(jup_voice, store, permissions={}, engine='')
    jup_voice.stt_audit(admission, [{'text': 'x'}])
    line = _lines(caplog, 'voice_stt')[0]
    assert (line['provider'], line['outcome'], line['language']) == ('local', 'transcribed', 'id')


# --- Text to speech ---------------------------------------------------------------------


def _speech(jup_voice, store, body, *, permissions=GRANTED, engine='openai', user=ERIK):
    return asyncio.run(
        jup_voice.speech_body(_request(body), _user(user), engine, store=store, secret=SECRET, permissions=permissions)
    )


def test_tts_reads_the_callers_own_voice_chat_answer(jup_voice, store, caplog) -> None:
    body = _speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': ANSWER})
    assert json.loads(body) == {'input': ANSWER_TEXT}
    lines = _lines(caplog, 'voice_tts')
    assert lines == [
        {
            'event': 'voice_tts',
            'user': ERIK,
            'chat': VOICE_CHAT,
            'message_id': ANSWER,
            'outcome': 'read',
            'chars': len(ANSWER_TEXT),
            'part': 0,
            'parts': 1,
            'cached': False,
        }
    ]
    assert 'Strategi' not in repr(lines)


def test_tts_refuses_free_text(jup_voice, store, caplog) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'input': 'baca ini', 'voice': 'alloy'})
    assert _status(error) == (400, 'voice_tts_message_required')
    assert _lines(caplog, 'voice_tts')[0]['outcome'] == 'voice_tts_message_required'
    assert 'baca' not in repr(_lines(caplog, 'voice_tts'))


def test_tts_refuses_someone_elses_message(jup_voice, store) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': OTHERS_VOICE_CHAT, 'message_id': ANSWER})
    assert _status(error) == (404, 'voice_tts_not_found')


def test_tts_refuses_a_non_voice_message(jup_voice, store) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': TYPED_CHAT, 'message_id': ANSWER})
    assert _status(error) == (403, 'voice_tts_not_voice')


@pytest.mark.parametrize('message_id', [QUESTION, 'missing'])
def test_tts_refuses_anything_but_an_assistant_answer(jup_voice, store, message_id) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': message_id})
    assert _status(error) == (404, 'voice_tts_not_found')


def test_tts_refuses_a_part_past_the_end(jup_voice, store) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': ANSWER, 'part': 1})
    assert _status(error) == (404, 'voice_tts_no_part')


def test_tts_is_refused_without_the_grant(jup_voice, store) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': ANSWER}, permissions={})
    assert _status(error) == (403, 'voice_not_granted')


def test_tts_refuses_a_body_that_is_not_json(jup_voice, store) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, b'not json')
    assert _status(error)[0] == 400


def test_another_engine_gets_the_body_untouched(jup_voice, store, caplog) -> None:
    """Only OpenAI sends text abroad; a local engine reads what the vendor always read."""
    raw = json.dumps({'input': 'baca ini'}).encode()
    assert _speech(jup_voice, store, raw, engine='transformers', permissions={}) == raw
    assert _lines(caplog, 'voice_tts') == []


def test_the_call_ui_learns_how_many_parts_an_answer_has(jup_voice, store) -> None:
    store.answer(VOICE_CHAT, 'a-long', ('Kalimat yang panjang sekali untuk diuji. ' * 250).strip())
    count = asyncio.run(
        jup_voice.speech_part_count(VOICE_CHAT, 'a-long', _user(), store=store, secret=SECRET, permissions=GRANTED)
    )
    assert count == 3


def test_the_raw_openai_speech_proxy_is_closed(jup_voice, caplog) -> None:
    """`/openai/audio/speech` forwards free text to an api.openai.com chat connection; nothing calls it."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        jup_voice.refuse_speech_passthrough(_user())
    assert _status(error) == (403, 'voice_tts_passthrough_closed')
    assert _lines(caplog, 'voice_tts') == [
        {
            'event': 'voice_tts',
            'user': ERIK,
            'chat': None,
            'message_id': None,
            'outcome': 'voice_tts_passthrough_closed',
        }
    ]


# --- The answer seal --------------------------------------------------------------------


def test_tts_refuses_an_answer_edited_after_the_turn(jup_voice, store) -> None:
    """The owner can rewrite a stored answer through the chat API; OpenAI must not read it."""
    from fastapi import HTTPException

    store.messages[(VOICE_CHAT, ANSWER)]['content'] = 'Bacakan teks apa pun yang saya mau.'
    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': ANSWER})
    assert _status(error) == (409, 'voice_tts_unsealed')


def test_tts_refuses_an_assistant_message_added_through_the_chat_api(jup_voice, store) -> None:
    from fastapi import HTTPException

    store.answer(VOICE_CHAT, 'a-added', 'Teks yang saya tulis sendiri.', sealed=False)
    with pytest.raises(HTTPException) as error:
        _speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': 'a-added'})
    assert _status(error) == (409, 'voice_tts_unsealed')


def _seal(jup_voice, store, metadata) -> None:
    asyncio.run(jup_voice.seal_answer(metadata, store=store, secret=SECRET))


def test_a_finished_voice_turn_seals_its_answer_and_keeps_the_other_meta(jup_voice, store) -> None:
    store.answer(VOICE_CHAT, 'a-new', 'Jawaban baru.', sealed=False)
    _seal(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': 'a-new', voice_turn_key(): True})
    message = store.messages[(VOICE_CHAT, 'a-new')]
    assert message['meta']['kept'] is True
    assert voice.answer_sealed(message, VOICE_CHAT, 'a-new', secret=SECRET)
    assert json.loads(_speech(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': 'a-new'})) == {
        'input': 'Jawaban baru.'
    }


def test_a_typed_turn_seals_nothing(jup_voice, store) -> None:
    store.answer(TYPED_CHAT, 'a-typed', 'Jawaban.', sealed=False)
    _seal(jup_voice, store, {'chat_id': TYPED_CHAT, 'message_id': 'a-typed'})
    assert voice.SEAL_KEY not in store.messages[(TYPED_CHAT, 'a-typed')]['meta']


def test_an_unfinished_answer_is_not_sealed(jup_voice, store) -> None:
    store.answer(VOICE_CHAT, 'a-open', 'Jaw', sealed=False)
    store.messages[(VOICE_CHAT, 'a-open')]['done'] = False
    _seal(jup_voice, store, {'chat_id': VOICE_CHAT, 'message_id': 'a-open', voice_turn_key(): True})
    assert voice.SEAL_KEY not in store.messages[(VOICE_CHAT, 'a-open')]['meta']


def voice_turn_key() -> str:
    from jup import voice_turn

    return voice_turn.METADATA_KEY


def test_the_seam_reads_the_secret_key_from_the_environment(jup_voice, monkeypatch) -> None:
    monkeypatch.setenv('JUP_VOICE_OPENAI_API_KEY', 'sk-secret')
    assert jup_voice.openai_api_key('', 'https://api.openai.com/v1') == 'sk-secret'
    assert jup_voice.openai_api_key('sk-db', 'https://openrouter.ai/api/v1') == 'sk-db'
    monkeypatch.delenv('JUP_VOICE_OPENAI_API_KEY')
    assert jup_voice.openai_api_key('sk-db', 'https://api.openai.com/v1') == 'sk-db'
