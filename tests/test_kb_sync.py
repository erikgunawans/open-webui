"""Tests for `jup.kb_sync` — the generator that makes `records/` the single source.

Trees are built in `tmp_path` rather than checked in under `tests/fixtures/`, because every
test here mutates one: the whole point of a drift check is what it does after somebody edits
something, and a shared on-disk fixture that tests edit is a suite that passes in the order
pytest happens to choose.

The forced-failure tests are the ones that matter. A drift check that has never been shown
to fail is a green tick with nothing behind it, which is worse than no check at all — it is
the `clean != safe` failure this system names in its own governance file.
"""

import os
from pathlib import Path

import pytest

from jup.kb_sync import (
    KbSyncError,
    check_tree,
    main,
    render_partner_state,
    render_stage_ladder,
    sync_partners,
    sync_tree,
)
from jup.portfolio import STAGE_LABELS, STAGES, project_portfolio

PARTNERS_TEMPLATE = """# Partners

Opening prose that must survive regeneration byte for byte.

<!-- BEGIN generated:partner-state -->
<!-- END generated:partner-state -->

| Pillar | Counterparty | What for |
|---|---|---|
| Waste | **Danantara** | The PLTSa mandate |

**The stage ladder.**

<!-- BEGIN generated:stage-ladder -->
<!-- END generated:stage-ladder -->

## The critical one

**SKK Migas + PGN/Pertagas** — argued by name in prose, which must never be refused.
"""

GAS_TEMPLATE = 'The 5 mmscfd **allocation is not secured**. Gate #1.\n'
GOVERNANCE_TEMPLATE = 'The 5 mmscfd allocation is not secured — Gate #1.\n'

ENGAGEMENT = """---
id: skk-migas-pgn-allocation
counterparty:
  - SKK Migas
  - PGN/Pertagas
pillar: gas
purpose: 'The 5 mmscfd allocation'
stage: contacted
artefact: SOURCES/analysis.pdf
---

Body prose.
"""

PROJECT = """---
id: gas-spbg-reactivation
name: SPBG reactivation
pillar: gas
---

Body prose.
"""

ASSESSMENT_FAIL = """---
project: gas-spbg-reactivation
gate: G1
verdict: fail
assessed_on: 2026-09-19
signed_by: Director
evidence:
  - requirement: gas allocation
    satisfied: false
    engagement: skk-migas-pgn-allocation
---

Body prose.
"""

