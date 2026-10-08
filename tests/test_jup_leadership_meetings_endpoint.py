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


# --- Tutup rapat and Buka kembali (#159) -------------------------------------------------------

ID = 'rd-2026-10-08-ab12'
CLOSED_AT = 1_759_910_000_000


def _closed(agenda: int = 8, reopenings: list | None = None) -> dict:
    """The document as the Corsec closes it: `session.closedAt` set."""
    document = _meeting(agenda=agenda)
    document['session'] |= {'closedAt': CLOSED_AT, 'doneAgendas': [agenda]}
    if reopenings is not None:
        document['session']['reopenings'] = reopenings
    return document


def _reopened(reason: str, before: list | None = None) -> dict:
    """The document as Buka kembali leaves it: no closing time, the reason as its last reopening."""
    document = _meeting(agenda=8)
    document['session'] |= {
        'doneAgendas': [8],
        'reopenings': [*(before or []), {'at': 1_759_920_000_000, 'reason': reason}],
    }
    return document


def _close(client, base: int, document: dict | None = None):
    return client.post(
        f'{BASE}/meetings/{ID}/close{Q}', json={'base_revision': base, 'document': document or _closed()}
    )


def _reopen(client, base: int, reason: str, document: dict | None = None):
    return client.post(
        f'{BASE}/meetings/{ID}/reopen{Q}',
        json={'base_revision': base, 'reason': reason, 'document': document or _reopened(reason.strip())},
    )


def _created_and_closed(client, directory) -> None:
    _as_corsec(client, directory)
    assert client.post(MEETINGS, json={'document': _meeting()}).status_code == 201
    closed = _close(client, 1)
    assert closed.status_code == 200, closed.text
    assert closed.json()['revision'] == 2


def test_closing_stores_the_closing_document_and_marks_the_meeting_closed(client, directory) -> None:
    _created_and_closed(client, directory)
    read = client.get(_one(ID)).json()
    assert read['revision'] == 2
    assert read['document'] == _closed()
    assert isinstance(read['closed_at'], int)
    assert read['reopenings'] == []


def test_a_closed_meeting_refuses_every_save_from_any_machine(client, directory) -> None:
    _created_and_closed(client, directory)
    # The current revision, the stale one, and a second machine signed in as the Corsec too.
    for base in (2, 1):
        refused = client.put(_one(ID), json={'base_revision': base, 'document': _meeting(agenda=4)})
        assert refused.status_code == 409
        assert refused.json()['detail']['revision'] == 2
        assert 'closed' in refused.json()['detail']['message']
    _sign_in_as(client, user_id='corsec-2')
    assert client.put(_one(ID), json={'base_revision': 2, 'document': _meeting(agenda=4)}).status_code == 409
    read = client.get(_one(ID)).json()
    assert read['revision'] == 2 and read['document'] == _closed()


def test_closing_a_closed_meeting_again_is_refused(client, directory) -> None:
    _created_and_closed(client, directory)
    again = _close(client, 2)
    assert again.status_code == 409
    assert again.json()['detail']['revision'] == 2


