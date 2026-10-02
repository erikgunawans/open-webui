"""The `main.py` lines that mount the fork's own routers.

A quarterly rebase (ADR-0007) that resolves a `main.py` conflict by taking upstream's side drops
these silently: the app boots, and the section just answers 404. A source read catches it in CI's
`--only-group dev` job without importing the runtime.
"""

import ast
from pathlib import Path

import pytest

MAIN_PY = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui' / 'main.py'

# Router module -> the prefix it must be mounted at.
ROUTERS = {
    'jup_portfolio': '/api/v1/portfolio',
    'jup_leadership': '/api/v1/leadership',
    'jup_kb_review': '/api/v1/kb-review',
    'jup_contracts': '/api/v1/contracts',
    'jup_voice': '/api/v1/voice',
}


def _tree() -> ast.Module:
    return ast.parse(MAIN_PY.read_text(encoding='utf-8'))


def _imported_routers(tree: ast.Module) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == 'open_webui.routers'
        for alias in node.names
    }


def _mounts(tree: ast.Module) -> dict[str, str]:
    mounts = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != 'include_router' or not node.args:
            continue
        target = node.args[0]
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)):
            continue
        prefix = next((kw.value for kw in node.keywords if kw.arg == 'prefix'), None)
        if isinstance(prefix, ast.Constant):
            mounts[target.value.id] = prefix.value
    return mounts


@pytest.mark.parametrize('module', sorted(ROUTERS))
def test_the_router_is_imported(module: str) -> None:
    assert module in _imported_routers(_tree()), (
        f'{module} is no longer imported in main.py — see deploy/gcp/VENDOR-PATCHES.md'
    )


@pytest.mark.parametrize(('module', 'prefix'), sorted(ROUTERS.items()))
def test_the_router_is_mounted_at_its_prefix(module: str, prefix: str) -> None:
    assert _mounts(_tree()).get(module) == prefix, (
        f'{module} is not mounted at {prefix} in main.py — see deploy/gcp/VENDOR-PATCHES.md'
    )
