"""The contract graph's runner against a scratch SQLite, and the migrated schema against the models.

Needs the runtime (alembic, sqlalchemy); skipped under `--only-group dev`, where `test_boot.py`'s
graph checks and `test_contract_migration_seam.py` are the guard.
"""

from pathlib import Path

import pytest

# A skip mark would not stop the imports below, and `jup.contracts.models` needs sqlalchemy, which
# CI's `--only-group dev` job does not install.
pytest.importorskip('sqlalchemy', reason='the runtime tree is not installed')
pytest.importorskip('alembic', reason='the runtime tree is not installed')

from jup.contracts import migrate, models  # noqa: E402

HEAD = 'jc0001'


@pytest.fixture
def engine(tmp_path: Path):
    from sqlalchemy import create_engine

    return create_engine(f'sqlite:///{tmp_path / "contracts.db"}')


def _version(engine) -> list[str]:
    from sqlalchemy import text

    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text(f'SELECT version_num FROM {migrate.VERSION_TABLE}'))]


def test_the_graph_reaches_head_twice_without_error(engine) -> None:
    from sqlalchemy import inspect

    assert migrate.run_contract_migrations(engine) is True
    assert migrate.schema_ready() is True
    assert migrate.run_contract_migrations(engine) is True
    assert _version(engine) == [HEAD]
    tables = set(inspect(engine).get_table_names())
    assert {table.name for table in models.metadata.sorted_tables} <= tables
    # Neither the vendor's nor Ruang Pimpinan's version table is touched.
    assert not {'alembic_version', 'jup_alembic_version'} & tables


def test_a_failure_is_contained(monkeypatch) -> None:
    class _Broken:
        def begin(self):
            raise RuntimeError('database is down')

    assert migrate.run_contract_migrations(_Broken()) is False
    assert migrate.schema_ready() is False


def _shape(engine, name: str):
    from sqlalchemy import inspect

    inspector = inspect(engine)
    columns = {c['name']: (type(c['type']).__name__.upper(), c['nullable']) for c in inspector.get_columns(name)}
    primary = tuple(inspector.get_pk_constraint(name)['constrained_columns'])
    foreign = sorted(
        (tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns']))
        for f in inspector.get_foreign_keys(name)
    )
    unique = sorted(tuple(u['column_names']) for u in inspector.get_unique_constraints(name))
    return columns, primary, foreign, unique


def test_the_migrated_schema_matches_the_models(engine, tmp_path: Path) -> None:
    from sqlalchemy import create_engine

    assert migrate.run_contract_migrations(engine) is True
    created = create_engine(f'sqlite:///{tmp_path / "models.db"}')
    models.metadata.create_all(created)
    for table in models.metadata.sorted_tables:
        assert _shape(engine, table.name) == _shape(created, table.name), table.name
