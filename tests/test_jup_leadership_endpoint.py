"""The Ruang Pimpinan HTTP seam: authentication, the read grant, and what each answer reveals.

Two things are faked and nothing else: who is signed in (`get_current_user`) and which groups
they belong to (`Groups.get_groups_by_member_id`). The real `get_verified_user`, the real
`get_permissions` merge and the real leadership policy run on every request, so an admin with
no group grant is refused by the same code production runs.

This file needs the vendor runtime, so it skips under CI's `--only-group dev` job, like
`test_jup_portfolio_endpoint.py`. A skip here is not a pass.
"""

import importlib.util
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The reader and policy are covered without a server.'
    ),
)

BASE = '/api/v1/leadership'
BOARD = f'{BASE}/overview?view=board&scope_id=jup-consolidated'
RKA = f'{BASE}/overview?view=rka&scope_id=jup-consolidated'


@dataclass(frozen=True)
class _Account:
    role: str
    id: str = 'test-user'


def _grant(board: bool = False, rka: bool = False, scope: bool = True) -> SimpleNamespace:
    """A group row carrying leadership permissions, shaped as the host stores them."""
    return SimpleNamespace(
        permissions={
            'jup': {
                'ruang_pimpinan': {
                    'board': {'view': board},
                    'rka': {'view': rka},
                    'scopes': {'jup_consolidated': scope},
                }
            }
        }
    )


class _Directory:
    """Group membership, changeable between requests to test revocation."""

    def __init__(self) -> None:
        self.groups: list[SimpleNamespace] = []

    async def get_groups_by_member_id(self, user_id: str, db=None) -> list[SimpleNamespace]:
        return list(self.groups)


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> _Directory:
    from open_webui.utils import access_control

    fake = _Directory()
    monkeypatch.setattr(access_control.Groups, 'get_groups_by_member_id', fake.get_groups_by_member_id)
    return fake


@pytest.fixture
def seed(fixture_path: Callable[..., Path]) -> Path:
    return fixture_path('leadership', 'illustrative-seed.json')


