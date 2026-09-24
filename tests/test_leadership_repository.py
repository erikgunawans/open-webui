"""Ruang Pimpinan's persistence adapter (P2 T1), against real databases.

Every table here arrives through the leadership migration graph, never `metadata.create_all`, so the
schema under test is the one production gets. The Postgres cases run only when
`JUP_TEST_POSTGRES_URL` points at a disposable server (production is Cloud SQL Postgres 16); each
case gets its own throwaway database there.

Needs the runtime (alembic, sqlalchemy); skipped under `--only-group dev`. The append-only source
check at the bottom needs neither and always runs.
"""

import ast
import importlib.util
import os
import threading
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

LEADERSHIP_DIR = Path(__file__).resolve().parent.parent / 'backend' / 'jup' / 'leadership'

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')

PG_URL = os.environ.get('JUP_TEST_POSTGRES_URL')
_NEEDS_PG = pytest.mark.skipif(not PG_URL, reason='set JUP_TEST_POSTGRES_URL')
_BACKENDS = ['sqlite', pytest.param('postgres', marks=_NEEDS_PG)]

EXPECTED_TABLES = {
    'leadership_action',
    'leadership_action_event',
    'leadership_evidence',
    'leadership_closure_request',
    'leadership_closure_decision',
    'leadership_snapshot',
    'leadership_snapshot_version',
    'leadership_rka_baseline',
    'leadership_import_batch',
    'leadership_import_candidate',
    'leadership_external_ref',
}

PIC = 'user-pic-1'
BOD = 'user-bod-1'


def _fresh_postgres():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    name = f'jl_{uuid.uuid4().hex[:12]}'
    admin = create_engine(PG_URL, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE {name}'))
    url = make_url(PG_URL).set(database=name)

    def drop() -> None:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)'))
        admin.dispose()

    return url, drop


@pytest.fixture(params=_BACKENDS)
def database(request, tmp_path: Path):
    """A URL for an empty database already brought to the leadership head; yields (url, backend)."""
    from sqlalchemy import create_engine

    from jup.leadership import migrate

    if request.param == 'sqlite':
        url, drop = f'sqlite:///{tmp_path / "webui.db"}', lambda: None
    else:
        url, drop = _fresh_postgres()
    engine = create_engine(url)
    assert migrate.run_leadership_migrations(engine) is True
    engine.dispose()
    try:
        yield url, request.param
    finally:
        drop()


@pytest.fixture
def engine(database):
    from sqlalchemy import create_engine

    engine = create_engine(database[0])
    yield engine
    engine.dispose()


def _new_action(engine, action_id: str = 'act-1', **overrides):
    from jup.leadership.repository import unit_of_work

    fields = {
        'title': 'Finalise SPBG offtake term sheet',
        'pic_user_id': PIC,
        'pic_label': 'PIC Komersial',
        'state': 'not_started',
        'original_due': '2026-11',
        'original_due_precision': 'month',
        'current_due': '2026-11',
        'current_due_precision': 'month',
    }
    fields.update(overrides)
    with unit_of_work(engine) as uow:
        return uow.create_action(action_id=action_id, fields=fields, author=PIC, reason='imported from deck')


def _progress(uow, expected_version: int, note: str, **kwargs):
    return uow.append_event(
        action_id='act-1',
        expected_version=expected_version,
        kind='progress_submitted',
        payload={'narrative': note},
        author=PIC,
        **kwargs,
    )


# --- schema ---------------------------------------------------------------------------------


@needs_runtime
def test_the_graph_creates_exactly_the_leadership_tables(engine) -> None:
    from sqlalchemy import inspect

    tables = set(inspect(engine).get_table_names())
    assert tables - {'jup_alembic_version'} == EXPECTED_TABLES


