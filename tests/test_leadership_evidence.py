"""The PIC's progress and evidence (P2 T3): who may submit, versioning, completion, file checks.

File checks are pure and always run. The commands run against a real SQLite database brought to
the leadership head by the migration graph, so they need the runtime.
"""

import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

from jup.leadership import evidence_store as store
from jup.leadership.evidence_store import EvidenceRejected, check_file, read_bounded

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')

PIC = 'user-pic-1'
OTHER_PIC = 'user-pic-2'
PDF_BYTES = b'%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF\n'


def _ooxml(marker: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as package:
        package.writestr('[Content_Types].xml', '<Types/>')
        package.writestr(marker, '<x/>')
    return buffer.getvalue()


# --- file checks ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('content', 'declared', 'expected'),
    [
        (PDF_BYTES, 'application/pdf', store.PDF),
        (b'\x89PNG\r\n\x1a\n rest', 'image/png', store.PNG),
        (b'\xff\xd8\xff\xe0 rest', 'image/jpeg', store.JPEG),
        (_ooxml('xl/workbook.xml'), store.XLSX, store.XLSX),
        (_ooxml('ppt/presentation.xml'), store.PPTX, store.PPTX),
        (b'a,b\n1,2\n', 'text/csv', store.CSV),
        (b'a,b\n1,2\n', 'text/plain', store.TEXT),
        (b'minutes of the meeting\n', None, store.TEXT),
    ],
)
def test_an_allowed_file_is_accepted_by_its_bytes(content: bytes, declared, expected: str) -> None:
    checked = check_file(content, 'x', declared)
    assert checked.content_type == expected
    assert checked.key == store.PREFIX + checked.sha256


@pytest.mark.parametrize(
    ('content', 'declared'),
    [
        (b'MZ\x90\x00 an executable', 'application/pdf'),  # bytes are not an allowed type
        (b'<html><script>x</script>', 'application/pdf'),  # text declared as pdf
        (PDF_BYTES, 'image/png'),  # declared type disagrees with the bytes
        (_ooxml('other/thing.xml'), store.DOCX),  # a zip that is not an Office document
        (b'text with \x1b[31m escapes', 'text/plain'),
        (b'\xff\xfe not utf-8 \x00', None),
    ],
)
def test_a_disallowed_or_mislabelled_file_is_415(content: bytes, declared) -> None:
    with pytest.raises(EvidenceRejected) as caught:
        check_file(content, 'x.pdf', declared)
    assert caught.value.status == 415


def test_an_empty_file_is_422() -> None:
    with pytest.raises(EvidenceRejected) as caught:
        check_file(b'', 'x.pdf', 'application/pdf')
    assert caught.value.status == 422


def test_an_oversized_upload_is_413_without_reading_it_all() -> None:
    stream = io.BytesIO(b'x' * 1000)
    with pytest.raises(EvidenceRejected) as caught:
        read_bounded(stream, 100)
    assert caught.value.status == 413
    assert stream.tell() == 101
    assert read_bounded(io.BytesIO(b'x' * 100), 100) == b'x' * 100


@pytest.mark.parametrize('filename', ['../../etc/passwd', 'C:\\Windows\\evil.pdf', '', '  '])
def test_the_client_filename_is_metadata_only(filename: str, tmp_path: Path) -> None:
    checked = check_file(PDF_BYTES, filename, 'application/pdf')
    assert '/' not in checked.filename and '\\' not in checked.filename
    assert checked.filename.strip()
    local = store.LocalEvidenceStore(tmp_path)
    local.put(checked.key, checked.content, checked.content_type)
    assert [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file()] == [checked.key]


def test_the_store_accepts_only_evidence_keys(tmp_path: Path) -> None:
    local = store.LocalEvidenceStore(tmp_path)
    for key in ('leadership/evidence/../x', 'uploads/abc', store.PREFIX + 'A' * 64, store.PREFIX + 'a' * 63):
        with pytest.raises(ValueError):
            local.put(key, b'x', 'text/plain')


