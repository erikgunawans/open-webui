"""The action aggregate (P2 T2): lifecycle, reasoned due-date revisions, derived flags (ACT-03).

Due dates and flags are pure and always run. The commands run against a real SQLite database
brought to the leadership head by the migration graph, so they need the runtime; the Postgres
behaviour of the underlying transaction is covered in `test_leadership_repository.py`.
"""

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from jup.leadership.actions import Due, derive_flags, fold_history

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')

PIC = 'user-pic-1'
TODAY = dt.date(2026, 9, 24)


# --- due dates ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('precision', 'value'),
    [('date', '2026-11-30'), ('month', '2026-11'), ('year', '2027'), ('year_range', '2026/2027')],
)
def test_a_due_date_keeps_the_precision_it_was_given(precision: str, value: str) -> None:
    due = Due(precision, value)
    assert (due.precision, due.value) == (precision, value)


@pytest.mark.parametrize(
    ('precision', 'value'),
    [
        ('day', '2026-11-30'),  # P1's vocabulary is 'date'
        ('date', '2026-11'),
        ('date', '2026-02-30'),
        ('date', '20261130'),
        ('month', '2026-13'),
        ('month', '2026-11-01'),
        ('year', '26'),
        ('year_range', '2027/2026'),
        ('year_range', '2026-2027'),
        ('month', '٢٠٢٦-11'),
    ],
)
def test_a_malformed_due_date_is_refused(precision: str, value: str) -> None:
    with pytest.raises(ValueError):
        Due(precision, value)


# --- derived flags --------------------------------------------------------------------------


def _row(state: str = 'in_progress', due: Due | None = Due('date', '2026-09-20')) -> dict:
    return {
        'state': state,
        'current_due': due.value if due else None,
        'current_due_precision': due.precision if due else None,
    }


def test_a_day_precise_past_due_date_is_overdue() -> None:
    flags = derive_flags(_row(), today=TODAY)
    assert flags.overdue is True
    assert flags.days_overdue == 4


def test_a_future_due_date_is_not_overdue() -> None:
    flags = derive_flags(_row(due=Due('date', '2026-10-01')), today=TODAY)
    assert (flags.overdue, flags.days_overdue) == (False, None)


@pytest.mark.parametrize('due', [Due('month', '2026-08'), Due('year', '2025'), Due('year_range', '2024/2025'), None])
def test_below_day_precision_no_overdue_value_is_invented(due) -> None:
    flags = derive_flags(_row(due=due), today=TODAY)
    assert flags.overdue is None and flags.days_overdue is None
    assert flags.reasons['overdue']


def test_due_before_the_next_meeting_needs_a_date_and_a_meeting() -> None:
    row = _row(due=Due('date', '2026-10-05'))
    assert derive_flags(row, today=TODAY, next_meeting=dt.date(2026, 10, 10)).due_before_next_meeting is True
    assert derive_flags(row, today=TODAY, next_meeting=dt.date(2026, 10, 1)).due_before_next_meeting is False
    assert derive_flags(row, today=TODAY).due_before_next_meeting is None


def test_staleness_needs_a_recorded_policy() -> None:
    last = int(dt.datetime(2026, 9, 1, tzinfo=dt.UTC).timestamp() * 1000)
    unpoliced = derive_flags(_row(), today=TODAY, last_update_at_ms=last)
    assert unpoliced.stale is None
    assert 'policy' in unpoliced.reasons['stale']
    assert derive_flags(_row(), today=TODAY, last_update_at_ms=last, stale_after_days=14).stale is True
    assert derive_flags(_row(), today=TODAY, last_update_at_ms=last, stale_after_days=30).stale is False


def test_flags_never_replace_the_state() -> None:
    flags = derive_flags(_row(state='closed'), today=TODAY)
    assert (flags.overdue, flags.due_before_next_meeting, flags.stale) == (None, None, None)
    assert 'closed' in flags.reasons['overdue']


# --- commands -------------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path, leadership_db_url: str):
    from sqlalchemy import create_engine

    from jup.leadership import migrate

    engine = create_engine(leadership_db_url)
    assert migrate.run_leadership_migrations(engine) is True
    yield engine
    engine.dispose()


