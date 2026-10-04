"""The Channel Turn, through its one entry point, with a fake turn runner, chat store and clock (E7.2, #86).

What a caller of `jup.channel` observes: the reply text and the chat link it gets back, the chat it
created, the request state the turn ran with (that is what makes an `external` tool fail closed),
and the one audit line. The grant and the request shape are tested here too, as the route's inputs.

`jup.channel` imports the standard library and `jup.*` only, so this runs under `--only-group dev`.
"""

import datetime as dt
import json
from types import SimpleNamespace

import pytest

from jup import channel
from jup.governance import CHANNEL_TURN_STATE_ATTR
from jup.tool_policy import CHANNEL_TURN, decide, path_of
from jup.turn import TurnResult

IDENTITY = 'a' * 64
NOW = dt.datetime(2026, 10, 4, 9, 30, tzinfo=dt.UTC)  # 16:30 in Jakarta


def body(**overrides) -> dict:
    return {
        'channel': 'teams',
        'identity_hash': IDENTITY,
        'conversation_key': 'k' * 64,
        'text': 'status proyek SPBG?',
        'has_attachment': False,
        **overrides,
    }


class FakeStore:
    def __init__(self) -> None:
        self.chats: list[dict] = []

    async def create_chat(self, chat_id: str, user_id: str, title: str, meta: dict) -> None:
        self.chats.append({'id': chat_id, 'user_id': user_id, 'title': title, 'meta': meta})


class FakeRunner:
    """Stands in for `jup.turn.run_turn` bound to Asisten JUP's defaults; records what it was asked."""

    def __init__(self, result: TurnResult | Exception) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def __call__(self, chat_id: str, text: str, request_state: dict) -> TurnResult:
        self.calls.append({'chat_id': chat_id, 'text': text, 'request_state': request_state})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class AuditLines:
    def __init__(self) -> None:
        self.lines: list[tuple[str, dict]] = []

    def __call__(self, event: str, **fields) -> None:
        self.lines.append((event, fields))


async def turn(result=None, request=None, **kwargs):
    store, audit = FakeStore(), AuditLines()
    runner = FakeRunner(result if result is not None else TurnResult('m1', 'Proyek SPBG on track.', True))
    reply = await channel.run_channel_turn(
        user_id='u-erik',
        request=request or channel.parse_request(body()),
        store=store,
        run=runner,
        base_url='https://non-jupe.jup.co.id/',
        audit=audit,
        now=lambda: NOW,
        **kwargs,
    )
    return reply, store, runner, audit


# --- the grant ------------------------------------------------------------------------------------


def test_the_grant_defaults_to_false():
    assert channel.DEFAULT_PERMISSIONS == {'jup': {'channel': {'use': False}}}
    assert channel.may_use_channel(channel.DEFAULT_PERMISSIONS) is False


@pytest.mark.parametrize('value', [True])
def test_only_an_exact_true_grants_it(value):
    assert channel.may_use_channel({'jup': {'channel': {'use': value}}}) is True


@pytest.mark.parametrize(
    'permissions', [{'jup': {'channel': {'use': 1}}}, {'jup': {'channel': {'use': 'true'}}}, {}, None]
)
def test_anything_else_does_not(permissions):
    assert channel.may_use_channel(permissions) is False


# --- the request shape ----------------------------------------------------------------------------


def test_a_well_formed_body_parses():
    request = channel.parse_request(body(text='  halo  ', has_attachment=True))

    assert request == channel.ChannelTurnRequest(
        channel='teams', identity_hash=IDENTITY, conversation_key='k' * 64, text='halo', has_attachment=True
    )


@pytest.mark.parametrize(
    'bad',
    [
        body(channel='slack'),
        body(channel=None),
        body(identity_hash='erik@axiara.ai'),
        body(identity_hash='A' * 64),
        body(identity_hash='a' * 63),
        body(conversation_key=''),
        body(conversation_key='k' * 513),
        body(text=''),
        body(text='   '),
        body(text='x' * (channel.TEXT_MAX_CHARS + 1)),
        body(text=7),
        body(has_attachment='yes'),
        {k: v for k, v in body().items() if k != 'has_attachment'},
        body(extra='field'),
        [],
        None,
    ],
)
def test_a_malformed_body_is_refused(bad):
    with pytest.raises(channel.ChannelRequestInvalid):
        channel.parse_request(bad)