def test_a_plain_save_never_closes_a_meeting(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    assert client.put(_one(ID), json={'base_revision': 1, 'document': _closed()}).status_code == 422
    read = client.get(_one(ID)).json()
    assert read['revision'] == 1 and read['closed_at'] is None


def test_closing_needs_a_closing_document_and_the_current_revision(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    assert _close(client, 1, _meeting(agenda=8)).status_code == 422
    client.put(_one(ID), json={'base_revision': 1, 'document': _meeting(agenda=2)})
    stale = _close(client, 1)
    assert stale.status_code == 409 and stale.json()['detail']['revision'] == 2
    assert client.get(_one(ID)).json()['closed_at'] is None


@pytest.mark.parametrize('reason', ['', '   \n '], ids=['empty', 'blank'])
def test_reopening_without_a_reason_is_refused(client, directory, reason) -> None:
    _created_and_closed(client, directory)
    refused = _reopen(client, 2, reason, _reopened('x'))
    assert refused.status_code == 422
    read = client.get(_one(ID)).json()
    assert read['revision'] == 2 and read['closed_at'] is not None and read['reopenings'] == []


def test_reopening_with_a_reason_opens_it_and_keeps_when_why_and_who(client, directory) -> None:
    _created_and_closed(client, directory)
    reopened = _reopen(client, 2, '  Keputusan agenda 07 perlu dikoreksi. ')
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()['revision'] == 3

    read = client.get(_one(ID)).json()
    assert read['closed_at'] is None
    [kept] = read['reopenings']
    assert kept['reason'] == 'Keputusan agenda 07 perlu dikoreksi.'
    assert kept['by'] == 'corsec-1'
    assert isinstance(kept['at'], int)
    # The document carries the reason too: that is what the Risalah prints.
    assert read['document']['session']['reopenings'][-1]['reason'] == 'Keputusan agenda 07 perlu dikoreksi.'
    # Open again: saves land.
    assert client.put(_one(ID), json={'base_revision': 3, 'document': _reopened('x')}).status_code == 200


def test_the_reopened_document_must_carry_the_reason_and_not_be_closed(client, directory) -> None:
    _created_and_closed(client, directory)
    assert _reopen(client, 2, 'Alasan A', _reopened('Alasan B')).status_code == 422
    assert _reopen(client, 2, 'Alasan A', _meeting(agenda=8)).status_code == 422
    assert _reopen(client, 2, 'Alasan A', _closed(reopenings=[{'at': 1, 'reason': 'Alasan A'}])).status_code == 422
    assert client.get(_one(ID)).json()['closed_at'] is not None


def test_reopening_an_open_meeting_or_on_a_stale_revision_is_a_conflict(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    not_closed = _reopen(client, 1, 'Alasan')
    assert not_closed.status_code == 409 and not_closed.json()['detail']['revision'] == 1
    _close(client, 1)
    stale = _reopen(client, 1, 'Alasan')
    assert stale.status_code == 409 and stale.json()['detail']['revision'] == 2
    assert client.get(_one(ID)).json()['closed_at'] is not None


def test_closing_again_freezes_it_again_and_every_reopening_is_kept(client, directory) -> None:
    _created_and_closed(client, directory)
    first = [{'at': 1_759_920_000_000, 'reason': 'Pertama'}]
    assert _reopen(client, 2, 'Pertama').status_code == 200
    assert _close(client, 3, _closed(reopenings=first)).status_code == 200
    assert client.put(_one(ID), json={'base_revision': 4, 'document': _meeting()}).status_code == 409
    assert _reopen(client, 4, 'Kedua', _reopened('Kedua', before=first)).status_code == 200

    read = client.get(_one(ID)).json()
    assert read['revision'] == 5 and read['closed_at'] is None
    assert [r['reason'] for r in read['reopenings']] == ['Pertama', 'Kedua']
    assert [r['reason'] for r in read['document']['session']['reopenings']] == ['Pertama', 'Kedua']


def test_a_meeting_created_closed_is_closed_on_the_server(client, directory) -> None:
    _as_corsec(client, directory)
    assert client.post(MEETINGS, json={'document': _closed()}).status_code == 201
    assert client.get(_one(ID)).json()['closed_at'] is not None
    assert client.put(_one(ID), json={'base_revision': 1, 'document': _meeting()}).status_code == 409


def test_closing_and_reopening_need_the_write_grant(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting()})
    directory.groups = [_grant(write=None)]
    _sign_in_as(client, user_id='direksi-1')
    assert _close(client, 1).status_code == 403
    directory.groups = [_grant(write=True)]
    _close(client, 1)
    directory.groups = [_grant(write=None)]
    assert _reopen(client, 2, 'Alasan').status_code == 403
    assert client.get(_one(ID)).json()['closed_at'] is not None


def test_closing_and_reopening_are_audited_without_the_reason(client, directory, caplog) -> None:
    caplog.set_level('INFO', logger='jup.governance')
    _created_and_closed(client, directory)
    _reopen(client, 2, '')
    _reopen(client, 2, 'Rahasia alasan pembukaan')

    writes = [line for line in _audit_lines(caplog) if "'leadership_write'" in line]
    close, refused, reopen = writes[-3:]
    assert "'operation': 'meeting_close'" in close and "'result': 'recorded'" in close and "'closed': True" in close
    assert "'operation': 'meeting_reopen'" in refused and "'result': 'MissingReason'" in refused
    assert (
        "'operation': 'meeting_reopen'" in reopen and "'result': 'recorded'" in reopen and "'closed': False" in reopen
    )
    assert all("'user': 'corsec-1'" in line and f"'meeting_id': '{ID}'" in line for line in writes[-3:])
    assert not any('Rahasia' in line for line in _audit_lines(caplog))


# --- Pindahkan ke server (#161) ----------------------------------------------------------------

MOVE = f'{BASE}/meetings/move{Q}'


def _move(client, *documents: dict):
    return client.post(MOVE, json={'documents': list(documents)})


def test_moving_creates_each_meeting_and_answers_one_result_per_meeting(client, directory) -> None:
    _as_corsec(client, directory)
    response = _move(client, _meeting('rd-a'), _meeting('rd-b', agenda=4))
    assert response.status_code == 200, response.text
    assert response.json()['results'] == [
        {'id': 'rd-a', 'result': 'moved', 'revision': 1, 'confirmed': True, 'reason': None},
        {'id': 'rd-b', 'result': 'moved', 'revision': 1, 'confirmed': True, 'reason': None},
    ]
    read = client.get(_one('rd-b')).json()
    assert read['document'] == _meeting('rd-b', agenda=4)
    assert read['owner_user_id'] == 'corsec-1'


def test_moving_never_overwrites_a_meeting_already_on_the_server(client, directory) -> None:
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting('rd-a', agenda=6)})
    client.put(_one('rd-a'), json={'base_revision': 1, 'document': _meeting('rd-a', agenda=7)})

    results = _move(client, _meeting('rd-a', agenda=0)).json()['results']
    # A different copy: on the server already, and not confirmed, so the browser keeps its own.
    assert results == [{'id': 'rd-a', 'result': 'on_server', 'revision': 2, 'confirmed': False, 'reason': None}]
    read = client.get(_one('rd-a')).json()
    assert read['revision'] == 2 and read['document']['session']['currentAgenda'] == 7