def test_the_store_follows_the_host_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('STORAGE_PROVIDER', 'local')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    assert isinstance(store.configured_store(), store.LocalEvidenceStore)
    monkeypatch.setenv('STORAGE_PROVIDER', 's3')
    assert store.configured_store() is None
    monkeypatch.setenv('STORAGE_PROVIDER', 'gcs')
    monkeypatch.delenv('GCS_BUCKET_NAME', raising=False)
    assert store.configured_store() is None


# --- commands -------------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path):
    from sqlalchemy import create_engine

    from jup.leadership import actions, migrate
    from jup.leadership.repository import unit_of_work

    engine = create_engine(f'sqlite:///{tmp_path / "webui.db"}')
    assert migrate.run_leadership_migrations(engine) is True
    for action_id, pic in (('act-1', PIC), ('act-2', OTHER_PIC), ('act-orphan', None)):
        with unit_of_work(engine) as uow:
            actions.create_action(
                uow, action_id=action_id, title='t', pic_label='PIC', pic_user_id=pic, author='importer'
            )
    with unit_of_work(engine) as uow:
        actions.change_state(uow, action_id='act-1', expected_version=1, to_state='in_progress', author=PIC)
    yield engine
    engine.dispose()


def _pdf_item(content: bytes = PDF_BYTES) -> dict:
    from jup.leadership.evidence import file_evidence

    return file_evidence(check_file(content, 'berita-acara.pdf', 'application/pdf'))


def _submit(engine, actor: str = PIC, action_id: str = 'act-1', expected_version: int = 2, **kwargs):
    from jup.leadership.evidence import submit_evidence
    from jup.leadership.repository import unit_of_work

    kwargs.setdefault('item', _pdf_item())
    with unit_of_work(engine) as uow:
        return submit_evidence(uow, action_id=action_id, expected_version=expected_version, actor=actor, **kwargs)


@needs_runtime
@pytest.mark.parametrize(
    ('actor', 'action_id'),
    [
        ('user-admin', 'act-1'),  # admin, BOC observer, read-only reader: none is the PIC
        (OTHER_PIC, 'act-1'),  # the PIC of another action
        (PIC, 'act-orphan'),  # no recorded PIC user means no submitter at all
    ],
)
def test_only_the_recorded_pic_submits(engine, actor: str, action_id: str) -> None:
    from jup.leadership.evidence import NotThePic, submit_progress
    from jup.leadership.repository import read_events, unit_of_work

    before = len(read_events(engine, action_id))
    with pytest.raises(NotThePic):
        _submit(engine, actor=actor, action_id=action_id, expected_version=1)
    with pytest.raises(NotThePic):
        with unit_of_work(engine) as uow:
            submit_progress(uow, action_id=action_id, actor=actor, expected_version=1, narrative='x')
    assert len(read_events(engine, action_id)) == before


@needs_runtime
def test_evidence_is_versioned_and_never_replaced(engine) -> None:
    from jup.leadership.evidence import link_evidence

    first = _submit(engine)
    second = _submit(engine, expected_version=3, item=link_evidence('https://sharepoint.example/berita-acara'))
    assert (first.evidence['revision'], second.evidence['revision']) == (1, 2)
    assert first.evidence['kind'] == 'file' and second.evidence['kind'] == 'link'
    assert first.closure_request_id is None and second.closure_request_id is None


@needs_runtime
def test_completion_evidence_requests_closure_and_never_closes(engine) -> None:
    from sqlalchemy import select

    from jup.leadership.models import closure_request
    from jup.leadership.repository import read_action

    submitted = _submit(engine, completion=True, note='BA signed')
    assert read_action(engine, 'act-1')['state'] == 'awaiting_bod_closure'
    with engine.connect() as connection:
        request = connection.execute(select(closure_request)).mappings().one()
    assert request['id'] == submitted.closure_request_id
    assert request['evidence_id'] == submitted.evidence['id']
    assert (request['closure_kind'], request['status'], request['requested_by']) == ('completed', 'open', PIC)


