"""Changes since the last meeting (P2 T8 discussion module).

The comparison of two frozen contents is pure and always runs. Choosing which two meeting records
to compare runs against a real database brought to the leadership head, so it needs the runtime.
"""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from jup.leadership.snapshots import compare_contents

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')


def _reading(value: str | None, **overrides: Any) -> dict[str, Any]:
    return {
        'value': value,
        'unit': 'IDR_billion',
        'kind': 'actual',
        'period_start': '2026-01-01',
        'period_end': '2026-07-31',
        'scope_id': 'jup-consolidated',
        'missing_reason': None if value is not None else 'not reported',
    } | overrides


def _metric(metric_id: str, reading: dict[str, Any], label: str = 'Pendapatan usaha') -> dict[str, Any]:
    return {'id': metric_id, 'label': label, 'primary': reading}


def _action(action_id: str, state: str, due: str | None = 'September 2026', title: str = 'Alokasi gas') -> dict:
    return {
        'id': action_id,
        'title': title,
        'state': state,
        'due': None if due is None else {'label': due, 'precision': 'month'},
    }


def _content(metrics: list[dict], actions: list[dict], source: str = 'records') -> dict[str, Any]:
    return {'view': 'board', 'metrics': metrics, 'actions': actions, 'actions_source': source}


# --- metrics --------------------------------------------------------------------------------


def test_a_metric_in_both_meetings_carries_its_decimal_difference() -> None:
    before = _content([_metric('rev', _reading('130.20'))], [])
    after = _content([_metric('rev', _reading('144.47', period_end='2026-08-31'))], [])
    [metric] = compare_contents(before, after)['metrics']
    assert metric['id'] == 'rev' and metric['change'] == 'changed'
    assert metric['before']['value'] == '130.20' and metric['after']['value'] == '144.47'
    # Decimal arithmetic on the strings, never a float: 144.47 - 130.20 is exactly 14.27.
    assert metric['difference'] == '14.27'
    assert metric['difference_note'] is None
    # Each side keeps its own period; the reader sees that YTD July became YTD August.
    assert metric['before']['period_end'] == '2026-07-31' and metric['after']['period_end'] == '2026-08-31'


def test_an_unchanged_metric_differs_by_zero() -> None:
    same = _content([_metric('rev', _reading('144.47'))], [])
    [metric] = compare_contents(same, same)['metrics']
    assert metric['change'] == 'unchanged' and metric['difference'] == '0'


@pytest.mark.parametrize(
    ('before', 'after', 'note'),
    [
        (_reading(None), _reading('144.47'), 'missing'),
        (_reading('144.47'), _reading(None), 'missing'),
        (_reading('10.5', unit='percent'), _reading('144.47'), 'unit'),
        (_reading('158.47', kind='budget'), _reading('144.47'), 'kind'),
        (_reading('144.47', scope_id='jup-parent'), _reading('150.00'), 'scope'),
    ],
)
def test_no_difference_is_invented_between_readings_that_do_not_compare(before, after, note) -> None:
    [metric] = compare_contents(_content([_metric('rev', before)], []), _content([_metric('rev', after)], []))[
        'metrics'
    ]
    assert metric['difference'] is None
    assert metric['difference_note'] == note
    assert metric['change'] == 'changed'


def test_metrics_only_in_one_meeting_are_added_or_removed() -> None:
    before = _content([_metric('old', _reading('1'), label='Lama')], [])
    after = _content([_metric('new', _reading('2'), label='Baru')], [])
    metrics = {item['id']: item for item in compare_contents(before, after)['metrics']}
    assert metrics['new']['change'] == 'added' and metrics['new']['before'] is None
    assert metrics['old']['change'] == 'removed' and metrics['old']['after'] is None
    assert metrics['new']['difference'] is None and metrics['old']['difference'] is None


# --- actions --------------------------------------------------------------------------------


def test_action_state_and_due_changes_are_named_with_both_sides() -> None:
    before = _content([], [_action('gas', 'in_progress'), _action('water', 'blocked')])
    after = _content([], [_action('gas', 'closed'), _action('water', 'blocked', due='Desember 2026')])
    result = compare_contents(before, after)
    assert result['actions_comparable'] is True and result['actions_source'] == 'records'
    changed = {item['id']: item for item in result['actions']['changed']}
    assert changed['gas']['state_before'] == 'in_progress' and changed['gas']['state_after'] == 'closed'
    assert changed['gas']['due_before'] == changed['gas']['due_after'] == 'September 2026'
    assert changed['water']['state_before'] == changed['water']['state_after'] == 'blocked'
    assert changed['water']['due_before'] == 'September 2026' and changed['water']['due_after'] == 'Desember 2026'


