"""The voice routes' HTTP seam (`routers/jup_voice.py`).

Faked: who is signed in (`get_current_user`), their groups (`Groups.get_groups_by_member_id`), the
server secret, and the vendor tables the router reaches through `voice_store`. The real
`get_verified_user`, the real `get_permissions` merge and the real rules in `jup.voice` run on every
request.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the other endpoint
tests. A skip here is not a pass. The rules are covered without a server in test_jup_voice.py.
"""

import asyncio
import importlib.util
import json
from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt', 'sqlalchemy')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The rules are covered without a server in test_jup_voice.py.'
    ),
)

BASE = '/api/v1/voice'
SECRET = 'test-secret'
ERIK = 'user-erik'
OTHER = 'user-other'


@dataclass(frozen=True)
class _Account:
    role: str
    id: str


class _Directory:
    def __init__(self) -> None:
        self.groups: dict[str, list[SimpleNamespace]] = {}

    def grant(self, user_id: str, value: Any = True, *, live: Any = None) -> None:
        grants = {'call': value} if live is None else {'call': value, 'live': live}
        self.groups[user_id] = [SimpleNamespace(permissions={'jup': {'voice': grants}})]

    async def get_groups_by_member_id(self, user_id: str, db=None) -> list[SimpleNamespace]:
        return list(self.groups.get(user_id, []))


class _Store:
    """The vendor tables, in memory. Same interface as `jup_voice.VoiceStore`."""

    def __init__(self) -> None:
        self.info: dict[str, dict] = {}
        self.chats: dict[str, dict] = {}

    async def user_info(self, user_id: str) -> dict | None:
        return self.info.get(user_id)

    async def set_user_info_key(self, user_id: str, key: str, value: Any) -> None:
        self.info[user_id] = {**self.info.get(user_id, {}), key: value}

    async def create_chat(self, chat_id: str, user_id: str, title: str, models: list[str], meta: dict) -> None:
        self.chats[chat_id] = {'user_id': user_id, 'title': title, 'models': models, 'meta': meta}

    async def get_chat(self, chat_id: str) -> Any:
        chat = self.chats.get(chat_id)
        return None if chat is None else SimpleNamespace(id=chat_id, user_id=chat['user_id'], meta=chat['meta'])


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> _Directory:
    from open_webui.utils import access_control

    fake = _Directory()
    monkeypatch.setattr(access_control.Groups, 'get_groups_by_member_id', fake.get_groups_by_member_id)
    return fake


@pytest.fixture
def store() -> _Store:
    return _Store()


