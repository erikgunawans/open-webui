"""A5+E5 #19: JUP's decisions register, read from `DECISIONS.md`.

Behaviour against `tests/fixtures/decisions/DECISIONS.md`, a cut-down copy of the real file's
shape: search by topic, get by number, a reversed or superseded Decision kept with its status,
open items served, and a missing or garbled file refused rather than read as empty.
"""

from pathlib import Path

import pytest

from jup.decisions import DecisionsError, load_register, render_decision, render_search

FIXTURE = Path(__file__).parent / 'fixtures' / 'decisions' / 'DECISIONS.md'


@pytest.fixture
def register():
    return load_register(FIXTURE)


# --- reading -------------------------------------------------------------------------------------


def test_every_decision_row_is_read_in_order(register):
    assert [d.number for d in register.decisions] == ['D2', 'D7', 'D13', 'D16', 'D18', 'D20', 'D21']


def test_a_decision_carries_its_text_status_reasoning_non_coverage_and_date(register):
    d16 = register.get('D16')
    assert d16.decision.startswith('JUP material may be spoken to an AI voice interface')
    assert d16.status == 'DECIDED — control (1) amended by D21 (2026-09-26)'
    assert d16.reasoning == 'The operating layer needs a director-facing briefing surface.'
    assert d16.non_coverage == '(a) no audit claim; (b) the named set bounds retrieval, not speech.'
    assert d16.date == '2026-09-19'


def test_non_coverage_is_found_without_bold_markers_too(register):
    assert register.get('D13').non_coverage == 'this record does not claim the hosting is audited.'


def test_a_decision_without_named_non_coverage_says_so_rather_than_inventing_one(register):
    assert register.get('D2').non_coverage == ''
    assert 'none named' in render_decision(register, 'D2')


# --- get by number -------------------------------------------------------------------------------


@pytest.mark.parametrize('asked', ['D20', 'd20', '20', ' D20 '])
def test_get_by_number_accepts_the_ways_people_write_it(register, asked):
    assert register.get(asked).number == 'D20'


def test_get_renders_the_whole_decision(register):
    out = render_decision(register, 'D20')
    assert 'D20' in out
    assert 'pre-approved class' in out
    assert 'DECIDED — standing rule' in out
    assert 'The line is drawn at egress.' in out
    assert '"read-only" is asserted at attach time' in out
    assert '2026-09-26' in out


def test_an_unknown_number_is_said_to_be_unknown_and_lists_what_exists(register):
    assert register.get('D99') is None
    out = render_decision(register, 'D99')
    assert 'No decision D99' in out and 'D21' in out


# --- reversed and superseded rows ----------------------------------------------------------------


def test_a_reversed_decision_is_served_as_written_with_its_status(register):
    assert register.get('D18').status == 'REVERSED the 2026-09-18 house style'
    assert 'REVERSED' in render_decision(register, 'D18')


def test_a_superseded_decision_keeps_its_status_in_search_results(register):
    out = render_search(register, 'offline')
    assert 'D13' in out and 'superseded 2026-07-14' in out


# --- search --------------------------------------------------------------------------------------


def test_search_by_topic_finds_the_decisions_and_nothing_else(register):
    assert [d.number for d in register.search('voice')] == ['D16', 'D21']


def test_search_ranks_a_match_in_the_decision_above_a_match_in_the_reasoning(register):
    found = [d.number for d in register.search('gas')]
    assert found[:2] == ['D2', 'D7']


def test_search_needs_every_word_before_it_settles_for_some(register):
    assert [d.number for d in register.search('gas allocation')][0] == 'D7'


def test_a_search_result_is_number_one_line_and_status(register):
    out = render_search(register, 'voice')
    line = next(line for line in out.splitlines() if line.startswith('- **D21**'))
    assert 'Voice (D16) may be built and used without zero data retention confirmed.' in line
    assert "DECIDED — Erik's final answer" in line
    assert 'Getting ZDR' not in out  # the reasoning is for get_decision, not the result list


def test_a_search_by_number_finds_that_decision(register):
    assert [d.number for d in register.search('D7')] == ['D7']


def test_a_search_with_no_match_says_so_plainly(register):
    out = render_search(register, 'hydrogen')
    assert 'No decision or open item matches' in out


# --- open items ----------------------------------------------------------------------------------


def test_open_items_are_read_with_what_they_block_and_who_holds_them(register):
    [gas, offtake] = register.open_items
    assert gas.item.startswith('Gas allocation, 5 mmscfd')
    assert gas.blocks == 'The entire gas pillar (D2, D7)'
    assert gas.counterparty == 'SKK Migas · PGN / Pertagas'
    assert offtake.counterparty == 'Transjakarta'


def test_search_serves_matching_open_items(register):
    out = render_search(register, 'gas pillar')
    assert 'Open items' in out and 'SKK Migas · PGN / Pertagas' in out


def test_a_decision_shows_the_open_items_that_block_it(register):
    out = render_decision(register, 'D7')
    assert 'Gas allocation, 5 mmscfd' in out and 'SKK Migas' in out
    assert 'Transjakarta' not in out


# --- refusing a register that cannot be read -----------------------------------------------------


def test_a_missing_file_raises_rather_than_reading_as_empty(tmp_path):
    with pytest.raises(DecisionsError, match='not found'):
        load_register(tmp_path / 'DECISIONS.md')


def test_an_unset_path_raises(monkeypatch):
    with pytest.raises(DecisionsError):
        load_register(None)


@pytest.mark.parametrize(
    'text, why',
    [
        ('', 'no decisions table'),
        ('# Decision Log\n\nNothing here yet.\n', 'no decisions table'),
        (
            '| # | Decision | Status | Why | Date |\n|---|---|---|---|---|\n',
            'no decisions',
        ),
        (
            '| # | Decision | Status | Why | Date |\n|---|---|---|---|---|\n| **D1** | x | DECIDED | y |\n',
            'row 1',
        ),
        (
            '| # | Decision | Status | Why | Date |\n|---|---|---|---|---|\n| **Dx** | x | DECIDED | y | 2026-01-01 |\n',
            'row 1',
        ),
    ],
)
def test_a_garbled_file_raises_and_says_where(tmp_path, text, why):
    path = tmp_path / 'DECISIONS.md'
    path.write_text(text)
    with pytest.raises(DecisionsError, match=why):
        load_register(path)


def test_the_real_register_parses_if_it_is_here():
    """A guard against the fixture drifting from the real file's shape, where the real file exists."""
    real = Path.home() / 'jup' / 'DECISIONS.md'
    if not real.is_file():
        pytest.skip('~/jup/DECISIONS.md is not on this machine')
    register = load_register(real)
    assert register.get('D20') is not None and register.open_items
