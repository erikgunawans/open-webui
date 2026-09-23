"""The `portfolio_status` chat tool: its admin gate, its rendering, and the wrapper stored in the app.

The tool's code is exec'd from the DB where nothing tests it, so everything that matters lives
in `jup.portfolio_tool` and is tested here without a server.
"""

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

from jup.portfolio import OPERATING_LAYER_ROLE, project_portfolio
from jup.portfolio_tool import REFUSAL, portfolio_status, render

TOOL_SOURCE = Path(__file__).resolve().parent.parent / 'tools' / 'portfolio_status.py'


@pytest.mark.parametrize('role', ['user', 'pending', None, ''])
def test_anyone_outside_the_operating_layer_is_refused(role, monkeypatch, fixture_path: Callable[..., Path]):
    monkeypatch.setenv('JUP_RECORDS_DIR', str(fixture_path('portfolio', 'engagements-shared')))
    assert portfolio_status(role) == REFUSAL


def test_the_operating_layer_reads_the_mounted_records(monkeypatch, fixture_path: Callable[..., Path]):
    monkeypatch.setenv('JUP_RECORDS_DIR', str(fixture_path('portfolio', 'engagements-shared')))
    monkeypatch.delenv('JUP_ARTEFACT_ROOT', raising=False)
    text = portfolio_status(OPERATING_LAYER_ROLE)
    assert text.startswith('# JUP portfolio status')
    assert 'gas-spbg-reactivation' in text


def test_an_unconfigured_mount_says_so_rather_than_rendering_nothing(monkeypatch):
    monkeypatch.delenv('JUP_RECORDS_DIR', raising=False)
    assert portfolio_status(OPERATING_LAYER_ROLE).startswith('Portfolio unavailable:')


def test_a_refused_project_is_not_reported_as_passed(fixture_path: Callable[..., Path]):
    portfolio = project_portfolio(fixture_path('portfolio', 'engagements-shared'))
    spbg = next(p for p in portfolio.projects if p.id == 'gas-spbg-reactivation')
    assert spbg.current_gate is None and spbg.has_assessments
    text = render(portfolio, 'spbg')
    assert 'has not passed G1 (assessed and refused)' in text
    assert 'Blocking requirements' in text


def test_the_filter_narrows_projects_and_engagements(fixture_path: Callable[..., Path]):
    portfolio = project_portfolio(fixture_path('portfolio', 'engagements-shared'))
    whole = render(portfolio)
    narrowed = render(portfolio, 'spbg')
    assert all(p.id in whole for p in portfolio.projects)
    assert 'gas-cng-transport' not in narrowed


def test_an_unknown_project_lists_what_exists(fixture_path: Callable[..., Path]):
    portfolio = project_portfolio(fixture_path('portfolio', 'engagements-shared'))
    text = render(portfolio, 'no-such-project')
    assert text.startswith("No project matches 'no-such-project'")
    assert 'gas-spbg-reactivation' in text


def test_non_coverage_travels_with_every_answer(fixture_path: Callable[..., Path]):
    portfolio = project_portfolio(fixture_path('portfolio', 'engagements-shared'))
    text = render(portfolio, 'spbg')
    for statement in portfolio.non_coverage:
        assert statement in text


def test_figures_carry_their_tier_and_are_never_totalled(fixture_path: Callable[..., Path]):
    portfolio = project_portfolio(fixture_path('portfolio', 'figures'))
    text = render(portfolio)
    for project in portfolio.projects:
        for group in project.figures_by_tier:
            for figure in group.figures:
                assert f'{figure.value} ({group.label}; basis: {figure.basis})' in text
    labels = ('Tier 1 · FAKTA', 'Tier 2 · POTENSI', 'Tier 3 · ILUSTRATIF')
    for line in text.splitlines():
        assert sum(label in line for label in labels) <= 1, f'two tiers on one line: {line}'


def test_the_stored_wrapper_holds_no_logic_of_its_own():
    """The DB copy is exec'd untested, so it may only delegate. A rule added there escapes CI."""
    tree = ast.parse(TOOL_SOURCE.read_text())
    tools = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Tools')
    methods = [n for n in tools.body if isinstance(n, ast.FunctionDef)]
    assert [m.name for m in methods] == ['portfolio_status']
    body = [n for n in methods[0].body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert len(body) == 1 and isinstance(body[0], ast.Return)
    assert '_portfolio_status(' in ast.unparse(body[0])
