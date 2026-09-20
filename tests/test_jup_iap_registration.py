"""The two lines in `main.py` that are the entire vendor surface of the IAP login.

ADR-0012 chose a fork-owned middleware over patching `routers/auths.py` and
`utils/auth.py` on exactly this argument: *"option 2's lost patch is a production login
loop that reads as a session bug, and option 3's is a missing registration line that a test
catches. An outage you can misdiagnose is worse than one you cannot."* This file is the
second half of that sentence. Without it the decision's central claim is unbacked, and the
ADR's Consequences section requires it by name.

The failure it guards is a quarterly rebase (ADR-0007) resolving a conflict in `main.py` by
taking upstream's side. Nothing else notices: the app boots, the page loads, and the login
loop only appears against a real IAP header, in production, where the prefix exists.

Two checks, deliberately different in cost, following `test_boot.py`:

- A source read, which needs no runtime and so runs in CI's `--only-group dev` job. This is
  the one that actually catches a rebase, because it runs on every push.
- A subprocess import of the real application, which proves the stack is ordered as
  intended rather than merely spelled correctly. Skipped where the runtime is not installed.
"""

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / 'backend'
MAIN_PY = BACKEND_DIR / 'open_webui' / 'main.py'
TRACKED_STATIC_DIR = BACKEND_DIR / 'open_webui' / 'static'

NORMALIZER = 'IapIdentityHeaderMiddleware'
ALLOWLIST = 'AdminAllowlistMiddleware'

REGISTRATIONS = {NORMALIZER: 'jup.iap_identity', ALLOWLIST: 'jup.admin_allowlist'}

# Same probe as `test_jup_portfolio_endpoint.py`. `open_webui/__init__.py` imports typer, so
# `pythonpath = ["backend"]` makes the package findable under `--only-group dev` while
# importing it still fails — probe the dependencies, not the package.
_RUNTIME_MODULES = ('typer', 'uvicorn', 'fastapi', 'alembic')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

_LOST_LINE = (
    'ADR-0012 registers this in `backend/open_webui/main.py`. Losing it on an upstream rebase '
    'is silent: the app boots and the page loads, and the only symptom is that a real IAP '
    'header — `accounts.google.com:erik@axiara.ai` — reaches the vendor auth code with its '
    'provider prefix intact. `utils/auth.py` then compares that against `user.email` on every '
    'request, so signin succeeds and the next request 401s. That reads as a session bug and '
    'nothing points at a prefix. Restore the two `app.add_middleware` lines rather than '
    'patching any vendor auth read site.'
)

_SNAPSHOT_SCRIPT = textwrap.dedent(
    """
    import json

    from open_webui.main import app

    print('STACK ' + json.dumps([m.cls.__name__ for m in app.user_middleware]))
    """
)


@pytest.fixture(scope='module')
def main_module() -> ast.Module:
    """`main.py` parsed, never imported — this check must cost nothing to run."""
    return ast.parse(MAIN_PY.read_text(), filename=str(MAIN_PY))


