"""The `main.py` lines that migrate the Channel Mapping tables (E9.1), read from source.

A rebase that takes upstream's side of `main.py` drops the call silently: the app boots, and every
WhatsApp sender is refused as `lookup_failed`. Runs under `--only-group dev`.
"""

import ast
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui' / 'main.py'


def _tree() -> ast.Module:
    return ast.parse(MAIN_PY.read_text(encoding='utf-8'))


def test_the_runner_is_imported() -> None:
    imported = {
        (node.module, alias.name)
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ('jup.channel_links.migrate', 'run_channel_link_migrations') in imported


def test_it_runs_on_the_vendor_engine_under_the_migration_switch() -> None:
    for node in _tree().body:
        if isinstance(node, ast.If) and getattr(node.test, 'id', None) == 'ENABLE_DB_MIGRATIONS':
            for statement in node.body:
                call = getattr(statement, 'value', None)
                if isinstance(call, ast.Call) and getattr(call.func, 'id', None) == 'run_channel_link_migrations':
                    assert [getattr(arg, 'id', None) for arg in call.args] == ['engine']
                    return
    raise AssertionError('main.py no longer calls run_channel_link_migrations under ENABLE_DB_MIGRATIONS')
