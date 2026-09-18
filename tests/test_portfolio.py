"""Behaviour of the portfolio projection: a records directory in, domain objects out.

Every test here drives `project_portfolio` from a fixture directory and asserts on what
comes back. Nothing reaches inside the parser. A test that breaks when the module is
reorganised but the outputs are unchanged is a bad test, so the helpers below deliberately
speak only in projects, gates and refusal messages.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from jup.portfolio import (
    GATES,
    STAGE_LABELS,
    STAGES,
    TIER_LABELS,
    TIER_MEANINGS,
    TIERS,
    Engagement,
    Portfolio,
    Project,
    RecordError,
    project_portfolio,
)


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


def _engagement(portfolio: Portfolio, identifier: str) -> Engagement:
    """Pick one engagement out by id, so a test never depends on positional order."""
    matches = [item for item in portfolio.engagements if item.id == identifier]
    assert matches, f'{identifier!r} missing from {[item.id for item in portfolio.engagements]}'
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
    """A prose body and a key the projection does not model must not break the read."""
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


def test_an_assessment_carries_the_evidence_it_required(fixture_path: Callable[..., Path]) -> None:
    """Each requirement survives projection with its satisfied flag and its citation."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    refusal = _project(portfolio, 'gas-spbg-reactivation').assessments[0]

    assert tuple((item.requirement, item.satisfied) for item in refusal.evidence) == (
        ('gas-allocation-5mmscfd', False),
        ('rued-alignment-test', True),
    )


def test_an_evidence_item_carries_the_citation_it_was_recorded_with(
    fixture_path: Callable[..., Path],
) -> None:
    """An Engagement is held as an id and an artefact as a path — never interchanged."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    allocation, rued = _project(portfolio, 'gas-spbg-reactivation').assessments[0].evidence

    assert allocation.engagement == 'skk-migas-pgn-allocation'
    assert allocation.artefact is None
    assert rued.artefact == 'deliverables/policy/JUP-RUED-Alignment-Brief.html'
    assert rued.engagement is None


def test_an_assessment_names_only_its_unsatisfied_requirements(fixture_path: Callable[..., Path]) -> None:
    """ "What is blocking this" is read off the record rather than reconstructed."""
    portfolio = _portfolio(fixture_path, 'portfolio-basic')
    refusal = _project(portfolio, 'gas-spbg-reactivation').assessments[0]

    assert tuple(item.requirement for item in refusal.unsatisfied) == ('gas-allocation-5mmscfd',)


def test_an_assessment_with_no_evidence_key_records_no_requirements(
    fixture_path: Callable[..., Path],
) -> None:
    """Absent evidence means none were stated — not that none were met."""
    portfolio = _portfolio(fixture_path, 'evidence')
    assessment = _project(portfolio, 'properti-kalibaru-rusun').assessments[0]

    assert assessment.evidence == ()
    assert assessment.unsatisfied == ()


def test_a_project_refused_twice_on_one_requirement_names_it_once(
    fixture_path: Callable[..., Path],
) -> None:
    """The anecdote ADR-0003 wants to retire becomes one named blocker, not three."""
    portfolio = _portfolio(fixture_path, 'evidence')
    project = _project(portfolio, 'gas-spbg-reactivation')

    assert tuple(item.requirement for item in project.blocking_requirements) == (
        'gas-allocation-5mmscfd',
        'offtake-letter',
    )


def test_a_requirement_waived_by_a_passing_verdict_is_not_a_blocker(
    fixture_path: Callable[..., Path],
) -> None:
    """A board that passed a gate with a requirement outstanding made a decision.

    Calling that a blocker would have the dashboard overrule a decision that was taken and
    signed, which is the mirror image of the failure this projection exists to prevent.
    """
    portfolio = _portfolio(fixture_path, 'evidence')
    project = _project(portfolio, 'air-marunda-perpipaan')

    assert tuple(item.requirement for item in project.assessments[0].unsatisfied) == ('tariff-confirmation',)
    assert project.blocking_requirements == ()


def test_a_project_with_no_unmet_requirements_has_no_blockers(fixture_path: Callable[..., Path]) -> None:
    """A refusal that states no requirements yields no blockers rather than a fabricated one."""
    portfolio = _portfolio(fixture_path, 'evidence')

    assert _project(portfolio, 'properti-kalibaru-rusun').blocking_requirements == ()


def test_an_evidence_item_citing_neither_an_artefact_nor_an_engagement_is_refused(
    fixture_path: Callable[..., Path],
) -> None:
    """A requirement nothing is cited against is an assertion, and assertions are refused."""
    message = _refusal(fixture_path('portfolio', 'malformed-evidence-uncited'))

    assert 'uncited.md' in message
    assert 'gas-allocation-5mmscfd' in message
    assert 'artefact' in message
    assert 'engagement' in message


def test_an_evidence_item_without_a_requirement_is_refused(fixture_path: Callable[..., Path]) -> None:
    """The refusal names the entry's position, because the missing field is its name."""
    message = _refusal(fixture_path('portfolio', 'malformed-evidence-no-requirement'))

    assert 'unnamed-requirement.md' in message
    assert 'evidence[1].requirement' in message


