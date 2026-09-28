"""#36: the GPT-Live relay — delegations answered with the governed answer, speech recorded.

The sideband, the governed turn and the store are faked; the real ledger, commentary parts, voice
seal and audit lines run. `open_webui.routers.jup_voice_live` imports only `jup` and the standard
library at module level, so this runs under `--only-group dev`.
"""

import asyncio
import ast
import json
from types import SimpleNamespace

import pytest

from jup import voice
from open_webui.routers import jup_voice_live

SECRET = 'test-secret'
ERIK = 'user-erik'
CHAT = 'chat-voice'
SESSION = 'live_123'


@pytest.fixture(autouse=True)
def _fast(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(jup_voice_live, 'SETTLE_SECONDS', 0)
    caplog.set_level('INFO', logger='jup.governance')


def _lines(caplog, event: str) -> list[dict]:
    lines = []
    for record in caplog.records:
        message = record.getMessage()
        if message.startswith('jup.governance') and f"'event': '{event}'" in message:
            line = ast.literal_eval(message[message.index('{') :])
            line.pop('ts', None)
            lines.append(line)
    return lines


class _Store:
    def __init__(self) -> None:
        self.message_meta: dict[tuple[str, str], dict] = {}
        self.chat_meta: dict[str, list] = {}
        self.messages: dict[tuple[str, str], dict] = {}
        self.chat = SimpleNamespace(chat={'history': {'currentId': None, 'messages': {}}})

    async def set_message_meta_key(self, chat_id, message_id, key, value) -> None:
        self.message_meta[(chat_id, message_id)] = {key: value}

    async def append_chat_meta_items(self, chat_id, key, items) -> None:
        self.chat_meta.setdefault(chat_id, []).extend(items)

    async def get_chat(self, chat_id):
        return self.chat

    async def get_message(self, chat_id, message_id):
        return self.messages.get((chat_id, message_id))


def _relay(answers=None, fail=False):
    sent: list[dict] = []
    asked: list[str] = []

    async def ask(question):
        asked.append(question)
        if fail:
            raise RuntimeError('pipeline down')
        return (answers or {}).get(question, ('m-1', 'Proyek SPBG masih di gerbang G1.'))

    async def send(event):
        sent.append(event)

    relay = jup_voice_live.LiveRelay(session_id=SESSION, user_id=ERIK, chat_id=CHAT, ask=ask, send=send)
    return relay, sent, asked


def _events(relay, events):
    async def run():
        for event in events:
            await relay.on_event(event)
        await relay.drain()

    asyncio.run(run())


HEARD = {'type': 'session.input_transcript.delta', 'delta': 'Apa status SPBG?', 'start_ms': 100, 'end_ms': 900}
DELEGATION = {
    'type': 'session.delegation.created',
    'offset_ms': 1000,
    'delegation': {'id': 'd1', 'type': 'delegation', 'target': 'client'},
}


def test_a_delegation_is_answered_with_the_governed_answer(caplog) -> None:
    relay, sent, asked = _relay()
    _events(relay, [HEARD, DELEGATION])
    assert asked == ['Apa status SPBG?']
    assert [(e['type'], e['delegation_id'], e['content']) for e in sent] == [
        ('session.commentary.append', 'd1', 'Proyek SPBG masih di gerbang G1.')
    ]
    line = _lines(caplog, 'voice_live_delegation')[0]
    assert line['outcome'] == 'relayed' and line['message_id'] == 'm-1' and line['chars'] == 32
    assert 'SPBG' not in repr(_lines(caplog, 'voice_live_delegation'))


def test_a_long_answer_goes_in_parts_under_the_same_delegation() -> None:
    long = ('Kalimat yang cukup panjang untuk diuji. ' * 100).strip()
    relay, sent, _ = _relay({'Apa status SPBG?': ('m-1', long)})
    _events(relay, [HEARD, DELEGATION])
    assert len(sent) > 1 and {e['delegation_id'] for e in sent} == {'d1'}
    assert ' '.join(e['content'] for e in sent) == long


def test_a_delegation_with_no_question_asks_the_caller_again(caplog) -> None:
    relay, sent, asked = _relay()
    _events(relay, [DELEGATION])
    assert asked == []
    assert sent[0]['content'] == jup_voice_live.ASK_AGAIN
    assert _lines(caplog, 'voice_live_delegation')[0]['outcome'] == 'no_question'


def test_a_failed_governed_turn_says_so_rather_than_guessing(caplog) -> None:
    relay, sent, _ = _relay(fail=True)
    _events(relay, [HEARD, DELEGATION])
    assert [e['content'] for e in sent] == [jup_voice_live.NO_ANSWER]
    assert _lines(caplog, 'voice_live_delegation')[0]['outcome'] == 'failed'


def test_a_delegation_for_another_target_is_not_ours() -> None:
    relay, sent, asked = _relay()
    other = {**DELEGATION, 'delegation': {'id': 'd1', 'type': 'delegation', 'target': 'responses'}}
    _events(relay, [HEARD, other])
    assert asked == [] and sent == []


def test_the_record_puts_speech_on_the_answer_and_self_answers_on_the_chat(caplog) -> None:
    relay, _, _ = _relay()
    store = _Store()
    _events(
        relay,
        [
            {'type': 'session.output_transcript.delta', 'delta': 'Halo, Pak Erik.', 'start_ms': 0, 'end_ms': 50},
            HEARD,
            DELEGATION,
            {
                'type': 'session.output_transcript.delta',
                'delta': 'Proyek masih di G1.',
                'start_ms': 1500,
                'end_ms': 2500,
            },
        ],
    )
    turns = asyncio.run(relay.record(store))
    assert [t['kind'] for t in turns] == ['self_answered', 'relayed']
    assert store.message_meta[(CHAT, 'm-1')] == {
        'jup_voice_live': [{'session': SESSION, 'delegation': 'd1', 'spoken': 'Proyek masih di G1.'}]
    }
    assert store.chat_meta[CHAT] == [
        {'session': SESSION, 'delegation': None, 'spoken': 'Halo, Pak Erik.', 'kind': 'self_answered'}
    ]
    lines = _lines(caplog, 'voice_live_turn')
    assert [(line['kind'], line['spoken_chars']) for line in lines] == [('self_answered', 15), ('relayed', 19)]
    assert 'Halo' not in repr(lines)


# --- The sideband loop ------------------------------------------------------------------------


class _Socket:
    def __init__(self, events) -> None:
        self._events = [SimpleNamespace(data=json.dumps(e)) for e in events]
        self.sent: list[dict] = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0)
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)

    async def send_str(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def close(self) -> None:
        self.closed = True


def test_the_sideband_attaches_with_the_key_answers_and_records(caplog) -> None:
    socket = _Socket([HEARD, DELEGATION])
    seen = {}

    async def connect(url, headers):
        seen.update(url=url, headers=headers)
        return socket

    relay, _, _ = _relay()
    store = _Store()
    asyncio.run(jup_voice_live.run_sideband(relay, 'sk-live', store=store, connect=connect))
    assert seen == {
        'url': 'wss://api.openai.com/v1/live/sessions/live_123/attach',
        'headers': {'Authorization': 'Bearer sk-live'},
    }
    types = [e['type'] for e in socket.sent]
    assert types == ['session.commentary.append', 'session.close'] and socket.closed
    outcomes = [line['outcome'] for line in _lines(caplog, 'voice_live')]
    assert outcomes == ['attached', 'ended']


def test_a_failed_attach_is_audited_and_the_call_still_ends_cleanly(caplog) -> None:
    async def connect(url, headers):
        raise OSError('refused')

    relay, _, _ = _relay()
    asyncio.run(jup_voice_live.run_sideband(relay, 'sk-live', store=_Store(), connect=connect))
    assert [line['outcome'] for line in _lines(caplog, 'voice_live')] == ['sideband_failed', 'ended']


def test_a_cancelled_call_still_writes_its_record(caplog) -> None:
    """The browser going away cancels the request; the record must still be written."""

    class _Endless(_Socket):
        async def __anext__(self):
            if self._events:
                return self._events.pop(0)
            await asyncio.sleep(3600)

    socket = _Endless([{'type': 'session.output_transcript.delta', 'delta': 'Halo.', 'start_ms': 0, 'end_ms': 10}])

    async def connect(url, headers):
        return socket

    relay, _, _ = _relay()
    store = _Store()

    async def run():
        task = asyncio.create_task(jup_voice_live.run_sideband(relay, 'sk-live', store=store, connect=connect))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.05)

    asyncio.run(run())
    assert store.chat_meta[CHAT][0]['spoken'] == 'Halo.'
    assert _lines(caplog, 'voice_live')[-1]['outcome'] == 'ended'


