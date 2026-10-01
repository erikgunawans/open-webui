"""The knowledge-base review queue's HTTP seam (`routers/jup_kb_review.py`).

Faked: who is signed in (`get_current_user`), their groups (`Groups.get_groups_by_member_id`), and
the vendor tables and handlers the router reaches through `kb_review_store`. The real
`get_verified_user`, the real `get_permissions` merge and the real rules in `jup.kb_review` run on
every request. The store's own SQL — the `meta` JSON filter above all — runs against a scratch
SQLite database at the end of this file, not against the fake.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job, like the other endpoint
tests. A skip here is not a pass.
"""

import importlib.util
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt', 'sqlalchemy', 'aiosqlite')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The rules are covered without a server in test_kb_review.py.'
    ),
)

BASE = '/api/v1/kb-review'
KEY = 'jup_kb_review'
OWNER = 'user-owner'
OTHER = 'user-other'
ADMIN = 'user-admin'


@dataclass(frozen=True)
class _Account:
    role: str
    id: str


def _submit_grant(value: Any = True) -> SimpleNamespace:
    return SimpleNamespace(permissions={'jup': {'kb': {'submit': value}}})


class _Directory:
    def __init__(self) -> None:
        self.groups: dict[str, list[SimpleNamespace]] = {}

    async def get_groups_by_member_id(self, user_id: str, db=None) -> list[SimpleNamespace]:
        return list(self.groups.get(user_id, []))


class _Store:
    """The vendor tables, in memory. Same interface as `jup_kb_review.KbReviewStore`."""

    def __init__(self) -> None:
        self.files: dict[str, SimpleNamespace] = {}
        self.collections: dict[str, str] = {}
        self.attached: list[tuple[str, str]] = []
        self.attach_error: Exception | None = None
        self.created = 0

    def add_file(
        self, file_id: str, owner: str = OWNER, filename: str = 'catatan.md', content: str | None = 'Isi dokumen.'
    ) -> SimpleNamespace:
        data = {'status': 'completed', 'content': content} if content is not None else {'status': 'pending'}
        row = SimpleNamespace(
            id=file_id,
            user_id=owner,
            filename=filename,
            data=data,
            meta={'name': filename, 'content_type': 'text/markdown', 'size': 12},
            created_at=len(self.files) + 1,
        )
        self.files[file_id] = row
        return row

    async def get_file(self, file_id: str):
        return self.files.get(file_id)

    async def set_review(self, file_id: str, review: dict) -> bool:
        row = self.files.get(file_id)
        if row is None:
            return False
        row.meta = {**row.meta, KEY: review}
        return True

    async def submissions(self, *, states: tuple[str, ...], user_id: str | None = None) -> list:
        return [
            row
            for row in self.files.values()
            if isinstance(row.meta.get(KEY), dict)
            and row.meta[KEY].get('state') in states
            and (user_id is None or row.user_id == user_id)
        ]

    async def find_collection(self) -> str | None:
        return self.collections.get('JUP Staff Contributions')

    async def create_collection(self, request, user) -> str:
        self.created += 1
        self.collections['JUP Staff Contributions'] = f'kb-{self.created}'
        return f'kb-{self.created}'

    async def attach(self, request, knowledge_id: str, file_id: str, user) -> None:
        if self.attach_error is not None:
            raise self.attach_error
        self.attached.append((knowledge_id, file_id))


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
def client(directory: _Directory, store: _Store, caplog: pytest.LogCaptureFixture) -> Iterator[Any]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from open_webui.routers import jup_kb_review

    app = FastAPI()
    app.include_router(jup_kb_review.router, prefix=BASE)
    app.dependency_overrides[jup_kb_review.kb_review_store] = lambda: store

    async def _names(user_ids: list[str]) -> dict[str, str]:
        return {user_id: user_id.replace('user-', '').title() for user_id in user_ids}

    app.dependency_overrides[jup_kb_review.kb_review_user_names] = lambda: _names
    caplog.set_level('INFO', logger='jup.governance')
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client


