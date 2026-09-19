"""The HTTP seam: authentication, the operating-layer permission, and the payload.

#1's Testing Decisions name this seam and call it thin: *"cover authentication, the
permission gate, and that the payload round-trips the projection."* Domain rules are not
re-tested here — `test_portfolio.py` covers them a hundred times over against the pure
function, which is where they belong.

Identity is the only thing faked. `get_current_user` is overridden to hand back an account
with a given role, so the **real** `get_verified_user` and the **real**
`get_operating_layer_user` run on every request. Overriding the permission dependency itself
would test the override.

This file needs the vendor runtime, so it skips under CI's `--only-group dev` job. The
`boot` job runs it. Importing the router pulls `open_webui.config`, which wipes `STATIC_DIR`
at import — `tests/conftest.py` redirects that before pytest imports this module.
"""

import importlib.util
import os
import re
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

_RUNTIME_MODULES = ('fastapi', 'httpx', 'jwt')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)

pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=(
        f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under '
        '`--only-group dev`. The projection itself is covered without a server in test_portfolio.py.'
    ),
)

# Every path a record can cite, so a fixture tree copied into tmp_path can have the cited
# documents created beside it. Artefact resolution is on by default at this seam, and a
# citation that does not resolve is refused — correctly, and unhelpfully for a fixture.
_CITATION = re.compile(r'^\s*(?:-\s*)?(?:artefact|basis):\s*(.+?)\s*$', re.MULTILINE)


@dataclass(frozen=True)
class _Account:
    """The smallest thing the dependency chain reads off a user: its role."""

    role: str
    id: str = 'test-user'


@pytest.fixture
def jup_tree(fixtures_dir: Path, tmp_path: Path) -> Path:
    """A writable JUP tree: the shared-engagements fixture plus every document it cites."""
    root = tmp_path / 'jup'
    shutil.copytree(fixtures_dir / 'portfolio' / 'engagements-shared', root / 'records')
    for record in (root / 'records').rglob('*.md'):
        for citation in _CITATION.findall(record.read_text(encoding='utf-8')):
            cited = root / citation.strip('\'"')
            cited.parent.mkdir(parents=True, exist_ok=True)
            cited.touch()
    return root