@needs_runtime
@pytest.mark.parametrize('state', ['not_started', 'blocked', 'awaiting_bod_closure', 'closed'])
def test_completion_comes_only_from_in_progress(engine, state: str) -> None:
    from sqlalchemy import update

    from jup.leadership.actions import CommandRefused
    from jup.leadership.models import action

    with engine.begin() as connection:
        connection.execute(update(action).where(action.c.id == 'act-1').values(state=state))
    with pytest.raises(CommandRefused):
        _submit(engine, completion=True)


@needs_runtime
def test_a_closed_action_takes_no_evidence(engine) -> None:
    from sqlalchemy import update

    from jup.leadership.actions import CommandRefused
    from jup.leadership.models import action

    with engine.begin() as connection:
        connection.execute(update(action).where(action.c.id == 'act-1').values(state='closed'))
    with pytest.raises(CommandRefused, match='closed'):
        _submit(engine)


@needs_runtime
def test_a_double_submitted_completion_replays_without_a_second_request(engine) -> None:
    from sqlalchemy import func, select

    from jup.leadership.models import closure_request, evidence

    first = _submit(engine, completion=True, idempotency_key='k1')
    second = _submit(engine, completion=True, idempotency_key='k1')
    assert second.replayed is True
    assert second.evidence == first.evidence
    assert second.closure_request_id == first.closure_request_id
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(evidence)).scalar() == 1
        assert connection.execute(select(func.count()).select_from(closure_request)).scalar() == 1


@needs_runtime
def test_a_failed_submission_leaves_no_evidence_row(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import func, select

    from jup.leadership import evidence as module
    from jup.leadership.models import evidence
    from jup.leadership.repository import read_action

    def broken(**_: object):
        raise RuntimeError('closure request insert failed')

    real_insert = module.closure_request.insert
    monkeypatch.setattr(module.closure_request, 'insert', broken, raising=False)
    try:
        with pytest.raises(RuntimeError):
            _submit(engine, completion=True)
    finally:
        monkeypatch.setattr(module.closure_request, 'insert', real_insert, raising=False)
    assert read_action(engine, 'act-1')['state'] == 'in_progress'
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(evidence)).scalar() == 0


@needs_runtime
@pytest.mark.parametrize('url', ['http://example.com/x', 'javascript:alert(1)', 'https://', 'ftp://h/x', ''])
def test_link_evidence_must_be_https(url: str) -> None:
    from jup.leadership.actions import CommandRefused
    from jup.leadership.evidence import link_evidence

    with pytest.raises(CommandRefused):
        link_evidence(url)


@needs_runtime
def test_the_pic_records_progress(engine) -> None:
    from jup.leadership.evidence import submit_progress
    from jup.leadership.repository import read_events, unit_of_work

    with unit_of_work(engine) as uow:
        submit_progress(uow, action_id='act-1', actor=PIC, expected_version=2, narrative='draft sent')
    assert read_events(engine, 'act-1')[-1].payload['narrative'] == 'draft sent'


# --- the deletion hold (the vendor's "delete all files") -------------------------------------


class _FakeBlob:
    def __init__(self, bucket: '_FakeBucket', name: str) -> None:
        self.bucket, self.name = bucket, name
        self.temporary_hold = None

    def _stored(self) -> dict | None:
        return self.bucket.objects.get(self.name)

    def exists(self) -> bool:
        return self._stored() is not None

    def upload_from_string(self, content: bytes, content_type: str, if_generation_match=None) -> None:
        if if_generation_match == 0 and self.exists():
            from google.api_core.exceptions import PreconditionFailed

            raise PreconditionFailed('exists')
        self.bucket.objects[self.name] = {'content': content, 'hold': False}

    def reload(self) -> None:
        self.temporary_hold = self._stored()['hold']

    def patch(self) -> None:
        if self.bucket.refuse_patch:
            return  # a patch that silently did not take
        self._stored()['hold'] = bool(self.temporary_hold)

    def delete(self) -> None:
        if self._stored()['hold']:
            from google.api_core.exceptions import Forbidden

            # What GCS answers for a held object.
            raise Forbidden(f'{self.name} is under a temporary hold')
        del self.bucket.objects[self.name]