def _as(client, role: str | None, user_id: str = OWNER) -> None:
    from fastapi import HTTPException, status

    from open_webui.utils.auth import get_current_user

    def _current_user():
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
        return _Account(role=role, id=user_id)

    client.app.dependency_overrides[get_current_user] = _current_user


def _audit(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith('jup.governance') and "'event': 'kb_review'" in record.getMessage()
    ]


def _code(response) -> str:
    return response.json()['detail']['code']


def _submit(client, directory, store, file_id: str = 'f1', owner: str = OWNER, **file_kwargs) -> None:
    """A granted owner submits one file."""
    store.add_file(file_id, owner=owner, **file_kwargs)
    directory.groups[owner] = [_submit_grant()]
    _as(client, 'user', owner)
    response = client.post(f'{BASE}/submissions', json={'file_id': file_id, 'note': 'Notulen'})
    assert response.status_code == 200, response.text


def _open(client, file_id: str = 'f1') -> str:
    """The reviewer opens a submission; returns the digest an approval must carry."""
    _as(client, 'admin', ADMIN)
    response = client.get(f'{BASE}/submissions/{file_id}')
    assert response.status_code == 200, response.text
    return response.json()['content_sha256']


# --- Capabilities -------------------------------------------------------------------


def test_signed_out_is_401(client) -> None:
    _as(client, None)
    assert client.get(f'{BASE}/capabilities').status_code == 401


def test_nobody_can_submit_by_default(client) -> None:
    _as(client, 'user', OWNER)
    assert client.get(f'{BASE}/capabilities').json() == {'submit': False, 'review': False}


def test_an_admin_reviews_but_needs_the_grant_to_submit(client) -> None:
    _as(client, 'admin', ADMIN)
    assert client.get(f'{BASE}/capabilities').json() == {'submit': False, 'review': True}


def test_a_granted_member_submits(client, directory) -> None:
    directory.groups[OWNER] = [_submit_grant()]
    _as(client, 'user', OWNER)
    assert client.get(f'{BASE}/capabilities').json() == {'submit': True, 'review': False}


def test_a_string_true_grant_is_no_grant(client, directory) -> None:
    directory.groups[OWNER] = [_submit_grant('true')]
    _as(client, 'user', OWNER)
    assert client.get(f'{BASE}/capabilities').json()['submit'] is False


# --- Submitting ---------------------------------------------------------------------


def test_submitting_without_the_grant_is_403(client, store, caplog) -> None:
    store.add_file('f1')
    _as(client, 'user', OWNER)
    response = client.post(f'{BASE}/submissions', json={'file_id': 'f1'})
    assert response.status_code == 403
    assert _code(response) == 'submit_forbidden'
    assert KEY not in store.files['f1'].meta
    assert any("'operation': 'submit'" in line and "'result': 'refused'" in line for line in _audit(caplog))


def test_an_admin_without_the_grant_cannot_submit(client, store) -> None:
    store.add_file('f1', owner=ADMIN)
    _as(client, 'admin', ADMIN)
    assert client.post(f'{BASE}/submissions', json={'file_id': 'f1'}).status_code == 403


def test_a_granted_owner_submits_and_it_is_pending(client, directory, store, caplog) -> None:
    _submit(client, directory, store)
    review = store.files['f1'].meta[KEY]
    assert review['state'] == 'pending'
    assert review['submitted_by'] == OWNER
    assert review['note'] == 'Notulen'
    assert isinstance(review['submitted_at'], int)
    lines = [line for line in _audit(caplog) if "'operation': 'submit'" in line]
    assert len(lines) == 1 and "'result': 'recorded'" in lines[0] and "'file': 'f1'" in lines[0]
    assert not any('Isi dokumen' in line or 'Notulen' in line for line in _audit(caplog)), 'ids, never content'


def test_someone_elses_file_cannot_be_submitted(client, directory, store) -> None:
    store.add_file('f1', owner=OTHER)
    directory.groups[OWNER] = [_submit_grant()]
    _as(client, 'user', OWNER)
    response = client.post(f'{BASE}/submissions', json={'file_id': 'f1'})
    assert response.status_code == 404
    assert KEY not in store.files['f1'].meta