def test_moving_the_same_meeting_again_is_confirmed_without_a_write(client, directory) -> None:
    _as_corsec(client, directory)
    _move(client, _meeting('rd-a'))
    again = _move(client, _meeting('rd-a')).json()['results']
    assert again == [{'id': 'rd-a', 'result': 'on_server', 'revision': 1, 'confirmed': True, 'reason': None}]
    assert client.get(_one('rd-a')).json()['revision'] == 1


def test_a_malformed_meeting_is_refused_and_the_others_still_move(client, directory) -> None:
    _as_corsec(client, directory)
    broken = MALFORMED['eight collections'] | {'id': 'rd-broken'}
    results = _move(client, _meeting('rd-a'), broken, 'not a meeting', _meeting('rd-b')).json()['results']
    assert [(r['id'], r['result'], r['confirmed']) for r in results] == [
        ('rd-a', 'moved', True),
        ('rd-broken', 'refused', False),
        (None, 'refused', False),
        ('rd-b', 'moved', True),
    ]
    assert results[1]['reason'] == 'a meeting holds exactly 9 record collections'
    assert [m['id'] for m in client.get(MEETINGS).json()['meetings']] == ['rd-a', 'rd-b']


def test_a_meeting_moved_closed_arrives_closed(client, directory) -> None:
    _as_corsec(client, directory)
    assert _move(client, _closed()).json()['results'][0]['result'] == 'moved'
    assert client.get(_one(ID)).json()['closed_at'] is not None
    assert client.put(_one(ID), json={'base_revision': 1, 'document': _meeting()}).status_code == 409


