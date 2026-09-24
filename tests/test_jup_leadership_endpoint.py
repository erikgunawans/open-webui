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


def _grant(board: bool = False, rka: bool = False, scope: bool = True, submit: bool | None = None) -> SimpleNamespace:
    """A group row carrying leadership permissions, shaped as the host stores them."""
    grants = {
        'board': {'view': board},
        'rka': {'view': rka},
        'scopes': {'jup_consolidated': scope},
    }
    if submit is not None:
        grants['actions'] = {'submit': submit}
    return SimpleNamespace(permissions={'jup': {'ruang_pimpinan': grants}})


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


def _sign_in_as(client, role: str | None, user_id: str = 'test-user') -> None:
    from fastapi import HTTPException, status

    from open_webui.utils.auth import get_current_user

    def _current_user():
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
        return _Account(role=role, id=user_id)

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


# --- One action and its history (P2 T2) ---------------------------------------------

ACTION = f'{BASE}/actions/act-1?view=board&scope_id=jup-consolidated'


@pytest.fixture
def records(client, tmp_path: Path):
    """A migrated SQLite records store holding one action with a revised due date."""
    from sqlalchemy import create_engine

    from jup.leadership import actions, migrate
    from jup.leadership.repository import unit_of_work
    from open_webui.routers import jup_leadership

    engine = create_engine(f'sqlite:///{tmp_path / "records.db"}')
    assert migrate.run_leadership_migrations(engine) is True
    with unit_of_work(engine) as uow:
        actions.create_action(
            uow,
            action_id='act-1',
            title='Finalise SPBG offtake term sheet',
            pic_label='PIC Komersial',
            pic_user_id='pic-1',
            due=actions.Due('date', '2026-09-01'),
            author='pic-1',
        )
    with unit_of_work(engine) as uow:
        actions.revise_due(
            uow,
            action_id='act-1',
            expected_version=1,
            due=actions.Due('month', '2026-12'),
            reason='PGN delay',
            author='pic-1',
        )
    client.app.dependency_overrides[jup_leadership.leadership_engine] = lambda: engine
    yield engine
    engine.dispose()


def _audit_lines(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.getMessage().startswith('jup.governance')]


def test_a_granted_reader_gets_the_action_its_history_and_its_flags(client, directory, records, caplog) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    with caplog.at_level('INFO'):
        response = client.get(ACTION)
    assert response.status_code == 200
    _no_store(response)
    body = response.json()
    assert body['action']['id'] == 'act-1'
    assert body['action']['version'] == 2
    assert body['action']['original_due'] == {'precision': 'date', 'value': '2026-09-01'}
    assert body['action']['current_due'] == {'precision': 'month', 'value': '2026-12'}
    assert [entry['kind'] for entry in body['history']] == ['created', 'due_revised']
    assert body['history'][1]['reason'] == 'PGN delay'
    # Month precision: no overdue value is invented, and the reason says why.
    assert body['flags']['overdue'] is None and body['flags']['reasons']['overdue']
    assert body['flags']['stale'] is None
    lines = _audit_lines(caplog)
    assert any("'operation': 'action'" in line and "'result': 'served'" in line for line in lines)
    assert not any('Finalise SPBG' in line for line in lines), 'audit lines carry ids, never record content'


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_the_action_route_refuses_without_a_grant(client, records, role: str, caplog) -> None:
    _sign_in_as(client, role)
    with caplog.at_level('INFO'):
        response = client.get(ACTION)
    assert response.status_code == 403
    _no_store(response)
    assert 'SPBG' not in response.text
    assert any("'result': 'refused'" in line for line in _audit_lines(caplog))


def test_the_action_route_refuses_signed_out(client, records) -> None:
    _sign_in_as(client, None)
    assert client.get(ACTION).status_code == 401


def test_an_unknown_action_is_404(client, directory, records) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(f'{BASE}/actions/nope?view=board&scope_id=jup-consolidated')
    assert response.status_code == 404
    _no_store(response)


def test_an_unready_records_store_is_503(client, directory, records, monkeypatch: pytest.MonkeyPatch) -> None:
    from jup.leadership import migrate

    monkeypatch.setattr(migrate, '_schema_ready', False)
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(ACTION)
    assert response.status_code == 503
    assert 'SPBG' not in response.text


