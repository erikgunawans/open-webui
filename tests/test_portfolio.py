"""Behaviour of the portfolio projection: a records directory in, domain objects out.

Every test here drives `project_portfolio` from a fixture directory and asserts on what
comes back. Nothing reaches inside the parser. A test that breaks when the module is
reorganised but the outputs are unchanged is a bad test, so the helpers below deliberately
speak only in projects, gates and refusal messages.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from jup.portfolio import GATES, Portfolio, Project, RecordError, project_portfolio


def _portfolio(fixture_path: Callable[..., Path], scenario: str) -> Portfolio:
    """Project one fixture scenario, asserting it was readable before a test reads it."""
    portfolio = project_portfolio(fixture_path('portfolio', scenario))
    assert portfolio.available, portfolio.unavailable_reason
    return portfolio


def _project(portfolio: Portfolio, identifier: str) -> Project:
    """Pick one project out by id, so a test never depends on positional order."""
    matches = [project for project in portfolio.projects if project.id == identifier]
    assert matches, f'{identifier!r} missing from {[project.id for project in portfolio.projects]}'
    return matches[0]


def _refusal(records_dir: Path) -> str:
    """Project a directory expecting a refusal, and hand back the message it carried."""
    with pytest.raises(RecordError) as refused:
        project_portfolio(records_dir)
    return str(refused.value)


def test_the_gate_ladder_is_the_four_fail_closed_gates_in_order() -> None:
    """The ladder is a closed set; a fifth gate is a record error, not a new rung."""
    assert GATES == ('G1', 'G2', 'G3', 'G4')


def test_a_project_with_no_assessments_has_no_current_gate(fixture_path: Callable[..., Path]) -> None:
    """Zero assessments: nobody has looked, so there is nothing to claim."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    project = _project(portfolio, 'properti-kalibaru-rusun')

    assert project.has_assessments is False
    assert project.current_gate is None


def test_a_single_pass_sets_the_current_gate(fixture_path: Callable[..., Path]) -> None:
    """One passing assessment is the whole basis for a current gate."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    project = _project(portfolio, 'air-marunda-perpipaan')

    assert project.current_gate == 'G1'


def test_a_project_whose_only_assessment_failed_has_no_current_gate(fixture_path: Callable[..., Path]) -> None:
    """A refusal is a record, not progress — the gas pillar's failed G1 stays ungated."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert project.has_assessments is True
    assert project.current_gate is None


def test_never_assessed_is_distinguishable_from_assessed_and_refused(fixture_path: Callable[..., Path]) -> None:
    """The load-bearing distinction: both have no gate, and they do not mean the same thing.

    A board that cannot tell "nobody looked" from "we said no" has lost the record ADR-0003
    exists to keep.
    """
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    never_assessed = _project(portfolio, 'properti-kalibaru-rusun')
    refused = _project(portfolio, 'gas-spbg-reactivation')

    assert never_assessed.current_gate is None
    assert refused.current_gate is None
    assert never_assessed.has_assessments != refused.has_assessments


def test_a_refused_assessment_is_retained_in_full(fixture_path: Callable[..., Path]) -> None:
    """Refusals are never dropped: the verdict, signatory and date all survive projection."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert len(project.assessments) == 1
    refusal = project.assessments[0]
    assert refusal.gate == 'G1'
    assert refusal.verdict == 'fail'
    assert refusal.signed_by == 'Erik Gunawan Supriatna'
    assert refusal.source == 'gas-spbg-reactivation-g1.md'


def test_project_metadata_survives_projection(fixture_path: Callable[..., Path]) -> None:
    """Name and pillar are carried through intact, em-dash and all."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert project.name == 'Gas — SPBG reactivation'
    assert project.pillar == 'gas'


