"""Ruang Pimpinan's migration runner, against real databases.

Needs the runtime (alembic, sqlalchemy); skipped under `--only-group dev`, where
`test_boot.py`'s graph checks and `test_leadership_migration_seam.py` are the guard. The Postgres
case runs only when `JUP_TEST_POSTGRES_URL` points at a disposable database, because production
is Cloud SQL Postgres 16 and SQLite alone proves nothing about its types.
"""

import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ('alembic', 'sqlalchemy')),
    reason='the runtime tree is not installed; the graph and seam tests are the guard here',
)

from jup.leadership import migrate  # noqa: E402

HEAD = 'jl0003'


def _engine(url: str):
    from sqlalchemy import create_engine

    return create_engine(url)


def _tables(engine) -> set[str]:
    from sqlalchemy import inspect

    return set(inspect(engine).get_table_names())


def _version(engine) -> list[str]:
    from sqlalchemy import text

    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text(f'SELECT version_num FROM {migrate.VERSION_TABLE}'))]


def _check_database(engine) -> None:
    assert migrate.run_leadership_migrations(engine) is True
    assert migrate.schema_ready() is True
    assert _version(engine) == [HEAD]
    # The vendor's own version table is never created or touched by this graph.
    assert 'alembic_version' not in _tables(engine)
    # A second boot is a no-op, not an error.
    assert migrate.run_leadership_migrations(engine) is True
    assert _version(engine) == [HEAD]


def test_sqlite_reaches_the_leadership_head_on_its_own_version_table(tmp_path: Path) -> None:
    _check_database(_engine(f'sqlite:///{tmp_path / "webui.db"}'))


def test_the_vendor_version_table_is_left_alone(tmp_path: Path) -> None:
    from sqlalchemy import text

    engine = _engine(f'sqlite:///{tmp_path / "webui.db"}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
        connection.execute(text("INSERT INTO alembic_version VALUES ('vendorhead')"))
    assert migrate.run_leadership_migrations(engine) is True
    with engine.connect() as connection:
        assert [r[0] for r in connection.execute(text('SELECT version_num FROM alembic_version'))] == ['vendorhead']


def test_a_failed_migration_marks_the_section_unready_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / 'migrations'
    (broken / 'versions').mkdir(parents=True)
    (broken / 'env.py').write_text("raise RuntimeError('broken on purpose')\n", encoding='utf-8')
    monkeypatch.setattr(migrate, 'MIGRATIONS_DIR', broken)

    assert migrate.run_leadership_migrations(_engine(f'sqlite:///{tmp_path / "webui.db"}')) is False
    assert migrate.schema_ready() is False


@pytest.mark.skipif(
    not os.environ.get('JUP_TEST_POSTGRES_URL'), reason='set JUP_TEST_POSTGRES_URL to a disposable Postgres 16'
)
def test_postgres_reaches_the_leadership_head() -> None:
    _check_database(_engine(os.environ['JUP_TEST_POSTGRES_URL']))
