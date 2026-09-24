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


def _grant(
    board: bool = False,
    rka: bool = False,
    scope: bool = True,
    submit: bool | None = None,
    review: bool | None = None,
    publish: bool | None = None,
    imports: bool | None = None,
    assign: bool | None = None,
) -> SimpleNamespace:
    """A group row carrying leadership permissions, shaped as the host stores them."""
    grants = {
        'board': {'view': board},
        'rka': {'view': rka},
        'scopes': {'jup_consolidated': scope},
    }
    if submit is not None or assign is not None:
        grants['actions'] = {'submit': bool(submit), 'assign': bool(assign)}
    if review is not None:
        grants['bod'] = {'review': review}
    if publish is not None:
        grants['snapshots'] = {'publish': publish}
    if imports is not None:
        grants['imports'] = {'review': imports}
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


def test_the_action_record_lists_its_evidence_and_hides_the_storage_key(client, directory, started, bucket) -> None:
    _as_pic(client, directory)
    first = _upload(client).json()['evidence']
    second = client.post(EVIDENCE, data={'expected_version': '4', 'url': 'https://example.test/ba'}).json()['evidence']

    body = client.get(ACTION).json()
    # Every revision, oldest first, in the evidence route's own shape: a reviewer can open each one.
    assert [item['id'] for item in body['evidence']] == [first['id'], second['id']]
    assert body['evidence'][0] == first and body['evidence'][1] == second
    # The bucket key is the server's; neither the list nor the history's event payload carries it.
    assert 'storage_key' not in _json_text(body)
    submitted = [entry for entry in body['history'] if entry['kind'] == 'evidence_submitted']
    assert submitted[0]['payload']['evidence']['filename'] == 'berita acara.pdf'
    assert submitted[0]['payload']['evidence']['evidence_id'] == first['id']
    link = {'kind': 'link', 'url': 'https://example.test/ba', 'evidence_id': second['id']}
    assert submitted[1]['payload']['evidence'] == link


def _json_text(body: dict) -> str:
    import json

    return json.dumps(body)


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


STATE = f'{BASE}/actions/act-1/state{Q}'


def test_the_pic_starts_blocks_and_unblocks_over_http(client, directory, records, caplog) -> None:
    _as_pic(client, directory)
    with caplog.at_level('INFO'):
        started = client.post(STATE, json={'expected_version': 2, 'to_state': 'in_progress'})
    assert started.status_code == 200, started.text
    assert started.json()['version'] == 3
    assert any("'operation': 'state'" in line and "'result': 'recorded'" in line for line in _audit_lines(caplog))

    unexplained = client.post(STATE, json={'expected_version': 3, 'to_state': 'blocked'})
    assert unexplained.status_code == 422
    blocked = client.post(STATE, json={'expected_version': 3, 'to_state': 'blocked', 'reason': 'Waiting on PGN'})
    assert blocked.status_code == 200, blocked.text
    assert client.post(STATE, json={'expected_version': 4, 'to_state': 'in_progress'}).status_code == 200
    _as_pic(client, directory)
    history = client.get(ACTION).json()['history']
    assert [h['state_after'] for h in history[-3:]] == ['in_progress', 'blocked', 'in_progress']
    assert history[-2]['reason'] == 'Waiting on PGN'


@pytest.mark.parametrize('to_state', ['closed', 'awaiting_bod_closure', 'not_started'])
def test_the_pic_cannot_move_an_action_to_a_bod_state(client, directory, records, to_state: str) -> None:
    _as_pic(client, directory)
    assert client.post(STATE, json={'expected_version': 2, 'to_state': to_state}).status_code == 422
    assert _action_state(client, directory) == ('not_started', 2)


def test_only_the_pic_with_the_grant_moves_the_state(client, directory, records) -> None:
    _as_pic(client, directory, submit=False)
    assert client.post(STATE, json={'expected_version': 2, 'to_state': 'in_progress'}).status_code == 403
    directory.groups = [_grant(board=True, submit=True)]
    _sign_in_as(client, 'user', user_id='someone-else')
    assert client.post(STATE, json={'expected_version': 2, 'to_state': 'in_progress'}).status_code == 403
    assert _action_state(client, directory) == ('not_started', 2)


