"""The voice routes' HTTP seam (`routers/jup_voice.py`).

Faked: who is signed in (`get_current_user`), their groups (`Groups.get_groups_by_member_id`), the
server secret, and the vendor tables the router reaches through `voice_store`. The real
`get_verified_user`, the real `get_permissions` merge and the real rules in `jup.voice` run on every
request.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the other endpoint
tests. A skip here is not a pass. The rules are covered without a server in test_jup_voice.py.
"""

import importlib.util
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

    def grant(self, user_id: str, value: Any = True) -> None:
        self.groups[user_id] = [SimpleNamespace(permissions={'jup': {'voice': {'call': value}}})]

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
