"""The title column's HTTP seam (`routers/jup_contracts.py`, D3).

Faked: who is signed in (`get_current_user`) and the vendor group tables (`contract_title_store`).
The real `get_verified_user` and the real rules in `jup.contracts.titles` run on every request.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the other endpoint
tests. A skip here is not a pass; the rules are covered without a server in test_contract_titles.py.
"""

import importlib.util
from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from jup.contracts import titles

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt', 'sqlalchemy', 'aiosqlite')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under `--only-group dev`.',
)

BASE = '/api/v1/contracts'
ADMIN = 'user-admin'
STAFF = 'user-staff'
TARGET = 'user-target'


@dataclass(frozen=True)
class _Account:
    role: str
    id: str


class _Store:
    def __init__(self) -> None:
        self.groups: dict[str, SimpleNamespace] = {}
        self.members: dict[str, set[str]] = {}
        self.users = {ADMIN, STAFF, TARGET}
        self.created = 0
        self.fail_add = False

    def put_group(self, group_id: str, title: str | None, permissions: dict | None = None) -> SimpleNamespace:
        data = {titles.MARKER: title} if title else {}
        group = SimpleNamespace(
            id=group_id,
            name=group_id,
            description='',
            data=data,
            permissions=permissions if permissions is not None else (titles.grants(title) if title else {}),
            created_at=len(self.groups) + 1,
        )
        self.groups[group_id] = group
        self.members.setdefault(group_id, set())
        return group

    async def all_groups(self) -> list[SimpleNamespace]:
        return list(self.groups.values())

    async def member_ids(self, group_id: str) -> list[str]:
        return sorted(self.members.get(group_id, set()))

    async def user_exists(self, user_id: str) -> bool:
        return user_id in self.users

    async def create_group(self, owner_id: str, form: dict[str, Any]) -> SimpleNamespace:
        self.created += 1
        group = self.put_group(f'g-{form["data"][titles.MARKER]}', form['data'][titles.MARKER], form['permissions'])
        group.name = form['name']
        group.owner = owner_id
        return group

    async def set_permissions(self, group: SimpleNamespace, permissions: dict[str, Any]) -> SimpleNamespace:
        group.permissions = permissions
        return group

    async def add(self, group_id: str, user_id: str) -> bool:
        if self.fail_add:
            return False
        self.members[group_id].add(user_id)
        return True

    async def remove(self, group_id: str, user_id: str) -> bool:
        self.members[group_id].discard(user_id)
        return True


@pytest.fixture
def store() -> _Store:
    return _Store()


@pytest.fixture
def client(store: _Store, caplog: pytest.LogCaptureFixture) -> Iterator[Any]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from open_webui.routers import jup_contracts

    app = FastAPI()
    app.include_router(jup_contracts.router, prefix=BASE)
    app.dependency_overrides[jup_contracts.contract_title_store] = lambda: store
    caplog.set_level('INFO', logger='jup.governance')
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client


def _as(client, role: str | None, user_id: str = ADMIN) -> None:
    from fastapi import HTTPException, status

    from open_webui.utils.auth import get_current_user

    def _current_user():
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
        return _Account(role=role, id=user_id)

    client.app.dependency_overrides[get_current_user] = _current_user


def _audit(caplog) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith('jup.governance') and "'event': 'contract_title'" in r.getMessage()
    ]


def test_a_non_admin_is_refused_with_403_on_both_routes(client, store, caplog) -> None:
    _as(client, 'user', STAFF)
    listed = client.get(f'{BASE}/titles')
    moved = client.put(f'{BASE}/titles/{TARGET}', json={'title': 'legal'})
    assert listed.status_code == 403 and moved.status_code == 403
    assert moved.json()['detail']['code'] == 'admin_only'
    assert store.created == 0
    assert "'result': 'refused'" in _audit(caplog)[-1]


def test_signed_out_is_401(client) -> None:
    _as(client, None)
    assert client.get(f'{BASE}/titles').status_code == 401


def test_the_first_move_creates_the_four_groups_and_sets_the_title(client, store, caplog) -> None:
    _as(client, 'admin')
    response = client.put(f'{BASE}/titles/{TARGET}', json={'title': 'legal'})
    assert response.status_code == 200, response.text
    assert response.json() == {'user_id': TARGET, 'titles': ['legal']}
    assert store.created == 4
    assert {g.data[titles.MARKER] for g in store.groups.values()} == set(titles.TITLES)
    assert all(getattr(g, 'owner', None) == ADMIN for g in store.groups.values())
    line = _audit(caplog)[-1]
    assert "'result': 'recorded'" in line and "'after': ['legal']" in line


def test_moving_leaves_exactly_one_title(client, store) -> None:
    _as(client, 'admin')
    for title in titles.TITLES:
        store.put_group(f'g-{title}', title)
    store.members['g-staff'].add(TARGET)
    store.members['g-legal'].add(TARGET)  # someone edited a group by hand
    response = client.put(f'{BASE}/titles/{TARGET}', json={'title': 'manager'})
    assert response.json()['titles'] == ['manager']
    assert TARGET not in store.members['g-staff'] | store.members['g-legal']
    assert store.created == 0


def test_null_clears_the_title(client, store) -> None:
    _as(client, 'admin')
    client.put(f'{BASE}/titles/{TARGET}', json={'title': 'direksi'})
    response = client.put(f'{BASE}/titles/{TARGET}', json={'title': None})
    assert response.json()['titles'] == []