def test_a_missing_file_is_404(client, directory) -> None:
    directory.groups[OWNER] = [_submit_grant()]
    _as(client, 'user', OWNER)
    assert client.post(f'{BASE}/submissions', json={'file_id': 'nope'}).status_code == 404


def test_a_file_cannot_be_submitted_twice(client, directory, store) -> None:
    _submit(client, directory, store)
    response = client.post(f'{BASE}/submissions', json={'file_id': 'f1'})
    assert response.status_code == 409
    assert _code(response) == 'already_submitted'


def test_an_unprocessed_file_is_refused(client, directory, store) -> None:
    store.add_file('f1', content=None)
    directory.groups[OWNER] = [_submit_grant()]
    _as(client, 'user', OWNER)
    response = client.post(f'{BASE}/submissions', json={'file_id': 'f1'})
    assert response.status_code == 409
    assert _code(response) == 'not_processed'


def test_an_image_is_refused(client, directory, store) -> None:
    store.add_file('f1', filename='foto.png')
    directory.groups[OWNER] = [_submit_grant()]
    _as(client, 'user', OWNER)
    response = client.post(f'{BASE}/submissions', json={'file_id': 'f1'})
    assert response.status_code == 422
    assert _code(response) == 'type_not_allowed'


def test_a_long_note_is_refused(client, directory, store) -> None:
    store.add_file('f1')
    directory.groups[OWNER] = [_submit_grant()]
    _as(client, 'user', OWNER)
    response = client.post(f'{BASE}/submissions', json={'file_id': 'f1', 'note': 'x' * 1001})
    assert response.status_code == 422
    assert _code(response) == 'note_too_long'


def test_mine_lists_only_the_callers_own_newest_first(client, directory, store) -> None:
    _submit(client, directory, store, 'f1')
    _submit(client, directory, store, 'f2')
    _submit(client, directory, store, 'f3', owner=OTHER)
    store.files['f2'].meta[KEY]['submitted_at'] += 10
    _as(client, 'user', OWNER)
    items = client.get(f'{BASE}/submissions/mine').json()['items']
    assert [item['file_id'] for item in items] == ['f2', 'f1']


def test_mine_shows_the_rejection_reason(client, directory, store) -> None:
    _submit(client, directory, store)
    _as(client, 'admin', ADMIN)
    client.post(f'{BASE}/submissions/f1/reject', json={'reason': 'Belum final.'})
    _as(client, 'user', OWNER)
    [item] = client.get(f'{BASE}/submissions/mine').json()['items']
    assert (item['state'], item['reason']) == ('rejected', 'Belum final.')


# --- The queue is admin only, and the refusal is 403 --------------------------------


@pytest.mark.parametrize(
    ('method', 'path', 'body'),
    [
        ('get', '/submissions', None),
        ('get', '/submissions?state=all', None),
        ('post', '/submissions/f1/approve', {'content_sha256': 'x'}),
        ('post', '/submissions/f1/reject', {'reason': 'x'}),
    ],
)
def test_a_non_admin_is_refused_with_403_not_401(client, directory, store, method, path, body, caplog) -> None:
    _submit(client, directory, store)
    _as(client, 'user', OWNER)  # the submitter, holding the submit grant
    response = getattr(client, method)(f'{BASE}{path}', **({'json': body} if body else {}))
    assert response.status_code == 403
    assert _code(response) == 'review_forbidden'
    assert store.files['f1'].meta[KEY]['state'] == 'pending'
    assert store.attached == []


def test_a_refused_decision_is_audited(client, directory, store, caplog) -> None:
    _submit(client, directory, store)
    _as(client, 'user', OTHER)
    client.post(f'{BASE}/submissions/f1/reject', json={'reason': 'x'})
    assert any("'operation': 'reject'" in line and "'result': 'refused'" in line for line in _audit(caplog))