@needs_runtime
def test_the_migrated_schema_matches_the_models(engine) -> None:
    """models.py is what the code writes through; the migration is what production has."""
    from sqlalchemy import inspect

    from jup.leadership.models import metadata

    inspector = inspect(engine)
    assert set(metadata.tables) == EXPECTED_TABLES
    for name, table in metadata.tables.items():
        migrated = {column['name']: column for column in inspector.get_columns(name)}
        assert set(migrated) == set(table.columns.keys()), name
        for column in table.columns:
            assert migrated[column.name]['nullable'] == column.nullable, f'{name}.{column.name}'
        assert set(inspector.get_pk_constraint(name)['constrained_columns']) == {c.name for c in table.primary_key}
        uniques = {tuple(sorted(u['column_names'])) for u in inspector.get_unique_constraints(name)}
        declared = {
            tuple(sorted(c.name for c in constraint.columns))
            for constraint in table.constraints
            if constraint.__class__.__name__ == 'UniqueConstraint'
        }
        assert declared <= uniques, name


@needs_runtime
def test_no_column_stores_a_binary_float() -> None:
    from sqlalchemy import Float

    from jup.leadership.models import metadata

    floats = [f'{t.name}.{c.name}' for t in metadata.tables.values() for c in t.columns if isinstance(c.type, Float)]
    assert floats == []


# --- aggregate and events -------------------------------------------------------------------


@needs_runtime
def test_creating_an_action_records_version_one_and_its_event(engine) -> None:
    from jup.leadership.repository import read_action, read_events

    result = _new_action(engine)
    assert result.replayed is False
    assert result.event.version == 1 and result.event.kind == 'created'

    action = read_action(engine, 'act-1')
    assert action['version'] == 1
    assert action['state'] == 'not_started'
    assert action['original_due'] == '2026-11'
    events = read_events(engine, 'act-1')
    assert [(e.version, e.kind, e.author) for e in events] == [(1, 'created', PIC)]
    assert events[0].reason == 'imported from deck'


@needs_runtime
def test_an_event_bumps_the_version_and_changes_the_aggregate_together(engine) -> None:
    from jup.leadership.repository import read_action, read_events, unit_of_work

    _new_action(engine)
    with unit_of_work(engine) as uow:
        result = uow.append_event(
            action_id='act-1',
            expected_version=1,
            kind='state_changed',
            payload={'from': 'not_started', 'to': 'in_progress'},
            author=PIC,
            changes={'state': 'in_progress'},
        )
    assert result.event.version == 2
    action = read_action(engine, 'act-1')
    assert (action['version'], action['state']) == (2, 'in_progress')
    assert [e.version for e in read_events(engine, 'act-1')] == [1, 2]
    assert read_events(engine, 'act-1')[1].payload == {'from': 'not_started', 'to': 'in_progress'}


@needs_runtime
def test_a_stale_version_conflicts_and_writes_nothing(engine) -> None:
    from jup.leadership.repository import VersionConflict, read_action, read_events, unit_of_work

    _new_action(engine)
    with unit_of_work(engine) as uow:
        _progress(uow, 1, 'newer update')

    with pytest.raises(VersionConflict) as caught:
        with unit_of_work(engine) as uow:
            _progress(uow, 1, 'older update from a stale tab', changes={'state': 'blocked'})
    assert (caught.value.expected, caught.value.actual) == (1, 2)
    assert read_action(engine, 'act-1')['version'] == 2
    assert read_action(engine, 'act-1')['state'] == 'not_started'
    assert [e.payload.get('narrative') for e in read_events(engine, 'act-1')] == [None, 'newer update']


@needs_runtime
def test_a_double_submission_returns_the_first_result(engine) -> None:
    from jup.leadership.repository import read_events, unit_of_work

    _new_action(engine)
    with unit_of_work(engine) as uow:
        first = _progress(uow, 1, 'done', idempotency_key='submit-abc')
    # The second click carries the same, now stale, expected version.
    with unit_of_work(engine) as uow:
        second = _progress(uow, 1, 'done', idempotency_key='submit-abc')
    assert second.replayed is True
    assert second.event == first.event
    assert len(read_events(engine, 'act-1')) == 2


@needs_runtime
def test_a_reused_idempotency_key_with_different_content_is_refused(engine) -> None:
    from jup.leadership.repository import IdempotencyKeyReused, read_events, unit_of_work

    _new_action(engine)
    with unit_of_work(engine) as uow:
        _progress(uow, 1, 'done', idempotency_key='submit-abc')
    with pytest.raises(IdempotencyKeyReused):
        with unit_of_work(engine) as uow:
            _progress(uow, 2, 'something else', idempotency_key='submit-abc')
    assert len(read_events(engine, 'act-1')) == 2