def test_the_action_route_is_off_when_the_section_is(client, directory, records, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', 'false')
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    assert client.get(ACTION).status_code == 503


def test_revocation_denies_the_action_history_on_the_next_request(client, directory, records) -> None:
    directory.groups = [_grant(rka=True)]
    _sign_in_as(client, 'user')
    rka = f'{BASE}/actions/act-1?view=rka&scope_id=jup-consolidated'
    assert client.get(rka).status_code == 200
    directory.groups = []
    assert client.get(rka).status_code == 403


# --- The PIC's writes (P2 T3) -------------------------------------------------------

PDF = b'%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF\n'
Q = '?view=board&scope_id=jup-consolidated'
EVIDENCE = f'{BASE}/actions/act-1/evidence{Q}'
PROGRESS = f'{BASE}/actions/act-1/progress{Q}'


@pytest.fixture
def bucket(client, tmp_path: Path):
    """A local evidence store standing in for the host bucket."""
    from jup.leadership.evidence_store import LocalEvidenceStore
    from open_webui.routers import jup_leadership

    root = tmp_path / 'bucket'
    client.app.dependency_overrides[jup_leadership.leadership_evidence_store] = lambda: LocalEvidenceStore(root)
    return root


@pytest.fixture
def started(records):
    """act-1 moved to in progress by its PIC (version 3)."""
    from jup.leadership import actions
    from jup.leadership.repository import unit_of_work

    with unit_of_work(records) as uow:
        actions.change_state(uow, action_id='act-1', expected_version=2, to_state='in_progress', author='pic-1')
    return records


def _as_pic(client, directory, submit: bool = True) -> None:
    directory.groups = [_grant(board=True, submit=submit)]
    _sign_in_as(client, 'user', user_id='pic-1')


def _upload(client, version: int = 3, content: bytes = PDF, **data):
    form = {'expected_version': str(version), **{k: str(v) for k, v in data.items()}}
    return client.post(EVIDENCE, data=form, files={'file': ('berita acara.pdf', content, 'application/pdf')})


def _stored_objects(bucket: Path) -> list[Path]:
    return [p for p in bucket.rglob('*') if p.is_file()] if bucket.exists() else []


def test_the_pic_uploads_evidence_and_downloads_it_back(client, directory, started, bucket, caplog) -> None:
    _as_pic(client, directory)
    with caplog.at_level('INFO'):
        response = _upload(client, note='signed BA')
    assert response.status_code == 200, response.text
    _no_store(response)
    body = response.json()
    assert body['version'] == 4 and body['replayed'] is False and body['closure_request_id'] is None
    evidence = body['evidence']
    assert (evidence['revision'], evidence['kind'], evidence['filename']) == (1, 'file', 'berita acara.pdf')
    assert [p.relative_to(bucket).as_posix() for p in _stored_objects(bucket)] == [
        f'leadership/evidence/{evidence["sha256"]}'
    ]
    assert any(
        "'operation': 'evidence_submit'" in line and "'result': 'recorded'" in line for line in _audit_lines(caplog)
    )

    download = client.get(f'{BASE}/evidence/{evidence["id"]}{Q}')
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers['content-type'] == 'application/pdf'
    assert download.headers['x-content-type-options'] == 'nosniff'
    assert download.headers['content-disposition'].startswith('attachment;')
    _no_store(download)


def test_completion_evidence_awaits_the_bod_and_does_not_close(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    response = _upload(client, completion='true')
    assert response.status_code == 200, response.text
    assert response.json()['closure_request_id']
    action = client.get(ACTION).json()['action']
    assert action['state'] == 'awaiting_bod_closure'


@pytest.mark.parametrize(
    ('role', 'user_id', 'submit'),
    [
        ('admin', 'admin-1', None),  # admin with a read grant only
        ('admin', 'admin-1', True),  # admin holding submit, but not the PIC
        ('user', 'boc-1', None),  # a BOC observer: read grant, no submit
        ('user', 'reader-1', False),  # a read-only reader
        ('user', 'pic-2', True),  # holds submit, is the PIC of another action
        ('user', 'pic-1', False),  # the PIC, without the submit capability
    ],
)
def test_only_the_pic_with_the_capability_writes(client, directory, started, bucket, role, user_id, submit) -> None:
    directory.groups = [_grant(board=True, submit=submit)]
    _sign_in_as(client, role, user_id=user_id)
    for response in (
        _upload(client),
        client.post(EVIDENCE, data={'expected_version': '3', 'url': 'https://example.com/ba'}),
        client.post(PROGRESS, json={'expected_version': 3, 'narrative': 'x'}),
    ):
        assert response.status_code == 403, response.text
        _no_store(response)
    # Nothing reached the bucket, and the action did not move.
    assert _stored_objects(bucket) == []
    assert client.app.dependency_overrides  # sanity: overrides still in place
    directory.groups = [_grant(board=True)]
    assert client.get(ACTION).json()['action']['version'] == 3


def test_a_pic_with_no_read_grant_cannot_write(client, directory, started, bucket) -> None:
    directory.groups = [_grant(board=False, submit=True)]
    _sign_in_as(client, 'user', user_id='pic-1')
    assert _upload(client).status_code == 403


def test_evidence_download_rechecks_access_after_revocation(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    evidence_id = _upload(client).json()['evidence']['id']
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user', user_id='boc-1')
    assert client.get(f'{BASE}/evidence/{evidence_id}{Q}').status_code == 200
    directory.groups = []
    response = client.get(f'{BASE}/evidence/{evidence_id}{Q}')
    assert response.status_code == 403
    assert PDF not in response.content


def test_link_evidence_is_served_as_a_link(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    response = client.post(EVIDENCE, data={'expected_version': '3', 'url': 'https://sharepoint.example/ba'})
    assert response.status_code == 200, response.text
    evidence_id = response.json()['evidence']['id']
    body = client.get(f'{BASE}/evidence/{evidence_id}{Q}').json()
    assert (body['kind'], body['url']) == ('link', 'https://sharepoint.example/ba')
    assert _stored_objects(bucket) == []


@pytest.mark.parametrize(
    ('data', 'files'),
    [
        ({'expected_version': '3'}, None),
        ({'expected_version': '3', 'url': 'https://example.com/x'}, {'file': ('a.pdf', PDF, 'application/pdf')}),
        ({'expected_version': '3', 'url': 'http://example.com/x'}, None),
    ],
)
def test_a_malformed_evidence_request_is_422(client, directory, started, bucket, data, files) -> None:
    _as_pic(client, directory)
    assert client.post(EVIDENCE, data=data, files=files).status_code == 422


def test_an_oversized_file_is_413_and_stores_nothing(client, directory, started, bucket, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_EVIDENCE_MAX_BYTES', '10')
    _as_pic(client, directory)
    assert _upload(client).status_code == 413
    assert _stored_objects(bucket) == []


def test_a_disguised_file_is_415_and_stores_nothing(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    assert _upload(client, content=b'MZ\x90\x00 not a pdf').status_code == 415
    assert _stored_objects(bucket) == []


def test_a_stale_version_is_409_and_names_the_current_one(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    response = _upload(client, version=2)
    assert response.status_code == 409
    assert response.json()['detail']['version'] == 3


def test_a_double_submitted_upload_returns_the_first_result(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    first = _upload(client, idempotency_key='click-1').json()
    second = _upload(client, idempotency_key='click-1').json()
    assert second['replayed'] is True
    assert second['evidence']['id'] == first['evidence']['id']


def test_file_evidence_without_a_configured_store_is_503(client, directory, started) -> None:
    from open_webui.routers import jup_leadership

    client.app.dependency_overrides[jup_leadership.leadership_evidence_store] = lambda: None
    _as_pic(client, directory)
    assert _upload(client).status_code == 503


def test_the_pic_records_progress_over_http(client, directory, started) -> None:
    _as_pic(client, directory)
    response = client.post(PROGRESS, json={'expected_version': 3, 'narrative': 'Draft sent to PGN'})
    assert response.status_code == 200, response.text
    assert response.json()['version'] == 4
    history = client.get(ACTION).json()['history']
    assert history[-1]['payload']['narrative'] == 'Draft sent to PGN'
    assert history[-1]['payload']['owner_update'] is True


def test_capabilities_list_submit_only_when_granted(client, directory) -> None:
    directory.groups = [_grant(board=True, submit=True)]
    _sign_in_as(client, 'user')
    assert client.get(f'{BASE}/capabilities').json()['operations'] == ['actions.submit']
    directory.groups = [_grant(board=True)]
    assert client.get(f'{BASE}/capabilities').json()['operations'] == []