class _FakeBucket:
    """GCS as far as the evidence store and the vendor's delete_all_files touch it."""

    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}
        self.refuse_patch = False

    def blob(self, name: str) -> _FakeBlob:
        return _FakeBlob(self, name)

    def list_blobs(self) -> list[_FakeBlob]:
        return [self.blob(name) for name in sorted(self.objects)]


def _gcs(bucket: _FakeBucket):
    gcs = object.__new__(store.GCSEvidenceStore)
    gcs.bucket = bucket
    return gcs


needs_gcs = pytest.mark.skipif(
    importlib.util.find_spec('google.api_core') is None, reason='the GCS client is not installed'
)


@needs_gcs
def test_gcs_evidence_is_held_against_deletion() -> None:
    bucket = _FakeBucket()
    checked = check_file(PDF_BYTES, 'ba.pdf', 'application/pdf')
    _gcs(bucket).put(checked.key, checked.content, checked.content_type)
    assert bucket.objects[checked.key]['hold'] is True


@needs_gcs
def test_an_unheld_object_already_there_gets_its_hold() -> None:
    bucket = _FakeBucket()
    checked = check_file(PDF_BYTES, 'ba.pdf', 'application/pdf')
    bucket.objects[checked.key] = {'content': checked.content, 'hold': False}  # an earlier try died mid-way
    _gcs(bucket).put(checked.key, checked.content, checked.content_type)
    assert bucket.objects[checked.key] == {'content': checked.content, 'hold': True}


@needs_gcs
def test_a_hold_that_does_not_take_fails_the_put() -> None:
    bucket = _FakeBucket()
    bucket.refuse_patch = True
    checked = check_file(PDF_BYTES, 'ba.pdf', 'application/pdf')
    with pytest.raises(store.EvidenceNotHeld):
        _gcs(bucket).put(checked.key, checked.content, checked.content_type)


@needs_gcs
def test_the_vendors_delete_all_files_cannot_remove_gcs_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    from open_webui.storage import provider

    bucket = _FakeBucket()
    checked = check_file(PDF_BYTES, 'ba.pdf', 'application/pdf')
    _gcs(bucket).put(checked.key, checked.content, checked.content_type)
    bucket.objects['zz-chat-upload.txt'] = {'content': b'x', 'hold': False}

    vendor = object.__new__(provider.GCSStorageProvider)
    vendor.bucket = bucket
    monkeypatch.setattr(provider.LocalStorageProvider, 'delete_all_files', staticmethod(lambda: None))
    from google.api_core.exceptions import Forbidden

    # The vendor wraps only NotFound, so the admin's call fails loudly at the first held object.
    with pytest.raises(Forbidden):
        vendor.delete_all_files()
    assert bucket.objects[checked.key]['content'] == checked.content


@needs_runtime
def test_the_vendors_local_delete_all_files_leaves_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from open_webui.storage import provider

    monkeypatch.setenv('STORAGE_PROVIDER', 'local')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    (uploads / 'chat-file.txt').write_text('x')
    monkeypatch.setattr(provider, 'UPLOAD_DIR', str(uploads))

    checked = check_file(PDF_BYTES, 'ba.pdf', 'application/pdf')
    store.configured_store().put(checked.key, checked.content, checked.content_type)
    provider.LocalStorageProvider.delete_all_files()
    assert list(uploads.iterdir()) == []
    assert (tmp_path / checked.key).read_bytes() == checked.content