def test_evidence_recorded_as_bare_paths_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A list of filed documents never says what was required, so it cannot be checked."""
    message = _refusal(fixture_path('portfolio', 'malformed-evidence-bare-strings'))

    assert 'bare-strings.md' in message
    assert 'evidence[1]' in message


def test_evidence_that_is_not_a_list_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Prose where requirements belong is the case where guessing would be worst."""
    message = _refusal(fixture_path('portfolio', 'malformed-evidence-not-a-list'))

    assert 'prose-evidence.md' in message
    assert 'evidence' in message


def test_an_evidence_item_that_does_not_say_whether_it_was_satisfied_is_refused(
    fixture_path: Callable[..., Path],
) -> None:
    """Both defaults invent a claim: one manufactures evidence, the other a blocker."""
    message = _refusal(fixture_path('portfolio', 'malformed-evidence-unstated'))

    assert 'unstated.md' in message
    assert 'evidence[1].satisfied' in message


def test_a_hedged_satisfied_flag_is_refused(fixture_path: Callable[..., Path]) -> None:
    """ "Partially" is the hedge a gate exists to refuse — there is no third state."""
    message = _refusal(fixture_path('portfolio', 'malformed-evidence-satisfied-not-a-bool'))

    assert 'hedged.md' in message
    assert 'evidence[1].satisfied' in message
    assert 'partially' in message