def test_the_queue_defaults_to_pending_and_filters(client, directory, store) -> None:
    _submit(client, directory, store, 'f1')
    _submit(client, directory, store, 'f2')
    _as(client, 'admin', ADMIN)
    client.post(f'{BASE}/submissions/f2/reject', json={'reason': 'Duplikat.'})
    assert [i['file_id'] for i in client.get(f'{BASE}/submissions').json()['items']] == ['f1']
    assert [i['file_id'] for i in client.get(f'{BASE}/submissions?state=rejected').json()['items']] == ['f2']
    assert client.get(f'{BASE}/submissions?state=approved').json()['items'] == []
    assert {i['file_id'] for i in client.get(f'{BASE}/submissions?state=all').json()['items']} == {'f1', 'f2'}
    assert client.get(f'{BASE}/submissions?state=bogus').status_code == 422


def test_queue_items_name_the_submitter(client, directory, store) -> None:
    _submit(client, directory, store)
    _as(client, 'admin', ADMIN)
    [item] = client.get(f'{BASE}/submissions').json()['items']
    assert item['submitted_by'] == OWNER and item['submitted_by_name'] == 'Owner'


# --- Opening one --------------------------------------------------------------------


def test_the_reviewer_sees_the_preview(client, directory, store) -> None:
    _submit(client, directory, store, content='A' * 25_000)
    _as(client, 'admin', ADMIN)
    body = client.get(f'{BASE}/submissions/f1').json()
    assert body['note'] == 'Notulen' and body['filename'] == 'catatan.md'
    assert len(body['preview']['text']) == 20_000 and body['preview']['truncated'] is True
    assert len(body['content_sha256']) == 64


def test_the_submitter_may_open_their_own(client, directory, store) -> None:
    _submit(client, directory, store)
    assert client.get(f'{BASE}/submissions/f1').status_code == 200


def test_another_member_cannot_open_it(client, directory, store) -> None:
    _submit(client, directory, store)
    _as(client, 'user', OTHER)
    assert client.get(f'{BASE}/submissions/f1').status_code == 404


def test_a_file_that_is_not_a_submission_is_404(client, store) -> None:
    store.add_file('plain')
    _as(client, 'admin', ADMIN)
    assert client.get(f'{BASE}/submissions/plain').status_code == 404


# --- Approving ----------------------------------------------------------------------


def test_approving_creates_the_collection_once_and_reuses_it(client, directory, store, caplog) -> None:
    _submit(client, directory, store, 'f1')
    _submit(client, directory, store, 'f2')
    digest = _open(client, 'f1')
    response = client.post(f'{BASE}/submissions/f1/approve', json={'content_sha256': digest})
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'approved'
    digest = _open(client, 'f2')
    assert client.post(f'{BASE}/submissions/f2/approve', json={'content_sha256': digest}).status_code == 200
    assert store.created == 1
    assert store.attached == [('kb-1', 'f1'), ('kb-1', 'f2')]
    review = store.files['f1'].meta[KEY]
    assert (review['state'], review['knowledge_id'], review['reviewed_by']) == ('approved', 'kb-1', ADMIN)
    lines = [line for line in _audit(caplog) if "'operation': 'approve'" in line]
    assert len(lines) == 2 and all("'result': 'recorded'" in line for line in lines)
    assert "'knowledge': 'kb-1'" in lines[0]


def test_an_existing_collection_is_reused(client, directory, store) -> None:
    store.collections['JUP Staff Contributions'] = 'kb-existing'
    _submit(client, directory, store)
    digest = _open(client)
    client.post(f'{BASE}/submissions/f1/approve', json={'content_sha256': digest})
    assert store.created == 0
    assert store.attached == [('kb-existing', 'f1')]


def test_a_failed_add_leaves_it_pending_and_says_why(client, directory, store, caplog) -> None:
    from fastapi import HTTPException

    _submit(client, directory, store)
    digest = _open(client)
    store.attach_error = HTTPException(status_code=400, detail='embedding service unavailable')
    response = client.post(f'{BASE}/submissions/f1/approve', json={'content_sha256': digest})
    assert response.status_code == 502
    assert _code(response) == 'attach_failed'
    assert 'embedding service unavailable' in response.json()['detail']['message']
    assert store.files['f1'].meta[KEY]['state'] == 'pending'
    assert any("'operation': 'approve'" in line and "'result': 'failed'" in line for line in _audit(caplog))