def test_moving_needs_the_write_grant_and_the_records_store(client, directory, monkeypatch) -> None:
    directory.groups = [_grant(write=None)]
    _sign_in_as(client, user_id='direksi-1')
    assert _move(client, _meeting('rd-a')).status_code == 403
    _as_corsec(client, directory)
    assert client.get(MEETINGS).json()['meetings'] == []
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'sample')
    assert _move(client, _meeting('rd-a')).status_code == 503


@pytest.mark.parametrize('documents', [[], [_meeting(f'rd-{n}') for n in range(201)]], ids=['none', '201'])
def test_a_move_carries_one_to_two_hundred_meetings(client, directory, documents) -> None:
    _as_corsec(client, directory)
    assert client.post(MOVE, json={'documents': documents}).status_code == 422
    assert client.get(MEETINGS).json()['meetings'] == []


def test_every_moved_meeting_is_audited_without_content(client, directory, caplog) -> None:
    caplog.set_level('INFO', logger='jup.governance')
    _as_corsec(client, directory)
    client.post(MEETINGS, json={'document': _meeting('rd-a', agenda=3)})
    _move(client, _meeting('rd-a'), _meeting('rd-b'), MALFORMED['no session'])
    directory.groups = [_grant(write=None)]
    _move(client, _meeting('rd-c'))

    moves = [line for line in _audit_lines(caplog) if "'operation': 'meeting_move'" in line]
    assert len(moves) == 4
    assert (
        "'result': 'on_server'" in moves[0] and "'meeting_id': 'rd-a'" in moves[0] and "'confirmed': False" in moves[0]
    )
    assert "'result': 'moved'" in moves[1] and "'meeting_id': 'rd-b'" in moves[1]
    assert "'result': 'refused'" in moves[2]
    assert "'result': 'refused'" in moves[3] and 'meeting_id' not in moves[3]
    assert all("'user': 'corsec-1'" in line for line in moves)
    assert not any('Rapat Direksi Oktober' in line or 'Pembahasan berjalan' in line for line in _audit_lines(caplog))


# --- Tindakan into the review queue at Tutup rapat (#160) ----------------------------------


def _tindakan(record_id: str, title: str, pic: str = '', due: str = '', id_tindakan: str = '', **extra) -> dict:
    values: dict = {
        'Tindakan / deliverable': title,
        'Agenda': '4. Program Prioritas',
        'Asal tindak lanjut': 'Rapat ini',
    }
    if pic:
        values['PIC utama'] = pic
    if due:
        values['Target waktu'] = {'start': due, 'end': ''}
    if id_tindakan:
        values['ID tindakan'] = id_tindakan
    return {'id': record_id, 'values': values | extra, 'body': '', 'time': {}, 'origin': 'Record baru'}


def _with_tindakan(document: dict, *tindakan: dict) -> dict:
    document = copy.deepcopy(document)
    document['records'][0][0]['values']['Tanggal & waktu'] = {'start': '2026-10-08T09:00', 'end': ''}
    document['records'][8] = list(tindakan)
    return document


TINDAKAN = (
    _tindakan('t1', 'Kirim revisi RKAP ke Dekom', pic='Dir. Keuangan', due='2026-10-31', id_tindakan='AP-01'),
    _tindakan('t2', 'Susun kajian tarif air', pic='Dir. Operasi', due='2026-11-15T10:00'),
)


def _engine(client):
    from open_webui.routers import jup_leadership

    return client.app.dependency_overrides[jup_leadership.leadership_engine]()


def _batches(client) -> list[dict]:
    from jup.leadership import imports

    with _engine(client).connect() as connection:
        return [imports.read_batch(connection, row['id']) for row in imports.list_batches(connection)]


def _close_with(client, directory, base: int, document: dict):
    response = _close(client, base, document)
    assert response.status_code == 200, response.text
    return response.json()


def _created(client, directory, *tindakan: dict) -> dict:
    _as_corsec(client, directory)
    document = _with_tindakan(_meeting(), *tindakan)
    assert client.post(MEETINGS, json={'document': document}).status_code == 201
    return document