def test_an_assessment_with_no_verdict_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Signed, dated, and never saying what was decided is not a governance record."""
    message = _refusal(fixture_path('portfolio', 'malformed-missing-verdict'))

    assert 'unresolved.md' in message
    assert 'verdict' in message


def test_an_engagement_record_carries_its_stage_and_evidencing_artefact(
    fixture_path: Callable[..., Path],
) -> None:
    """Who, what for, which rung, and the document the rung stands on (ADR-0008)."""
    portfolio = _portfolio(fixture_path, 'engagements-shared')
    allocation = _engagement(portfolio, 'skk-migas-pgn-allocation')

    assert allocation.counterparty == ('SKK Migas', 'PGN/Pertagas')
    assert allocation.pillar == 'gas'
    assert allocation.purpose == 'The 5 mmscfd allocation — Gate #1 of the gas pillar'
    assert allocation.stage == 'contacted'
    assert allocation.artefact == 'SOURCES/Analisa-Bisnis-Gas-BUMD.pdf'


def test_a_single_counterparty_may_be_a_bare_string(fixture_path: Callable[..., Path]) -> None:
    """The common case should not have to be written as a one-item list."""
    portfolio = _portfolio(fixture_path, 'engagements-shared')

    assert _engagement(portfolio, 'kemenperin-rued').counterparty == ('Kemenperin',)


def test_an_engagement_may_span_pillars_by_naming_none(fixture_path: Callable[..., Path]) -> None:
    """`pillar` is optional — an engagement that spans pillars should not have to pick one."""
    portfolio = _portfolio(fixture_path, 'engagements-shared')

    assert _engagement(portfolio, 'kemenperin-rued').pillar is None


def test_the_stage_ladder_is_the_five_rungs_in_order() -> None:
    """A closed set, lowest rung first. `no-contact` is a position, not an absence."""
    assert STAGES == ('no-contact', 'contacted', 'in-discussion', 'written-intent', 'executed')


def test_every_rung_has_a_label_for_a_reader() -> None:
    """The record holds the slug, so renaming a label never becomes a data migration."""
    assert tuple(STAGE_LABELS[stage] for stage in STAGES) == (
        'No contact',
        'Contacted',
        'In discussion',
        'Written intent',
        'Executed',
    )


def test_one_engagement_cited_by_two_projects_resolves_to_a_single_record(
    fixture_path: Callable[..., Path],
) -> None:
    """The load-bearing ADR-0008 property: one record, however many gates cite it.

    Two copies is how a counterparty's stage ends up current in one place and stale in
    another, which is the failure the citation model exists to make impossible.
    """
    portfolio = _portfolio(fixture_path, 'engagements-shared')
    matches = [item for item in portfolio.engagements if item.id == 'skk-migas-pgn-allocation']

    assert len(matches) == 1
    assert _project(portfolio, 'gas-spbg-reactivation').awaiting_engagements == ('skk-migas-pgn-allocation',)
    assert _project(portfolio, 'gas-cng-transport').awaiting_engagements == ('skk-migas-pgn-allocation',)


def test_a_gate_names_the_engagements_it_waits_on(fixture_path: Callable[..., Path]) -> None:
    """Only the unsatisfied citations. A satisfied one is provenance, not a wait."""
    portfolio = _portfolio(fixture_path, 'engagements-shared')
    assessment = _project(portfolio, 'gas-spbg-reactivation').assessments[0]

    assert assessment.awaiting_engagements == ('skk-migas-pgn-allocation',)
    assert 'kemenperin-rued' not in assessment.awaiting_engagements


def test_engagements_are_ordered_by_id(fixture_path: Callable[..., Path]) -> None:
    """Ordered so the projection never varies with how the filesystem lists files."""
    portfolio = _portfolio(fixture_path, 'engagements-shared')

    assert tuple(item.id for item in portfolio.engagements) == (
        'kemenperin-rued',
        'skk-migas-pgn-allocation',
    )


def test_a_citation_to_an_unknown_engagement_is_refused(fixture_path: Callable[..., Path]) -> None:
    """The message names the id, because that id is the thing to go and look for."""
    message = _refusal(fixture_path('portfolio', 'malformed-engagement-unknown-citation'))

    assert 'orphan-citation.md' in message
    assert 'pgn-allocation-typo' in message


def test_a_citation_with_no_engagements_directory_says_so_specifically(
    fixture_path: Callable[..., Path],
) -> None:
    """A missing record and a missing directory send an operator to different places.

    One is a record to write; the other is a mount to fix. Reporting both as "no engagement
    record" would send someone hunting for a file in a directory that is not there.
    """
    message = _refusal(fixture_path('portfolio', 'malformed-engagement-no-directory'))

    assert 'uncitable.md' in message
    assert 'engagements/' in message


def test_a_stage_outside_the_ladder_is_refused_and_the_message_lists_the_rungs(
    fixture_path: Callable[..., Path],
) -> None:
    """ "Follow-up" is the retired vocabulary — a tone, not a rung (ADR-0008)."""
    message = _refusal(fixture_path('portfolio', 'malformed-engagement-stage'))

    assert 'loose-vocabulary.md' in message
    assert 'stage' in message
    for stage in STAGES:
        assert stage in message


def test_an_engagement_without_an_evidencing_artefact_is_refused(
    fixture_path: Callable[..., Path],
) -> None:
    """Each rung requires a document. Written intent with no LOI is a claim, not a record."""
    message = _refusal(fixture_path('portfolio', 'malformed-engagement-missing-artefact'))

    assert 'unevidenced.md' in message
    assert 'artefact' in message


def test_two_engagements_claiming_one_id_are_refused(fixture_path: Callable[..., Path]) -> None:
    """Ambiguous provenance must stop the projection rather than pick a winner."""
    message = _refusal(fixture_path('portfolio', 'malformed-engagement-duplicate-id'))

    assert 'b-second-claim.md' in message
    assert 'id' in message


def test_a_likelihood_field_on_an_engagement_is_refused(fixture_path: Callable[..., Path]) -> None:
    """ADR-0009 enforced by the parser, not by a review comment."""
    message = _refusal(fixture_path('portfolio', 'malformed-likelihood-engagement'))

    assert 'forecast.md' in message
    assert 'likelihood' in message


def test_a_forecast_field_nested_inside_an_evidence_item_is_refused(
    fixture_path: Callable[..., Path],
) -> None:
    """The ban reaches any depth — an evidence item is a mapping inside a list."""
    message = _refusal(fixture_path('portfolio', 'malformed-likelihood-nested'))

    assert 'nested-forecast.md' in message
    assert 'win_probability' in message


def test_a_hyphenated_forecast_key_on_a_project_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Every record type, and hyphen or underscore reads the same."""
    message = _refusal(fixture_path('portfolio', 'malformed-likelihood-project'))

    assert 'forecast.md' in message
    assert 'expected-close' in message