def _create(engine, due: Due | None = Due('month', '2026-11')):
    from jup.leadership import actions
    from jup.leadership.repository import unit_of_work

    with unit_of_work(engine) as uow:
        return actions.create_action(
            uow,
            action_id='act-1',
            title='Finalise SPBG offtake term sheet',
            pic_label='PIC Komersial',
            pic_user_id=PIC,
            due=due,
            author=PIC,
            reason='carried from the September BOD deck',
        )


def _run(engine, command, **kwargs):
    from jup.leadership.repository import unit_of_work

    with unit_of_work(engine) as uow:
        return command(uow, action_id='act-1', author=PIC, **kwargs)


@needs_runtime
def test_a_new_action_starts_not_started_with_its_original_due_date(engine) -> None:
    from jup.leadership.repository import read_action

    _create(engine)
    row = read_action(engine, 'act-1')
    assert row['state'] == 'not_started'
    assert (row['original_due'], row['original_due_precision']) == ('2026-11', 'month')
    assert (row['current_due'], row['current_due_precision']) == ('2026-11', 'month')


@needs_runtime
def test_an_unknown_due_date_stays_unknown(engine) -> None:
    from jup.leadership.repository import read_action

    _create(engine, due=None)
    row = read_action(engine, 'act-1')
    assert row['original_due'] is None and row['current_due_precision'] is None