def test_a_stale_state_move_conflicts(client, directory, records) -> None:
    _as_pic(client, directory)
    response = client.post(STATE, json={'expected_version': 1, 'to_state': 'in_progress'})
    assert response.status_code == 409
    assert response.json()['detail']['version'] == 2


def test_capabilities_list_submit_only_when_granted(client, directory) -> None:
    directory.groups = [_grant(board=True, submit=True)]
    _sign_in_as(client, 'user')
    assert client.get(f'{BASE}/capabilities').json()['operations'] == ['actions.submit']
    directory.groups = [_grant(board=True)]
    assert client.get(f'{BASE}/capabilities').json()['operations'] == []


# --- The BOD's decisions (P2 T4) ----------------------------------------------------

CLOSURE = f'{BASE}/actions/act-1/closure{Q}'
INDIVIDUAL = '{"mode": "individual"}'
COLLECTIVE = '{"mode": "collective", "quorum": 2}'


@pytest.fixture
def awaiting(started, monkeypatch: pytest.MonkeyPatch):
    """act-1 awaiting BOD closure on link evidence revision 1 (version 4), individual policy."""
    from jup.leadership.evidence import link_evidence, submit_evidence
    from jup.leadership.repository import unit_of_work

    monkeypatch.setenv('JUP_LEADERSHIP_BOD_POLICY', INDIVIDUAL)
    with unit_of_work(started) as uow:
        submission = submit_evidence(
            uow,
            action_id='act-1',
            expected_version=3,
            actor='pic-1',
            item=link_evidence('https://sharepoint.example/ba'),
            completion=True,
        )
    return submission.evidence['id']


def _as_bod(client, directory, user_id: str = 'bod-1', role: str = 'user') -> None:
    directory.groups = [_grant(board=True, review=True)]
    _sign_in_as(client, role, user_id=user_id)


def _close(client, evidence_id: str, version: int = 4, **extra):
    return client.post(
        CLOSURE, json={'expected_version': version, 'decision': 'close', 'evidence_id': evidence_id, **extra}
    )


def _action_state(client, directory) -> tuple[str, int]:
    directory.groups = [_grant(board=True)]
    action = client.get(ACTION).json()['action']
    return action['state'], action['version']


@pytest.mark.parametrize(
    ('role', 'user_id', 'grant'),
    [
        ('user', 'pic-1', {'submit': True, 'review': True}),  # the PIC, even holding bod.review
        ('user', 'boc-1', {}),  # a BOC observer: read grant only
        ('admin', 'admin-1', {}),  # an admin without BOD
        ('admin', 'admin-1', {'submit': True}),  # an admin holding every other capability
        ('user', 'reader-1', {'review': False}),  # a read-only reader
    ],
)
def test_a_direct_api_closure_by_each_unauthorised_identity_is_refused(
    client, directory, awaiting, role, user_id, grant, caplog
) -> None:
    directory.groups = [_grant(board=True, **grant)]
    _sign_in_as(client, role, user_id=user_id)
    with caplog.at_level('INFO'):
        for body in (
            {'decision': 'close', 'evidence_id': awaiting},
            {'decision': 'return', 'evidence_id': awaiting, 'reason': 'x', 'return_to': 'in_progress'},
            {'decision': 'reopen', 'reason': 'x'},
        ):
            response = client.post(CLOSURE, json={'expected_version': 4, **body})
            assert response.status_code == 403, response.text
            _no_store(response)
    assert any("'operation': 'closure_decision'" in line for line in _audit_lines(caplog))
    assert _action_state(client, directory) == ('awaiting_bod_closure', 4)


def test_a_bod_reviewer_without_a_read_grant_is_refused(client, directory, awaiting) -> None:
    directory.groups = [_grant(board=False, review=True)]
    _sign_in_as(client, 'user', user_id='bod-1')
    assert _close(client, awaiting).status_code == 403