# --- the turn -------------------------------------------------------------------------------------


async def test_the_answer_text_and_the_chat_link_come_back():
    reply, store, _, _ = await turn()

    (chat,) = store.chats
    assert reply == channel.ChannelReply(
        reply='Proyek SPBG on track.',
        chat_url=f'https://non-jupe.jup.co.id/c/{chat["id"]}',
        outcome='answered',
    )


async def test_each_turn_runs_in_a_new_chat_of_the_user_marked_with_its_channel():
    reply, store, runner, _ = await turn()

    (chat,) = store.chats
    assert chat['user_id'] == 'u-erik'
    assert chat['title'] == 'Teams · 2026-10-04 16:30'
    assert chat['meta'][channel.CHAT_KEY]['channel'] == 'teams'
    assert chat['meta'][channel.CHAT_KEY]['identity_hash'] == IDENTITY
    assert runner.calls[0]['chat_id'] == chat['id']
    assert runner.calls[0]['text'] == 'status proyek SPBG?'


async def test_the_turn_runs_marked_as_a_channel_turn_so_an_external_tool_is_refused():
    _, _, runner, _ = await turn()

    state = SimpleNamespace(**runner.calls[0]['request_state'])
    path = path_of({'chat_id': runner.calls[0]['chat_id']}, state)
    assert path == CHANNEL_TURN
    ruling = decide('gate_probe', {'tool_id': 'gate_probe', 'risk_class': 'external'}, path=path)
    assert not ruling.runs
    assert ruling.approval == 'rejected_unattended'
    assert runner.calls[0]['request_state'] == {CHANNEL_TURN_STATE_ATTR: 'teams'}


async def test_one_audit_line_with_the_hashes_and_never_an_email():
    _, store, _, audit = await turn()

    ((event, fields),) = audit.lines
    assert event == 'channel_turn'
    assert fields == {
        'channel': 'teams',
        'identity_hash': IDENTITY,
        'conversation': channel.hash_key('k' * 64),
        'chat': store.chats[0]['id'],
        'outcome': 'answered',
        'reason': None,
    }
    assert '@' not in json.dumps(audit.lines)
    assert 'k' * 64 not in json.dumps(audit.lines)


async def test_an_unfinished_answer_returns_the_link_and_the_turn_keeps_running():
    reply, store, _, audit = await turn(TurnResult('m1', '', False))

    link = f'https://non-jupe.jup.co.id/c/{store.chats[0]["id"]}'
    assert reply == channel.ChannelReply(
        reply=f'Jawaban masih diproses — lihat di {link}', chat_url=link, outcome='processing'
    )
    assert audit.lines[0][1]['outcome'] == 'processing'


async def test_a_failed_turn_is_raised_for_the_route_to_answer_with_one_failed_audit_line():
    store, audit = FakeStore(), AuditLines()
    with pytest.raises(RuntimeError):
        await channel.run_channel_turn(
            user_id='u-erik',
            request=channel.parse_request(body()),
            store=store,
            run=FakeRunner(RuntimeError('boom')),
            base_url='https://non-jupe.jup.co.id',
            audit=audit,
            now=lambda: NOW,
        )

    ((event, fields),) = audit.lines
    assert (event, fields['outcome'], fields['reason']) == ('channel_turn', 'failed', 'turn_error')


def test_the_conversation_key_hash_is_stable_and_not_the_key():
    assert channel.hash_key('abc') == channel.hash_key('abc')
    assert channel.hash_key('abc') != channel.hash_key('abd')
    assert 'abc' not in channel.hash_key('abc')


async def test_a_chat_that_cannot_be_created_is_audited_as_failed_and_no_turn_runs():
    class Broken(FakeStore):
        async def create_chat(self, *args):
            raise RuntimeError('insert failed')

    audit, runner = AuditLines(), FakeRunner(TurnResult('m1', 'x', True))
    with pytest.raises(RuntimeError):
        await channel.run_channel_turn(
            user_id='u-erik',
            request=channel.parse_request(body()),
            store=Broken(),
            run=runner,
            base_url='https://non-jupe.jup.co.id',
            audit=audit,
            now=lambda: NOW,
        )

    assert runner.calls == []
    assert [fields['outcome'] for _, fields in audit.lines] == ['failed']
