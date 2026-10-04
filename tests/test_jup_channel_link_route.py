"""The link route's HTTP seam (`routers/jup_channel.py`, `POST /api/jup/channel/link`, E9.1).

The middleware's admission is stood in for by a tiny one that sets the request state it would set;
the Mapping tables are a scratch SQLite brought to head by the real migration graph. What runs for
real: the route, `jup.channel_links.links.claim`, and the audit call it makes.

Needs the vendor runtime; skipped under `--only-group dev`, where the middleware's ADR tests and
`test_channel_links.py`'s rules are the guard.
"""

import importlib.util
import time

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'sqlalchemy', 'alembic', 'typer')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under --only-group dev',
)

NUMBER = 'c' * 64


@pytest.fixture
def world(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    import open_webui.internal.db as db
    from jup.channel_links import links, migrate
    from jup.governance import CHANNEL_LINK_STATE_ATTR, CHANNEL_TURN_STATE_ATTR, CHANNEL_USER_STATE_ATTR
    from open_webui.routers import jup_channel

    engine = create_engine(f'sqlite:///{tmp_path / "links.db"}')
    assert migrate.run_channel_link_migrations(engine)
    monkeypatch.setattr(db, 'engine', engine)
    lines: list[tuple[str, dict]] = []
    monkeypatch.setattr(jup_channel, 'audit', lambda event, **fields: lines.append((event, fields)))

    admitted: dict = {}

    app = FastAPI()

    @app.middleware('http')
    async def admit(request, call_next):
        for key, value in admitted.items():
            setattr(request.state, key, value)
        return await call_next(request)

    app.include_router(jup_channel.router, prefix='/api/jup/channel')

    class World:
        client = TestClient(app)

        def admit_code(self, code: str, user_id: str = 'u-erik') -> None:
            admitted.clear()
            admitted[CHANNEL_LINK_STATE_ATTR] = {'code': code, 'identity_hash': NUMBER}
            admitted[CHANNEL_USER_STATE_ATTR] = user_id

        def admit_turn(self) -> None:
            admitted.clear()
            admitted[CHANNEL_TURN_STATE_ATTR] = True
            admitted[CHANNEL_USER_STATE_ATTR] = 'u-erik'

        def issue(self, user_id: str, code: str) -> None:
            links.issue_code(engine, user_id, int(time.time() * 1000), draw=lambda: code)

    w = World()
    w.engine, w.lines, w.links = engine, lines, links
    return w


def test_a_code_admission_links_the_number_and_audits_it(world):
    world.issue('u-erik', '482913')
    world.admit_code('482913')

    response = world.client.post('/api/jup/channel/link', json={'hint': '1234'})

    assert response.status_code == 200
    assert response.json() == {'linked': True, 'outcome': 'linked'}
    assert world.links.resolve(world.engine, NUMBER) == 'u-erik'
    event, fields = world.lines[-1]
    assert event == 'channel_link'
    assert fields == {'channel': 'whatsapp', 'identity_hash': NUMBER, 'user': 'u-erik', 'outcome': 'linked'}


def test_a_spent_code_answers_403_and_links_nothing_more(world):
    world.issue('u-erik', '482913')
    world.admit_code('482913')
    assert world.client.post('/api/jup/channel/link', json={'hint': '1234'}).status_code == 200

    again = world.client.post('/api/jup/channel/link', json={'hint': '1234'})

    assert again.status_code == 403
    assert world.lines[-1][1]['outcome'] == 'refused'


def test_a_turn_admission_cannot_link(world):
    world.issue('u-erik', '482913')
    world.admit_turn()

    assert world.client.post('/api/jup/channel/link', json={'hint': '1234'}).status_code == 403
    assert world.links.resolve(world.engine, NUMBER) is None


def test_a_link_admission_cannot_run_a_turn(world):
    world.admit_code('482913')
    response = world.client.post(
        '/api/jup/channel/turn',
        json={
            'channel': 'whatsapp',
            'identity_hash': NUMBER,
            'conversation_key': 'k',
            'text': 'halo',
            'has_attachment': False,
        },
    )

    assert response.status_code == 403


@pytest.mark.parametrize('body', [{}, {'hint': '123'}, {'hint': '+62812'}, {'hint': '1234', 'number': 'x'}, []])
def test_a_bad_body_is_422_and_the_code_stays_unspent(world, body):
    world.issue('u-erik', '482913')
    world.admit_code('482913')

    assert world.client.post('/api/jup/channel/link', json=body).status_code == 422
    assert world.client.post('/api/jup/channel/link', json={'hint': '1234'}).status_code == 200