# --- The governed turn -------------------------------------------------------------------------


def test_a_live_turn_runs_the_voice_pipeline_and_returns_the_sealed_answer() -> None:
    store = _Store()
    store.chat = SimpleNamespace(
        chat={
            'history': {
                'currentId': 'a0',
                'messages': {
                    'q0': {'role': 'user', 'content': 'Halo', 'parentId': None},
                    'a0': {'role': 'assistant', 'content': 'Halo juga.', 'parentId': 'q0'},
                },
            }
        }
    )
    calls = []

    async def handler(request, form_data, user):
        calls.append(form_data)
        content = 'Proyek masih di G1.'
        message_id = form_data['id']
        store.messages[(CHAT, message_id)] = {
            'role': 'assistant',
            'content': content,
            'done': True,
            'meta': {voice.SEAL_KEY: voice.answer_seal(CHAT, message_id, content, secret=SECRET)},
        }

    app = SimpleNamespace(state=SimpleNamespace())
    message_id, answer = asyncio.run(
        jup_voice_live.live_turn(
            app,
            SimpleNamespace(id=ERIK),
            CHAT,
            'Apa status SPBG?',
            store=store,
            secret=SECRET,
            handler=handler,
            build_request=lambda app: None,
        )
    )
    assert answer == 'Proyek masih di G1.'
    form = calls[0]
    assert form['model'] == voice.VOICE_MODEL_ID and form['chat_id'] == CHAT and form['id'] == message_id
    assert form['parent_id'] == 'a0' and form['user_message']['parentId'] == 'a0'
    assert form['user_message']['content'] == 'Apa status SPBG?'
    assert form['messages'] == [
        {'role': 'user', 'content': 'Halo'},
        {'role': 'assistant', 'content': 'Halo juga.'},
        {'role': 'user', 'content': 'Apa status SPBG?'},
    ]