@needs_runtime
def test_a_rollback_leaves_no_partial_event_version_or_key(engine) -> None:
    from jup.leadership.repository import read_action, read_events, unit_of_work

    _new_action(engine)
    with pytest.raises(RuntimeError, match='storage write failed'):
        with unit_of_work(engine) as uow:
            _progress(uow, 1, 'with evidence', idempotency_key='submit-xyz', changes={'state': 'in_progress'})
            raise RuntimeError('storage write failed')

    assert read_action(engine, 'act-1')['version'] == 1
    assert read_action(engine, 'act-1')['state'] == 'not_started'
    assert len(read_events(engine, 'act-1')) == 1
    # The key was never recorded, so the retry is a fresh submission, not a replay.
    with unit_of_work(engine) as uow:
        retry = _progress(uow, 1, 'with evidence', idempotency_key='submit-xyz')
    assert retry.replayed is False and retry.event.version == 2


@needs_runtime
def test_state_survives_a_restart(database) -> None:
    from sqlalchemy import create_engine

    from jup.leadership.repository import read_action, read_events, unit_of_work

    first = create_engine(database[0])
    _new_action(first)
    with unit_of_work(first) as uow:
        _progress(uow, 1, 'before restart')
    first.dispose()

    reopened = create_engine(database[0])
    try:
        assert read_action(reopened, 'act-1')['version'] == 2
        assert [e.kind for e in read_events(reopened, 'act-1')] == ['created', 'progress_submitted']
    finally:
        reopened.dispose()


@needs_runtime
def test_an_unknown_action_is_not_found(engine) -> None:
    from jup.leadership.repository import ActionNotFound, read_action, unit_of_work

    assert read_action(engine, 'missing') is None
    with pytest.raises(ActionNotFound):
        with unit_of_work(engine) as uow:
            uow.append_event(action_id='missing', expected_version=1, kind='x', payload={}, author=PIC)


@needs_runtime
def test_creating_an_existing_action_is_refused(engine) -> None:
    from jup.leadership.repository import ActionExists, read_events

    _new_action(engine)
    with pytest.raises(ActionExists):
        _new_action(engine, title='a different title')
    assert len(read_events(engine, 'act-1')) == 1


@needs_runtime
@pytest.mark.parametrize('field', ['id', 'version', 'created_at', 'created_by', 'no_such_column'])
def test_an_event_cannot_rewrite_identity_version_or_unknown_columns(engine, field: str) -> None:
    from jup.leadership.repository import read_events, unit_of_work

    _new_action(engine)
    with pytest.raises(ValueError, match=field):
        with unit_of_work(engine) as uow:
            _progress(uow, 1, 'x', changes={field: 'tampered'})
    assert len(read_events(engine, 'act-1')) == 1


@needs_runtime
@pytest.mark.parametrize('payload', [{'value': 1.5}, {'nested': [{'amount': 0.1}]}, {'value': float('nan')}])
def test_a_float_never_enters_an_event(engine, payload) -> None:
    from jup.leadership.repository import unit_of_work

    _new_action(engine)
    with pytest.raises(ValueError, match='float'):
        with unit_of_work(engine) as uow:
            uow.append_event(action_id='act-1', expected_version=1, kind='x', payload=payload, author=PIC)


@needs_runtime
def test_money_travels_as_a_decimal_string(engine) -> None:
    from jup.leadership.repository import read_events, unit_of_work

    _new_action(engine)
    with unit_of_work(engine) as uow:
        uow.append_event(
            action_id='act-1', expected_version=1, kind='x', payload={'value': str(Decimal('10.10'))}, author=PIC
        )
    assert read_events(engine, 'act-1')[1].payload == {'value': '10.10'}