def test_a_forecast_key_is_refused_rather_than_quietly_dropped(fixture_path: Callable[..., Path]) -> None:
    """The distinction ADR-0009 turns on.

    Ignoring the key would let a record carry a forecast the dashboard merely declined to
    show, and its author would believe it had been recorded. Refusing is the only outcome
    that tells them it has no home here.
    """
    with pytest.raises(RecordError):
        project_portfolio(fixture_path('portfolio', 'malformed-likelihood-engagement'))


def test_certainty_is_not_mistaken_for_a_forecast_field(fixture_path: Callable[..., Path]) -> None:
    """Certainty Tier (D11) is the legitimate concept, and the ban must not catch it.

    Banning `certainty` alongside `confidence` would refuse the very field that keeps FAKTA
    and POTENSI apart — the opposite of what ADR-0009 is for.
    """
    portfolio = _portfolio(fixture_path, 'certainty-tier')

    assert _engagement(portfolio, 'skk-migas-pgn-allocation').stage == 'contacted'


def test_a_purpose_containing_a_hash_survives_when_quoted(fixture_path: Callable[..., Path]) -> None:
    """The trap that silently truncates the most likely purpose JUP will ever write.

    In YAML a bare ` #` starts a comment, so `purpose: The 5 mmscfd allocation — Gate #1 of
    the gas pillar` parses as `...— Gate` and the rest is gone. Nothing raises: the parser
    receives a shorter string that is perfectly valid, so no guard in this module can catch
    it. Quoting is the only fix, and the spec's own worked example is written unquoted.

    Pinned as a test because "Gate #1" is the exact phrase the first real records use.
    """
    portfolio = _portfolio(fixture_path, 'engagements-shared')

    assert _engagement(portfolio, 'skk-migas-pgn-allocation').purpose.endswith('Gate #1 of the gas pillar')


def test_the_three_certainty_tiers_are_ordered_strongest_basis_first() -> None:
    """A closed set. A fourth tier is a record error, not a new kind of evidence."""
    assert TIERS == ('FAKTA', 'POTENSI', 'ILUSTRATIF')


def test_every_tier_carries_its_ordinal_and_its_meaning() -> None:
    """D11 writes the ordinal alongside the name, and a board member reads the meaning."""
    assert TIER_LABELS['POTENSI'] == 'Tier 2 · POTENSI'
    assert 'Never margin' in TIER_MEANINGS['POTENSI']