def test_an_unexpected_add_error_also_leaves_it_pending(client, directory, store) -> None:
    _submit(client, directory, store)
    digest = _open(client)
    store.attach_error = RuntimeError('vector db down')
    assert client.post(f'{BASE}/submissions/f1/approve', json={'content_sha256': digest}).status_code == 502
    assert store.files['f1'].meta[KEY]['state'] == 'pending'


def test_approval_refuses_content_changed_after_the_preview(client, directory, store) -> None:
    _submit(client, directory, store)
    digest = _open(client)
    store.files['f1'].data = {'status': 'completed', 'content': 'Isi yang diganti setelah dibuka.'}
    response = client.post(f'{BASE}/submissions/f1/approve', json={'content_sha256': digest})
    assert response.status_code == 409
    assert _code(response) == 'content_changed'
    assert store.attached == []


@pytest.mark.parametrize('first', ['approve', 'reject'])
def test_only_pending_can_be_decided(client, directory, store, first) -> None:
    _submit(client, directory, store)
    digest = _open(client)
    decide = {
        'approve': lambda: client.post(f'{BASE}/submissions/f1/approve', json={'content_sha256': digest}),
        'reject': lambda: client.post(f'{BASE}/submissions/f1/reject', json={'reason': 'Tidak relevan.'}),
    }
    assert decide[first]().status_code == 200
    for second in ('approve', 'reject'):
        response = decide[second]()
        assert response.status_code == 409, second
        assert _code(response) == 'not_pending'
    assert store.attached == ([('kb-1', 'f1')] if first == 'approve' else [])


def test_approving_a_file_that_was_never_submitted_is_404(client, store) -> None:
    store.add_file('plain')
    _as(client, 'admin', ADMIN)
    assert client.post(f'{BASE}/submissions/plain/approve', json={'content_sha256': 'x'}).status_code == 404


# --- Rejecting ----------------------------------------------------------------------


def test_rejecting_needs_a_reason(client, directory, store) -> None:
    _submit(client, directory, store)
    _as(client, 'admin', ADMIN)
    for body in ({}, {'reason': ''}, {'reason': '   '}):
        response = client.post(f'{BASE}/submissions/f1/reject', json=body)
        assert response.status_code == 422, body
    assert store.files['f1'].meta[KEY]['state'] == 'pending'


def test_rejecting_records_the_reason_and_audits(client, directory, store, caplog) -> None:
    _submit(client, directory, store)
    _as(client, 'admin', ADMIN)
    response = client.post(f'{BASE}/submissions/f1/reject', json={'reason': '  Bukan versi final.  '})
    assert response.status_code == 200
    review = store.files['f1'].meta[KEY]
    assert (review['state'], review['reason'], review['reviewed_by']) == ('rejected', 'Bukan versi final.', ADMIN)
    assert store.attached == []
    lines = [line for line in _audit(caplog) if "'operation': 'reject'" in line]
    assert len(lines) == 1 and "'result': 'recorded'" in lines[0]
    assert 'Bukan versi final' not in lines[0], 'the audit line carries ids, never the reason text'


def test_every_response_is_no_store(client, directory, store) -> None:
    _submit(client, directory, store)
    _as(client, 'user', OTHER)
    for response in (client.get(f'{BASE}/submissions/f1'), client.get(f'{BASE}/submissions')):
        assert response.headers.get('cache-control') == 'private, no-store'


# --- The real store, against a scratch SQLite database ------------------------------


@pytest.fixture
async def real_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from open_webui.internal import db as host_db
    from open_webui.models.files import File
    from open_webui.models.knowledge import Knowledge
    from open_webui.models.users import User
    from open_webui.routers.jup_kb_review import KbReviewStore

    # Off by default, and then the vendor ignores a passed session and opens the app's own database.
    monkeypatch.setattr(host_db, 'DATABASE_ENABLE_SESSION_SHARING', True)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "kb.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: File.__table__.create(sync))
        await connection.run_sync(lambda sync: Knowledge.__table__.create(sync))
        await connection.run_sync(lambda sync: User.__table__.create(sync))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield KbReviewStore(db=session), session
    await engine.dispose()


