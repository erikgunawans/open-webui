"""The Channel Turn, through its one entry point, with a fake turn runner, chat store and clock (E7.2–E7.4, #86–#88).

What a caller of `jup.channel` observes: the reply text and the chat link it gets back, the chat it
created, the request state the turn ran with (that is what makes an `external` tool fail closed),
and the one audit line. The grant and the request shape are tested here too, as the route's inputs.

`jup.channel` imports the standard library and `jup.*` only, so this runs under `--only-group dev`.
"""

import asyncio
import datetime as dt
import json
from types import SimpleNamespace

import pytest

from jup import channel, office_floor
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
    """Chats as the vendor table keeps them; `updated_at` is set from the fake clock on create, and a
    test moves it to stand for later activity."""

    def __init__(self, clock=lambda: NOW) -> None:
        self.chats: list[dict] = []
        self.clock = clock
        #: chat id -> chat meta written by the floor (`jup.office_floor.mark_restricted`) during a turn.
        self.floor_meta: dict[str, object] = {}

    async def create_chat(self, chat_id: str, user_id: str, title: str, meta: dict) -> None:
        self.chats.append(
            {
                'id': chat_id,
                'user_id': user_id,
                'title': title,
                'meta': meta,
                'updated_at': int(self.clock().timestamp()),
                'archived': False,
            }
        )

    async def latest_chat(self, user_id: str, channel_id: str, conversation: str):
        mine = [
            chat
            for chat in self.chats
            if chat['user_id'] == user_id
            and not chat['archived']
            and chat['meta'].get(channel.CHAT_KEY, {}).get('channel') == channel_id
            and chat['meta'].get(channel.CHAT_KEY, {}).get('conversation') == conversation
        ]
        if not mine:
            return None
        newest = mine[-1]  # by creation, as the store orders them
        return channel.ChannelChat(id=newest['id'], updated_at=newest['updated_at'])

    async def turn_restricted(self, chat_id: str, message_id: str) -> bool:
        return office_floor.turn_restricted(self.floor_meta.get(chat_id), message_id)


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