@needs_runtime
def test_the_owner_moves_between_not_started_in_progress_and_blocked(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_action

    _create(engine)
    _run(engine, actions.change_state, expected_version=1, to_state='in_progress')
    _run(engine, actions.change_state, expected_version=2, to_state='blocked', reason='waiting on PGN pricing')
    _run(engine, actions.change_state, expected_version=3, to_state='in_progress', reason='pricing received')
    assert read_action(engine, 'act-1')['state'] == 'in_progress'


@needs_runtime
def test_blocking_needs_a_reason(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_events

    _create(engine)
    with pytest.raises(actions.CommandRefused, match='reason'):
        _run(engine, actions.change_state, expected_version=1, to_state='blocked', reason='  ')
    assert len(read_events(engine, 'act-1')) == 1


@needs_runtime
@pytest.mark.parametrize('target', ['awaiting_bod_closure', 'closed', 'not_started', 'done'])
def test_the_owner_cannot_request_closure_or_close_by_changing_state(engine, target: str) -> None:
    """Awaiting closure comes only from completion evidence (T3); closing only from the BOD (T4)."""
    from jup.leadership import actions
    from jup.leadership.repository import read_action

    _create(engine)
    with pytest.raises(actions.CommandRefused):
        _run(engine, actions.change_state, expected_version=1, to_state=target, reason='r')
    assert read_action(engine, 'act-1')['state'] == 'not_started'


@needs_runtime
def test_a_closed_action_takes_no_owner_command(engine) -> None:
    from sqlalchemy import update

    from jup.leadership import actions
    from jup.leadership.models import action

    _create(engine)
    # Closure is T4's; put the aggregate there directly to test the refusal alone.
    with engine.begin() as connection:
        connection.execute(update(action).values(state='closed'))
    for command, kwargs in (
        (actions.change_state, {'to_state': 'in_progress'}),
        (actions.record_progress, {'narrative': 'more work'}),
        (actions.revise_due, {'due': Due('month', '2026-12'), 'reason': 'late'}),
    ):
        with pytest.raises(actions.CommandRefused, match='closed'):
            _run(engine, command, expected_version=1, **kwargs)


@needs_runtime
@pytest.mark.parametrize(
    ('state', 'target'),
    [
        # Only the BOD returns an action under review (T4); the owner cannot withdraw it.
        ('awaiting_bod_closure', 'in_progress'),
        ('awaiting_bod_closure', 'blocked'),
        # A move to where it already is would be an event that changed nothing.
        ('in_progress', 'in_progress'),
        ('blocked', 'blocked'),
    ],
)
def test_the_owner_cannot_leave_review_or_repeat_a_state(engine, state: str, target: str) -> None:
    from sqlalchemy import update

    from jup.leadership import actions
    from jup.leadership.models import action
    from jup.leadership.repository import read_events

    _create(engine)
    with engine.begin() as connection:
        connection.execute(update(action).values(state=state))
    with pytest.raises(actions.CommandRefused, match='cannot move'):
        _run(engine, actions.change_state, expected_version=1, to_state=target, reason='r')
    assert len(read_events(engine, 'act-1')) == 1


@needs_runtime
def test_a_due_revision_keeps_the_original_and_needs_a_reason(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_action, read_events

    _create(engine)
    with pytest.raises(actions.CommandRefused, match='reason'):
        _run(engine, actions.revise_due, expected_version=1, due=Due('month', '2027-01'), reason='')
    _run(engine, actions.revise_due, expected_version=1, due=Due('month', '2027-01'), reason='PGN delayed pricing')
    _run(engine, actions.revise_due, expected_version=2, due=Due('date', '2027-01-31'), reason='BOD set a day')

    row = read_action(engine, 'act-1')
    assert (row['original_due'], row['original_due_precision']) == ('2026-11', 'month')
    assert (row['current_due'], row['current_due_precision']) == ('2027-01-31', 'date')

    history = fold_history(read_events(engine, 'act-1'))
    revisions = [entry for entry in history if entry['kind'] == 'due_revised']
    assert [(r['due_before'], r['due_after'], r['reason']) for r in revisions] == [
        ({'precision': 'month', 'value': '2026-11'}, {'precision': 'month', 'value': '2027-01'}, 'PGN delayed pricing'),
        ({'precision': 'month', 'value': '2027-01'}, {'precision': 'date', 'value': '2027-01-31'}, 'BOD set a day'),
    ]


@needs_runtime
def test_revising_to_the_same_due_date_is_refused(engine) -> None:
    from jup.leadership import actions

    _create(engine)
    with pytest.raises(actions.CommandRefused, match='unchanged'):
        _run(engine, actions.revise_due, expected_version=1, due=Due('month', '2026-11'), reason='no-op')


@needs_runtime
def test_progress_is_an_owner_update_and_changes_no_state(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_action, read_events

    _create(engine)
    _run(
        engine,
        actions.record_progress,
        expected_version=1,
        narrative='Term sheet draft sent to PGN',
        milestones_completed=['draft sent'],
        remaining_work='PGN comments',
        next_step='review call',
    )
    assert read_action(engine, 'act-1')['state'] == 'not_started'
    event = read_events(engine, 'act-1')[-1]
    assert event.kind == 'progress_submitted'
    assert event.payload['owner_update'] is True
    assert event.payload['milestones_completed'] == ['draft sent']
    # Nothing invents a completion percentage.
    assert 'percent' not in str(event.payload)


@needs_runtime
def test_an_older_progress_update_cannot_replace_a_newer_one(engine) -> None:
    """Both tabs read version 1. The later-arriving one conflicts, whatever its client clock says."""
    from jup.leadership import actions
    from jup.leadership.repository import VersionConflict, read_events

    _create(engine)
    _run(engine, actions.record_progress, expected_version=1, narrative='newer', reported_at='2026-09-24T10:00:00Z')
    with pytest.raises(VersionConflict):
        _run(engine, actions.record_progress, expected_version=1, narrative='older', reported_at='2026-09-24T11:00:00Z')

    latest = actions.latest_progress(read_events(engine, 'act-1'))
    assert latest is not None and latest.payload['narrative'] == 'newer'


@needs_runtime
def test_latest_progress_follows_version_order_not_client_time(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_events

    _create(engine)
    _run(engine, actions.record_progress, expected_version=1, narrative='first', reported_at='2026-09-24T12:00:00Z')
    _run(engine, actions.record_progress, expected_version=2, narrative='second', reported_at='2026-09-24T08:00:00Z')
    assert actions.latest_progress(read_events(engine, 'act-1')).payload['narrative'] == 'second'


@needs_runtime
def test_a_double_submitted_command_returns_the_first_result(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_events

    _create(engine)
    kwargs = {'expected_version': 1, 'to_state': 'blocked', 'reason': 'waiting', 'idempotency_key': 'k1'}
    first = _run(engine, actions.change_state, **kwargs)
    second = _run(engine, actions.change_state, **kwargs)
    assert second.replayed is True and second.event == first.event
    assert len(read_events(engine, 'act-1')) == 2


@needs_runtime
def test_the_history_folds_state_and_due_after_each_event(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_events

    _create(engine)
    _run(engine, actions.change_state, expected_version=1, to_state='in_progress')
    _run(engine, actions.revise_due, expected_version=2, due=Due('year', '2027'), reason='scope grew')
    history = fold_history(read_events(engine, 'act-1'))
    assert [(h['version'], h['kind'], h['state_after']) for h in history] == [
        (1, 'created', 'not_started'),
        (2, 'state_changed', 'in_progress'),
        (3, 'due_revised', 'in_progress'),
    ]
    assert history[1]['state_before'] == 'not_started'
    assert history[2]['due_after'] == {'precision': 'year', 'value': '2027'}
    assert all(h['author'] == PIC for h in history)


@needs_runtime
def test_a_stale_state_change_is_a_conflict_not_a_refusal(engine) -> None:
    """With a stale version the command must not judge the transition against newer state."""
    from jup.leadership import actions
    from jup.leadership.repository import VersionConflict

    _create(engine)
    _run(engine, actions.change_state, expected_version=1, to_state='blocked', reason='waiting')
    with pytest.raises(VersionConflict):
        _run(engine, actions.change_state, expected_version=1, to_state='blocked', reason='also waiting')


# --- PIC assignment (T8 follow-up) ------------------------------------------------------------


def _create_without_pic(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import unit_of_work

    with unit_of_work(engine) as uow:
        actions.create_action(
            uow, action_id='act-1', title='Imported action', pic_label='PIC Pengadaan', author='rev-1'
        )


@needs_runtime
def test_a_first_pic_assignment_needs_no_reason_and_is_an_event(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_action, read_events

    _create_without_pic(engine)
    with_uow = _run_as(engine, 'lead-1')
    with_uow(actions.assign_pic, expected_version=1, pic_user_id='user-new-pic')
    row = read_action(engine, 'act-1')
    assert (row['pic_user_id'], row['pic_label'], row['version']) == ('user-new-pic', 'PIC Pengadaan', 2)
    event = read_events(engine, 'act-1')[-1]
    assert event.kind == 'pic_assigned'
    assert event.payload == {'pic_user_id': 'user-new-pic', 'pic_label': 'PIC Pengadaan', 'previous_pic_user_id': None}


@needs_runtime
def test_replacing_a_pic_needs_a_reason_and_may_relabel(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import read_action

    _create(engine)
    assign = _run_as(engine, 'lead-1')
    with pytest.raises(actions.CommandRefused, match='reason'):
        assign(actions.assign_pic, expected_version=1, pic_user_id='user-other')
    assign(actions.assign_pic, expected_version=1, pic_user_id='user-other', pic_label='PIC Hukum', reason='handover')
    row = read_action(engine, 'act-1')
    assert (row['pic_user_id'], row['pic_label']) == ('user-other', 'PIC Hukum')


@needs_runtime
def test_an_assignment_that_changes_nothing_is_refused(engine) -> None:
    from jup.leadership import actions

    _create(engine)
    with pytest.raises(actions.CommandRefused, match='unchanged'):
        _run_as(engine, 'lead-1')(actions.assign_pic, expected_version=1, pic_user_id=PIC, reason='same')


@needs_runtime
@pytest.mark.parametrize('state', ['closed', 'awaiting_bod_closure'])
def test_no_pic_change_on_a_closed_action_or_under_review(engine, state: str) -> None:
    from sqlalchemy import update

    from jup.leadership import actions
    from jup.leadership.models import action

    _create(engine)
    with engine.begin() as connection:
        connection.execute(update(action).values(state=state))
    with pytest.raises(actions.CommandRefused):
        _run_as(engine, 'lead-1')(actions.assign_pic, expected_version=1, pic_user_id='user-other', reason='x')


@needs_runtime
def test_a_stale_assignment_is_a_conflict(engine) -> None:
    from jup.leadership import actions
    from jup.leadership.repository import VersionConflict

    _create_without_pic(engine)
    assign = _run_as(engine, 'lead-1')
    assign(actions.assign_pic, expected_version=1, pic_user_id='user-a')
    with pytest.raises(VersionConflict):
        assign(actions.assign_pic, expected_version=1, pic_user_id='user-b', reason='x')


def _run_as(engine, author: str):
    from jup.leadership.repository import unit_of_work

    def run(command, **kwargs):
        with unit_of_work(engine) as uow:
            return command(uow, action_id='act-1', author=author, **kwargs)

    return run