async def _insert(session, file_id: str, owner: str, meta: dict) -> None:
    from open_webui.models.files import File

    session.add(File(id=file_id, user_id=owner, filename=f'{file_id}.md', data={}, meta=meta, created_at=1))
    await session.commit()


async def test_the_store_filters_on_the_meta_json_key(real_store) -> None:
    store, session = real_store
    await _insert(session, 'plain', OWNER, {'name': 'plain.md'})
    await _insert(session, 'p1', OWNER, {KEY: {'state': 'pending'}})
    await _insert(session, 'p2', OTHER, {KEY: {'state': 'pending'}})
    await _insert(session, 'r1', OWNER, {KEY: {'state': 'rejected'}})

    pending = await store.submissions(states=('pending',))
    assert {row.id for row in pending} == {'p1', 'p2'}
    mine = await store.submissions(states=('pending', 'approved', 'rejected'), user_id=OWNER)
    assert {row.id for row in mine} == {'p1', 'r1'}


async def test_the_store_merges_the_review_into_meta(real_store) -> None:
    store, session = real_store
    await _insert(session, 'f1', OWNER, {'name': 'f1.md', 'size': 3})
    assert await store.set_review('f1', {'state': 'pending'}) is True
    row = await store.get_file('f1')
    assert row.meta == {'name': 'f1.md', 'size': 3, KEY: {'state': 'pending'}}
    assert [r.id for r in await store.submissions(states=('pending',))] == ['f1']
    assert await store.set_review('missing', {'state': 'pending'}) is False


async def test_the_store_finds_the_collection_by_exact_name(real_store) -> None:
    from open_webui.models.knowledge import Knowledge
    from open_webui.models.users import User

    store, session = real_store
    assert await store.find_collection() is None
    for uid, role in ((ADMIN, 'admin'), (OWNER, 'user')):
        stamps = {'created_at': 1, 'updated_at': 1, 'last_active_at': 1}
        session.add(User(id=uid, name=uid, email=f'{uid}@example.test', role=role, **stamps))
    # A same-named collection owned by a non-admin, created first, must never be chosen.
    session.add(Knowledge(id='squatter', user_id=OWNER, name='JUP Staff Contributions', description='', created_at=1))
    session.add(Knowledge(id='strategy', user_id=ADMIN, name='JUP Strategy KB', description='', created_at=1))
    session.add(Knowledge(id='later', user_id=ADMIN, name='JUP Staff Contributions', description='', created_at=5))
    session.add(Knowledge(id='first', user_id=ADMIN, name='JUP Staff Contributions', description='', created_at=2))
    await session.commit()
    assert await store.find_collection() == 'first'


async def test_the_store_hands_the_vendor_attach_a_real_session(monkeypatch) -> None:
    """Production builds the store with `db=None`; the vendor's `process_file` commits on the session
    it is given, so attach must open one. Every live approval failed with "'NoneType' object has no
    attribute 'commit'" until it did (2026-10-01)."""
    import sys
    from contextlib import asynccontextmanager
    from types import ModuleType

    from open_webui.routers.jup_kb_review import KbReviewStore

    opened = object()
    seen: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_context(db=None):
        seen['given'] = db
        yield opened

    async def fake_add(request, knowledge_id, form_data, user=None, db=None):
        seen['db'], seen['knowledge'], seen['file'] = db, knowledge_id, form_data.file_id

    knowledge = ModuleType('open_webui.routers.knowledge')
    knowledge.KnowledgeFileIdForm = lambda file_id: SimpleNamespace(file_id=file_id)
    knowledge.add_file_to_knowledge_by_id = fake_add
    monkeypatch.setitem(sys.modules, 'open_webui.routers.knowledge', knowledge)
    import open_webui.internal.db as internal_db

    monkeypatch.setattr(internal_db, 'get_async_db_context', fake_context)

    await KbReviewStore().attach(None, 'kb-1', 'f1', SimpleNamespace(id=ADMIN))
    assert seen == {'given': None, 'db': opened, 'knowledge': 'kb-1', 'file': 'f1'}