def test_an_unsealed_answer_is_never_relayed() -> None:
    store = _Store()

    async def handler(request, form_data, user):
        store.messages[(CHAT, form_data['id'])] = {'role': 'assistant', 'content': 'Tebakan.', 'done': True, 'meta': {}}

    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(TimeoutError):
        asyncio.run(
            jup_voice_live.live_turn(
                app,
                SimpleNamespace(id=ERIK),
                CHAT,
                'Apa status SPBG?',
                store=store,
                secret=SECRET,
                handler=handler,
                build_request=lambda app: None,
                wait_seconds=0.05,
                poll_seconds=0.01,
            )
        )


def test_the_vendor_internals_the_relay_leans_on_still_exist() -> None:
    """A live turn runs through the vendor's own chat handler; an upstream rename must fail here, not in a call."""
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui'
    automations = (backend / 'utils' / 'automations.py').read_text(encoding='utf-8')
    main = (backend / 'main.py').read_text(encoding='utf-8')
    assert 'def _build_request(\n    app,\n    token: Optional[str] = None,\n) -> Request:' in automations
    assert 'app.state.CHAT_COMPLETION_HANDLER = ' in main
    assert 'jup_voice_turn = await jup_voice.enforce_voice_turn(form_data, user)' in main


def test_two_quick_delegations_run_their_governed_turns_one_after_the_other() -> None:
    """Both would otherwise branch from the same last message and fork the voice chat."""
    running = {'now': 0, 'most': 0}

    async def ask(question):
        running['now'] += 1
        running['most'] = max(running['most'], running['now'])
        await asyncio.sleep(0.02)
        running['now'] -= 1
        return ('m-' + question[-2], 'Jawaban.')

    async def send(event):
        pass

    relay = jup_voice_live.LiveRelay(session_id=SESSION, user_id=ERIK, chat_id=CHAT, ask=ask, send=send)
    second_heard = {**HEARD, 'delta': 'Dan G1?', 'start_ms': 1100, 'end_ms': 1500}
    second = {**DELEGATION, 'offset_ms': 1600, 'delegation': {**DELEGATION['delegation'], 'id': 'd2'}}
    _events(relay, [HEARD, DELEGATION, second_heard, second])
    assert running['most'] == 1