@needs_runtime
@pytest.mark.skipif(not PG_URL, reason='row locking is a Postgres property; set JUP_TEST_POSTGRES_URL')
def test_two_concurrent_writers_on_postgres_yield_one_event_and_one_conflict() -> None:
    """The second writer blocks on the first's row lock, then sees the new version and conflicts."""
    from sqlalchemy import create_engine

    from jup.leadership import migrate
    from jup.leadership.repository import VersionConflict, read_events, unit_of_work

    url, drop = _fresh_postgres()
    engine = create_engine(url)
    try:
        assert migrate.run_leadership_migrations(engine) is True
        _new_action(engine)
        outcome: dict[str, object] = {}
        first_holds_lock = threading.Event()
        release_first = threading.Event()

        def first() -> None:
            with unit_of_work(engine) as uow:
                _progress(uow, 1, 'first')
                first_holds_lock.set()
                release_first.wait(10)

        def second() -> None:
            first_holds_lock.wait(10)
            try:
                with unit_of_work(engine) as uow:
                    _progress(uow, 1, 'second')
                outcome['second'] = 'committed'
            except VersionConflict as conflict:
                outcome['second'] = conflict

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for thread in threads:
            thread.start()
        first_holds_lock.wait(10)
        threading.Timer(1.0, release_first.set).start()
        for thread in threads:
            thread.join(20)

        assert isinstance(outcome['second'], VersionConflict)
        assert [e.payload.get('narrative') for e in read_events(engine, 'act-1')] == [None, 'first']
    finally:
        engine.dispose()
        drop()


# --- append-only, by source ------------------------------------------------------------------

APPEND_ONLY = {
    'leadership_action_event',
    'leadership_evidence',
    'leadership_closure_decision',
    'leadership_snapshot_version',
    'leadership_rka_baseline',
}


def _python_sources() -> list[Path]:
    return [p for p in LEADERSHIP_DIR.rglob('*.py') if '__pycache__' not in p.parts and 'versions' not in p.parts]


def test_no_code_path_updates_or_deletes_an_append_only_table() -> None:
    """Events, evidence, decisions, snapshot versions and baselines are only ever inserted.

    Two shapes are caught: `update(<table>)` / `delete(<table>)` and `<table>.update()` /
    `<table>.delete()`, where the table is one of the append-only module attributes in
    models.py; and raw SQL naming one of these tables after UPDATE or DELETE FROM.
    """
    append_only_names = {name.removeprefix('leadership_') for name in APPEND_ONLY}
    offenders: list[str] = []
    for path in _python_sources():
        source = path.read_text(encoding='utf-8')
        upper = source.upper()
        for table in APPEND_ONLY:
            for verb in ('UPDATE ', 'DELETE FROM '):
                if f'{verb}{table.upper()}' in upper:
                    offenders.append(f'{path.name}: raw {verb.strip()} {table}')
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id in {'update', 'delete'} and node.args:
                target = ast.unparse(node.args[0])
            elif isinstance(func, ast.Attribute) and func.attr in {'update', 'delete'}:
                target = ast.unparse(func.value)
            else:
                continue
            leaf = target.rsplit('.', 1)[-1]
            if leaf in append_only_names or leaf in APPEND_ONLY:
                offenders.append(f'{path.name}:{node.lineno} {func.__class__.__name__} {target}')
    assert not offenders, 'append-only tables written to: ' + '; '.join(offenders)


def test_the_append_only_guard_sees_a_forbidden_update(tmp_path: Path) -> None:
    """Forced failure: the guard above must actually fire on the shapes it claims to catch."""
    planted = tmp_path / 'leadership'
    planted.mkdir()
    (planted / 'bad.py').write_text(
        'from sqlalchemy import update\n'
        'from jup.leadership.models import action_event\n'
        'def rewrite(conn):\n'
        '    conn.execute(update(action_event).values(kind="x"))\n'
        '    conn.execute(models.evidence.delete())\n'
        '    conn.exec_driver_sql("DELETE FROM leadership_rka_baseline")\n',
        encoding='utf-8',
    )
    globals()['LEADERSHIP_DIR'], saved = planted, LEADERSHIP_DIR
    try:
        with pytest.raises(AssertionError) as caught:
            test_no_code_path_updates_or_deletes_an_append_only_table()
    finally:
        globals()['LEADERSHIP_DIR'] = saved
    report = str(caught.value)
    assert 'action_event' in report and 'evidence' in report and 'leadership_rka_baseline' in report
