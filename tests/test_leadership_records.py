"""Leadership dataset contracts: illustrative source records in, refusal or arithmetic out.

The dashboard reader is intentionally narrow: it accepts a board-facing illustrative seed
only when every citation can be traced inside the view that will render it. These tests
mutate a fresh copy of the real fixture, one field at a time, so the contract stays tied to
what the product will actually read. They speak only in `validate_dataset`,
`calculate_variance` and the path an `InvalidDataset` names, never in the helpers behind them.
"""

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from jup.leadership.records import InvalidDataset, calculate_variance, validate_dataset


def _dataset(fixture_path: Callable[..., Path]) -> dict[str, Any]:
    """A fresh parse of the seed per test, so no mutation can leak between tests."""
    return json.loads(fixture_path('leadership', 'illustrative-seed.json').read_text(encoding='utf-8'))


def _board_metric(dataset: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return dataset['views']['board']['metrics'][index]


def _rka_metric(dataset: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return dataset['views']['rka']['metrics'][index]


def _refused_at(dataset: dict[str, Any], path: str) -> None:
    """Assert the dataset is refused and that the refusal names exactly this path."""
    with pytest.raises(InvalidDataset, match=f'^{re.escape(path)}: '):
        validate_dataset(dataset)


def test_seed_validates_and_keeps_illustrative_unverified_status(fixture_path: Callable[..., Path]) -> None:
    """The committed seed is the reference shape; if it fails, the validator is wrong."""
    dataset = _dataset(fixture_path)

    validate_dataset(dataset)

    assert dataset['data_mode'] == 'illustrative'
    assert _board_metric(dataset)['verification_status'] == 'unverified'


@pytest.mark.parametrize(
    ('index', 'expected'),
    [(0, '-14.00'), (1, '-2.25'), (2, '-0.9')],
    ids=['revenue', 'net-result', 'gross-margin'],
)
def test_seed_variance_is_actual_minus_budget(
    fixture_path: Callable[..., Path],
    index: int,
    expected: str,
) -> None:
    """Exact decimal subtraction, scale preserved: 144.47 - 158.47 is '-14.00', not -14.0."""
    dataset = _dataset(fixture_path)
    validate_dataset(dataset)

    assert calculate_variance(_board_metric(dataset, index)) == expected


def test_variance_is_none_when_baseline_period_differs(fixture_path: Callable[..., Path]) -> None:
    """A budget for a shorter period is a different quantity; subtracting it would mislead."""
    dataset = _dataset(fixture_path)
    metric = _board_metric(dataset)
    metric['baseline']['period_end'] = '2026-07-31'
    validate_dataset(dataset)

    assert calculate_variance(metric) is None


def test_variance_is_none_for_narrative_only_metric(fixture_path: Callable[..., Path]) -> None:
    """A narrative comparison has no baseline reading, so there is nothing to subtract."""
    dataset = _dataset(fixture_path)
    validate_dataset(dataset)

    assert calculate_variance(_rka_metric(dataset)) is None


def test_missing_value_with_reason_validates_and_has_no_variance(fixture_path: Callable[..., Path]) -> None:
    """A gap that says why it is a gap is honest data, and yields no variance."""
    dataset = _dataset(fixture_path)
    metric = _board_metric(dataset)
    metric['primary']['value'] = None
    metric['primary']['missing_reason'] = 'Belum tersedia dari sumber.'
    validate_dataset(dataset)

    assert calculate_variance(metric) is None


@pytest.mark.parametrize('missing_reason', [None, ''])
def test_missing_value_without_reason_is_refused(
    fixture_path: Callable[..., Path],
    missing_reason: str | None,
) -> None:
    """An empty cell with no explanation would render as a silent zero or a blank."""
    dataset = _dataset(fixture_path)
    metric = _board_metric(dataset)
    metric['primary']['value'] = None
    metric['primary']['missing_reason'] = missing_reason

    _refused_at(dataset, 'views.board.metrics[0].primary.missing_reason')


def test_duplicate_action_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Two actions under one id would make every action reference ambiguous."""
    dataset = _dataset(fixture_path)
    dataset['actions'][1]['id'] = dataset['actions'][0]['id']

    _refused_at(dataset, 'actions[1].id')


def test_dangling_view_action_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A view may not list an action that does not exist."""
    dataset = _dataset(fixture_path)
    dataset['views']['board']['action_ids'][0] = 'missing-action'

    _refused_at(dataset, 'views.board.action_ids[0]')


def test_dangling_assumption_action_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """An assumption's linked action must resolve just as a view's does."""
    dataset = _dataset(fixture_path)
    dataset['views']['rka']['assumptions'][0]['action_ids'][0] = 'missing-action'

    _refused_at(dataset, 'views.rka.assumptions[0].action_ids[0]')


def test_dangling_metric_source_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A figure citing a document that is not in the dataset cannot be traced."""
    dataset = _dataset(fixture_path)
    _board_metric(dataset)['source_ids'][0] = 'missing-source'

    _refused_at(dataset, 'views.board.metrics[0].source_ids[0]')


def test_dangling_action_source_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """An action's evidence must resolve to a known source."""
    dataset = _dataset(fixture_path)
    dataset['actions'][0]['source_ids'][0] = 'missing-source'

    _refused_at(dataset, 'actions[0].source_ids[0]')


def test_dangling_context_source_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A view's own source list may only name sources the dataset carries."""
    dataset = _dataset(fixture_path)
    dataset['views']['board']['context']['source_ids'].append('missing-source')

    _refused_at(dataset, 'views.board.context.source_ids[4]')


def test_duplicate_source_id_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Two sources under one id would let a citation point at either document."""
    dataset = _dataset(fixture_path)
    dataset['sources'][1]['id'] = dataset['sources'][0]['id']

    _refused_at(dataset, 'sources[1].id')


@pytest.mark.parametrize('schema_version', [2, True, '1'], ids=['two', 'bool', 'string'])
def test_unsupported_schema_version_is_refused(
    fixture_path: Callable[..., Path],
    schema_version: object,
) -> None:
    """Only integer 1 is understood; `True == 1` in Python, so booleans are named explicitly."""
    dataset = _dataset(fixture_path)
    dataset['schema_version'] = schema_version

    _refused_at(dataset, 'schema_version')


@pytest.mark.parametrize(
    'value',
    [144.47, 144, True, 'NaN', 'Infinity', '-Infinity', '', '1.234,5', '1,5', '1e3', '+1', ' 1', '١٤٤'],
    ids=[
        'float',
        'int',
        'bool',
        'nan',
        'infinity',
        'negative-infinity',
        'empty',
        'locale-thousands',
        'locale-comma',
        'exponent',
        'leading-plus',
        'whitespace',
        'non-ascii-digits',
    ],
)
def test_invalid_decimal_values_are_refused(fixture_path: Callable[..., Path], value: object) -> None:
    """Figures are plain ASCII decimal strings; anything `Decimal` would coerce is still refused."""
    dataset = _dataset(fixture_path)
    _board_metric(dataset)['primary']['value'] = value

    _refused_at(dataset, 'views.board.metrics[0].primary.value')


def test_zero_decimal_string_is_valid_and_calculates_zero_variance(fixture_path: Callable[..., Path]) -> None:
    """Zero is a reading, not a missing value, and must never be treated as falsy."""
    dataset = _dataset(fixture_path)
    metric = _board_metric(dataset)
    metric['primary']['value'] = '0'
    metric['baseline']['value'] = '0'
    validate_dataset(dataset)

    assert calculate_variance(metric) == '0'


def test_view_source_reachability_is_enforced_for_metrics(fixture_path: Callable[..., Path]) -> None:
    """A metric citing a source outside its view's list would render an unopenable citation."""
    dataset = _dataset(fixture_path)
    dataset['views']['board']['context']['source_ids'].remove('board-financial')

    _refused_at(dataset, 'views.board.metrics[0].source_ids[0]')


def test_view_source_reachability_is_enforced_for_actions(fixture_path: Callable[..., Path]) -> None:
    """An action shown in a view must cite only sources that view can show."""
    dataset = _dataset(fixture_path)
    dataset['views']['board']['context']['source_ids'].remove('board-gas')

    _refused_at(dataset, 'views.board.action_ids[0]')


def test_view_source_reachability_is_enforced_for_assumptions(fixture_path: Callable[..., Path]) -> None:
    """An assumption must cite only sources its view can show."""
    dataset = _dataset(fixture_path)
    dataset['views']['rka']['assumptions'][0]['source_ids'] = ['board-financial']

    _refused_at(dataset, 'views.rka.assumptions[0].source_ids[0]')


def test_validate_dataset_does_not_mutate_input(fixture_path: Callable[..., Path]) -> None:
    """Validation is a read; the caller's object is exactly as it was handed over."""
    dataset = _dataset(fixture_path)
    before = copy.deepcopy(dataset)

    validate_dataset(dataset)

    assert dataset == before


@pytest.mark.parametrize('data_mode', ['live', 'verified'])
def test_non_illustrative_data_mode_is_refused(fixture_path: Callable[..., Path], data_mode: str) -> None:
    """This reader serves example material only and must never vouch for live data."""
    dataset = _dataset(fixture_path)
    dataset['data_mode'] = data_mode

    _refused_at(dataset, 'data_mode')


@pytest.mark.parametrize('slide', [True, 0, -1, '4'], ids=['bool', 'zero', 'negative', 'string'])
def test_invalid_physical_slide_is_refused(fixture_path: Callable[..., Path], slide: object) -> None:
    """Slide numbers are positive integers; `True` would otherwise pass as slide 1."""
    dataset = _dataset(fixture_path)
    dataset['sources'][0]['physical_slides'][0] = slide

    _refused_at(dataset, 'sources[0].physical_slides[0]')


def test_empty_physical_slides_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A source with no slide cannot be located inside its deck."""
    dataset = _dataset(fixture_path)
    dataset['sources'][0]['physical_slides'] = []

    _refused_at(dataset, 'sources[0].physical_slides')


@pytest.mark.parametrize('month', [0, 13, True], ids=['zero', 'thirteen', 'bool'])
def test_due_month_outside_calendar_range_is_refused(fixture_path: Callable[..., Path], month: object) -> None:
    """A month-precision due date needs a real calendar month."""
    dataset = _dataset(fixture_path)
    dataset['actions'][0]['due']['month'] = month

    _refused_at(dataset, 'actions[0].due.month')


def test_reversed_due_year_range_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A year range that ends before it starts is a writer error, not a range."""
    dataset = _dataset(fixture_path)
    dataset['actions'][1]['due']['start_year'] = 2028

    _refused_at(dataset, 'actions[1].due.start_year')


def test_unknown_action_state_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Action state is a closed set; 'done' is not one of its members."""
    dataset = _dataset(fixture_path)
    dataset['actions'][0]['state'] = 'done'

    _refused_at(dataset, 'actions[0].state')


def test_reversed_reading_period_is_refused(fixture_path: Callable[..., Path]) -> None:
    """A reading whose period starts after it ends describes no period at all."""
    dataset = _dataset(fixture_path)
    _board_metric(dataset)['primary']['period_start'] = '2026-09-01'

    _refused_at(dataset, 'views.board.metrics[0].primary.period_start')


@pytest.mark.parametrize(
    'document_date',
    ['2026-02-30', '20260918', '2026-09-18T00:00:00', '18-09-2026'],
    ids=['impossible-day', 'compact', 'datetime', 'day-first'],
)
def test_non_iso_calendar_date_is_refused(fixture_path: Callable[..., Path], document_date: str) -> None:
    """Dates are plain YYYY-MM-DD calendar dates, and must exist on the calendar."""
    dataset = _dataset(fixture_path)
    dataset['sources'][0]['document_date'] = document_date

    _refused_at(dataset, 'sources[0].document_date')


def test_unknown_view_key_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Only the board and RKA workspaces exist; any other view would have nowhere to render."""
    dataset = _dataset(fixture_path)
    dataset['views']['summary'] = copy.deepcopy(dataset['views']['board'])

    _refused_at(dataset, 'views.summary')


def test_view_workspace_must_match_its_key(fixture_path: Callable[..., Path]) -> None:
    """A board view that claims to be the RKA workspace would be filed under the wrong page."""
    dataset = _dataset(fixture_path)
    dataset['views']['board']['context']['workspace'] = 'rka'

    _refused_at(dataset, 'views.board.context.workspace')


def test_duplicate_metric_id_across_views_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Metric ids are unique across the whole dataset, not just within one view."""
    dataset = _dataset(fixture_path)
    _rka_metric(dataset)['id'] = _board_metric(dataset)['id']

    _refused_at(dataset, 'views.rka.metrics[0].id')


def test_invalid_module_state_is_refused(fixture_path: Callable[..., Path]) -> None:
    """Module state is a closed set, and each state must carry a reason."""
    dataset = _dataset(fixture_path)
    dataset['views']['board']['module_states'][0]['reason'] = ''

    _refused_at(dataset, 'views.board.module_states[0].reason')


def test_missing_required_field_is_refused(fixture_path: Callable[..., Path]) -> None:
    """An absent key is named by the path it should have lived at."""
    dataset = _dataset(fixture_path)
    del dataset['actions'][0]['history_complete']

    _refused_at(dataset, 'actions[0].history_complete')