@pytest.fixture
def client(
    directory: _Directory, store: _Store, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from open_webui.routers import jup_voice

    monkeypatch.setenv('JUP_VOICE_ENABLED', 'true')
    app = FastAPI()
    app.include_router(jup_voice.router, prefix=BASE)
    app.dependency_overrides[jup_voice.voice_store] = lambda: store
    app.dependency_overrides[jup_voice.voice_secret] = lambda: SECRET
    caplog.set_level('INFO', logger='jup.governance')
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client


def _as(client, role: str | None, user_id: str = ERIK) -> None:
    from fastapi import HTTPException, status

    from open_webui.utils.auth import get_current_user

    def _current_user():
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
        return _Account(role=role, id=user_id)

    client.app.dependency_overrides[get_current_user] = _current_user


def _audit(caplog, event: str) -> list[dict]:
    import ast

    lines = []
    for record in caplog.records:
        message = record.getMessage()
        if message.startswith('jup.governance') and f"'event': '{event}'" in message:
            lines.append(ast.literal_eval(message[message.index('{') :]))
    return lines


def _acks(caplog) -> list[dict]:
    return _audit(caplog, 'voice_ack')


def _ack(client) -> Any:
    from jup import voice

    return client.post(f'{BASE}/acknowledge', json={'version': voice.DISCLOSURE_VERSION})


# --- Capabilities -----------------------------------------------------------------------


def test_capabilities_when_the_switch_is_off(client, directory, monkeypatch) -> None:
    monkeypatch.setenv('JUP_VOICE_ENABLED', 'false')
    directory.grant(ERIK)
    _as(client, 'admin')
    body = client.get(f'{BASE}/capabilities').json()
    assert body['enabled'] is False and body['granted'] is False and body['acknowledged'] is False


def test_capabilities_report_grant_and_acknowledgement(client, directory) -> None:
    from jup import voice

    directory.grant(ERIK)
    _as(client, 'admin')
    before = client.get(f'{BASE}/capabilities').json()
    assert before == {
        'enabled': True,
        'granted': True,
        'acknowledged': False,
        'disclosure_version': voice.DISCLOSURE_VERSION,
        'live': {'granted': False, 'acknowledged': False, 'disclosure_version': voice.LIVE_DISCLOSURE_VERSION},
    }
    assert _ack(client).status_code == 200
    assert client.get(f'{BASE}/capabilities').json()['acknowledged'] is True


def test_an_admin_without_the_grant_is_not_granted(client) -> None:
    _as(client, 'admin')
    assert client.get(f'{BASE}/capabilities').json()['granted'] is False


def test_capabilities_need_a_signed_in_user(client) -> None:
    _as(client, None)
    assert client.get(f'{BASE}/capabilities').status_code == 401


# --- Acknowledge ------------------------------------------------------------------------


def test_acknowledging_stores_a_signed_record_and_audits_it(client, directory, store, caplog) -> None:
    from jup import voice

    directory.grant(ERIK)
    _as(client, 'admin')
    response = _ack(client)
    assert response.status_code == 200
    assert voice.acknowledged(store.info[ERIK], ERIK, secret=SECRET) is True
    lines = _acks(caplog)
    assert len(lines) == 1
    assert {key: value for key, value in lines[0].items() if key != 'ts'} == {
        'event': 'voice_ack',
        'user': ERIK,
        'version': voice.DISCLOSURE_VERSION,
    }


def test_acknowledging_an_old_version_is_refused(client, directory, store, caplog) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    response = client.post(f'{BASE}/acknowledge', json={'version': '2000-01-01'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'voice_disclosure_changed'
    assert ERIK not in store.info and _acks(caplog) == []


def test_acknowledging_needs_the_grant(client, store) -> None:
    _as(client, 'admin')
    response = _ack(client)
    assert response.status_code == 403 and ERIK not in store.info


def test_acknowledging_needs_the_switch(client, directory, store, monkeypatch) -> None:
    monkeypatch.setenv('JUP_VOICE_ENABLED', '')
    directory.grant(ERIK)
    _as(client, 'admin')
    assert _ack(client).status_code == 503 and ERIK not in store.info


def test_acknowledging_keeps_the_users_other_info(client, directory, store) -> None:
    directory.grant(ERIK)
    store.info[ERIK] = {'location': 'Bekasi'}
    _as(client, 'admin')
    _ack(client)
    assert store.info[ERIK]['location'] == 'Bekasi'


# --- Start a call -----------------------------------------------------------------------


def test_a_call_is_refused_with_the_switch_off(client, directory, store, monkeypatch) -> None:
    monkeypatch.setenv('JUP_VOICE_ENABLED', '0')
    directory.grant(ERIK)
    _as(client, 'admin')
    response = client.post(f'{BASE}/calls')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'voice_disabled'
    assert store.chats == {}


def test_a_call_is_refused_without_the_grant(client, store) -> None:
    _as(client, 'admin')
    response = client.post(f'{BASE}/calls')
    assert response.status_code == 403
    assert response.json()['detail']['code'] == 'voice_not_granted'
    assert store.chats == {}


def test_a_string_grant_is_not_a_grant(client, directory, store) -> None:
    directory.grant(ERIK, 'true')
    _as(client, 'user')
    assert client.post(f'{BASE}/calls').status_code == 403 and store.chats == {}


def test_a_call_is_refused_before_the_disclosure_is_acknowledged(client, directory, store) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    response = client.post(f'{BASE}/calls')
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'voice_ack_required'
    assert store.chats == {}


def test_an_acknowledgement_the_user_wrote_does_not_open_a_call(client, directory, store) -> None:
    from jup import voice

    directory.grant(ERIK)
    store.info[ERIK] = {voice.ACK_KEY: {'version': voice.DISCLOSURE_VERSION, 'at': 1, 'sig': 'f' * 64}}
    _as(client, 'admin')
    assert client.post(f'{BASE}/calls').status_code == 409 and store.chats == {}


def test_a_call_creates_a_marked_voice_chat_for_the_caller(client, directory, store) -> None:
    from jup import voice

    directory.grant(ERIK)
    _as(client, 'admin')
    _ack(client)
    response = client.post(f'{BASE}/calls')
    assert response.status_code == 200
    chat_id = response.json()['chat_id']
    chat = store.chats[chat_id]
    assert chat['user_id'] == ERIK
    assert chat['models'] == [voice.VOICE_MODEL_ID]
    assert voice.is_voice_chat(chat['meta'], chat_id=chat_id, user_id=ERIK, secret=SECRET) is True
    assert voice.is_voice_chat(chat['meta'], chat_id=chat_id, user_id=OTHER, secret=SECRET) is False


def test_each_call_is_a_new_chat(client, directory, store) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    _ack(client)
    first = client.post(f'{BASE}/calls').json()['chat_id']
    second = client.post(f'{BASE}/calls').json()['chat_id']
    assert first != second and len(store.chats) == 2


def test_another_users_acknowledgement_does_not_open_a_call(client, directory, store) -> None:
    directory.grant(ERIK)
    directory.grant(OTHER)
    _as(client, 'admin', ERIK)
    _ack(client)
    store.info[OTHER] = dict(store.info[ERIK])
    _as(client, 'user', OTHER)
    assert client.post(f'{BASE}/calls').status_code == 409


def test_voice_routes_are_not_cached(client, directory) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    assert client.get(f'{BASE}/capabilities').headers['cache-control'] == 'private, no-store'
    assert client.post(f'{BASE}/calls').headers['cache-control'] == 'private, no-store'


# --- Audit of calls ---------------------------------------------------------------------


def test_calls_are_audited_started_and_refused(client, directory, caplog) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    client.post(f'{BASE}/calls')
    _ack(client)
    chat_id = client.post(f'{BASE}/calls').json()['chat_id']
    lines = [{k: v for k, v in line.items() if k != 'ts'} for line in _audit(caplog, 'voice_call')]
    assert lines == [
        {'event': 'voice_call', 'user': ERIK, 'outcome': 'voice_ack_required', 'chat': None},
        {'event': 'voice_call', 'user': ERIK, 'outcome': 'started', 'chat': chat_id},
    ]


# --- No other door into a voice chat ----------------------------------------------------


def test_an_imported_chat_does_not_keep_a_voice_mark(client, directory, store) -> None:
    """Chat import stores the client's meta under a fresh id, so a copied mark no longer verifies."""
    from jup import voice
    from open_webui.models.chats import ChatImportForm, Chats

    directory.grant(ERIK)
    _as(client, 'admin')
    _ack(client)
    original = client.post(f'{BASE}/calls').json()['chat_id']
    copied_meta = store.chats[original]['meta']
    imported = Chats._chat_import_form_to_chat_model(ERIK, ChatImportForm(chat={'title': 'x'}, meta=copied_meta))
    assert imported.id != original
    assert voice.is_voice_chat(imported.meta, chat_id=imported.id, user_id=ERIK, secret=SECRET) is False


# --- Misconfiguration -------------------------------------------------------------------


def test_no_server_secret_refuses_instead_of_failing(client, directory) -> None:
    from open_webui.routers import jup_voice

    directory.grant(ERIK)
    client.app.dependency_overrides[jup_voice.voice_secret] = lambda: ''
    _as(client, 'admin')
    for response in (_ack(client), client.post(f'{BASE}/calls')):
        assert response.status_code == 503
        assert response.json()['detail']['code'] == 'voice_misconfigured'


# --- GPT-Live: grant and acknowledgement (#34, ADR-0018) --------------------------------


def _live_ack(client, version: str | None = None) -> Any:
    from jup import voice

    return client.post(f'{BASE}/live/acknowledge', json={'version': version or voice.LIVE_DISCLOSURE_VERSION})


def test_live_capabilities_follow_the_live_grant_and_acknowledgement(client, directory) -> None:
    directory.grant(ERIK, live=True)
    _as(client, 'admin')
    assert client.get(f'{BASE}/capabilities').json()['live']['granted'] is True
    assert client.get(f'{BASE}/capabilities').json()['live']['acknowledged'] is False
    assert _live_ack(client).status_code == 200
    assert client.get(f'{BASE}/capabilities').json()['live']['acknowledged'] is True


def test_live_is_off_when_the_switch_is_off(client, directory, monkeypatch) -> None:
    monkeypatch.setenv('JUP_VOICE_ENABLED', 'false')
    directory.grant(ERIK, live=True)
    _as(client, 'admin')
    assert client.get(f'{BASE}/capabilities').json()['live']['granted'] is False
    response = _live_ack(client)
    assert response.status_code == 503


def test_the_call_grant_alone_does_not_open_live(client, directory, store) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    assert client.get(f'{BASE}/capabilities').json()['live']['granted'] is False
    response = _live_ack(client)
    assert response.status_code == 403 and response.json()['detail']['code'] == 'voice_live_not_granted'
    assert ERIK not in store.info


def test_the_live_grant_without_the_call_grant_is_refused(client, directory) -> None:
    directory.grant(ERIK, False, live=True)
    _as(client, 'admin')
    response = _live_ack(client)
    assert response.status_code == 403 and response.json()['detail']['code'] == 'voice_not_granted'


def test_acknowledging_live_stores_its_own_signed_record_and_audits_it(client, directory, store, caplog) -> None:
    from jup import voice

    directory.grant(ERIK, live=True)
    _as(client, 'admin')
    assert _live_ack(client).json() == {'acknowledged': True, 'disclosure_version': voice.LIVE_DISCLOSURE_VERSION}
    assert voice.live_acknowledged(store.info[ERIK], ERIK, secret=SECRET) is True
    assert voice.ACK_KEY not in store.info[ERIK]
    lines = _audit(caplog, 'voice_live_ack')
    assert [{k: v for k, v in line.items() if k != 'ts'} for line in lines] == [
        {'event': 'voice_live_ack', 'user': ERIK, 'version': voice.LIVE_DISCLOSURE_VERSION}
    ]


def test_acknowledging_an_old_live_version_is_refused(client, directory, store) -> None:
    directory.grant(ERIK, live=True)
    _as(client, 'admin')
    response = _live_ack(client, '2000-01-01')
    assert response.status_code == 409 and response.json()['detail']['code'] == 'voice_live_disclosure_changed'
    assert ERIK not in store.info


def test_the_call_acknowledgement_does_not_acknowledge_live(client, directory) -> None:
    directory.grant(ERIK, live=True)
    _as(client, 'admin')
    assert _ack(client).status_code == 200
    body = client.get(f'{BASE}/capabilities').json()
    assert body['acknowledged'] is True and body['live']['acknowledged'] is False


# --- GPT-Live: the server mints the session (#35) ----------------------------------------

OFFER = 'v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\n'
ANSWER = 'v=0\r\no=- answer\r\n'


@pytest.fixture
def openai_live(monkeypatch: pytest.MonkeyPatch):
    from open_webui.routers import jup_voice

    monkeypatch.setenv('JUP_VOICE_OPENAI_API_KEY', 'sk-live\n\n')
    fake = SimpleNamespace(
        sent=[], reply=(201, {'session': {'id': 'live_123'}, 'transport': {'type': 'webrtc', 'sdp': ANSWER}})
    )

    async def _create(body, key):
        fake.sent.append((body, key))
        return fake.reply

    monkeypatch.setattr(jup_voice, '_live_create', _create)

    async def _relay(**kwargs):
        fake.relayed.append(kwargs)

    fake.relayed = []
    monkeypatch.setattr(jup_voice, '_live_relay', _relay)
    monkeypatch.setattr(jup_voice, 'LIVE_PING_SECONDS', 0.01)
    return fake


def _live_ready(client, directory, *, live_ack: bool = True) -> str:
    """Erik, granted call and live, both disclosures acknowledged, in a voice call he just started."""
    directory.grant(ERIK, live=True)
    _as(client, 'admin')
    assert _ack(client).status_code == 200
    if live_ack:
        assert _live_ack(client).status_code == 200
    return client.post(f'{BASE}/calls').json()['chat_id']


def _mint(client, chat_id, sdp=OFFER):
    return client.post(f'{BASE}/live/sessions', json={'chat_id': chat_id, 'sdp': sdp})


def _live_lines(caplog) -> list[dict]:
    return [{k: v for k, v in line.items() if k != 'ts'} for line in _audit(caplog, 'voice_live')]


def test_the_server_mints_the_session_and_returns_only_the_answer(client, directory, openai_live, caplog) -> None:
    from jup import voice_live

    chat_id = _live_ready(client, directory)
    response = _mint(client, chat_id)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/x-ndjson')
    lines = [json.loads(line) for line in response.text.splitlines() if line]
    assert lines[0] == {'type': 'session', 'session_id': 'live_123', 'sdp': ANSWER}
    assert lines[-1] == {'type': 'ended'}
    assert openai_live.sent == [(voice_live.session_request(OFFER), 'sk-live')]
    assert _live_lines(caplog) == [
        {'event': 'voice_live', 'user': ERIK, 'chat': chat_id, 'outcome': 'started', 'session': 'live_123'}
    ]


def test_the_relay_runs_inside_the_same_request_for_the_whole_call(client, directory, openai_live) -> None:
    """Option A (#36): the stream stays open while the relay runs, so CPU stays allocated on Cloud Run."""
    chat_id = _live_ready(client, directory)
    _mint(client, chat_id)
    assert len(openai_live.relayed) == 1
    relayed = openai_live.relayed[0]
    assert relayed['session_id'] == 'live_123' and relayed['chat_id'] == chat_id and relayed['key'] == 'sk-live'
    assert relayed['user'].id == ERIK


def test_the_stream_pings_while_the_call_runs(client, directory, openai_live, monkeypatch) -> None:
    from open_webui.routers import jup_voice

    async def _slow(**kwargs):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(jup_voice, '_live_relay', _slow)
    chat_id = _live_ready(client, directory)
    lines = [json.loads(line) for line in _mint(client, chat_id).text.splitlines() if line]
    assert {'type': 'ping'} in lines[1:-1]


def test_a_refused_start_never_starts_a_relay(client, directory, openai_live) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    assert _ack(client).status_code == 200
    chat_id = client.post(f'{BASE}/calls').json()['chat_id']
    assert _mint(client, chat_id).status_code == 403
    assert openai_live.relayed == []


def test_live_needs_the_live_grant(client, directory, openai_live, caplog) -> None:
    directory.grant(ERIK)
    _as(client, 'admin')
    assert _ack(client).status_code == 200
    chat_id = client.post(f'{BASE}/calls').json()['chat_id']
    response = _mint(client, chat_id)
    assert response.status_code == 403 and response.json()['detail']['code'] == 'voice_live_not_granted'
    assert openai_live.sent == []
    assert _live_lines(caplog)[0]['outcome'] == 'voice_live_not_granted'


def test_live_needs_its_own_acknowledgement(client, directory, openai_live) -> None:
    chat_id = _live_ready(client, directory, live_ack=False)
    response = _mint(client, chat_id)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'voice_live_ack_required'
    assert openai_live.sent == []


@pytest.mark.parametrize('which', ['missing', 'typed', 'others'])
def test_live_runs_only_in_the_callers_own_voice_chat(client, directory, store, openai_live, which) -> None:
    _live_ready(client, directory)
    if which == 'typed':
        store.chats['chat-typed'] = {'user_id': ERIK, 'title': 't', 'models': [], 'meta': {}}
        chat_id = 'chat-typed'
    elif which == 'others':
        from jup import voice

        chat_id = 'chat-other'
        mark = voice.voice_mark(chat_id, OTHER, at=1, secret=SECRET)
        store.chats[chat_id] = {'user_id': OTHER, 'title': 't', 'models': [], 'meta': {voice.CHAT_KEY: mark}}
    else:
        chat_id = 'no-such-chat'
    response = _mint(client, chat_id)
    assert response.status_code == 404 and response.json()['detail']['code'] == 'voice_live_chat_not_found'
    assert openai_live.sent == []


def test_a_bad_offer_is_refused_before_openai(client, directory, openai_live) -> None:
    chat_id = _live_ready(client, directory)
    response = _mint(client, chat_id, sdp='hello')
    assert response.status_code == 400 and response.json()['detail']['code'] == 'voice_live_bad_offer'
    assert openai_live.sent == []


def test_without_the_key_live_is_unavailable(client, directory, openai_live, monkeypatch) -> None:
    chat_id = _live_ready(client, directory)
    monkeypatch.setenv('JUP_VOICE_OPENAI_API_KEY', '\n')
    response = _mint(client, chat_id)
    assert response.status_code == 503 and response.json()['detail']['code'] == 'voice_live_unavailable'
    assert openai_live.sent == []


@pytest.mark.parametrize('reply', [(500, {'error': {'message': 'boom'}}), (201, {'session': {}})])
def test_an_openai_failure_is_a_502_and_audited(client, directory, openai_live, caplog, reply) -> None:
    chat_id = _live_ready(client, directory)
    openai_live.reply = reply
    response = _mint(client, chat_id)
    assert response.status_code == 502 and response.json()['detail']['code'] == 'voice_live_upstream'
    line = _live_lines(caplog)[-1]
    assert line['outcome'] == 'voice_live_upstream' and line['upstream_status'] == reply[0]


def test_a_network_failure_reaching_openai_is_a_502_and_audited(
    client, directory, openai_live, caplog, monkeypatch
) -> None:
    from open_webui.routers import jup_voice

    chat_id = _live_ready(client, directory)

    async def _down(body, key):
        raise OSError('connection reset')

    monkeypatch.setattr(jup_voice, '_live_create', _down)
    response = _mint(client, chat_id)
    assert response.status_code == 502 and response.json()['detail']['code'] == 'voice_live_upstream'
    line = _live_lines(caplog)[-1]
    assert line['outcome'] == 'voice_live_upstream' and line['upstream_status'] is None