ASSESSMENT_PASS = ASSESSMENT_FAIL.replace('verdict: fail', 'verdict: pass').replace(
    'satisfied: false', 'satisfied: true'
)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A minimal JUP tree: one engagement, one gas project refused at G1, and a KB."""
    for subdir in ('records/projects', 'records/gate-assessments', 'records/engagements', 'kb', 'SOURCES'):
        (tmp_path / subdir).mkdir(parents=True)
    (tmp_path / 'SOURCES/analysis.pdf').write_text('pdf', encoding='utf-8')
    (tmp_path / 'records/engagements/skk-migas-pgn-allocation.md').write_text(ENGAGEMENT, encoding='utf-8')
    (tmp_path / 'records/projects/gas-spbg-reactivation.md').write_text(PROJECT, encoding='utf-8')
    (tmp_path / 'records/gate-assessments/gas-g1.md').write_text(ASSESSMENT_FAIL, encoding='utf-8')
    (tmp_path / 'kb/partners.md').write_text(PARTNERS_TEMPLATE, encoding='utf-8')
    (tmp_path / 'kb/gas.md').write_text(GAS_TEMPLATE, encoding='utf-8')
    (tmp_path / 'kb/governance.md').write_text(GOVERNANCE_TEMPLATE, encoding='utf-8')
    sync_tree(tmp_path)
    return tmp_path


def partners_text(tree: Path) -> str:
    return (tree / 'kb/partners.md').read_text(encoding='utf-8')


# --- Generation ---------------------------------------------------------------------


def test_the_ladder_line_comes_from_stage_labels_not_a_second_copy() -> None:
    line = render_stage_ladder()
    for stage in STAGES:
        assert STAGE_LABELS[stage] in line
    assert line.index(STAGE_LABELS['no-contact']) < line.index(STAGE_LABELS['executed'])


def test_one_row_per_record_not_per_counterparty(tree: Path) -> None:
    """ADR-0008: one engagement faces several counterparties, and stays one row."""
    rows = [line for line in partners_text(tree).splitlines() if line.startswith('| Gas ')]
    assert len(rows) == 1
    assert 'SKK Migas' in rows[0]
    assert 'PGN/Pertagas' in rows[0]


def test_every_generated_row_cites_the_document_its_rung_stands_on(tree: Path) -> None:
    row = next(line for line in partners_text(tree).splitlines() if line.startswith('| Gas '))
    assert '`SOURCES/analysis.pdf`' in row


def test_an_empty_records_directory_says_so_rather_than_rendering_an_empty_table() -> None:
    assert 'No engagement record is filed' in render_partner_state(())


def test_prose_survives_regeneration_byte_identical(tree: Path) -> None:
    """The strategic argument is the reason anyone opens this file. It is not generated."""
    before = partners_text(tree)
    engagements = project_portfolio(tree / 'records', tree).engagements
    after = sync_partners(before, engagements)
    assert after == before
    for sentence in (
        'Opening prose that must survive regeneration byte for byte.',
        '**SKK Migas + PGN/Pertagas** — argued by name in prose, which must never be refused.',
        '| Waste | **Danantara** | The PLTSa mandate |',
    ):
        assert sentence in after


def test_sync_is_idempotent(tree: Path) -> None:
    assert sync_tree(tree) is False


def test_a_file_without_the_region_is_refused_rather_than_appended_to(tree: Path) -> None:
    (tree / 'kb/partners.md').write_text('# Partners\n\nNo markers here.\n', encoding='utf-8')
    with pytest.raises(KbSyncError, match='generated:stage-ladder'):
        sync_tree(tree)


# --- The check, in the clean case ---------------------------------------------------


def test_a_freshly_generated_tree_has_no_drift(tree: Path) -> None:
    assert check_tree(tree) == []


# --- Forced failure: every way the two can disagree ---------------------------------


def test_drift_in_the_record_is_caught_and_names_the_record_and_field(tree: Path) -> None:
    record = tree / 'records/engagements/skk-migas-pgn-allocation.md'
    record.write_text(record.read_text().replace('stage: contacted', 'stage: in-discussion'), encoding='utf-8')

    drifts = check_tree(tree)

    assert [drift.field for drift in drifts] == ['stage']
    assert 'skk-migas-pgn-allocation.md' in drifts[0].problem
    assert 'In discussion' in drifts[0].problem


def test_drift_in_the_kb_is_caught_the_same_way(tree: Path) -> None:
    partners = tree / 'kb/partners.md'
    partners.write_text(partners_text(tree).replace('**Contacted**', '**Executed**'), encoding='utf-8')

    drifts = check_tree(tree)

    assert [drift.field for drift in drifts] == ['stage']
    assert 'Executed' in drifts[0].problem


def test_a_hand_written_row_may_not_carry_a_stage_claim(tree: Path) -> None:
    partners = tree / 'kb/partners.md'
    partners.write_text(
        partners_text(tree).replace(
            '| Waste | **Danantara** | The PLTSa mandate |',
            '| Waste | **Danantara** | The PLTSa mandate | **Contacted** |',
        ),
        encoding='utf-8',
    )

    drifts = check_tree(tree)

    assert len(drifts) == 1
    assert "states the rung 'Contacted'" in drifts[0].problem


def test_the_ladder_stated_as_prose_is_not_a_stage_claim(tree: Path) -> None:
    """The definition teaches a reader what the table means. Refusing it would be absurd."""
    partners = tree / 'kb/partners.md'
    partners.write_text(f'{partners_text(tree)}\n\nNo contact → Contacted → Executed.\n', encoding='utf-8')
    assert check_tree(tree) == []


def test_a_recorded_counterparty_may_not_also_be_listed_by_hand(tree: Path) -> None:
    partners = tree / 'kb/partners.md'
    partners.write_text(
        partners_text(tree).replace(
            '| Waste | **Danantara** | The PLTSa mandate |',
            '| Gas | **SKK Migas** | allocation |',
        ),
        encoding='utf-8',
    )

    drifts = check_tree(tree)

    assert len(drifts) == 1
    assert "names 'SKK Migas'" in drifts[0].problem


def test_a_counterparty_argued_by_name_in_prose_is_permitted(tree: Path) -> None:
    """ "The critical one" names SKK Migas. A check that refused that would refuse the case."""
    assert '**SKK Migas + PGN/Pertagas**' in partners_text(tree)
    assert check_tree(tree) == []


def test_a_kb_row_with_no_record_behind_it_is_caught(tree: Path) -> None:
    partners = tree / 'kb/partners.md'
    row = next(line for line in partners_text(tree).splitlines() if line.startswith('| Gas '))
    partners.write_text(
        partners_text(tree).replace(row, f'{row}\n| Water | **Pelindo** | offtake | **Executed** | `x.pdf` |'),
        encoding='utf-8',
    )

    problems = ' '.join(drift.problem for drift in check_tree(tree))

    assert 'no engagement record' in problems


# --- Gate claims in gas.md and governance.md ----------------------------------------


@pytest.mark.parametrize('name', ['gas.md', 'governance.md'])
def test_deleting_the_unsecured_caveat_is_itself_drift(tree: Path, name: str) -> None:
    """A governance caveat is a claim. Its disappearance is as much drift as a wrong stage."""
    path = tree / 'kb' / name
    path.write_text(path.read_text().replace('allocation is not secured', 'allocation is in hand'), encoding='utf-8')

    drifts = check_tree(tree)

    assert [drift.path for drift in drifts] == [path]
    assert 'no longer says' in drifts[0].problem


@pytest.mark.parametrize('name', ['gas.md', 'governance.md'])
def test_a_passing_g1_contradicts_the_caveat_and_is_caught(tree: Path, name: str) -> None:
    (tree / 'records/gate-assessments/gas-g1.md').write_text(ASSESSMENT_PASS, encoding='utf-8')

    problems = {drift.path: drift.problem for drift in check_tree(tree)}

    assert 'passing G1' in problems[tree / 'kb' / name]


def test_a_missing_kb_file_is_a_broken_tree_not_a_drift(tree: Path) -> None:
    (tree / 'kb/gas.md').unlink()
    with pytest.raises(KbSyncError, match='gas.md'):
        check_tree(tree)


# --- The CLI ------------------------------------------------------------------------


def test_check_exits_zero_on_a_clean_tree(tree: Path) -> None:
    assert main(['--jup-root', str(tree), '--check']) == 0


def test_check_exits_one_on_drift(tree: Path) -> None:
    partners = tree / 'kb/partners.md'
    partners.write_text(partners_text(tree).replace('**Contacted**', '**Executed**'), encoding='utf-8')
    assert main(['--jup-root', str(tree), '--check']) == 1


def test_check_writes_nothing(tree: Path) -> None:
    partners = tree / 'kb/partners.md'
    partners.write_text(partners_text(tree).replace('**Contacted**', '**Executed**'), encoding='utf-8')
    before = partners_text(tree)
    main(['--jup-root', str(tree), '--check'])
    assert partners_text(tree) == before


def test_a_malformed_tree_exits_two_not_one(tmp_path: Path) -> None:
    """CI must tell a stale document from a mount that never arrived."""
    assert main(['--jup-root', str(tmp_path), '--check']) == 2


# --- The live tree ------------------------------------------------------------------


def test_the_real_jup_tree_has_no_drift() -> None:
    """The gate that actually protects the deployed assistant, run against the live tree.

    `kb/partners.md` is loaded whole by the strategy assistant, so drift here is not a stale
    document — it is what a commissioner is told when they ask where PGN stands. This is the
    only test in the suite that touches anything outside the repo, and it is read-only.

    It skips where the JUP tree is not mounted, which includes GitHub CI: both repositories
    are private and no cross-repo checkout is wired up. **That makes this a developer gate,
    not a CI gate** — the CI gate is every forced-failure test above, which proves the check
    catches drift, while this one proves the live tree is currently clean. The `~/jup`
    pre-commit hook is what stops a drifting record being committed at source.
    """
    root = Path(os.environ.get('JUP_TREE', '').strip() or Path.home() / 'jup')
    if not (root / 'records').is_dir() or not (root / 'kb').is_dir():
        pytest.skip(f'no JUP tree at {root} — set JUP_TREE to point at one')

    drifts = check_tree(root)

    assert not drifts, 'kb/ disagrees with records/:\n' + '\n'.join(f'  {drift}' for drift in drifts)