def test_unknown_frontmatter_keys_and_prose_bodies_are_ignored(fixture_path: Callable[..., Path]) -> None:
    """`evidence:` belongs to ticket #4; encountering it early must not break the read."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert project.assessments[0].gate == 'G1'


def test_a_passing_g1_with_a_failing_g2_yields_g1(fixture_path: Callable[..., Path]) -> None:
    """The current gate is the highest gate *passed*, not the highest gate attempted."""
    portfolio = _portfolio(fixture_path, 'gate-ladder')
    project = _project(portfolio, 'air-marunda-perpipaan')

    assert project.current_gate == 'G1'


def test_a_later_refusal_does_not_revoke_an_earlier_pass(fixture_path: Callable[..., Path]) -> None:
    """A pass is durable. G2 passed in March stands even after G2 is refused in June."""
    portfolio = _portfolio(fixture_path, 'gate-ladder')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert project.current_gate == 'G2'


def test_the_current_gate_is_derived_from_several_assessments(fixture_path: Callable[..., Path]) -> None:
    """Every assessment is kept, and the gate is computed over them rather than stored."""
    portfolio = _portfolio(fixture_path, 'gate-ladder')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert len(project.assessments) == 3
    assert project.current_gate == 'G2'


def test_the_current_gate_cannot_be_assigned(fixture_path: Callable[..., Path]) -> None:
    """There is no setter, by construction — a mutable gate is the artefact ADR-0003 bans."""
    portfolio = _portfolio(fixture_path, 'gate-ladder')
    project = _project(portfolio, 'gas-spbg-reactivation')

    with pytest.raises(AttributeError):
        project.current_gate = 'G4'


def test_projects_are_ordered_by_id_not_by_filename(fixture_path: Callable[..., Path]) -> None:
    """The fixture's filenames sort the other way, so only an id sort passes this."""
    portfolio = _portfolio(fixture_path, 'ordering')

    assert tuple(project.id for project in portfolio.projects) == (
        'air-marunda-perpipaan',
        'gas-spbg-reactivation',
    )


def test_assessments_are_ordered_by_gate_then_date_then_source(fixture_path: Callable[..., Path]) -> None:
    """All three sort keys are exercised: two records share a gate and a date."""
    portfolio = _portfolio(fixture_path, 'ordering')
    project = _project(portfolio, 'air-marunda-perpipaan')

    assert tuple(assessment.source for assessment in project.assessments) == (
        'b-g1-same.md',
        'c-g1-same.md',
        'z-g1-early.md',
        'm-g1-late.md',
        'a-g2-later.md',
    )


def test_an_empty_gate_assessments_directory_still_reads_its_projects(
    fixture_path: Callable[..., Path],
) -> None:
    """No assessments recorded yet is a readable portfolio, not an unavailable one."""
    portfolio = _portfolio(fixture_path, 'no-assessments')

    assert len(portfolio.projects) == 1
    assert portfolio.projects[0].has_assessments is False


def test_a_none_records_directory_is_empty_with_a_reason() -> None:
    """An unconfigured path must say so rather than render a confident blank page."""
    portfolio = project_portfolio(None)

    assert portfolio.available is False
    assert portfolio.projects == ()
    assert portfolio.unavailable_reason
    assert 'configured' in portfolio.unavailable_reason


def test_an_absent_records_directory_is_empty_with_a_reason(fixtures_dir: Path) -> None:
    """The reason names the path, so a PMO has something to go and fix."""
    absent = fixtures_dir / 'portfolio' / 'definitely-not-a-records-directory'
    portfolio = project_portfolio(absent)

    assert portfolio.available is False
    assert portfolio.projects == ()
    assert portfolio.unavailable_reason
    assert str(absent) in portfolio.unavailable_reason


def test_a_file_instead_of_a_directory_is_empty_with_a_reason(fixture_path: Callable[..., Path]) -> None:
    """A path that resolves to a file is unavailable, not silently empty."""
    portfolio = project_portfolio(fixture_path('portfolio', 'not-a-directory.md'))

    assert portfolio.available is False
    assert portfolio.projects == ()
    assert portfolio.unavailable_reason
    assert 'file' in portfolio.unavailable_reason


def test_a_missing_projects_subdirectory_is_named_specifically(fixture_path: Callable[..., Path]) -> None:
    """Naming the subdirectory separates "wrong root" from "nothing recorded"."""
    portfolio = project_portfolio(fixture_path('portfolio', 'missing-projects-dir'))

    assert portfolio.available is False
    assert portfolio.unavailable_reason
    assert 'projects/' in portfolio.unavailable_reason


def test_a_missing_gate_assessments_subdirectory_is_named_specifically(
    fixture_path: Callable[..., Path],
) -> None:
    """Same reasoning, and the half-present root must not read as a portfolio with no gates."""
    portfolio = project_portfolio(fixture_path('portfolio', 'missing-assessments-dir'))

    assert portfolio.available is False
    assert portfolio.unavailable_reason
    assert 'gate-assessments/' in portfolio.unavailable_reason