def test_an_unconfigured_policy_is_503_for_a_reviewer_and_403_for_everyone_else(
    client, directory, awaiting, monkeypatch: pytest.MonkeyPatch
) -> None:
    for raw in ('', '{"mode": "collective", "quorum": 1}'):
        monkeypatch.setenv('JUP_LEADERSHIP_BOD_POLICY', raw)
        _as_bod(client, directory)
        response = _close(client, awaiting)
        assert response.status_code == 503
        assert 'not configured' in response.json()['detail']
        _no_store(response)
        # An unauthorised caller cannot tell unconfigured from denied.
        directory.groups = [_grant(board=True)]
        assert _close(client, awaiting).status_code == 403
    assert _action_state(client, directory) == ('awaiting_bod_closure', 4)


def test_an_authorised_bod_reviewer_closes_in_individual_mode(client, directory, awaiting, caplog) -> None:
    _as_bod(client, directory)
    with caplog.at_level('INFO'):
        response = _close(client, awaiting)
    assert response.status_code == 200, response.text
    _no_store(response)
    assert (response.json()['outcome'], response.json()['version']) == ('closed', 5)
    assert any(
        "'operation': 'closure_decision'" in line and "'result': 'closed'" in line for line in _audit_lines(caplog)
    )
    assert _action_state(client, directory) == ('closed', 5)
    last = client.get(ACTION).json()['history'][-1]
    assert (last['kind'], last['author'], last['state_after']) == ('bod_decision', 'bod-1', 'closed')