@pytest.fixture
def client(jup_tree: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """A bare app carrying only the portfolio router, pointed at the fixture tree.

    Bare rather than `open_webui.main.app`: importing that runs migrations and builds the
    whole route table, which would make a seam test into a boot test — and the boot test
    already exists.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from open_webui.routers import jup_portfolio

    monkeypatch.setenv('JUP_RECORDS_DIR', str(jup_tree / 'records'))
    monkeypatch.setenv('JUP_ARTEFACT_ROOT', str(jup_tree))

    app = FastAPI()
    app.include_router(jup_portfolio.router, prefix='/api/v1/portfolio')
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client


def _sign_in_as(client, role: str | None) -> None:
    """Present the dependency chain with an account of `role`, or with nobody at all."""
    from fastapi import HTTPException, status

    from open_webui.utils.auth import get_current_user

    def _current_user():
        if role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
        return _Account(role=role)

    client.app.dependency_overrides[get_current_user] = _current_user


# --- Authentication and the permission gate -----------------------------------------


def test_signed_out_is_refused(client) -> None:
    _sign_in_as(client, None)

    assert client.get('/api/v1/portfolio/').status_code == 401


def test_a_pending_account_is_refused(client) -> None:
    """`pending` is the role a new account holds before an admin approves it."""
    _sign_in_as(client, 'pending')

    assert client.get('/api/v1/portfolio/').status_code == 401


def test_a_verified_member_outside_the_operating_layer_is_refused(client) -> None:
    """The gap #10 exists to close: `user` passes `get_verified_user` and reads everything.

    ADR-0001 puts up to fifty seats in this workspace. Gate refusals, blocking requirements
    and every counterparty's rung are not a fifty-seat surface.
    """
    _sign_in_as(client, 'user')

    assert client.get('/api/v1/portfolio/').status_code == 403


def test_the_refusal_is_distinguishable_from_being_signed_out(client) -> None:
    """403, not 401 — otherwise the frontend bounces a signed-in member to a sign-in page.

    The vendor's own `get_admin_user` answers 401 here, which is why the fork has its own
    dependency. This test is what stops someone "simplifying" it back.
    """
    _sign_in_as(client, None)
    signed_out = client.get('/api/v1/portfolio/')
    _sign_in_as(client, 'user')
    without_permission = client.get('/api/v1/portfolio/')

    assert signed_out.status_code != without_permission.status_code
    assert 'operating layer' in without_permission.json()['detail']


def test_the_operating_layer_is_served(client) -> None:
    _sign_in_as(client, 'admin')

    assert client.get('/api/v1/portfolio/').status_code == 200


# --- Forced failure -----------------------------------------------------------------


def test_removing_the_permission_lets_an_ordinary_member_through(client) -> None:
    """Prove the refusal is the dependency's doing and not an accident of the fixture.

    A permission test that would pass with the permission removed is the `clean != safe`
    failure in miniature: green, and guarding nothing. Overriding the dependency to a
    pass-through is the same edit as deleting it from the signature.
    """
    from open_webui.routers.jup_portfolio import get_operating_layer_user

    _sign_in_as(client, 'user')
    assert client.get('/api/v1/portfolio/').status_code == 403

    client.app.dependency_overrides[get_operating_layer_user] = lambda: _Account(role='user')

    assert client.get('/api/v1/portfolio/').status_code == 200


# --- The payload --------------------------------------------------------------------


def test_the_payload_round_trips_the_projection(client, jup_tree: Path) -> None:
    """The endpoint serialises the same projection the pure function produces, unchanged."""
    from jup.portfolio import project_portfolio

    _sign_in_as(client, 'admin')
    payload = client.get('/api/v1/portfolio/').json()
    expected = project_portfolio(jup_tree / 'records', jup_tree)

    assert [project['id'] for project in payload['projects']] == [project.id for project in expected.projects]
    assert [project['current_gate'] for project in payload['projects']] == [
        project.current_gate for project in expected.projects
    ]
    assert [engagement['id'] for engagement in payload['engagements']] == [
        engagement.id for engagement in expected.engagements
    ]
    assert payload['non_coverage'] == list(expected.non_coverage)
    assert payload['engagement_non_coverage'] == list(expected.engagement_non_coverage)
    assert payload['unavailable_reason'] is None


def test_one_engagement_record_serves_every_gate_that_cites_it(client) -> None:
    """ADR-0008 at the wire: the counterparty's stage crosses the seam exactly once."""
    _sign_in_as(client, 'admin')

    payload = client.get('/api/v1/portfolio/').json()

    shared = [engagement for engagement in payload['engagements'] if engagement['id'] == 'skk-migas-pgn-allocation']
    assert len(shared) == 1
    citing = [
        project['id']
        for project in payload['projects']
        if 'skk-migas-pgn-allocation' in project['awaiting_engagements']
    ]
    assert len(citing) > 1, 'the fixture is meant to have two projects awaiting one engagement'


def test_no_response_field_carries_a_likelihood(client) -> None:
    """ADR-0009 is a property of the schema, so it is asserted against the wire format."""
    _sign_in_as(client, 'admin')

    body = client.get('/api/v1/portfolio/').text.lower()

    for banned in ('likelihood', 'probability', 'confidence', 'expected_close', 'close_date'):
        assert banned not in body


# --- Configuration and failure ------------------------------------------------------


def test_an_unreadable_record_is_a_500_naming_the_file_and_field(
    client, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never an empty 200. A gate that cannot verify its records must stop, and say why."""
    monkeypatch.setenv('JUP_RECORDS_DIR', str(fixtures_dir / 'portfolio' / 'malformed-missing-verdict'))
    monkeypatch.delenv('JUP_ARTEFACT_ROOT', raising=False)
    _sign_in_as(client, 'admin')

    response = client.get('/api/v1/portfolio/')

    assert response.status_code == 500
    detail = response.json()['detail']
    assert 'unresolved.md' in detail
    assert 'verdict' in detail


def test_configuration_is_read_per_request_not_at_import(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """The change #10 needed before the seam could be tested at all.

    Read at module import, `JUP_RECORDS_DIR` could not be pointed anywhere without
    reimporting the router — which is why this endpoint had no tests. The same property is
    what lets a restarted container pick up a new mount without a rebuild.
    """
    _sign_in_as(client, 'admin')
    assert client.get('/api/v1/portfolio/').json()['projects']

    monkeypatch.delenv('JUP_RECORDS_DIR')

    payload = client.get('/api/v1/portfolio/').json()
    assert payload['projects'] == []
    assert 'No records directory is configured' in payload['unavailable_reason']


def test_an_absent_records_directory_is_reasoned_rather_than_blank(
    client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A misconfiguration must look like one, not like a portfolio with nothing in it."""
    monkeypatch.setenv('JUP_RECORDS_DIR', str(tmp_path / 'not-mounted'))
    _sign_in_as(client, 'admin')

    payload = client.get('/api/v1/portfolio/').json()

    assert payload['projects'] == []
    assert 'not-mounted' in payload['unavailable_reason']


def test_the_artefact_root_defaults_to_the_records_parent(client, jup_tree: Path, monkeypatch) -> None:
    """Unset, citations are still checked — against the tree the records live in."""
    from open_webui.routers.jup_portfolio import _artefact_root

    monkeypatch.delenv('JUP_ARTEFACT_ROOT')

    assert _artefact_root(jup_tree / 'records') == jup_tree
    assert _artefact_root(None) is None
    assert client.get('/api/v1/portfolio/') is not None


def test_os_environ_is_not_read_at_module_scope() -> None:
    """The regression guard for the shape, not just the behaviour.

    A module-level `os.environ.get` is the specific thing that made this endpoint
    untestable. Asserting on the source is crude, and it is the only assertion that fails
    when someone reintroduces the constant beside the function rather than in place of it.
    """
    from open_webui.routers import jup_portfolio

    source = Path(jup_portfolio.__file__).read_text(encoding='utf-8')
    module_level = [
        line for line in source.splitlines() if line.startswith(('JUP_', 'RECORDS_')) and 'os.environ' in line
    ]

    assert not module_level, f'configuration is read at import again: {module_level}'
    assert 'os.environ' in source, 'the guard above would pass vacuously if nothing read the environment'


def test_the_operating_layer_role_is_one_line_to_change() -> None:
    """The governance call lives in a named constant, not scattered as a literal."""
    from open_webui.routers.jup_portfolio import OPERATING_LAYER_ROLE

    assert OPERATING_LAYER_ROLE == 'admin'
    assert os.environ.get('JUP_OPERATING_LAYER_ROLE') is None, (
        'if this becomes configurable, the refusal tests above must cover the configured value'
    )