async def turn(result=None, request=None, store=None, runner=None, audit=None, now=NOW, user_id='u-erik', **kwargs):
    store = store if store is not None else FakeStore()
    audit = audit if audit is not None else AuditLines()
    runner = runner or FakeRunner(result if result is not None else TurnResult('m1', 'Proyek SPBG on track.', True))
    reply = await channel.run_channel_turn(
        user_id=user_id,
        request=request or channel.parse_request(body()),
        store=store,
        run=runner,
        base_url='https://non-jupe.jup.co.id/',
        audit=audit,
        now=lambda: now,
        locks=kwargs.pop('locks', channel.ConversationLocks()),
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
        body(text='', has_attachment='yes'),
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


async def test_a_first_turn_runs_in_a_new_chat_of_the_user_marked_with_its_channel():
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
    audit = AuditLines()
    with pytest.raises(RuntimeError):
        await turn(runner=FakeRunner(RuntimeError('boom')), audit=audit)

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
        await turn(store=Broken(), runner=runner, audit=audit)

    assert runner.calls == []
    assert [fields['outcome'] for _, fields in audit.lines] == ['failed']


# --- the conversation (E7.3, #87) -------------------------------------------------------------------

LATER = dt.timedelta(hours=channel.REUSE_HOURS)


async def test_a_follow_up_within_eight_hours_lands_in_the_same_chat():
    _, store, _, _ = await turn()
    reply, store, runner, _ = await turn(store=store, now=NOW + LATER - dt.timedelta(seconds=1))

    (chat,) = store.chats
    assert runner.calls[0]['chat_id'] == chat['id']
    assert reply.chat_url.endswith(f'/c/{chat["id"]}')


async def test_silence_is_counted_from_the_last_activity_not_from_the_chat_start():
    _, store, _, _ = await turn()
    store.chats[0]['updated_at'] = int((NOW + dt.timedelta(hours=7)).timestamp())  # a web-app follow-up
    _, store, _, _ = await turn(store=store, now=NOW + dt.timedelta(hours=14))

    assert len(store.chats) == 1


async def test_after_eight_hours_of_silence_a_new_chat_starts_with_its_title_and_channel_meta():
    _, store, _, _ = await turn()
    later = NOW + LATER
    _, store, runner, _ = await turn(store=store, now=later)

    first, second = store.chats
    assert runner.calls[0]['chat_id'] == second['id'] != first['id']
    assert second['title'] == 'Teams · 2026-10-05 00:30'
    assert second['meta'][channel.CHAT_KEY] == {
        'channel': 'teams',
        'identity_hash': IDENTITY,
        'conversation': channel.hash_key('k' * 64),
    }


async def test_another_conversation_or_channel_or_user_never_shares_a_chat():
    _, store, _, _ = await turn()
    await turn(store=store, request=channel.parse_request(body(conversation_key='other')))
    await turn(store=store, request=channel.parse_request(body(channel='whatsapp')))
    await turn(store=store, user_id='u-other')

    assert len(store.chats) == 4
    assert store.chats[2]['title'] == 'WhatsApp · 2026-10-04 16:30'


async def test_an_archived_chat_is_not_reused():
    _, store, _, _ = await turn()
    store.chats[0]['archived'] = True
    _, store, _, _ = await turn(store=store)

    assert len(store.chats) == 2


@pytest.mark.parametrize('text', ['baru', 'Baru', ' BARU '])
async def test_baru_starts_a_new_chat_and_never_calls_the_model(text):
    _, store, _, _ = await turn()
    reply, store, runner, audit = await turn(store=store, request=channel.parse_request(body(text=text)))

    first, second = store.chats
    assert runner.calls == []
    assert reply == channel.ChannelReply(
        reply=channel.NEW_CHAT_TEXT, chat_url=f'https://non-jupe.jup.co.id/c/{second["id"]}', outcome='new_chat'
    )
    assert audit.lines[0][1]['outcome'] == 'new_chat'
    assert audit.lines[0][1]['chat'] == second['id']


async def test_the_question_after_baru_lands_in_the_new_chat():
    _, store, _, _ = await turn()
    await turn(store=store, request=channel.parse_request(body(text='baru')))
    _, store, runner, _ = await turn(store=store)

    assert len(store.chats) == 2
    assert runner.calls[0]['chat_id'] == store.chats[1]['id']


async def test_after_baru_a_late_answer_in_the_old_chat_does_not_pull_the_conversation_back():
    _, store, _, _ = await turn()
    await turn(store=store, request=channel.parse_request(body(text='baru')))
    store.chats[0]['updated_at'] += 60  # the old chat's answer finishes after `baru`
    _, store, runner, _ = await turn(store=store)

    assert runner.calls[0]['chat_id'] == store.chats[1]['id']


@pytest.mark.parametrize('text', ['bantuan', 'baru saja', 'yang baru?', 'barus'])
async def test_any_other_word_is_a_normal_question(text):
    _, store, runner, _ = await turn(request=channel.parse_request(body(text=text)))

    assert runner.calls[0]['text'] == text.strip()


class GatedRunner:
    """A turn runner whose turns finish only when the test releases them, recording start order."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.gates: dict[str, asyncio.Event] = {}

    async def __call__(self, chat_id: str, text: str, request_state: dict) -> TurnResult:
        self.started.append(text)
        gate = self.gates.setdefault(text, asyncio.Event())
        await gate.wait()
        return TurnResult('m', f'jawaban: {text}', True)

    def release(self, text: str) -> None:
        self.gates.setdefault(text, asyncio.Event()).set()


async def settle() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


async def test_turns_of_one_conversation_run_one_after_another_in_arrival_order():
    store, runner, locks = FakeStore(), GatedRunner(), channel.ConversationLocks()

    def send(text: str):
        return asyncio.create_task(
            turn(store=store, runner=runner, locks=locks, request=channel.parse_request(body(text=text)))
        )

    first = send('satu')
    await settle()
    second, third = send('dua'), send('tiga')
    await settle()
    assert runner.started == ['satu']

    runner.release('dua')  # released early: still waits its turn
    runner.release('tiga')
    await settle()
    assert runner.started == ['satu']

    runner.release('satu')
    replies = [(await task)[0].reply for task in (first, second, third)]
    assert runner.started == ['satu', 'dua', 'tiga']
    assert replies == ['jawaban: satu', 'jawaban: dua', 'jawaban: tiga']
    assert len(store.chats) == 1
    assert len(locks) == 0


async def test_different_conversations_do_not_wait_for_each_other():
    store, runner, locks = FakeStore(), GatedRunner(), channel.ConversationLocks()
    blocked = asyncio.create_task(
        turn(store=store, runner=runner, locks=locks, request=channel.parse_request(body(text='lama')))
    )
    await settle()
    runner.release('cepat')
    other = await turn(
        store=store,
        runner=runner,
        locks=locks,
        request=channel.parse_request(body(text='cepat', conversation_key='other')),
    )

    assert other[0].reply == 'jawaban: cepat'
    assert not blocked.done()
    runner.release('lama')
    await blocked


async def test_a_failed_turn_releases_the_conversation_for_the_next():
    store, locks = FakeStore(), channel.ConversationLocks()
    with pytest.raises(RuntimeError):
        await turn(store=store, locks=locks, runner=FakeRunner(RuntimeError('boom')))
    reply, _, _, _ = await turn(store=store, locks=locks)

    assert reply.outcome == 'answered'
    assert len(locks) == 0


def test_the_lock_notes_that_it_assumes_one_ent_os_instance():
    assert 'one ent-os instance' in (channel.ConversationLocks.__doc__ or '')


# --- the reply's shape (E7.4, #88) ------------------------------------------------------------------


def restrict(store: FakeStore, message_id: str, *, level: str = 'TERBATAS') -> None:
    """What `mark_restricted` writes when a restricted read happens in the turn of `message_id`."""
    chat_id = store.chats[-1]['id']
    meta = store.floor_meta.get(chat_id) or {}
    record = office_floor.marked(meta, level, 'contracts', at=1, message_id=message_id)
    store.floor_meta[chat_id] = {**meta, office_floor.KEY: record} if record else meta


class RestrictingRunner(FakeRunner):
    """A turn whose tool read restricted material into the chat, as the contracts tool does."""

    def __init__(self, store: FakeStore, result: TurnResult) -> None:
        super().__init__(result)
        self.store = store

    async def __call__(self, chat_id, text, request_state):
        restrict(self.store, self.result.message_id)
        return await super().__call__(chat_id, text, request_state)


async def test_a_turn_that_read_restricted_material_replies_with_the_link_only():
    store = FakeStore()
    reply, store, _, audit = await turn(
        store=store, runner=RestrictingRunner(store, TurnResult('m1', 'Nilai kontrak Rp 9 M', True))
    )

    link = f'https://non-jupe.jup.co.id/c/{store.chats[0]["id"]}'
    assert reply == channel.ChannelReply(reply=link, chat_url=link, outcome='restricted')
    assert 'Rp' not in json.dumps(audit.lines)
    assert audit.lines[0][1]['outcome'] == 'restricted'


async def test_a_clean_turn_in_a_chat_restricted_earlier_still_arrives_as_text():
    store = FakeStore()
    await turn(store=store, runner=RestrictingRunner(store, TurnResult('m1', 'rahasia', True)))
    reply, _, _, _ = await turn(store=store, result=TurnResult('m2', 'Proyek SPBG on track.', True))

    assert (reply.reply, reply.outcome) == ('Proyek SPBG on track.', 'answered')


async def test_a_chat_marked_before_messages_were_listed_counts_as_restricted_earlier_only():
    store = FakeStore()
    await turn(store=store)
    store.floor_meta[store.chats[0]['id']] = {office_floor.KEY: {'level': 'TERBATAS', 'source': 'contracts', 'at': 1}}
    reply, _, _, _ = await turn(store=store, result=TurnResult('m2', 'teks', True))

    assert reply.outcome == 'answered'


@pytest.mark.parametrize(
    'meta',
    [
        'not an object',
        {office_floor.KEY: 'TERBATAS'},
        {office_floor.KEY: {'level': 'TERBATAS', office_floor.MESSAGES: 'm1'}},
    ],
)
async def test_an_unreadable_marker_replies_with_the_link_only(meta):
    store = FakeStore()
    await turn(store=store)
    store.floor_meta[store.chats[0]['id']] = meta
    reply, _, _, _ = await turn(store=store, result=TurnResult('m2', 'teks', True))

    assert (reply.reply, reply.outcome) == (reply.chat_url, 'restricted')


async def test_a_store_that_cannot_read_the_marker_replies_with_the_link_only():
    class Broken(FakeStore):
        async def turn_restricted(self, chat_id, message_id):
            raise RuntimeError('database unavailable')

    reply, _, _, _ = await turn(store=Broken())

    assert (reply.reply, reply.outcome) == (reply.chat_url, 'restricted')


LINK = 'https://non-jupe.jup.co.id/c/x'


def test_an_answer_at_the_limit_is_untouched():
    text = 'a' * channel.CUT_CHARS
    assert channel.cut(text, LINK) == text
    assert channel.cut('pendek', LINK) == 'pendek'


def test_a_long_answer_is_cut_at_the_last_paragraph_before_the_limit_and_links_to_the_rest():
    first, second = 'a' * 700, 'b' * 700
    text = f'{first}\n\n{second}\n\n' + 'c' * 200  # paragraph 3 crosses the limit

    assert channel.cut(text, LINK) == f'{first}\n\n{second}\n\nJawaban lengkap: {LINK}'


def test_one_char_over_the_limit_is_cut():
    text = 'a' * 1000 + '\n\n' + 'b' * (channel.CUT_CHARS - 1001)
    assert len(text) == channel.CUT_CHARS + 1
    assert channel.cut(text, LINK) == 'a' * 1000 + f'\n\nJawaban lengkap: {LINK}'


def test_without_a_paragraph_the_cut_falls_back_to_a_line_then_to_the_limit():
    lines = 'a' * 1000 + '\n' + 'b' * 1000
    assert channel.cut(lines, LINK) == 'a' * 1000 + f'\n\nJawaban lengkap: {LINK}'
    assert channel.cut('a' * 2000, LINK) == 'a' * channel.CUT_CHARS + f'\n\nJawaban lengkap: {LINK}'


async def test_a_long_answer_comes_back_cut_with_its_chat_link():
    long = 'a' * 1000 + '\n\n' + 'b' * 1000
    reply, store, _, _ = await turn(result=TurnResult('m1', long, True))

    assert reply.reply == 'a' * 1000 + f'\n\nJawaban lengkap: {reply.chat_url}'
    assert reply.outcome == 'answered'


async def test_an_attachment_with_text_gets_the_notice_and_the_text_is_still_answered():
    reply, store, runner, _ = await turn(request=channel.parse_request(body(has_attachment=True)))

    link = reply.chat_url
    assert runner.calls[0]['text'] == 'status proyek SPBG?'
    assert reply.reply == f'Lampiran belum didukung di Teams — unggah lewat {link}\n\nProyek SPBG on track.'
    assert reply.outcome == 'answered'


async def test_an_attachment_alone_gets_the_notice_and_no_turn():
    reply, store, runner, audit = await turn(request=channel.parse_request(body(text='', has_attachment=True)))

    (chat,) = store.chats
    assert runner.calls == []
    assert reply == channel.ChannelReply(
        reply=f'Lampiran belum didukung di Teams — unggah lewat https://non-jupe.jup.co.id/c/{chat["id"]}',
        chat_url=f'https://non-jupe.jup.co.id/c/{chat["id"]}',
        outcome='attachment',
    )
    assert audit.lines[0][1]['outcome'] == 'attachment'


async def test_the_whatsapp_notice_names_whatsapp():
    reply, _, _, _ = await turn(request=channel.parse_request(body(channel='whatsapp', text='', has_attachment=True)))

    assert reply.reply.startswith('Lampiran belum didukung di WhatsApp — unggah lewat ')


def test_the_fixed_texts_match_the_plan_exactly():
    link = 'L'
    assert channel.PROCESSING_TEXT.format(link=link) == 'Jawaban masih diproses — lihat di L'
    assert channel.CUT_TEXT.format(link=link) == 'Jawaban lengkap: L'
    assert (
        channel.ATTACHMENT_TEXT.format(channel='Teams', link=link)
        == 'Lampiran belum didukung di Teams — unggah lewat L'
    )


async def test_an_answer_that_ended_in_an_error_fails_the_turn_instead_of_promising_it():
    audit = AuditLines()
    with pytest.raises(channel.AnswerFailed):
        await turn(result=TurnResult('m1', '', False, error='OpenRouter could not verify credits'), audit=audit)

    ((event, fields),) = audit.lines
    assert (event, fields['outcome'], fields['reason']) == ('channel_turn', 'failed', 'answer_error')
    assert 'OpenRouter' not in json.dumps(audit.lines)
