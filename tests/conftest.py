"""Root pytest configuration for the ent-os backend suite.

This directory sits outside `backend/` on purpose: the quarterly upstream rebase
(ADR-0007) should never have to merge our tests against open-webui's own tree, and
the vendor tree already owns `test/` (singular) for its image-generation fixtures.
"""

import atexit
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / 'fixtures'
STATIC_DIR = Path(__file__).parent.parent / 'backend' / 'open_webui' / 'static'


def _redirect_static_dir() -> None:
    """Point `STATIC_DIR` at a throwaway copy before anything can import `open_webui`.

    `open_webui/config.py` unlinks **every file** in `STATIC_DIR` at import and repopulates
    it from `FRONTEND_BUILD_DIR/static`, which this tree does not have unless the frontend
    was just built. So the wipe has nothing to put back — and the unlink loop swallows every
    exception, so it is silent. Importing the app once deletes 17 tracked vendor assets
    (favicons, logo, loader.js, the manifests), and a `git add -u` afterwards commits that.

    This runs at conftest import, which pytest does before it imports any test module, so a
    test that imports `open_webui` anywhere — today or in a year — is covered without having
    to know. `tests/test_boot.py` still sets it in the subprocess environment it builds,
    because that process does not inherit this one's conftest, only its environment.

    Respects an existing value: a caller who has already pointed it somewhere safe knows
    something we do not.
    """
    if os.environ.get('STATIC_DIR'):
        return
    scratch = Path(tempfile.mkdtemp(prefix='ent-os-static-'))
    atexit.register(shutil.rmtree, scratch, ignore_errors=True)
    target = scratch / 'static'
    shutil.copytree(STATIC_DIR, target)
    os.environ['STATIC_DIR'] = str(target)
    # Importing `open_webui.env` exits the process outright without one. Set only if unset,
    # so a suite run against a real configuration keeps its own key.
    os.environ.setdefault('WEBUI_SECRET_KEY', 'ent-os-test-suite')


_redirect_static_dir()


@pytest.fixture(scope='session')
def fixtures_dir() -> Path:
    """Absolute path to `tests/fixtures/` — the shared home for fixture data."""
    return FIXTURES_DIR


@pytest.fixture
def fixture_path(fixtures_dir: Path) -> Callable[..., Path]:
    """Resolve a path under `tests/fixtures/`, failing loudly when it is missing.

    A missing fixture raises here rather than surfacing as a confusing assertion
    failure deeper inside the test.
    """

    def _resolve(*parts: str) -> Path:
        path = fixtures_dir.joinpath(*parts)
        if not path.exists():
            raise FileNotFoundError(f'fixture not found: {path}')
        return path

    return _resolve


@pytest.fixture
def leadership_db_url(tmp_path: Path):
    """An empty database URL for one test's leadership records store.

    SQLite in a temp dir by default. With `JUP_TEST_POSTGRES_URL` set (a disposable server;
    production is Cloud SQL Postgres 16), a fresh database is created on it and dropped after,
    so every suite that builds its store here runs on Postgres too, not only the repository's
    own Postgres-marked cases. Imports stay inside: CI's dev-only group has no sqlalchemy.
    """
    base = os.environ.get('JUP_TEST_POSTGRES_URL')
    if not base:
        yield f'sqlite:///{tmp_path / "webui.db"}'
        return

    import uuid

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    name = f'jl_{uuid.uuid4().hex[:12]}'
    admin = create_engine(base, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE {name}'))
    try:
        yield make_url(base).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)'))
        admin.dispose()