def test_an_untouched_action_is_not_listed_as_changed() -> None:
    same = _content([], [_action('gas', 'in_progress')])
    assert compare_contents(same, same)['actions'] == {'added': [], 'removed': [], 'changed': []}


def test_new_and_dropped_actions_are_listed() -> None:
    before = _content([], [_action('gas', 'in_progress')])
    after = _content([], [_action('water', 'not_started', due=None, title='Mutu air')])
    actions = compare_contents(before, after)['actions']
    assert actions['added'] == [{'id': 'water', 'title': 'Mutu air', 'state': 'not_started', 'due': None}]
    gas = {'id': 'gas', 'title': 'Alokasi gas', 'state': 'in_progress', 'due': 'September 2026'}
    assert actions['removed'] == [gas]


def test_actions_from_different_sources_are_not_compared() -> None:
    # A deck's reported state and the records lifecycle are different vocabularies.
    before = _content([], [_action('gas', 'in_progress')], source='sample')
    after = _content([], [_action('gas', 'closed')], source='records')
    result = compare_contents(before, after)
    assert result['actions_comparable'] is False
    assert result['actions'] == {'added': [], 'removed': [], 'changed': []}


# --- choosing the two meeting records -------------------------------------------------------


@pytest.fixture
def dataset(fixture_path: Callable[..., Path]) -> dict:
    from jup.leadership.reader import load_dataset

    return load_dataset(fixture_path('leadership', 'illustrative-seed.json'))


@pytest.fixture
def engine(leadership_db_url: str):
    from sqlalchemy import create_engine

    from jup.leadership import migrate

    engine = create_engine(leadership_db_url)
    assert migrate.run_leadership_migrations(engine) is True
    yield engine
    engine.dispose()


def _meeting(engine, dataset, label: str, date: str | None, *, published: bool = True, view: str = 'board'):
    from jup.leadership.snapshots import PublicationPolicy, create_draft, publish, view_content

    with engine.begin() as connection:
        draft = create_draft(
            connection,
            view=view,
            meeting_label=label,
            meeting_date=date,
            content=view_content(connection, dataset, view),
            author='sec-1',
        )
        if not published:
            return draft
        return publish(
            connection,
            snapshot_id=draft.snapshot_id,
            expected_version=draft.version,
            content_hash=draft.content_hash,
            publisher='sec-2',
            policy=PublicationPolicy(four_eyes=True),
        )


def _changes(engine, view: str = 'board') -> dict[str, Any]:
    from jup.leadership.snapshots import meeting_changes

    with engine.connect() as connection:
        return meeting_changes(connection, view)


@needs_runtime
def test_fewer_than_two_meeting_records_is_unavailable_not_empty(engine, dataset) -> None:
    assert _changes(engine) == {'available': False, 'published_meetings': 0}
    _meeting(engine, dataset, 'Agustus', '2026-08-27')
    assert _changes(engine) == {'available': False, 'published_meetings': 1}


@needs_runtime
def test_a_draft_is_never_a_meeting_to_compare_against(engine, dataset) -> None:
    _meeting(engine, dataset, 'Agustus', '2026-08-27')
    _meeting(engine, dataset, 'September', '2026-09-24', published=False)
    assert _changes(engine)['available'] is False


@needs_runtime
def test_the_two_latest_meetings_by_date_are_compared(engine, dataset) -> None:
    _meeting(engine, dataset, 'Juli', '2026-07-30')
    _meeting(engine, dataset, 'September', '2026-09-24')
    # Published last, but it is the earlier meeting: meeting date decides, not publication order.
    _meeting(engine, dataset, 'Agustus', '2026-08-27')
    result = _changes(engine)
    assert result['available'] is True
    assert result['before']['meeting_label'] == 'Agustus' and result['after']['meeting_label'] == 'September'
    assert result['before']['content_hash'] and result['after']['state'] == 'published'
    # Same dataset twice: every metric is present in both and nothing moved.
    assert result['metrics'] and all(item['change'] == 'unchanged' for item in result['metrics'])


@needs_runtime
def test_meetings_of_the_other_view_are_not_compared(engine, dataset) -> None:
    _meeting(engine, dataset, 'Agustus', '2026-08-27', view='rka')
    _meeting(engine, dataset, 'September', '2026-09-24', view='rka')
    assert _changes(engine, 'board')['available'] is False
    assert _changes(engine, 'rka')['available'] is True