def test_a_figure_carries_the_basis_it_rests_on(fixture_path: Callable[..., Path]) -> None:
    """Value and basis travel together — a figure is never surfaced without its source."""
    portfolio = _portfolio(fixture_path, 'figures')
    figures = _project(portfolio, 'gas-spbg-reactivation').figures

    npv = next(figure for figure in figures if figure.label == 'NPV at 12%')
    assert npv.tier == 'FAKTA'
    assert npv.value == 'IDR 412 bn'
    assert npv.basis == 'deliverables/feasibility/SPBG-Feasibility-v3.xlsx'


def test_figures_are_grouped_by_tier_and_never_returned_as_one_list(
    fixture_path: Callable[..., Path],
) -> None:
    """The structural half of D11: a caller is handed groups, each with exactly one tier.

    A flat list is an invitation to render a feasibility NPV beside a top-line revenue
    potential as though they were comparable, which is the misreading the tiers exist to
    prevent. Grouping makes composing two tiers into one statement something a renderer has
    to go out of its way to do.
    """
    portfolio = _portfolio(fixture_path, 'figures')
    groups = _project(portfolio, 'gas-spbg-reactivation').figures_by_tier

    assert tuple(group.tier for group in groups) == ('FAKTA', 'POTENSI', 'ILUSTRATIF')
    for group in groups:
        assert {figure.tier for figure in group.figures} == {group.tier}


def test_only_tiers_with_figures_appear_as_groups(fixture_path: Callable[..., Path]) -> None:
    """An empty group would imply a basis nobody claimed."""
    portfolio = _portfolio(fixture_path, 'figures-potensi-legitimate')
    groups = _project(portfolio, 'gas-spbg-reactivation').figures_by_tier

    assert tuple(group.tier for group in groups) == ('POTENSI',)


def test_a_project_may_surface_no_figures_at_all(fixture_path: Callable[..., Path]) -> None:
    """The correct default. A dashboard with no numbers proves less, and is honest."""
    portfolio = _portfolio(fixture_path, 'figures')
    project = _project(portfolio, 'air-marunda-perpipaan')

    assert project.figures == ()
    assert project.figures_by_tier == ()


def test_there_is_no_total_or_blended_figure_anywhere(fixture_path: Callable[..., Path]) -> None:
    """D11 enforced by absence: there is nothing to reach for that crosses tiers.

    A `total` property would be used, and the only sum this system must never compute is
    one that spans two bases. The value is kept as written text for the same reason — a
    parsed number is a number something eventually adds up.
    """
    portfolio = _portfolio(fixture_path, 'figures')
    project = _project(portfolio, 'gas-spbg-reactivation')

    for forbidden in ('total', 'sum', 'combined', 'blended', 'aggregate'):
        assert not hasattr(project, forbidden)
        assert not hasattr(project.figures_by_tier[0], forbidden)
    assert isinstance(project.figures[0].value, str)


def test_a_potensi_figure_labelled_as_margin_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A revenue potential dressed as money the company would keep (D11)."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-potensi-margin'))

    assert 'revenue-as-profit.md' in message
    assert 'margin' in message
    assert 'POTENSI' in message


def test_a_potensi_figure_labelled_as_npv_is_refused(fixture_path: Callable[..., Path]) -> None:
    """NPV is feasibility economics — FAKTA's territory, never POTENSI's."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-potensi-npv'))

    assert 'revenue-as-npv.md' in message
    assert 'npv' in message.lower()


def test_a_potensi_figure_labelled_as_profit_in_bahasa_is_refused(
    fixture_path: Callable[..., Path],
) -> None:
    """These records are written by people who work in Bahasa; `laba` is `profit`."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-potensi-bahasa'))

    assert 'revenue-as-laba.md' in message
    assert 'laba' in message