def test_authorised_bod_reviewers_close_in_collective_mode(client, directory, awaiting, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_BOD_POLICY', COLLECTIVE)
    _as_bod(client, directory, 'bod-1')
    first = _close(client, awaiting).json()
    assert (first['outcome'], first['close_votes'], first['quorum']) == ('vote_recorded', 1, 2)
    assert _close(client, awaiting, version=5).status_code == 422  # the same reviewer again
    _as_bod(client, directory, 'bod-2')
    assert _close(client, awaiting, version=5).json()['outcome'] == 'closed'
    assert _action_state(client, directory) == ('closed', 6)


def test_returned_evidence_goes_back_to_the_pic(client, directory, awaiting) -> None:
    _as_bod(client, directory)
    response = client.post(
        CLOSURE,
        json={
            'expected_version': 4,
            'decision': 'return',
            'evidence_id': awaiting,
            'reason': 'BA is unsigned',
            'return_to': 'in_progress',
        },
    )
    assert response.json()['outcome'] == 'returned'
    assert _action_state(client, directory) == ('in_progress', 5)
    # The PIC can submit again; the returned request stays in the record.
    _as_pic(client, directory)
    assert (
        client.post(
            EVIDENCE, data={'expected_version': '5', 'url': 'https://x.example/ba-2', 'completion': 'true'}
        ).status_code
        == 200
    )


def test_stale_evidence_is_409_and_names_the_latest(client, directory, awaiting) -> None:
    _as_pic(client, directory)
    newer = client.post(EVIDENCE, data={'expected_version': '4', 'url': 'https://x.example/ba-2'}).json()['evidence'][
        'id'
    ]
    _as_bod(client, directory)
    response = _close(client, awaiting, version=5)
    assert response.status_code == 409
    assert response.json()['detail']['evidence_id'] == newer
    assert _close(client, newer, version=5).json()['outcome'] == 'closed'


def test_a_reopened_action_keeps_its_closure_in_the_history(client, directory, awaiting) -> None:
    _as_bod(client, directory)
    _close(client, awaiting)
    reopen = client.post(CLOSURE, json={'expected_version': 5, 'decision': 'reopen', 'reason': 'PGN withdrew'})
    assert reopen.json()['outcome'] == 'reopened'
    history = client.get(ACTION).json()['history']
    assert [h['state_after'] for h in history[-2:]] == ['closed', 'in_progress']


def test_a_stale_version_is_409_and_an_invalid_decision_422(client, directory, awaiting) -> None:
    _as_bod(client, directory)
    assert _close(client, awaiting, version=3).status_code == 409
    assert client.post(CLOSURE, json={'expected_version': 4, 'decision': 'approve'}).status_code == 422
    assert client.post(CLOSURE, json={'expected_version': 4, 'decision': 'reopen'}).status_code == 422


def test_capabilities_list_bod_review_only_with_a_policy(client, directory, monkeypatch) -> None:
    directory.groups = [_grant(board=True, review=True)]
    _sign_in_as(client, 'user')
    monkeypatch.delenv('JUP_LEADERSHIP_BOD_POLICY', raising=False)
    assert client.get(f'{BASE}/capabilities').json()['operations'] == []
    monkeypatch.setenv('JUP_LEADERSHIP_BOD_POLICY', INDIVIDUAL)
    assert client.get(f'{BASE}/capabilities').json()['operations'] == ['bod.review']


# --- Meeting snapshots and RKA records (P2 T5) --------------------------------------

SNAPSHOTS = f'{BASE}/snapshots{Q}'
RKA_Q = '?view=rka&scope_id=jup-consolidated'
OPEN_PUBLICATION = '{"four_eyes": false}'


def _as_publisher(client, directory, user_id: str = 'sec-1', role: str = 'user', rka: bool = False) -> None:
    directory.groups = [_grant(board=True, rka=rka, publish=True)]
    _sign_in_as(client, role, user_id=user_id)


def _new_draft(client, url: str = SNAPSHOTS):
    return client.post(url, json={'meeting_label': 'Rapat BOD September 2026', 'meeting_date': '2026-09-28'})


@pytest.mark.parametrize(
    ('role', 'grant'),
    [('admin', {}), ('user', {}), ('admin', {'submit': True, 'review': True}), ('user', {'publish': False})],
)
def test_only_a_publisher_freezes_a_draft(client, directory, records, role, grant) -> None:
    directory.groups = [_grant(board=True, **grant)]
    _sign_in_as(client, role, user_id='someone')
    response = _new_draft(client)
    assert response.status_code == 403
    _no_store(response)
    assert client.get(SNAPSHOTS).json()['snapshots'] == []


def test_a_draft_is_frozen_and_never_served_as_the_record(client, directory, records, caplog) -> None:
    _as_publisher(client, directory)
    with caplog.at_level('INFO'):
        draft = _new_draft(client)
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert (body['state'], body['version'], body['view']) == ('draft', 1, 'board')
    assert any("'operation': 'snapshot_draft'" in line for line in _audit_lines(caplog))

    read = client.get(f'{BASE}/snapshots/{body["snapshot_id"]}{Q}')
    assert read.status_code == 200
    _no_store(read)
    served = read.json()
    assert served['published'] is None
    assert served['latest']['state'] == 'draft'
    assert served['latest']['content']['data_mode'] == 'illustrative'
    listed = client.get(SNAPSHOTS).json()['snapshots']
    assert [(item['latest']['state'], item['published']) for item in listed] == [('draft', None)]


def test_publication_is_unavailable_until_a_policy_is_configured(client, directory, records, monkeypatch) -> None:
    monkeypatch.delenv('JUP_LEADERSHIP_PUBLICATION_POLICY', raising=False)
    _as_publisher(client, directory)
    draft = _new_draft(client).json()
    publish = f'{BASE}/snapshots/{draft["snapshot_id"]}/publish{Q}'
    response = client.post(publish, json={'expected_version': 1, 'content_hash': draft['content_hash']})
    assert response.status_code == 503
    # Without the capability, the answer is 403 whatever the configuration.
    directory.groups = [_grant(board=True)]
    assert client.post(publish, json={'expected_version': 1, 'content_hash': draft['content_hash']}).status_code == 403


def test_a_publisher_publishes_the_draft_they_reviewed(client, directory, records, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_PUBLICATION_POLICY', OPEN_PUBLICATION)
    _as_publisher(client, directory)
    draft = _new_draft(client).json()
    publish = f'{BASE}/snapshots/{draft["snapshot_id"]}/publish{Q}'
    stale = client.post(publish, json={'expected_version': 1, 'content_hash': '0' * 64})
    assert stale.status_code == 409
    response = client.post(publish, json={'expected_version': 1, 'content_hash': draft['content_hash']})
    assert response.status_code == 200, response.text
    assert (response.json()['state'], response.json()['content_hash']) == ('published', draft['content_hash'])
    served = client.get(f'{BASE}/snapshots/{draft["snapshot_id"]}{Q}').json()
    assert served['published']['version'] == 2
    assert client.post(publish, json={'expected_version': 2, 'content_hash': draft['content_hash']}).status_code == 422


def test_four_eyes_publication_over_http(client, directory, records, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_PUBLICATION_POLICY', '{"four_eyes": true}')
    _as_publisher(client, directory, 'sec-1')
    draft = _new_draft(client).json()
    publish = f'{BASE}/snapshots/{draft["snapshot_id"]}/publish{Q}'
    body = {'expected_version': 1, 'content_hash': draft['content_hash']}
    assert client.post(publish, json=body).status_code == 422
    _as_publisher(client, directory, 'pub-2')
    assert client.post(publish, json=body).status_code == 200


def test_a_snapshot_is_read_only_through_the_view_it_froze(client, directory, records) -> None:
    _as_publisher(client, directory, rka=True)
    rka_draft = _new_draft(client, f'{BASE}/snapshots{RKA_Q}').json()
    assert rka_draft['view'] == 'rka'
    assert client.get(f'{BASE}/snapshots/{rka_draft["snapshot_id"]}{Q}').status_code == 404
    assert client.get(f'{BASE}/snapshots/{rka_draft["snapshot_id"]}{RKA_Q}').status_code == 200


def test_a_revoked_reader_is_denied_a_snapshot_they_could_read_before(client, directory, records) -> None:
    _as_publisher(client, directory)
    snapshot_id = _new_draft(client).json()['snapshot_id']
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user', user_id='boc-1')
    assert client.get(f'{BASE}/snapshots/{snapshot_id}{Q}').status_code == 200
    directory.groups = []
    for url in (f'{BASE}/snapshots/{snapshot_id}{Q}', SNAPSHOTS):
        response = client.get(url)
        assert response.status_code == 403
        _no_store(response)


def test_rka_records_are_for_an_rka_reader(client, directory, records) -> None:
    from jup.leadership.snapshots import record_rka

    with records.begin() as connection:
        record_rka(
            connection,
            kind='baseline',
            label='RKA 2026',
            period_start='2026-01-01',
            period_end='2026-12-31',
            content={'revenue_idr_billion': '144.0'},
            author='sec-1',
            approved_by='rups',
            approved_at=1_780_000_000_000,
        )
    baselines = f'{BASE}/baselines?scope_id=jup-consolidated'
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'admin', user_id='admin-1')
    assert client.get(baselines).status_code == 403
    directory.groups = [_grant(rka=True)]
    response = client.get(baselines)
    assert response.status_code == 200
    _no_store(response)
    (record,) = response.json()['records']
    assert (record['record_kind'], record['content']) == ('baseline', {'revenue_idr_billion': '144.0'})


def test_capabilities_list_publish_only_with_a_policy(client, directory, monkeypatch) -> None:
    directory.groups = [_grant(board=True, publish=True)]
    _sign_in_as(client, 'user')
    monkeypatch.delenv('JUP_LEADERSHIP_PUBLICATION_POLICY', raising=False)
    assert client.get(f'{BASE}/capabilities').json()['operations'] == []
    monkeypatch.setenv('JUP_LEADERSHIP_PUBLICATION_POLICY', OPEN_PUBLICATION)
    assert client.get(f'{BASE}/capabilities').json()['operations'] == ['snapshots.publish']


# --- Reviewed imports (P2 T6) -------------------------------------------------------

IMPORTS = f'{BASE}/imports{Q}'
CANDIDATE_FILE = {
    'schema_version': 1,
    'source_document': 'BOD-2026-09.pptx',
    'meeting_date': '2026-09-28',
    'candidates': [
        {
            'key': 's12-r1',
            'slide': '12',
            'external_id': 'GAS-01',
            'title': 'Finalisasi alokasi gas',
            'owner_label': 'Pak Deco',
            'due': {'precision': 'month', 'value': '2026-09'},
            'state': 'in_progress',
            'progress_summary': None,
            'source_metadata': {'slide_hidden': True},
            'missing': {'progress_summary': 'blank cell'},
        }
    ],
}


def _upload_candidates(client, body: dict | None = None, raw: bytes | None = None):
    content = raw if raw is not None else json.dumps(body or CANDIDATE_FILE).encode()
    return client.post(IMPORTS, files={'file': ('bod.json', content, 'application/json')})


def _as_import_reviewer(client, directory, user_id: str = 'rev-1', role: str = 'user') -> None:
    directory.groups = [_grant(board=True, imports=True)]
    _sign_in_as(client, role, user_id=user_id)


@pytest.mark.parametrize(
    ('role', 'grant'),
    [
        ('admin', {}),
        ('user', {}),
        ('admin', {'submit': True, 'review': True, 'publish': True}),
        ('user', {'imports': False}),
    ],
)
def test_only_an_import_reviewer_uploads_or_reads_candidates(client, directory, records, role, grant) -> None:
    directory.groups = [_grant(board=True, **grant)]
    _sign_in_as(client, role, user_id='someone')
    for response in (_upload_candidates(client), client.get(IMPORTS)):
        assert response.status_code == 403
        _no_store(response)


def test_an_import_reviewer_uploads_reviews_and_the_action_appears(client, directory, records, caplog) -> None:
    _as_import_reviewer(client, directory)
    with caplog.at_level('INFO'):
        uploaded = _upload_candidates(client)
    assert uploaded.status_code == 200, uploaded.text
    batch_id = uploaded.json()['batch_id']
    assert _upload_candidates(client).json() == {'batch_id': batch_id, 'created': False}
    assert any("'operation': 'import_upload'" in line for line in _audit_lines(caplog))

    batch = client.get(f'{BASE}/imports/{batch_id}{Q}').json()
    (candidate,) = batch['candidates']
    assert (candidate['match_kind'], candidate['verification']) == ('new', 'unverified')
    assert candidate['payload']['source_metadata'] == {'slide_hidden': True}

    review = f'{BASE}/imports/candidates/{candidate["id"]}/review{Q}'
    accepted = client.post(review, json={'decision': 'accept'})
    assert accepted.status_code == 200, accepted.text
    action_id = accepted.json()['action_id']
    assert client.post(review, json={'decision': 'reject'}).status_code == 409
    directory.groups = [_grant(board=True)]
    action = client.get(f'{BASE}/actions/{action_id}{Q}').json()['action']
    assert (action['title'], action['state'], action['pic_user_id']) == ('Finalisasi alokasi gas', 'not_started', None)


def test_a_malformed_or_oversized_candidate_file_is_refused(client, directory, records, monkeypatch) -> None:
    from jup.leadership import imports

    _as_import_reviewer(client, directory)
    assert _upload_candidates(client, raw=b'{"schema_version": 1}').status_code == 422
    monkeypatch.setattr(imports, 'MAX_BYTES', 10)
    assert _upload_candidates(client).status_code == 413
    assert client.get(IMPORTS).json()['batches'] == []


def test_a_review_that_breaks_a_rule_is_422(client, directory, records) -> None:
    _as_import_reviewer(client, directory)
    batch_id = _upload_candidates(client).json()['batch_id']
    candidate_id = client.get(f'{BASE}/imports/{batch_id}{Q}').json()['candidates'][0]['id']
    review = f'{BASE}/imports/candidates/{candidate_id}/review{Q}'
    assert client.post(review, json={'decision': 'link', 'action_id': 'no-such-action'}).status_code == 422
    assert client.post(review, json={'decision': 'approve'}).status_code == 422
    assert client.post(f'{BASE}/imports/candidates/nope/review{Q}', json={'decision': 'reject'}).status_code == 404
    assert client.get(f'{BASE}/imports/nope{Q}').status_code == 404


# --- Reader and API integration (P2 T7) ---------------------------------------------


def test_the_overview_says_its_actions_are_the_sample_and_is_audited(client, directory, caplog) -> None:
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user', user_id='boc-1')
    with caplog.at_level('INFO'):
        body = client.get(BOARD).json()
        client.get(f'{BASE}/sources/board-gas?view=board&scope_id=jup-consolidated')
    assert (body['actions_source'], body['data_mode']) == ('sample', 'illustrative')
    lines = _audit_lines(caplog)
    assert any("'operation': 'overview'" in line and "'actions_source': 'sample'" in line for line in lines)
    assert any("'operation': 'source'" in line and "'result': 'served'" in line for line in lines)


def test_a_refused_overview_is_audited_too(client, caplog) -> None:
    _sign_in_as(client, 'admin', user_id='admin-1')
    with caplog.at_level('INFO'):
        assert client.get(BOARD).status_code == 403
    assert any("'operation': 'overview'" in line and "'result': 'refused'" in line for line in _audit_lines(caplog))


def test_the_records_source_serves_the_register(client, directory, records, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    directory.groups = [_grant(board=True, rka=True)]
    _sign_in_as(client, 'user', user_id='boc-1')
    board = client.get(BOARD).json()
    assert board['actions_source'] == 'records'
    (served,) = board['actions']
    assert (served['id'], served['owner_label'], served['state']) == ('act-1', 'PIC Komersial', 'not_started')
    assert served['due']['label'] == 'Desember 2026'
    assert served['record']['original_due']['date'] == '2026-09-01'
    # act-1 is not referenced by the RKA section, so the RKA view has no recorded action.
    rka = client.get(RKA).json()
    assert (rka['actions'], rka['actions_note']) == ([], 'No action is recorded for this view yet.')


def test_an_empty_register_never_falls_back_to_the_sample(client, directory, tmp_path, monkeypatch) -> None:
    from sqlalchemy import create_engine

    from jup.leadership import migrate
    from open_webui.routers import jup_leadership

    engine = create_engine(f'sqlite:///{tmp_path / "empty.db"}')
    assert migrate.run_leadership_migrations(engine) is True
    client.app.dependency_overrides[jup_leadership.leadership_engine] = lambda: engine
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    body = client.get(BOARD).json()
    assert (body['actions_source'], body['actions']) == ('records', [])
    engine.dispose()


@pytest.mark.parametrize('value', ['live', 'verified', 'sample,records'])
def test_a_misconfigured_actions_source_is_503(client, directory, monkeypatch, value: str) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', value)
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    response = client.get(BOARD)
    assert response.status_code == 503
    _no_store(response)


def test_the_records_source_needs_a_ready_store(client, directory, monkeypatch) -> None:
    from jup.leadership import migrate

    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    monkeypatch.setattr(migrate, 'schema_ready', lambda: False)
    directory.groups = [_grant(board=True)]
    _sign_in_as(client, 'user')
    assert client.get(BOARD).status_code == 503


def test_a_draft_in_records_mode_freezes_the_register(client, directory, records, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'records')
    _as_publisher(client, directory)
    snapshot_id = _new_draft(client).json()['snapshot_id']
    content = client.get(f'{BASE}/snapshots/{snapshot_id}{Q}').json()['latest']['content']
    assert content['actions_source'] == 'records'
    assert [a['id'] for a in content['actions']] == ['act-1']
    assert content['actions'][0]['record']['version'] == 2


def test_the_pic_requests_a_cancellation_and_the_bod_closes_it(client, directory, started, monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_BOD_POLICY', INDIVIDUAL)
    _as_pic(client, directory)
    refused = client.post(
        EVIDENCE, data={'expected_version': '3', 'url': 'https://x.example/m', 'closure_kind': 'cancelled'}
    )
    assert refused.status_code == 422  # no reason
    requested = client.post(
        EVIDENCE,
        data={
            'expected_version': '3',
            'url': 'https://x.example/m',
            'closure_kind': 'cancelled',
            'reason': 'Dibatalkan RUPS',
        },
    )
    assert requested.status_code == 200, requested.text
    evidence_id = requested.json()['evidence']['id']
    _as_bod(client, directory)
    assert _close(client, evidence_id).json()['outcome'] == 'closed'
    assert _action_state(client, directory) == ('closed', 5)


# --- PIC assignment (T8 follow-up) -----------------------------------------------------------

PIC_ROUTE = f'{BASE}/actions/act-1/pic{Q}'


@pytest.fixture
def people(client):
    """The host's user directory, by email: two known people."""
    from types import SimpleNamespace

    from open_webui.routers import jup_leadership

    known = {'pic@jup.test': 'pic-1', 'new@jup.test': 'pic-2'}

    async def lookup(email: str):
        user_id = known.get(email.strip().lower())
        return SimpleNamespace(id=user_id) if user_id else None

    client.app.dependency_overrides[jup_leadership.leadership_user_lookup] = lambda: lookup
    return known


def _as_assigner(client, directory, user_id: str = 'lead-1') -> None:
    directory.groups = [_grant(board=True, assign=True)]
    _sign_in_as(client, 'user', user_id=user_id)


def test_the_capability_is_listed_for_an_assigner(client, directory) -> None:
    _as_assigner(client, directory)
    assert 'actions.assign' in client.get(f'{BASE}/capabilities').json()['operations']


def test_an_assigner_replaces_the_pic_and_the_new_pic_can_submit(client, directory, records, people, bucket, caplog):
    _as_assigner(client, directory)
    with caplog.at_level('INFO'):
        response = client.post(
            PIC_ROUTE, json={'expected_version': 2, 'pic_email': 'NEW@jup.test', 'reason': 'handover to legal'}
        )
    assert response.status_code == 200, response.text
    _no_store(response)
    assert response.json()['version'] == 3
    lines = _audit_lines(caplog)
    assert any("'operation': 'pic_assign'" in line and "'result': 'recorded'" in line for line in lines)
    assert not any('new@jup.test' in line.lower() for line in lines), 'audit lines carry ids, never emails'

    record = client.get(ACTION).json()
    assert record['action']['pic_user_id'] == 'pic-2'
    assert record['history'][-1]['kind'] == 'pic_assigned'

    directory.groups = [_grant(board=True, submit=True)]
    _sign_in_as(client, 'user', user_id='pic-2')
    submitted = client.post(EVIDENCE, data={'expected_version': '3', 'url': 'https://example.test/ba'})
    assert submitted.status_code == 200, submitted.text
    _sign_in_as(client, 'user', user_id='pic-1')
    assert client.post(EVIDENCE, data={'expected_version': '4', 'url': 'https://example.test/x'}).status_code == 403


@pytest.mark.parametrize('grant', [{'board': True}, {'board': True, 'submit': True}, {'board': True, 'review': True}])
def test_only_the_assign_capability_assigns(client, directory, records, people, grant) -> None:
    directory.groups = [_grant(**grant)]
    _sign_in_as(client, 'admin', user_id='pic-1')
    response = client.post(PIC_ROUTE, json={'expected_version': 2, 'pic_email': 'new@jup.test', 'reason': 'x'})
    assert response.status_code == 403


def test_an_unknown_person_is_422_and_nothing_changes(client, directory, records, people) -> None:
    _as_assigner(client, directory)
    response = client.post(PIC_ROUTE, json={'expected_version': 2, 'pic_email': 'nobody@jup.test', 'reason': 'x'})
    assert response.status_code == 422
    assert client.get(ACTION).json()['action']['version'] == 2


def test_replacing_without_a_reason_is_422(client, directory, records, people) -> None:
    _as_assigner(client, directory)
    response = client.post(PIC_ROUTE, json={'expected_version': 2, 'pic_email': 'new@jup.test'})
    assert response.status_code == 422
    assert 'reason' in response.json()['detail']


def test_a_stale_assignment_is_409(client, directory, records, people) -> None:
    _as_assigner(client, directory)
    response = client.post(PIC_ROUTE, json={'expected_version': 1, 'pic_email': 'new@jup.test', 'reason': 'x'})
    assert response.status_code == 409
    assert response.json()['detail']['version'] == 2
