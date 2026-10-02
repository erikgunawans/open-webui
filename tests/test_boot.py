"""The boot baseline: alembic has one head, and the application actually starts.

These two assertions guard the failure mode that takes everything else down with it. A
fork migration whose `down_revision` collides with an upstream one leaves alembic with two
heads; migrations run at config-import time; the process does not come up at all. Nothing
else in the suite can fail usefully once that happens, so this file runs first in spirit
even though pytest does not order it.

They are deliberately different in cost and in reach. The head check is a pure AST read of
the versions directory: it needs no runtime, runs in milliseconds, and is the check to run
after every upstream rebase (ADR-0007). The boot check imports the real application in a
subprocess against a throwaway database, and is skipped where the runtime tree is not
installed — which includes CI's `--only-group dev` job, by design.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from jup.migrations import (
    Revision,
    dangling_parents,
    describe,
    duplicate_identifiers,
    heads,
    read_revisions,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent / 'backend'
VERSIONS_DIR = BACKEND_DIR / 'open_webui' / 'migrations' / 'versions'
# Ruang Pimpinan's tables migrate on their own graph and version table (ADR-0014), so a fork
# revision never shares a head with upstream. The same four checks hold for it.
LEADERSHIP_VERSIONS_DIR = BACKEND_DIR / 'jup' / 'leadership' / 'migrations' / 'versions'
# The contract KB's graph, separate again so a broken contract migration disables only contracts.
CONTRACTS_VERSIONS_DIR = BACKEND_DIR / 'jup' / 'contracts' / 'migrations' / 'versions'
# The tracked tree `config.py` wipes at import. `tests/conftest.py` redirects STATIC_DIR away
# from it before pytest imports any test module; the last test in this file asserts that.
TRACKED_STATIC_DIR = BACKEND_DIR / 'open_webui' / 'static'

# `open_webui/__init__.py` imports typer, so `pythonpath = ["backend"]` makes the package
# findable under `--only-group dev` while importing it still fails. Probing the package
# itself would therefore report a runtime that is not there; probe its dependencies.
_RUNTIME_MODULES = ('typer', 'uvicorn', 'fastapi', 'alembic')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

# Import the app, prove it is the ASGI application, and say so on stdout. Anything the
# import does on the way — including running migrations against DATABASE_URL — has to
# succeed for this to print, which is the whole point of importing rather than inspecting.
_BOOT_SCRIPT = textwrap.dedent(
    """
    from open_webui.main import app
    from fastapi import FastAPI

    assert isinstance(app, FastAPI), f'open_webui.main.app is {type(app)!r}, not a FastAPI application'
    from jup.leadership.migrate import schema_ready

    assert schema_ready(), 'the Ruang Pimpinan graph did not reach its head during boot (ADR-0014)'
    from jup.contracts.migrate import schema_ready as contracts_ready

    assert contracts_ready(), 'the contract KB graph did not reach its head during boot'
    print('BOOTED', len(app.routes))
    """
)


@pytest.fixture(
    scope='module',
    params=[VERSIONS_DIR, LEADERSHIP_VERSIONS_DIR, CONTRACTS_VERSIONS_DIR],
    ids=['vendor', 'leadership', 'contracts'],
)
def revisions(request: pytest.FixtureRequest) -> tuple[Revision, ...]:
    """One whole revision graph, read once for every assertion in this file."""
    return read_revisions(request.param)


def test_every_revision_declares_a_distinct_identifier(revisions: tuple[Revision, ...]) -> None:
    """Checked before the head count, which two files sharing an id would render meaningless."""
    duplicated = duplicate_identifiers(revisions)

    assert not duplicated, (
        f'{len(duplicated)} revision id(s) are declared by more than one migration:\n'
        f'{describe(revisions, duplicated)}\n'
        'Two files claiming one id is the same rebase collision as two heads, and it hides '
        'a head behind the other file. Give the fork revision a fresh id.'
    )


def test_every_cited_parent_exists(revisions: tuple[Revision, ...]) -> None:
    """A `down_revision` pointing at a revision upstream deleted also stops the app booting."""
    dangling = dangling_parents(revisions)

    assert not dangling, (
        f'{len(dangling)} `down_revision` value(s) cite a revision no file declares:\n'
        f'{describe(revisions, dangling)}\n'
        'Alembic cannot walk the chain, so migrations fail at config-import time and the '
        'application does not start. Repoint the child at a revision that exists.'
    )


def test_alembic_resolves_to_exactly_one_head(revisions: tuple[Revision, ...]) -> None:
    """The guard this file exists for — run it after every upstream rebase (ADR-0007).

    The message names each head with its file and its `down_revision`, because "Found 2
    head revisions" sends a maintainer to alembic's documentation while two filenames send
    them to the two lines that disagree.
    """
    found = heads(revisions)

    assert len(found) == 1, (
        f'alembic resolves to {len(found)} heads, not 1, across {len(revisions)} revisions:\n'
        f'{describe(revisions, found)}\n'
        'Migrations run at config-import time, so this does not degrade the application — '
        'it stops it starting. Repoint the fork revision at the upstream head, or merge them.'
    )


def test_the_revision_graph_has_exactly_one_base(revisions: tuple[Revision, ...]) -> None:
    """A second base is a chain grafted in without a parent, and it never migrates."""
    bases = tuple(revision.identifier for revision in revisions if not revision.down)

    assert len(bases) == 1, (
        f'the revision graph has {len(bases)} base revisions, not 1:\n{describe(revisions, bases)}\n'
        'A revision with no `down_revision` starts its own chain, which alembic will not '
        'reach from the existing one.'
    )


@pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`, where the head checks above are the guard. Install the project to run this.'
    ),
)
def test_the_application_imports_and_boots(tmp_path: Path) -> None:
    """Import the real application against a throwaway database and prove it comes up.

    Run in a subprocess for two reasons. Importing `open_webui.main` runs migrations and
    pulls in the whole model tree, which would leave that state in the test process and
    turn a sub-second suite into a slow one. And a boot failure is often a hard exit rather
    than an exception, which only a separate process can report as one.
    """
    database = tmp_path / 'boot-baseline.db'

    # A throwaway copy of the real static tree. The app requires STATIC_DIR to exist, and
    # copying rather than creating an empty directory keeps the boot realistic — swagger-ui
    # and the font assets are served from here.
    static = tmp_path / 'static'
    shutil.copytree(TRACKED_STATIC_DIR, static)
    environment = {
        **os.environ,
        'DATABASE_URL': f'sqlite:///{database}',
        'DATA_DIR': str(tmp_path / 'data'),
        # config.py unlinks EVERY file in STATIC_DIR at import and repopulates from
        # FRONTEND_BUILD_DIR/static — which this tree does not have unless the frontend has
        # just been built. Left at its default, importing the app deletes 17 tracked vendor
        # assets (favicons, logo, loader.js, the manifests) and puts nothing back, silently:
        # the unlink loop swallows every exception. Point it at a throwaway directory so a
        # test run cannot leave the working tree dirty.
        'STATIC_DIR': str(tmp_path / 'static'),
        'WEBUI_SECRET_KEY': 'boot-baseline',
        # Offline and disabled: this asserts the app starts, not that it can reach a model.
        'RAG_EMBEDDING_ENGINE': 'ollama',
        'ENABLE_OLLAMA_API': 'false',
        'ENABLE_OPENAI_API': 'false',
        'OFFLINE_MODE': 'true',
        'HF_HUB_OFFLINE': '1',
    }

    completed = subprocess.run(  # noqa: S603
        [sys.executable, '-c', _BOOT_SCRIPT],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    assert completed.returncode == 0, (
        f'the application did not import and boot (exit {completed.returncode}).\n'
        'Migrations run at config-import time, so a two-headed alembic tree surfaces here '
        'as a failure to start rather than as a broken feature.\n'
        f'--- stderr ---\n{completed.stderr[-4000:]}'
    )
    assert 'BOOTED' in completed.stdout, (
        f'the app imported without reporting a route table:\n{completed.stdout[-2000:]}'
    )


def test_the_static_wipe_guard_is_in_place() -> None:
    """`conftest.py` redirects STATIC_DIR before anything can import the app. Asserted here.

    A landmine that fires silently needs a loud tripwire. `config.py` unlinks every file in
    STATIC_DIR at import and repopulates from a frontend build this tree does not have, so
    one unguarded import deletes 17 tracked vendor assets and the unlink loop swallows the
    errors. This test fails the moment the guard stops working, rather than the working tree
    quietly losing its favicons.
    """
    redirected = Path(os.environ['STATIC_DIR']).resolve()

    assert redirected != TRACKED_STATIC_DIR.resolve(), (
        f'STATIC_DIR still points at the tracked tree at {TRACKED_STATIC_DIR}. Importing '
        'open_webui from any test will delete every file in it and put nothing back.'
    )
    assert (redirected / 'loader.js').is_file(), (
        f'the throwaway static tree at {redirected} is not a copy of the real one — the app '
        'boots against it, so an empty directory makes a boot failure look like a code bug.'
    )
