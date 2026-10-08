"""Rapat Direksi meetings over HTTP (D27 step 1, #157): who reads, who writes, and revisions.

Faked, as in `test_jup_leadership_endpoint.py`: who is signed in and which groups they belong to.
The real `get_verified_user`, `get_permissions` merge, leadership policy and a migrated records
store (SQLite, or Postgres with `JUP_TEST_POSTGRES_URL`) run on every request.

Needs the vendor runtime; skipped under CI's `--only-group dev`. A skip here is not a pass.
"""

import copy
import importlib.util
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt', 'sqlalchemy')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing)',
)

BASE = '/api/v1/leadership'
Q = '?scope_id=jup-consolidated'
MEETINGS = f'{BASE}/meetings{Q}'


def _one(meeting_id: str) -> str:
    return f'{BASE}/meetings/{meeting_id}{Q}'


@dataclass(frozen=True)
class _Account:
    role: str
    id: str = 'corsec-1'


def _grant(board: bool = True, scope: bool = True, write: bool | None = None, rka: bool = False) -> SimpleNamespace:
    grants: dict = {'board': {'view': board}, 'rka': {'view': rka}, 'scopes': {'jup_consolidated': scope}}
    if write is not None:
        grants['rapat'] = {'write': write}
    return SimpleNamespace(permissions={'jup': {'ruang_pimpinan': grants}})


class _Directory:
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
def client(
    fixture_path: Callable[..., Path], directory: _Directory, monkeypatch: pytest.MonkeyPatch, leadership_db_url: str
) -> Iterator[object]:
    """The leadership router alone, enabled, on the records store, over a migrated database."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    from jup.leadership import migrate
    from open_webui.routers import jup_leadership

    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', 'true')
    monkeypatch.setenv('JUP_LEADERSHIP_SAMPLE_FILE', str(fixture_path('leadership', 'illustrative-seed.json')))
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    engine = create_engine(leadership_db_url)
    assert migrate.run_leadership_migrations(engine) is True

    app = FastAPI()
    app.include_router(jup_leadership.router, prefix=BASE)
    app.dependency_overrides[jup_leadership.leadership_engine] = lambda: engine
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client
    engine.dispose()


def _sign_in_as(client, role: str = 'user', user_id: str = 'corsec-1') -> None:
    from open_webui.utils.auth import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: _Account(role=role, id=user_id)


def _meeting(meeting_id: str = 'rd-2026-10-08-ab12', agenda: int = 0) -> dict:
    """A document in the client's shape: nine record collections, a session, notes."""
    return {
        'id': meeting_id,
        'records': [
            [
                {
                    'id': 'r1',
                    'values': {'Nama rapat': 'Rapat Direksi Oktober'},
                    'body': '',
                    'time': {},
                    'origin': 'Record sumber',
                }
            ]
        ]
        + [[] for _ in range(8)],
        'session': {'currentAgenda': agenda, 'doneAgendas': [], 'agendaEnteredAt': 1_759_900_000_000},
        'plan': {'agendas': [{'menit': 10, 'pemapar': 'Dirut'}], 'revenueMonthly': [['Jan', 1.5, 2.25]]},
        'notes': {'1': 'Pembahasan berjalan.'},
    }


def _as_corsec(client, directory: _Directory) -> None:
    directory.groups = [_grant(write=True)]
    _sign_in_as(client)


def _audit_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith('jup.governance')]


# --- Round trip and revisions --------------------------------------------------------------


def test_the_corsec_creates_saves_and_reads_back_a_meeting(client, directory) -> None:
    _as_corsec(client, directory)
    created = client.post(MEETINGS, json={'document': _meeting()})
    assert created.status_code == 201
    assert created.json()['revision'] == 1
    assert created.headers['cache-control'] == 'private, no-store'

    saved = client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting(agenda=3)})
    assert saved.status_code == 200
    assert saved.json()['revision'] == 2

    read = client.get(_one('rd-2026-10-08-ab12')).json()
    assert read['revision'] == 2
    # The document comes back exactly as sent, floats in the plan included.
    assert read['document'] == _meeting(agenda=3)
    assert read['owner_user_id'] == 'corsec-1'
    assert read['closed_at'] is None and read['reopenings'] == []