def _closing(document: dict) -> dict:
    document = copy.deepcopy(document)
    document['session'] |= {'closedAt': CLOSED_AT, 'doneAgendas': [8]}
    return document


def _reopening(document: dict, reason: str = 'Tindakan perlu dikoreksi.') -> dict:
    document = copy.deepcopy(document)
    document['session'].pop('closedAt', None)
    document['session']['reopenings'] = [*document['session'].get('reopenings', []), {'at': 1, 'reason': reason}]
    return document


def _close_reopen_close(client, base: int, closed: dict, reclosed: dict) -> dict:
    reopened = _reopening(closed)
    assert _reopen(client, base, 'Tindakan perlu dikoreksi.', reopened).status_code == 200
    again = _close(client, base + 1, _closing(reclosed))
    assert again.status_code == 200, again.text
    return again.json()


def test_closing_puts_every_tindakan_in_one_review_batch_mapped_from_the_notulen(client, directory, caplog) -> None:
    caplog.set_level('INFO')
    document = _created(client, directory, *TINDAKAN)
    answer = _close_with(client, directory, 1, _closing(document))
    assert answer['import_batch']['created'] is True

    [batch] = _batches(client)
    assert batch['id'] == answer['import_batch']['id']
    assert batch['source_filename'] == f'Rapat Direksi, 2026-10-08, {ID}'
    assert batch['meeting_date'] == '2026-10-08'
    assert batch['uploaded_by'] == 'corsec-1'
    assert batch['status'] == 'open'
    first, second = batch['candidates']
    assert [first['match_kind'], second['match_kind']] == ['new', 'new']
    assert first['review_state'] == 'pending' and first['verification'] == 'unverified'
    assert {k: first['payload'][k] for k in ('key', 'external_id', 'title', 'owner_label', 'due', 'slide')} == {
        'key': 't1',
        'external_id': 'AP-01',
        'title': 'Kirim revisi RKAP ke Dekom',
        'owner_label': 'Dir. Keuangan',
        'due': {'precision': 'date', 'value': '2026-10-31'},
        'slide': '4. Program Prioritas · Tindakan 1',
    }
    assert first['payload']['source_document'] == f'Rapat Direksi, 2026-10-08, {ID}'
    # No ID tindakan: the record id is the external id. A datetime keeps only its day.
    assert second['payload']['external_id'] == 't2'
    assert second['payload']['due'] == {'precision': 'date', 'value': '2026-11-15'}
    assert second['payload']['slide'] == '4. Program Prioritas · Tindakan 2'

    lines = [line for line in _audit_lines(caplog) if 'import_upload' in line]
    assert len(lines) == 1
    assert batch['id'] in lines[0] and 'meeting_close' in lines[0] and 'recorded' in lines[0]


def test_closing_an_unchanged_meeting_again_creates_no_new_batch(client, directory, caplog) -> None:
    caplog.set_level('INFO')
    document = _created(client, directory, *TINDAKAN)
    first = _close_with(client, directory, 1, _closing(document))
    again = _close_reopen_close(client, 2, _closing(document), document)
    assert again['import_batch'] == {'id': first['import_batch']['id'], 'created': False}
    assert len(_batches(client)) == 1
    assert any('replayed' in line for line in _audit_lines(caplog) if 'import_upload' in line)


def test_an_accepted_tindakan_matches_its_reference_on_re_close_and_is_never_duplicated(client, directory) -> None:
    from sqlalchemy import func, select

    from jup.leadership import imports
    from jup.leadership.models import action

    document = _created(client, directory, *TINDAKAN)
    _close_with(client, directory, 1, _closing(document))
    [batch] = _batches(client)
    for candidate in batch['candidates']:
        imports.review_candidate(_engine(client), candidate_id=candidate['id'], decision='accept', reviewer='rev-1')

    # Reopened and closed again with one more Tindakan: the file changed, so a new batch.
    added = _with_tindakan(_meeting(), *TINDAKAN, _tindakan('t3', 'Laporkan progres SPAM', pic='Dir. Operasi'))
    again = _close_reopen_close(client, 2, _closing(document), added)
    assert again['import_batch']['created'] is True
    newest = next(b for b in _batches(client) if b['id'] == again['import_batch']['id'])
    kinds = {c['candidate_key']: c['match_kind'] for c in newest['candidates']}
    assert kinds == {'t1': 'external_ref', 't2': 'external_ref', 't3': 'new'}
    for candidate in newest['candidates']:
        if candidate['match_kind'] == 'external_ref':
            imports.review_candidate(_engine(client), candidate_id=candidate['id'], decision='accept', reviewer='rev-1')
    with _engine(client).connect() as connection:
        assert connection.execute(select(func.count()).select_from(action)).scalar() == 2