def test_a_legitimate_potensi_label_containing_a_banned_word_is_not_refused(
    fixture_path: Callable[..., Path],
) -> None:
    """ "Marginal" is not "margin" — the ban matches whole words.

    A false refusal blocks a PMO analyst from recording a true figure, which is a worse
    failure than the narrower ban missing an exotic synonym.
    """
    portfolio = _portfolio(fixture_path, 'figures-potensi-legitimate')
    figure = _project(portfolio, 'gas-spbg-reactivation').figures[0]

    assert figure.label == 'Marginal volume above the RUED floor'
    assert figure.tier == 'POTENSI'


def test_an_npv_labelled_figure_on_the_fakta_tier_is_accepted(fixture_path: Callable[..., Path]) -> None:
    """The ban is POTENSI-only. NPV is exactly what FAKTA is for."""
    portfolio = _portfolio(fixture_path, 'figures')
    figures = _project(portfolio, 'gas-spbg-reactivation').figures

    assert any(figure.label == 'NPV at 12%' and figure.tier == 'FAKTA' for figure in figures)


def test_a_tier_outside_the_three_is_refused_and_the_message_lists_them(
    fixture_path: Callable[..., Path],
) -> None:
    """A fourth basis is not a new kind of evidence, it is an unstated one."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-tier'))

    assert 'untiered.md' in message
    for tier in TIERS:
        assert tier in message


def test_a_figure_without_a_tier_is_refused(fixture_path: Callable[..., Path]) -> None:
    """An untiered figure is the blend D11 prohibits, waiting to happen."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-no-tier'))

    assert 'no-basis-stated.md' in message
    assert 'tier' in message


def test_a_figure_without_a_basis_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A figure whose source cannot be opened is an assertion."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-no-basis'))

    assert 'unsourced.md' in message
    assert 'basis' in message