def test_the_list_holds_every_meeting_whole(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting('rd-a')})
    client.post(MEETINGS, json={'document': _meeting('rd-b')})
    listed = client.get(MEETINGS).json()['meetings']
    assert [m['id'] for m in listed] == ['rd-a', 'rd-b']
    assert listed[0]['document'] == _meeting('rd-a')
    assert listed[0]['revision'] == 1


def test_a_stale_revision_is_a_conflict_and_writes_nothing(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    assert (
        client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting(agenda=2)}).status_code
        == 200
    )

    # A second machine still on revision 1.
    stale = client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting(agenda=7)})
    assert stale.status_code == 409
    assert stale.json()['detail']['revision'] == 2
    read = client.get(_one('rd-2026-10-08-ab12')).json()
    assert read['revision'] == 2
    assert read['document']['session']['currentAgenda'] == 2


def test_creating_an_id_already_stored_is_a_conflict_never_an_overwrite(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting(agenda=4)})
    again = client.post(MEETINGS, json={'document': _meeting(agenda=0)})
    assert again.status_code == 409
    assert again.json()['detail']['revision'] == 1
    assert client.get(_one('rd-2026-10-08-ab12')).json()['document']['session']['currentAgenda'] == 4


def test_saving_a_meeting_that_does_not_exist_is_404(client, directory) -> None:
    _as_corsec(client, directory)
    response = client.put(_one('rd-nope'), json={'base_revision': 1, 'document': _meeting('rd-nope')})
    assert response.status_code == 404
    assert client.get(_one('rd-nope')).status_code == 404


def _broken(change: Callable[[dict], None]) -> dict:
    document = copy.deepcopy(_meeting())
    change(document)
    return document


MALFORMED = {
    'eight collections': _broken(lambda d: d['records'].pop()),
    'a collection that is not a list': _broken(lambda d: d['records'].__setitem__(3, {})),
    'no session': _broken(lambda d: d.pop('session')),
    'a boolean agenda': _broken(lambda d: d['session'].__setitem__('currentAgenda', True)),
    'done agendas missing': _broken(lambda d: d['session'].pop('doneAgendas')),
    'an id a URL cannot carry': _broken(lambda d: d.__setitem__('id', '../etc')),
}


@pytest.mark.parametrize('document', MALFORMED.values(), ids=MALFORMED.keys())
def test_a_malformed_document_is_refused_on_create(client, directory, document) -> None:
    _as_corsec(client, directory)
    assert client.post(MEETINGS, json={'document': document}).status_code == 422
    assert client.get(MEETINGS).json()['meetings'] == []


@pytest.mark.parametrize('document', MALFORMED.values(), ids=MALFORMED.keys())
def test_a_malformed_document_is_refused_on_save_and_the_stored_one_stays(client, directory, document) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    saved = client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': document})
    assert saved.status_code == 422
    read = client.get(_one('rd-2026-10-08-ab12')).json()
    assert read['revision'] == 1 and read['document'] == _meeting()


def test_a_document_saved_under_another_meetings_id_is_refused(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting('rd-a')})
    client.post(MEETINGS, json={'document': _meeting('rd-b')})
    response = client.put(_one('rd-a'), json={'base_revision': 1, 'document': _meeting('rd-b')})
    assert response.status_code == 422
    assert client.get(_one('rd-a')).json()['revision'] == 1


def test_an_oversized_meeting_is_refused(client, directory, monkeypatch) -> None:
    from jup.leadership import meetings

    monkeypatch.setattr(meetings, 'MAX_BYTES', 1_000)
    _as_corsec(client, directory)
    big = _meeting() | {'notes': {'1': 'x' * 2_000}}
    assert client.post(MEETINGS, json={'document': big}).status_code == 422


# --- Who reads, who writes ------------------------------------------------------------------


