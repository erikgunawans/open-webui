"""One server-side assistant turn, run and waited for (E7.1, #85).

Runs under `--only-group dev`: `jup.turn` imports the standard library only. The vendor's chat
pipeline, its request builder and the model-default resolver are all injected, so each test hands
in a fake handler that writes the assistant message the way the pipeline would.
"""

import asyncio
from types import SimpleNamespace

from jup import turn

CHAT = 'chat-1'
ERIK = 'user-erik'


class _Store:
    def __init__(self, chat=None) -> None:
        self.chat = chat
        self.messages: dict[tuple[str, str], dict] = {}

    async def get_chat(self, chat_id):
        return self.chat

    async def get_message(self, chat_id, message_id):
        return self.messages.get((chat_id, message_id))


def _history_chat() -> SimpleNamespace:
    return SimpleNamespace(
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


def _answering(store: _Store, content: str = 'Jawaban.', calls: list | None = None, done: bool = True):
    async def handler(request, form_data, user):
        if calls is not None:
            calls.append((request, form_data, user))
        store.messages[(CHAT, form_data['id'])] = {'role': 'assistant', 'content': content, 'done': done}

    return handler


def _run(store, handler, **kwargs) -> turn.TurnResult:
    params = dict(
        user=SimpleNamespace(id=ERIK),
        chat_id=CHAT,
        text='Apa status SPBG?',
        model_id='asisten-jup',
        store=store,
        handler=handler,
        build_request=lambda: SimpleNamespace(state=SimpleNamespace()),
        poll_seconds=0.01,
    )
    params.update(kwargs)
    return asyncio.run(turn.run_turn(**params))


def test_a_turn_continues_the_chat_and_returns_the_finished_answer() -> None:
    store, calls = _Store(_history_chat()), []
    result = _run(store, _answering(store, 'Proyek masih di G1.', calls), session_id='channel:abc')

    assert result.finished and result.content == 'Proyek masih di G1.'
    _, form, user = calls[0]
    assert user.id == ERIK
    assert form['model'] == 'asisten-jup' and form['chat_id'] == CHAT and form['id'] == result.message_id
    assert form['parent_id'] == 'a0' and form['user_message']['parentId'] == 'a0'
    assert form['user_message']['content'] == 'Apa status SPBG?'
    assert form['user_message']['models'] == ['asisten-jup']
    assert form['session_id'] == 'channel:abc'
    assert form['messages'] == [
        {'role': 'user', 'content': 'Halo'},
        {'role': 'assistant', 'content': 'Halo juga.'},
        {'role': 'user', 'content': 'Apa status SPBG?'},
    ]


def test_a_new_chat_has_no_parent_and_only_the_question() -> None:
    store, calls = _Store(None), []
    _run(store, _answering(store, calls=calls))
    form = calls[0][1]
    assert form['parent_id'] is None and form['messages'] == [{'role': 'user', 'content': 'Apa status SPBG?'}]


def test_the_context_carries_at_most_the_last_n_messages() -> None:
    store, calls = _Store(_history_chat()), []
    _run(store, _answering(store, calls=calls), context_messages=1)
    assert calls[0][1]['messages'] == [
        {'role': 'assistant', 'content': 'Halo juga.'},
        {'role': 'user', 'content': 'Apa status SPBG?'},
    ]


def test_model_defaults_are_sent_and_empty_ones_are_left_out() -> None:
    store, calls = _Store(), []
    defaults = turn.TurnDefaults(tool_ids=('jup_documents',), features={'web_search': True})
    _run(store, _answering(store, calls=calls), defaults=defaults)
    form = calls[0][1]
    assert form['tool_ids'] == ['jup_documents'] and form['features'] == {'web_search': True}
    assert 'filter_ids' not in form and 'terminal_id' not in form


def test_request_state_is_set_on_the_built_request() -> None:
    store, calls = _Store(), []
    _run(store, _answering(store, calls=calls), request_state={'jup_turn_path': 'channel_turn'})
    assert calls[0][0].state.jup_turn_path == 'channel_turn'


def test_a_turn_past_the_time_limit_is_not_finished_and_keeps_its_message_id() -> None:
    store, calls = _Store(), []
    result = _run(store, _answering(store, done=False, calls=calls), wait_seconds=0.05)
    assert not result.finished and result.content == ''
    assert result.message_id == calls[0][1]['id']


def test_an_answer_the_caller_does_not_accept_is_never_finished() -> None:
    store = _Store()
    result = _run(store, _answering(store), wait_seconds=0.05, accept=lambda message, message_id: False)
    assert not result.finished


def test_defaults_come_from_the_injected_resolver() -> None:
    async def resolver(app, model_id):
        assert model_id == 'asisten-jup'
        return ['jup_documents'], {'web_search': True}, ['f1'], 'term-1'

    defaults = asyncio.run(turn.resolve_defaults(object(), 'asisten-jup', resolver=resolver))
    assert defaults == turn.TurnDefaults(
        tool_ids=('jup_documents',), features={'web_search': True}, filter_ids=('f1',), terminal_id='term-1'
    )


def test_an_answer_that_ended_in_an_error_stops_the_wait_at_once() -> None:
    store = _Store()

    async def handler(request, form_data, user):
        store.messages[(CHAT, form_data['id'])] = {
            'role': 'assistant',
            'content': '',
            'done': True,
            'error': {'content': 'OpenRouter could not verify available credits for this request in time.'},
        }

    result = _run(store, handler, wait_seconds=30)
    assert not result.finished and result.content == ''
    assert result.error == 'OpenRouter could not verify available credits for this request in time.'


def test_an_error_beside_an_answer_or_before_done_is_not_a_failure() -> None:
    assert turn.message_error({'done': True, 'content': 'Jawaban.', 'error': {'content': 'x'}}) is None
    assert turn.message_error({'done': False, 'content': '', 'error': {'content': 'x'}}) is None
    assert turn.message_error({'done': True, 'content': ''}) is None
    assert turn.message_error({'done': True, 'content': '', 'error': 'plain'}) == 'plain'