def _imported_names(tree: ast.Module) -> dict[str, str]:
    """Every `from X import N` at module level, as `{N: X}`."""
    return {
        alias.asname or alias.name: node.module or ''
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def _registered_middleware(tree: ast.Module) -> list[str]:
    """The class names passed to a module-level `app.add_middleware(...)`, in call order.

    Only the first positional argument is read, which is the whole of the ASGI middleware
    registration contract. Nesting is not walked on purpose: a registration inside an `if`
    is a registration that can be skipped, and this file exists to assert it cannot be.
    """
    registered: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != 'add_middleware':
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != 'app':
            continue
        if call.args and isinstance(call.args[0], ast.Name):
            registered.append(call.args[0].id)
    return registered


@pytest.mark.parametrize(('name', 'module'), sorted(REGISTRATIONS.items()))
def test_main_imports_the_middleware_from_the_fork_owned_module(
    main_module: ast.Module, name: str, module: str
) -> None:
    """And from `backend/jup/`, not from a copy pasted into the vendor tree."""
    imports = _imported_names(main_module)

    assert imports.get(name) == module, (
        f'`main.py` does not import {name} from `{module}` (found {imports.get(name)!r}).\n{_LOST_LINE}'
    )


@pytest.mark.parametrize('name', sorted(REGISTRATIONS))
def test_main_registers_the_middleware_unconditionally(main_module: ast.Module, name: str) -> None:
    registered = _registered_middleware(main_module)

    assert name in registered, (
        f'`main.py` has no module-level `app.add_middleware({name})`. It registers: {registered}\n{_LOST_LINE}'
    )


def test_the_normalizer_is_registered_last_so_it_ends_up_outermost(main_module: ast.Module) -> None:
    """Starlette runs the LAST-added middleware outermost, so the order here is inverted.

    This is not cosmetic. `AdminAllowlistMiddleware` reads the identity header to decide
    whose role to settle; putting the normalizer outside it means the allowlist — and every
    vendor read site below it — sees one already-bare address rather than each re-deriving
    it. Swapping these two lines leaves both middlewares installed and working, which is
    exactly why it needs an assertion rather than a reader's attention.
    """
    registered = _registered_middleware(main_module)

    assert registered.index(ALLOWLIST) < registered.index(NORMALIZER), (
        f'{NORMALIZER} must be added AFTER {ALLOWLIST} so it runs outermost. `main.py` registers: {registered}'
    )


def test_no_vendor_auth_read_site_was_patched_as_well() -> None:
    """ADR-0012 chose this shape to leave all three read sites untouched. Belt and braces
    here is not free: a patch added "just to be safe" re-adds the surface the decision
    exists to avoid, and the middleware then hides it until the next rebase drops it."""
    auths = (BACKEND_DIR / 'open_webui' / 'routers' / 'auths.py').read_text()
    auth_utils = (BACKEND_DIR / 'open_webui' / 'utils' / 'auth.py').read_text()

    for label, source in (('routers/auths.py', auths), ('utils/auth.py', auth_utils)):
        assert 'jup.iap_identity' not in source and 'normalize_iap_value' not in source, (
            f'{label} imports the normalizer. ADR-0012 option 3 was chosen precisely so that no '
            'vendor auth read site is patched — the middleware already gives this file a bare '
            'address. Remove the patch; it is the surface the decision exists to avoid.'
        )


@pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`, where the source checks above are the guard. Install the project to run this.'
    ),
)
def test_the_running_application_puts_the_normalizer_outermost(tmp_path: Path) -> None:
    """The source checks prove the lines are there; this proves they took effect.

    Imported in a subprocess for `test_boot.py`'s reasons: importing `open_webui.main` runs
    migrations and pulls in the whole model tree, and a boot failure is often a hard exit
    rather than an exception.
    """
    static = tmp_path / 'static'
    shutil.copytree(TRACKED_STATIC_DIR, static)
    environment = {
        **os.environ,
        'DATABASE_URL': f'sqlite:///{tmp_path / "registration.db"}',
        'DATA_DIR': str(tmp_path / 'data'),
        # config.py unlinks every file in STATIC_DIR at import and swallows the errors.
        'STATIC_DIR': str(static),
        'WEBUI_SECRET_KEY': 'iap-registration',
        'RAG_EMBEDDING_ENGINE': 'ollama',
        'ENABLE_OLLAMA_API': 'false',
        'ENABLE_OPENAI_API': 'false',
        'OFFLINE_MODE': 'true',
        'HF_HUB_OFFLINE': '1',
    }

    completed = subprocess.run(  # noqa: S603
        [sys.executable, '-c', _SNAPSHOT_SCRIPT],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    assert completed.returncode == 0, (
        f'the application did not import (exit {completed.returncode}).\n--- stderr ---\n{completed.stderr[-4000:]}'
    )
    line = next((ln for ln in completed.stdout.splitlines() if ln.startswith('STACK ')), None)
    assert line is not None, f'no middleware stack was reported:\n{completed.stdout[-2000:]}'

    stack = json.loads(line.removeprefix('STACK '))

    assert NORMALIZER in stack, f'{NORMALIZER} is not in the running stack {stack}\n{_LOST_LINE}'
    assert ALLOWLIST in stack, f'{ALLOWLIST} is not in the running stack {stack}\n{_LOST_LINE}'

    # `user_middleware[0]` is the outermost layer — Starlette wraps the list in reverse. The
    # assertions are relational rather than absolute, and that is a considered choice: the
    # vendor registers its session middleware at the very bottom of `main.py`, inside a
    # try/except, so it lands outside these two and *which* session class it is depends on
    # whether Redis resolved. Pinning an absolute index would fail on that alone. It is also
    # harmless — the session layers read a cookie, never `x-goog-authenticated-user-email`.
    # What must hold is that the normalizer is outside everything that reads that header.
    assert stack.index(ALLOWLIST) == stack.index(NORMALIZER) + 1, (
        f'{ALLOWLIST} should sit directly inside {NORMALIZER}; the running stack is {stack}. '
        'Anything wedged between them reads the identity header at whichever position it landed.'
    )
    for inner in ('CORSMiddleware', 'AppHTTPMiddleware'):
        if inner not in stack:
            continue
        assert stack.index(NORMALIZER) < stack.index(inner), (
            f'{NORMALIZER} runs inside {inner}; the running stack is {stack}. Every vendor layer '
            'that touches the request must sit below the normalizer, or it sees the raw prefix.'
        )