def test_a_figure_without_a_value_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A labelled, sourced, tiered blank is not a figure."""
    message = _refusal(fixture_path('portfolio', 'malformed-figure-no-value'))

    assert 'valueless.md' in message
    assert 'value' in message


def test_the_portfolio_view_states_what_it_does_not_prove(fixture_path: Callable[..., Path]) -> None:
    """Named Non-Coverage, published beside the view rather than left to a reader."""
    portfolio = _portfolio(fixture_path, 'figures')

    assert len(portfolio.non_coverage) >= 3
    joined = ' '.join(portfolio.non_coverage).lower()
    assert 'well-formed and wrong' in joined
    assert 'has not passed' in joined


def test_the_engagements_view_states_its_own_non_coverage(fixture_path: Callable[..., Path]) -> None:
    """A separate view makes a separate claim, so it names its own limits (ADR-0009)."""
    portfolio = _portfolio(fixture_path, 'figures')

    assert portfolio.engagement_non_coverage
    assert 'never' in ' '.join(portfolio.engagement_non_coverage).lower()


def test_non_coverage_is_present_even_when_the_records_are_unavailable() -> None:
    """A view that could not load still states what it does not prove.

    The empty state is exactly where a reader is most likely to fill the silence with an
    assumption, so it is the last place non-coverage should disappear.
    """
    portfolio = project_portfolio(None)

    assert portfolio.available is False
    assert portfolio.non_coverage


def test_an_unreadable_records_directory_is_empty_with_a_distinguishable_reason(
    tmp_path: Path,
) -> None:
    """Unreadable and absent are different problems, and must not read alike.

    Absent means nobody mounted it; unreadable means it is there and the process cannot
    open it — a permissions fix, not a deployment one. Both must beat a blank page, and a
    reader must be able to tell which they are looking at.

    Skipped when the chmod does not actually bite, which is the case for root.
    """
    records = tmp_path / 'records'
    (records / 'projects').mkdir(parents=True)
    (records / 'gate-assessments').mkdir()
    (records / 'projects' / 'a.md').write_text('---\nid: a\nname: A\n---\n', encoding='utf-8')

    records.chmod(0o000)
    try:
        if os.access(records, os.R_OK):
            pytest.skip('this process can read a 0o000 directory, so the case cannot be exercised')
        portfolio = project_portfolio(records)
    finally:
        records.chmod(0o755)

    assert portfolio.available is False
    assert portfolio.projects == ()
    assert portfolio.unavailable_reason
    assert 'could not be read' in portfolio.unavailable_reason
    assert 'does not exist' not in portfolio.unavailable_reason


def test_unreadable_and_absent_reasons_are_not_the_same_sentence(tmp_path: Path) -> None:
    """Stated as a comparison, because "distinguishable" is a claim about two messages."""
    records = tmp_path / 'records'
    (records / 'projects').mkdir(parents=True)
    (records / 'gate-assessments').mkdir()

    records.chmod(0o000)
    try:
        if os.access(records, os.R_OK):
            pytest.skip('this process can read a 0o000 directory, so the case cannot be exercised')
        unreadable = project_portfolio(records).unavailable_reason
    finally:
        records.chmod(0o755)

    absent = project_portfolio(tmp_path / 'not-mounted-at-all').unavailable_reason

    assert unreadable and absent
    assert unreadable != absent


def _records_tree(root: Path) -> Path:
    """Build a minimal records root citing one artefact, for the artefact-tree tests."""
    records = root / 'records'
    (records / 'projects').mkdir(parents=True)
    (records / 'gate-assessments').mkdir()
    (records / 'engagements').mkdir()
    (records / 'projects' / 'gas.md').write_text(
        '---\nid: gas\nname: Gas\nfigures:\n  - label: Revenue potential\n    value: Rp 63,3 M\n'
        '    tier: POTENSI\n    basis: SOURCES/analysis.pdf\n---\n',
        encoding='utf-8',
    )
    return records


def test_artefact_citations_are_not_checked_without_an_artefact_root(tmp_path: Path) -> None:
    """The default stays pure over the records directory alone.

    The fixture suite has no artefact tree and should not need one; checking is something a
    deployment opts into by naming where the documents live.
    """
    portfolio = project_portfolio(_records_tree(tmp_path))

    assert portfolio.available
    assert portfolio.projects[0].figures[0].basis == 'SOURCES/analysis.pdf'


def test_a_cited_artefact_that_is_not_in_the_tree_is_refused(tmp_path: Path) -> None:
    """A rename in the JUP tree must be loud (ADR-0004's cost, paid deliberately).

    Without this the failure is silent in the worst way: every gate still renders and every
    one of them cites a file nobody can open.
    """
    records = _records_tree(tmp_path)
    (tmp_path / 'SOURCES').mkdir()

    with pytest.raises(RecordError) as refused:
        project_portfolio(records, artefact_root=tmp_path)

    message = str(refused.value)
    assert 'SOURCES/analysis.pdf' in message
    assert 'renamed, moved or never existed' in message


def test_a_cited_artefact_that_is_present_resolves(tmp_path: Path) -> None:
    """The same records pass once the document is where they say it is."""
    records = _records_tree(tmp_path)
    (tmp_path / 'SOURCES').mkdir()
    (tmp_path / 'SOURCES' / 'analysis.pdf').write_bytes(b'%PDF-1.4\n')

    portfolio = project_portfolio(records, artefact_root=tmp_path)

    assert portfolio.available
    assert portfolio.projects[0].figures[0].basis == 'SOURCES/analysis.pdf'


def test_an_artefact_path_escaping_the_tree_is_refused(tmp_path: Path) -> None:
    """A citation that climbs out of the tree is refused as firmly as a missing one.

    Nothing here opens the file, so this is not a read primitive — but a record that can
    name a path outside the mounted tree is one whose provenance claim is meaningless.
    """
    records = _records_tree(tmp_path)
    (records / 'projects' / 'gas.md').write_text(
        '---\nid: gas\nname: Gas\nfigures:\n  - label: Revenue potential\n    value: Rp 63,3 M\n'
        '    tier: POTENSI\n    basis: ../../../etc/hosts\n---\n',
        encoding='utf-8',
    )

    with pytest.raises(RecordError) as refused:
        project_portfolio(records, artefact_root=tmp_path)

    assert 'outside the artefact tree' in str(refused.value)
