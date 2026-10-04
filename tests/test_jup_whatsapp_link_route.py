"""The web app's WhatsApp link API at its HTTP seam (`routers/jup_whatsapp_link.py`, E9.2, #103).

The signed-in user and their group grant are stood in for; the Mapping tables are a scratch SQLite
brought to head by the real migration graph. What runs for real: the routes, `jup.channel_links.links`,
and the audit call.

Needs the vendor runtime; skipped under `--only-group dev`.
"""

import importlib.util
import time
from types import SimpleNamespace

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'sqlalchemy', 'alembic', 'typer')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing), as under --only-group dev',
)

NUMBER = 'c' * 64
GRANTED = {'jup': {'channel': {'use': True}}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    import open_webui.internal.db as db
    from jup.channel_links import links, migrate
    from open_webui.routers import jup_whatsapp_link
    from open_webui.utils.auth import get_verified_user

    engine = create_engine(f'sqlite:///{tmp_path / "links.db"}')
    assert migrate.run_channel_link_migrations(engine)
    monkeypatch.setattr(db, 'engine', engine)
    lines: list[tuple[str, dict]] = []
    monkeypatch.setattr(jup_whatsapp_link, 'audit', lambda event, **fields: lines.append((event, fields)))

    state = SimpleNamespace(user_id='u-erik', permissions=GRANTED, enabled=True)

    async def permissions(user_id, defaults):
        return state.permissions

    monkeypatch.setattr(jup_whatsapp_link, 'get_permissions', permissions)
    monkeypatch.setattr(jup_whatsapp_link, 'channels_enabled', lambda: state.enabled)
    monkeypatch.delenv('JUP_WHATSAPP_NUMBER', raising=False)

    app = FastAPI()
    app.include_router(jup_whatsapp_link.router, prefix='/api/v1/whatsapp-link')
    app.dependency_overrides[get_verified_user] = lambda: SimpleNamespace(id=state.user_id, role='user')

    class World:
        client = TestClient(app)

        def link(self, user_id: str = 'u-erik', identity_hash: str = NUMBER, hint: str = '7890') -> None:
            now = int(time.time() * 1000)
            code = links.issue_code(engine, user_id, now).code
            assert links.claim(engine, code, identity_hash, hint, now) is not None

    w = World()
    w.engine, w.lines, w.links, w.state = engine, lines, links, state
    return w


URL = '/api/v1/whatsapp-link'


def test_a_grant_holder_sees_the_section_unlinked(world):
    assert world.client.get(URL).json() == {'available': True, 'linked': False}


@pytest.mark.parametrize('change', ['no_grant', 'kill_switch'])
def test_without_the_grant_or_with_channels_off_the_section_is_hidden_and_no_code_is_issued(world, change):
    if change == 'no_grant':
        world.state.permissions = {'jup': {'channel': {'use': False}}}
    else:
        world.state.enabled = False
    assert world.client.get(URL).json() == {'available': False}
    assert world.client.post(f'{URL}/code').status_code == 403


def test_a_code_comes_with_its_wa_me_link_expiry_and_the_meta_notice(world):
    before = int(time.time() * 1000)
    body = world.client.post(f'{URL}/code').json()

    assert len(body['code']) == 6 and body['code'].isdigit()
    assert body['wa_link'] == f'https://wa.me/15556537220?text=hubungkan%20{body["code"]}'
    assert before + 9 * 60_000 < body['expires_at'] <= int(time.time() * 1000) + 10 * 60_000
    assert 'Meta' in body['disclosure']
    # The code is the one the gateway's link call will be admitted on.
    assert world.links.code_owner(world.engine, body['code'], NUMBER, int(time.time() * 1000)) == 'u-erik'


def test_a_new_code_replaces_the_old_one(world):
    first = world.client.post(f'{URL}/code').json()['code']
    second = world.client.post(f'{URL}/code').json()['code']
    now = int(time.time() * 1000)
    if first != second:
        assert world.links.code_owner(world.engine, first, NUMBER, now) is None
    assert world.links.code_owner(world.engine, second, NUMBER, now) == 'u-erik'


def test_a_linked_user_sees_the_last_four_digits_and_since_when(world):
    world.link()
    body = world.client.get(URL).json()
    assert body['available'] is True and body['linked'] is True
    assert body['hint'] == '7890'
    assert isinstance(body['since'], int)
    assert NUMBER not in str(body)


def test_unlinking_cuts_the_number_off_and_is_audited(world):
    world.link()
    assert world.client.delete(URL).json() == {'unlinked': True}
    assert world.links.resolve(world.engine, NUMBER) is None
    assert world.lines == [
        ('channel_link', {'channel': 'whatsapp', 'identity_hash': NUMBER, 'user': 'u-erik', 'outcome': 'unlinked'})
    ]
    assert world.client.delete(URL).json() == {'unlinked': False}
    assert len(world.lines) == 1


def test_unlinking_needs_no_grant(world):
    world.link()
    world.state.permissions = {}
    assert world.client.delete(URL).json() == {'unlinked': True}


def test_one_user_cannot_unlink_another(world):
    world.link(user_id='u-other')
    assert world.client.delete(URL).json() == {'unlinked': False}
    assert world.links.resolve(world.engine, NUMBER) == 'u-other'