def test_hand_edited_grants_are_put_back_before_the_move(client, store) -> None:
    _as(client, 'admin')
    for title in titles.TITLES:
        store.put_group(f'g-{title}', title)
    store.groups['g-staff'].permissions = {
        'jup': {'contracts': {'cards': True, 'fulltext': True}, 'kb': {'submit': True}}
    }
    client.put(f'{BASE}/titles/{TARGET}', json={'title': 'staff'})
    assert store.groups['g-staff'].permissions['jup']['contracts'] == titles.grants('staff')['jup']['contracts']
    assert store.groups['g-staff'].permissions['jup']['kb'] == {'submit': True}


def test_list_reports_every_titled_user(client, store) -> None:
    _as(client, 'admin')
    client.put(f'{BASE}/titles/{TARGET}', json={'title': 'staff'})
    client.put(f'{BASE}/titles/{STAFF}', json={'title': 'legal'})
    body = client.get(f'{BASE}/titles').json()
    assert [t['key'] for t in body['titles']] == list(titles.TITLES)
    assert body['users'] == {TARGET: ['staff'], STAFF: ['legal']}


def test_an_unknown_title_or_user_is_refused(client, store) -> None:
    _as(client, 'admin')
    assert client.put(f'{BASE}/titles/{TARGET}', json={'title': 'admin'}).status_code == 422
    assert client.put(f'{BASE}/titles/nobody', json={'title': 'staff'}).status_code == 404
    assert store.created == 0


def test_a_failed_add_is_a_500_and_leaves_no_title(client, store) -> None:
    _as(client, 'admin')
    client.put(f'{BASE}/titles/{TARGET}', json={'title': 'staff'})
    store.fail_add = True
    response = client.put(f'{BASE}/titles/{TARGET}', json={'title': 'legal'})
    assert response.status_code == 500
    # Removed first, so the failure leaves less access, never more.
    assert client.get(f'{BASE}/titles').json()['users'] == {}


# --- Import, PDF, capabilities, names --------------------------------------------------------------


@pytest.fixture
def data_client(tmp_path, monkeypatch, caplog) -> Iterator[Any]:
    import json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    from jup.contracts import access, migrate
    from open_webui.routers import jup_contracts
    from tests.test_contract_repository import _field, card, record

    engine = create_engine(f'sqlite:///{tmp_path / "c.db"}')
    assert migrate.run_contract_migrations(engine)
    root = tmp_path / 'bucket'
    (root / 'full' / 'cards').mkdir(parents=True)
    (root / 'full' / 'src').mkdir(parents=True)
    rec = record('0001', 'item-1', card(mitra=_field('Budi Santoso'), perorangan_non_penandatangan=['Budi Santoso']))
    (root / 'full' / 'cards' / '0001.json').write_text(json.dumps(rec), encoding='utf-8')
    (root / 'full' / 'src' / '0001.pdf').write_bytes(b'%PDF-1.4 synthetic')

    state = {'title': None}
    app = FastAPI()
    app.include_router(jup_contracts.router, prefix=BASE)
    app.dependency_overrides[jup_contracts.contracts_engine] = lambda: engine
    app.dependency_overrides[jup_contracts.contracts_root] = lambda: root
    app.dependency_overrides[jup_contracts.contract_reader] = lambda: access.Access.from_permissions(
        titles.grants(state['title']) if state['title'] else {}
    )
    monkeypatch.setattr(jup_contracts, 'schema_ready', lambda: True)
    caplog.set_level('INFO', logger='jup.governance')
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        test_client.state = state  # type: ignore[attr-defined]
        yield test_client


def test_import_is_admin_only_and_idempotent(data_client) -> None:
    _as(data_client, 'user', STAFF)
    assert data_client.post(f'{BASE}/import', json={'run': 'full'}).status_code == 403
    _as(data_client, 'admin')
    first = data_client.post(f'{BASE}/import', json={'run': 'full'}).json()
    assert first['created'] == 1
    assert data_client.post(f'{BASE}/import', json={'run': 'full'}).json()['unchanged'] == 1
    assert data_client.post(f'{BASE}/import', json={'run': 'nope'}).status_code == 404
    assert data_client.post(f'{BASE}/import', json={'run': '../x'}).status_code == 404


def test_the_pdf_needs_full_text_and_hides_the_file_name(data_client) -> None:
    _as(data_client, 'admin')
    data_client.post(f'{BASE}/import', json={'run': 'full'})
    _as(data_client, 'user', STAFF)
    data_client.state['title'] = 'manager'
    assert data_client.get(f'{BASE}/0001/pdf').status_code == 403
    data_client.state['title'] = 'direksi'
    response = data_client.get(f'{BASE}/0001/pdf')
    assert response.status_code == 200 and response.content.startswith(b'%PDF')
    assert 'kontrak-0001.pdf' in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'private, no-store'
    assert data_client.get(f'{BASE}/9999/pdf').status_code == 404


def test_names_resolve_only_with_the_names_grant(data_client) -> None:
    _as(data_client, 'admin')
    data_client.post(f'{BASE}/import', json={'run': 'full'})
    _as(data_client, 'user', STAFF)
    data_client.state['title'] = 'manager'
    assert data_client.post(f'{BASE}/parties/resolve', json={'codes': ['Perorangan A']}).json() == {'names': {}}
    data_client.state['title'] = 'legal'
    got = data_client.post(f'{BASE}/parties/resolve', json={'codes': ['Perorangan A', 'DROP TABLE']})
    assert got.json() == {'names': {'Perorangan A': 'Budi Santoso'}}
    assert data_client.post(f'{BASE}/parties/resolve', json={'codes': ['x'] * 51}).status_code == 422


def test_capabilities_reflect_the_title(data_client) -> None:
    _as(data_client, 'user', STAFF)
    data_client.state['title'] = 'staff'
    assert data_client.get(f'{BASE}/capabilities').json() == {
        'cards': True,
        'money': False,
        'fulltext': False,
        'names': False,
        'review': False,
    }