@pytest.fixture
def client(seed: Path, directory: _Directory, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """A bare app carrying only the leadership router, enabled and pointed at the seed."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from open_webui.routers import jup_leadership

    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', 'true')
    monkeypatch.setenv('JUP_LEADERSHIP_SAMPLE_FILE', str(seed))

    app = FastAPI()
    app.include_router(jup_leadership.router, prefix=BASE)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client


def _sign_in_as(client, role: str | None) -> None:
    from fastapi import HTTPException, status

    from open_webui.utils.auth import get_current_user

    def _current_user():
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
        return _Account(role=role)

    client.app.dependency_overrides[get_current_user] = _current_user


def _no_store(response) -> None:
    assert response.headers.get('cache-control') == 'private, no-store'


# --- Who gets in --------------------------------------------------------------------


def test_signed_out_is_refused(client) -> None:
    _sign_in_as(client, None)
    response = client.get(BOARD)
    assert response.status_code == 401
    _no_store(response)


def test_a_pending_account_is_refused(client) -> None:
    _sign_in_as(client, 'pending')
    assert client.get(BOARD).status_code == 401


def test_a_member_without_a_grant_is_refused(client) -> None:
    _sign_in_as(client, 'user')
    response = client.get(BOARD)
    assert response.status_code == 403
    _no_store(response)


def test_an_admin_without_a_grant_is_refused(client) -> None:
    # Admin is Portfolio's operating layer, not the BOD. It opens nothing here.
    _sign_in_as(client, 'admin')
    assert client.get(BOARD).status_code == 403
    assert client.get(RKA).status_code == 403
    assert client.get(f'{BASE}/sources/board-financial?view=board&scope_id=jup-consolidated').status_code == 403


def test_a_board_only_reader_gets_board_and_not_rka(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 200
    assert client.get(RKA).status_code == 403


def test_a_view_grant_without_the_scope_grant_is_refused(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True, scope=False)]
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 403


def test_grants_from_two_groups_combine(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True), _grant(rka=True)]
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 200
    assert client.get(RKA).status_code == 200


def test_a_string_true_in_a_group_row_is_not_a_grant(client, directory: _Directory) -> None:
    group = _grant()
    group.permissions['jup']['ruang_pimpinan']['board']['view'] = 'true'
    directory.groups = [group]
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 403


def test_revocation_stops_the_next_request(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 200
    directory.groups = []
    assert client.get(BOARD).status_code == 403


# --- Capabilities -------------------------------------------------------------------


def test_capabilities_for_an_ungranted_reader_list_nothing(client) -> None:
    _sign_in_as(client, 'admin')
    response = client.get(f'{BASE}/capabilities')
    assert response.status_code == 200
    body = response.json()
    assert body['enabled'] is True
    assert body['views'] == []
    assert body['scope_ids'] == []
    assert body['operations'] == []
    assert 'metrics' not in body and 'actions' not in body
    _no_store(response)


def test_capabilities_for_a_granted_reader(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True, rka=True)]
    _sign_in_as(client, 'user')
    body = client.get(f'{BASE}/capabilities').json()
    assert body['views'] == ['board', 'rka']
    assert body['scope_ids'] == ['jup-consolidated']
    assert body['operations'] == []


def test_capabilities_when_disabled(client, monkeypatch: pytest.MonkeyPatch, directory: _Directory) -> None:
    directory.groups = [_grant(board=True, rka=True)]
    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', '')
    _sign_in_as(client, 'user')
    body = client.get(f'{BASE}/capabilities').json()
    assert body['enabled'] is False
    assert body['views'] == []
    assert body['reason']


# --- The payload --------------------------------------------------------------------


def test_the_board_overview_is_served_as_illustrative(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(BOARD)
    assert response.status_code == 200
    body = response.json()
    assert body['data_mode'] == 'illustrative'
    assert body['coverage'] == 'partial'
    assert body['context']['kind'] == 'source_example'
    assert body['metrics'][0]['variance'] == '-14.00'
    _no_store(response)


def test_the_shared_action_is_the_same_record_over_http(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True, rka=True)]
    _sign_in_as(client, 'user')
    board = {action['id']: action for action in client.get(BOARD).json()['actions']}
    rka = {action['id']: action for action in client.get(RKA).json()['actions']}
    assert board['example-action-water'] == rka['example-action-water']


@pytest.mark.parametrize(
    'query',
    ['view=overview&scope_id=jup-consolidated', 'view=board&scope_id=jup-spbg', 'view=board', ''],
)
def test_an_unsupported_view_or_scope_is_rejected(client, directory: _Directory, query: str) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(f'{BASE}/overview?{query}')
    assert response.status_code == 422
    _no_store(response)


# --- Sources ------------------------------------------------------------------------


def test_a_declared_source_is_served(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(f'{BASE}/sources/board-financial?view=board&scope_id=jup-consolidated')
    assert response.status_code == 200
    assert response.json()['physical_slides'] == [4]


def test_the_other_views_source_is_not_found_through_this_view(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(f'{BASE}/sources/rka-cash?view=board&scope_id=jup-consolidated')
    assert response.status_code == 404
    _no_store(response)


def test_a_source_through_an_ungranted_view_is_refused_before_lookup(client, directory: _Directory) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    assert client.get(f'{BASE}/sources/rka-cash?view=rka&scope_id=jup-consolidated').status_code == 403


# --- Unavailable ---------------------------------------------------------------------


def test_disabled_is_unavailable(client, directory: _Directory, monkeypatch: pytest.MonkeyPatch) -> None:
    directory.groups = [_grant(board=True)]
    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', 'false')
    _sign_in_as(client, 'user')
    response = client.get(BOARD)
    assert response.status_code == 503
    _no_store(response)


def test_unconfigured_is_unavailable(client, directory: _Directory, monkeypatch: pytest.MonkeyPatch) -> None:
    directory.groups = [_grant(board=True)]
    monkeypatch.delenv('JUP_LEADERSHIP_SAMPLE_FILE')
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 503


def test_a_malformed_dataset_is_unavailable_and_leaks_no_path(
    client, directory: _Directory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, seed: Path
) -> None:
    data = json.loads(seed.read_text(encoding='utf-8'))
    data['views']['board']['action_ids'].append('no-such-action')
    broken = tmp_path / 'private-mount' / 'dataset.json'
    broken.parent.mkdir()
    broken.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setenv('JUP_LEADERSHIP_SAMPLE_FILE', str(broken))
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(BOARD)
    assert response.status_code == 503
    assert 'private-mount' not in response.text


def test_an_ungranted_reader_cannot_tell_disabled_from_denied(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # Authorisation runs first, so configuration state is not disclosed to someone without access.
    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', 'false')
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 403


# --- Forced failure -----------------------------------------------------------------


def test_the_refusal_is_the_policys_doing(client) -> None:
    """Grant everything through the permission dependency and the same request passes.

    Proves the 403s above come from the leadership policy, not from an accident of the fixture.
    """
    from open_webui.routers.jup_leadership import leadership_permissions

    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 403
    client.app.dependency_overrides[leadership_permissions] = lambda: _grant(board=True).permissions
    assert client.get(BOARD).status_code == 200