def test_a_changed_tindakan_comes_through_again_with_its_difference(client, directory) -> None:
    from jup.leadership import imports

    document = _created(client, directory, *TINDAKAN)
    _close_with(client, directory, 1, _closing(document))
    [batch] = _batches(client)
    first = next(c for c in batch['candidates'] if c['candidate_key'] == 't1')
    imports.review_candidate(_engine(client), candidate_id=first['id'], decision='accept', reviewer='rev-1')

    moved = _tindakan('t1', 'Kirim revisi RKAP ke Dekom', pic='Dir. Keuangan', due='2026-11-30', id_tindakan='AP-01')
    again = _close_reopen_close(client, 2, _closing(document), _with_tindakan(_meeting(), moved, TINDAKAN[1]))
    newest = next(b for b in _batches(client) if b['id'] == again['import_batch']['id'])
    changed = next(c for c in newest['candidates'] if c['candidate_key'] == 't1')
    assert changed['match_kind'] == 'conflict'
    assert changed['matched_action_id'] is not None
    assert changed['conflict'] == {
        'due': {
            'recorded': {'precision': 'date', 'value': '2026-10-31'},
            'candidate': {'precision': 'date', 'value': '2026-11-30'},
        }
    }
    # The unaccepted one stays a new-action candidate.
    assert next(c for c in newest['candidates'] if c['candidate_key'] == 't2')['match_kind'] == 'new'


def test_a_tindakan_without_pic_or_date_is_marked_missing_with_a_reason(client, directory) -> None:
    document = _created(client, directory, _tindakan('t1', 'Tindak lanjuti temuan audit'))
    _close_with(client, directory, 1, _closing(document))
    [batch] = _batches(client)
    [candidate] = batch['candidates']
    payload = candidate['payload']
    assert payload['owner_label'] is None and payload['due'] is None
    assert payload['missing']['owner_label'] == 'PIC utama belum diisi di Notulen'
    assert payload['missing']['due'] == 'Target waktu belum diisi di Notulen'


def test_a_meeting_without_tindakan_closes_without_a_batch(client, directory, caplog) -> None:
    caplog.set_level('INFO')
    document = _created(client, directory, _tindakan('t1', '   '))
    answer = _close_with(client, directory, 1, _closing(document))
    assert answer['import_batch'] is None
    assert _batches(client) == []
    assert not [line for line in _audit_lines(caplog) if 'import_upload' in line]


def test_an_id_tindakan_used_twice_falls_back_to_record_ids_and_still_closes(client, directory) -> None:
    document = _created(
        client,
        directory,
        _tindakan('t1', 'Satu', id_tindakan='AP-01'),
        _tindakan('t2', 'Dua', id_tindakan='AP-01'),
    )
    _close_with(client, directory, 1, _closing(document))
    [batch] = _batches(client)
    payloads = {c['candidate_key']: c['payload'] for c in batch['candidates']}
    assert payloads['t1']['external_id'] == 't1' and payloads['t2']['external_id'] == 't2'
    assert payloads['t1']['source_metadata']['id_tindakan_duplicate'] is True


def test_a_refused_close_creates_no_batch(client, directory) -> None:
    document = _created(client, directory, *TINDAKAN)
    client.put(_one(ID), json={'base_revision': 1, 'document': document})
    assert _close(client, 1, _closing(document)).status_code == 409
    assert _batches(client) == []