def test_a_board_reader_without_the_write_grant_reads_but_cannot_write(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})

    directory.groups = [_grant(write=None)]
    _sign_in_as(client, user_id='direksi-1')
    assert client.get(MEETINGS).status_code == 200
    assert client.get(_one('rd-2026-10-08-ab12')).json()['revision'] == 1
    assert client.post(MEETINGS, json={'document': _meeting('rd-other')}).status_code == 403
    saved = client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting(agenda=5)})
    assert saved.status_code == 403
    assert client.get(_one('rd-2026-10-08-ab12')).json()['revision'] == 1


@pytest.mark.parametrize(
    'groups',
    [[], [_grant(board=False, rka=True)], [_grant(scope=False)], [_grant(board=False, write=True)]],
    ids=['no grant', 'rka only', 'no scope', 'write without board view'],
)
def test_reading_needs_the_board_view_and_the_scope(client, directory, groups) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    directory.groups = groups
    assert client.get(MEETINGS).status_code == 403
    assert client.get(_one('rd-2026-10-08-ab12')).status_code == 403
    assert client.post(MEETINGS, json={'document': _meeting('rd-x')}).status_code == 403


def test_an_admin_without_grants_is_refused_everything(client, directory) -> None:
    directory.groups = []
    _sign_in_as(client, role='admin', user_id='admin-1')
    assert client.get(MEETINGS).status_code == 403
    assert client.get(_one('rd-2026-10-08-ab12')).status_code == 403
    assert client.post(MEETINGS, json={'document': _meeting()}).status_code == 403
    assert client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting()}).status_code == 403


def test_a_refused_reader_cannot_tell_whether_meetings_are_served(client, directory, monkeypatch) -> None:
    """Authorisation comes before readiness: 403 whether or not records are on."""
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'sample')
    directory.groups = []
    _sign_in_as(client)
    assert client.get(MEETINGS).status_code == 403


def test_meetings_are_served_only_on_the_records_store(client, directory, monkeypatch) -> None:
    _as_corsec(client, directory)
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'sample')
    assert client.get(MEETINGS).status_code == 503
    assert client.post(MEETINGS, json={'document': _meeting()}).status_code == 503
    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', '')
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    assert client.get(MEETINGS).status_code == 503


def test_capabilities_say_when_records_and_the_write_grant_are_on(client, directory, monkeypatch) -> None:
    _as_corsec(client, directory)
    body = client.get(f'{BASE}/capabilities').json()
    assert body['records'] is True
    assert body['operations'] == ['rapat.write']

    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'sample')
    assert client.get(f'{BASE}/capabilities').json()['records'] is False
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'nonsense')
    assert client.get(f'{BASE}/capabilities').json()['records'] is False

    # A reader with no view learns nothing about the store.
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    directory.groups = []
    assert client.get(f'{BASE}/capabilities').json()['records'] is False


# --- Audit ------------------------------------------------------------------------------------


def test_every_create_and_save_is_audited_without_content(client, directory, caplog) -> None:
    caplog.set_level('INFO', logger='jup.governance')
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting(agenda=1)})
    client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 1, 'document': _meeting(agenda=2)})
    directory.groups = [_grant()]
    client.put(_one('rd-2026-10-08-ab12'), json={'base_revision': 2, 'document': _meeting(agenda=3)})

    lines = _audit_lines(caplog)
    writes = [line for line in lines if "'leadership_write'" in line]
    assert len(writes) == 4
    assert "'operation': 'meeting_create'" in writes[0] and "'result': 'recorded'" in writes[0]
    assert "'operation': 'meeting_save'" in writes[1] and "'revision': 2" in writes[1]
    assert "'result': 'StaleRevision'" in writes[2]
    assert "'result': 'refused'" in writes[3]
    assert all("'user': 'corsec-1'" in line for line in writes)
    assert all("'meeting_id': 'rd-2026-10-08-ab12'" in line for line in writes)
    # The minutes themselves never reach the trail.
    assert not any('Rapat Direksi Oktober' in line or 'Pembahasan berjalan' in line for line in lines)
    assert json.dumps(_meeting()) not in '\n'.join(lines)
