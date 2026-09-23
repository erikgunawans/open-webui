"""The `main.py` lines that migrate Ruang Pimpinan's own tables.

The leadership tables live on their own alembic graph with their own version table (ADR-0014), and
`main.py` runs it once the vendor upgrade is done, under the same `ENABLE_DB_MIGRATIONS` switch. A
rebase that takes upstream's side of `main.py` drops the call silently: the app boots and the
section reports its schema as not ready. A source read catches that under `--only-group dev`.
See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import ast
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui' / 'main.py'


def _tree() -> ast.Module:
    return ast.parse(MAIN_PY.read_text(encoding='utf-8'))


def _migration_call(tree: ast.Module) -> ast.If:
    for node in tree.body:
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Name)):
            continue
        if node.test.id != 'ENABLE_DB_MIGRATIONS':
            continue
        for statement in node.body:
            call = getattr(statement, 'value', None)
            if isinstance(call, ast.Call) and getattr(call.func, 'id', None) == 'run_leadership_migrations':
                return node
    raise AssertionError('main.py no longer calls run_leadership_migrations under ENABLE_DB_MIGRATIONS')


def test_the_runner_and_its_switch_are_imported() -> None:
    imported = {
        (node.module, alias.name)
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ('jup.leadership.migrate', 'run_leadership_migrations') in imported
    assert ('open_webui.env', 'ENABLE_DB_MIGRATIONS') in imported


def test_the_migration_runs_on_the_vendor_engine() -> None:
    guard = _migration_call(_tree())
    call = guard.body[0].value
    assert [getattr(arg, 'id', None) for arg in call.args] == ['engine'], 'pass the vendor engine'


def test_the_migration_runs_before_the_leadership_router_is_mounted() -> None:
    tree = _tree()
    guard = _migration_call(tree)
    mounts = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, 'attr', None) == 'include_router'
        and node.args
        and getattr(getattr(node.args[0], 'value', None), 'id', None) == 'jup_leadership'
    ]
    assert mounts and guard.lineno < mounts[0]