def test_a_record_without_frontmatter_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Prose where a record should be is untrustworthy, not empty."""
    message = _refusal(fixture_path('portfolio', 'malformed-absent-frontmatter'))

    assert 'prose-only.md' in message
    assert 'frontmatter' in message


def test_unterminated_frontmatter_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Without a closing delimiter the prose body would be parsed as fields."""
    message = _refusal(fixture_path('portfolio', 'malformed-unterminated-frontmatter'))

    assert 'runaway.md' in message
    assert 'frontmatter' in message


def test_frontmatter_that_is_not_a_mapping_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A YAML list parses cleanly and still cannot answer "what is this project's id?"."""
    message = _refusal(fixture_path('portfolio', 'malformed-not-a-mapping'))

    assert 'a-list.md' in message
    assert 'frontmatter' in message


def test_invalid_yaml_is_refused_as_a_record_error(fixture_path: Callable[..., Path]) -> None:
    """A parser error surfaces as a named record refusal, not a raw yaml exception."""
    message = _refusal(fixture_path('portfolio', 'malformed-invalid-yaml'))

    assert 'broken.md' in message
    assert 'frontmatter' in message


def test_a_project_without_an_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Nothing can cite a project that never declared what to call it."""
    message = _refusal(fixture_path('portfolio', 'malformed-missing-id'))

    assert 'anonymous.md' in message
    assert 'id' in message


def test_a_project_without_a_name_is_refused(fixture_path: Callable[..., Path]) -> None:
    """An unnamed project would render as a blank row on a board dashboard."""
    message = _refusal(fixture_path('portfolio', 'malformed-missing-name'))

    assert 'no-title.md' in message
    assert 'name' in message


def test_two_projects_claiming_one_id_are_refused(fixture_path: Callable[..., Path]) -> None:
    """Ambiguous provenance must stop the projection rather than pick a winner."""
    message = _refusal(fixture_path('portfolio', 'malformed-duplicate-id'))

    assert 'second-claim.md' in message
    assert 'id' in message


def test_an_assessment_missing_a_signatory_is_refused(fixture_path: Callable[..., Path]) -> None:
    """An unsigned verdict is not a governance record."""
    message = _refusal(fixture_path('portfolio', 'malformed-missing-assessment-field'))

    assert 'unattributed.md' in message
    assert 'signed_by' in message


def test_a_gate_outside_the_ladder_is_refused_and_the_message_lists_the_gates(
    fixture_path: Callable[..., Path],
) -> None:
    """The permitted gates go in the message, because a PMO analyst reads it, not this module."""
    message = _refusal(fixture_path('portfolio', 'malformed-gate'))

    assert 'out-of-ladder.md' in message
    assert 'gate' in message
    for gate in GATES:
        assert gate in message


def test_a_verdict_outside_pass_or_fail_is_refused_and_never_defaulted(
    fixture_path: Callable[..., Path],
) -> None:
    """ "pending" is not a third verdict — quietly treating it as a fail would invent a record."""
    message = _refusal(fixture_path('portfolio', 'malformed-verdict'))

    assert 'unrecognised-outcome.md' in message
    assert 'verdict' in message
    assert 'pass' in message
    assert 'fail' in message


def test_an_assessment_without_a_real_date_is_refused(fixture_path: Callable[..., Path]) -> None:
    """When a gate was passed is half of what the record is for."""
    message = _refusal(fixture_path('portfolio', 'malformed-assessed-on'))

    assert 'undated.md' in message
    assert 'assessed_on' in message


def test_an_assessment_citing_an_unknown_project_is_refused(fixture_path: Callable[..., Path]) -> None:
    """The message names the unknown id, because that id is the thing to go and look for."""
    message = _refusal(fixture_path('portfolio', 'malformed-unknown-project'))

    assert 'orphan.md' in message
    assert 'project' in message
    assert 'air-kanal-banjir' in message


def test_projecting_the_same_directory_twice_gives_the_same_answer(
    fixture_path: Callable[..., Path],
) -> None:
    """Purity, stated as a test: no cache, no clock, no global state between calls."""
    records = fixture_path('portfolio', 'ordering')

    assert project_portfolio(records) == project_portfolio(records)
