"""BOD closure review (P2 T4): the policy, who decides, quorum, stale evidence, return and reopen.

The policy parser is pure and always runs. The decisions run against a real SQLite database
brought to the leadership head by the migration graph, so they need the runtime. The HTTP half
(each unauthorised identity trying a direct API closure) is in `test_jup_leadership_endpoint.py`.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from jup.leadership.closure import BodPolicy, configured_policy, parse_policy

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')

PIC = 'pic-1'
BOD_A = 'bod-a'
BOD_B = 'bod-b'
BOD_C = 'bod-c'
INDIVIDUAL = BodPolicy('individual', 1)
COLLECTIVE = BodPolicy('collective', 2)


# --- the policy -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('{"mode": "individual"}', INDIVIDUAL),
        ('{"mode": "individual", "quorum": 1}', INDIVIDUAL),
        ('{"mode": "collective", "quorum": 2}', COLLECTIVE),
        ('{"mode": "collective", "quorum": 3}', BodPolicy('collective', 3)),
    ],
)
def test_a_valid_policy_is_read(raw: str, expected: BodPolicy) -> None:
    assert parse_policy(raw) == expected


@pytest.mark.parametrize(
    'raw',
    [
        '',
        '   ',
        'individual',  # not JSON
        '[]',
        '{"mode": "unanimous", "quorum": 2}',
        '{"mode": "individual", "quorum": 2}',  # one reviewer cannot need two
        '{"mode": "collective"}',  # collective without a quorum says nothing
        '{"mode": "collective", "quorum": 1}',  # a quorum of one is individual under another name
        '{"mode": "collective", "quorum": 0}',
        '{"mode": "collective", "quorum": true}',  # a bool is not a count
        '{"mode": "collective", "quorum": "2"}',
        '{"mode": "collective", "quorum": 2.0}',
        '{"mode": "collective", "quorum": 2, "chair": "x"}',  # unknown keys are not ignored
    ],
)
def test_an_unset_or_invalid_policy_means_no_closure_path(raw: str) -> None:
    assert parse_policy(raw) is None


def test_the_policy_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('JUP_LEADERSHIP_BOD_POLICY', raising=False)
    assert configured_policy() is None
    monkeypatch.setenv('JUP_LEADERSHIP_BOD_POLICY', json.dumps({'mode': 'collective', 'quorum': 2}))
    assert configured_policy() == COLLECTIVE


# --- decisions ------------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path):
    """act-1 awaiting BOD closure on evidence revision 1 (version 3); act-2 in progress."""
    from sqlalchemy import create_engine

    from jup.leadership import actions, migrate
    from jup.leadership.evidence import link_evidence, submit_evidence
    from jup.leadership.repository import unit_of_work

    engine = create_engine(f'sqlite:///{tmp_path / "webui.db"}')
    assert migrate.run_leadership_migrations(engine) is True
    for action_id in ('act-1', 'act-2'):
        with unit_of_work(engine) as uow:
            actions.create_action(uow, action_id=action_id, title='t', pic_label='PIC', pic_user_id=PIC, author='imp')
        with unit_of_work(engine) as uow:
            actions.change_state(uow, action_id=action_id, expected_version=1, to_state='in_progress', author=PIC)
    with unit_of_work(engine) as uow:
        submit_evidence(
            uow,
            action_id='act-1',
            expected_version=2,
            actor=PIC,
            item=link_evidence('https://sharepoint.example/ba-1'),
            completion=True,
        )
    yield engine
    engine.dispose()


def _decide(engine, reviewer: str = BOD_A, expected_version: int = 3, policy: BodPolicy = INDIVIDUAL, **kwargs):
    from jup.leadership.closure import decide
    from jup.leadership.repository import unit_of_work

    kwargs.setdefault('action_id', 'act-1')
    if kwargs.get('decision', 'close') != 'reopen':
        kwargs.setdefault('evidence_id', _latest_evidence(engine, kwargs['action_id']))
    kwargs.setdefault('decision', 'close')
    with unit_of_work(engine) as uow:
        return decide(uow, reviewer=reviewer, expected_version=expected_version, policy=policy, **kwargs)


def _latest_evidence(engine, action_id: str = 'act-1') -> str:
    from sqlalchemy import select

    from jup.leadership.models import evidence

    with engine.connect() as connection:
        return connection.execute(
            select(evidence.c.id).where(evidence.c.action_id == action_id).order_by(evidence.c.revision.desc())
        ).scalar()


def _requests(engine, action_id: str = 'act-1') -> list[dict]:
    from sqlalchemy import select

    from jup.leadership.models import closure_request

    with engine.connect() as connection:
        rows = connection.execute(
            select(closure_request)
            .where(closure_request.c.action_id == action_id)
            .order_by(closure_request.c.created_at)
        ).mappings()
        return [dict(row) for row in rows]


def _decisions(engine) -> list[dict]:
    from sqlalchemy import select

    from jup.leadership.models import closure_decision

    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(closure_decision)).mappings()]


def _state(engine, action_id: str = 'act-1') -> tuple[str, int]:
    from jup.leadership.repository import read_action

    row = read_action(engine, action_id)
    return row['state'], row['version']


def _add_evidence(engine, expected_version: int, completion: bool = False, action_id: str = 'act-1'):
    from jup.leadership.evidence import link_evidence, submit_evidence
    from jup.leadership.repository import unit_of_work

    with unit_of_work(engine) as uow:
        return submit_evidence(
            uow,
            action_id=action_id,
            expected_version=expected_version,
            actor=PIC,
            item=link_evidence(f'https://sharepoint.example/ba-{expected_version}'),
            completion=completion,
        )


@needs_runtime
def test_an_individual_bod_reviewer_closes(engine) -> None:
    from jup.leadership.repository import read_events

    decided = _decide(engine)
    assert decided.outcome == 'closed'
    assert _state(engine) == ('closed', 4)
    (request,) = _requests(engine)
    assert request['status'] == 'closed' and request['resolved_at'] is not None
    (decision,) = _decisions(engine)
    assert (decision['decision'], decision['reviewer_user_id']) == ('close', BOD_A)
    assert decision['evidence_id'] == request['evidence_id']
    assert decision['event_id'] == decided.event.event.id
    event = read_events(engine, 'act-1')[-1]
    assert (event.kind, event.author, event.payload['outcome']) == ('bod_decision', BOD_A, 'closed')


@needs_runtime
def test_the_pic_never_reviews_their_own_action(engine) -> None:
    from jup.leadership.closure import OwnerCannotReview

    for decision, extra in (('close', {}), ('return', {'reason': 'x', 'return_to': 'in_progress'})):
        with pytest.raises(OwnerCannotReview):
            _decide(engine, reviewer=PIC, decision=decision, **extra)
    assert _state(engine) == ('awaiting_bod_closure', 3)
    assert _decisions(engine) == []


@needs_runtime
def test_collective_mode_closes_at_the_quorum_of_distinct_reviewers(engine) -> None:
    from jup.leadership.actions import CommandRefused

    first = _decide(engine, policy=COLLECTIVE)
    assert (first.outcome, first.close_votes, first.quorum) == ('vote_recorded', 1, 2)
    assert _state(engine) == ('awaiting_bod_closure', 4)
    assert _requests(engine)[0]['status'] == 'open'

    # The same reviewer twice is still one reviewer.
    with pytest.raises(CommandRefused, match='already'):
        _decide(engine, policy=COLLECTIVE, expected_version=4)

    second = _decide(engine, reviewer=BOD_B, policy=COLLECTIVE, expected_version=4)
    assert (second.outcome, second.close_votes) == ('closed', 2)
    assert _state(engine) == ('closed', 5)
    assert _requests(engine)[0]['status'] == 'closed'
    assert [d['reviewer_user_id'] for d in _decisions(engine)] == [BOD_A, BOD_B]


@needs_runtime
def test_stale_evidence_is_refused_and_the_reviewer_must_look_again(engine) -> None:
    from jup.leadership.closure import StaleEvidence

    seen = _latest_evidence(engine)
    _add_evidence(engine, expected_version=3)  # revision 2 arrives while the request is pending
    with pytest.raises(StaleEvidence):
        _decide(engine, expected_version=4, evidence_id=seen)
    assert _state(engine) == ('awaiting_bod_closure', 4)
    assert _decisions(engine) == []

    assert _decide(engine, expected_version=4).outcome == 'closed'
    assert _decisions(engine)[0]['evidence_id'] == _latest_evidence(engine)


@needs_runtime
def test_a_new_revision_makes_pending_collective_votes_stale(engine) -> None:
    first = _decide(engine, policy=COLLECTIVE)
    assert first.close_votes == 1
    _add_evidence(engine, expected_version=4)

    # BOD_A's vote was on revision 1; it does not count toward revision 2.
    second = _decide(engine, reviewer=BOD_B, policy=COLLECTIVE, expected_version=5)
    assert (second.outcome, second.close_votes) == ('vote_recorded', 1)
    assert _state(engine) == ('awaiting_bod_closure', 6)

    third = _decide(engine, reviewer=BOD_A, policy=COLLECTIVE, expected_version=6)
    assert (third.outcome, third.close_votes) == ('closed', 2)


@needs_runtime
@pytest.mark.parametrize('return_to', ['in_progress', 'blocked'])
def test_returned_evidence_goes_back_to_the_pic_with_a_reason(engine, return_to: str) -> None:
    returned = _decide(engine, decision='return', return_to=return_to, reason='BA is unsigned')
    assert returned.outcome == 'returned'
    assert _state(engine) == (return_to, 4)
    (request,) = _requests(engine)
    assert request['status'] == 'returned'
    assert _decisions(engine)[0]['reason'] == 'BA is unsigned'

    if return_to == 'blocked':
        from jup.leadership.actions import change_state
        from jup.leadership.repository import unit_of_work

        with unit_of_work(engine) as uow:
            change_state(uow, action_id='act-1', expected_version=4, to_state='in_progress', author=PIC)
    version = _state(engine)[1]
    again = _add_evidence(engine, expected_version=version, completion=True)
    assert again.closure_request_id != request['id']
    assert _decide(engine, expected_version=version + 1).outcome == 'closed'
    assert [r['status'] for r in _requests(engine)] == ['returned', 'closed']


@needs_runtime
@pytest.mark.parametrize(
    'extra',
    [
        {'return_to': 'in_progress'},  # no reason
        {'return_to': 'in_progress', 'reason': '   '},
        {'return_to': 'closed', 'reason': 'x'},
        {'return_to': 'not_started', 'reason': 'x'},
        {'reason': 'x'},  # nowhere to return to
    ],
)
def test_a_return_needs_a_reason_and_an_open_state(engine, extra: dict) -> None:
    from jup.leadership.actions import CommandRefused

    with pytest.raises(CommandRefused):
        _decide(engine, decision='return', **extra)
    assert _state(engine) == ('awaiting_bod_closure', 3)


@needs_runtime
def test_a_reopened_action_keeps_its_prior_closure(engine) -> None:
    from jup.leadership.actions import fold_history
    from jup.leadership.repository import read_events

    _decide(engine)
    reopened = _decide(engine, decision='reopen', expected_version=4, reason='offtake cancelled by PGN')
    assert reopened.outcome == 'reopened'
    assert _state(engine) == ('in_progress', 5)
    (request,) = _requests(engine)
    assert request['status'] == 'closed'  # the closure stands in the record
    assert [d['decision'] for d in _decisions(engine)] == ['close', 'reopen']
    history = fold_history(read_events(engine, 'act-1'))
    assert [(h['state_before'], h['state_after']) for h in history[-2:]] == [
        ('awaiting_bod_closure', 'closed'),
        ('closed', 'in_progress'),
    ]


@needs_runtime
def test_reopening_needs_a_reason_and_a_closed_action(engine) -> None:
    from jup.leadership.actions import CommandRefused

    with pytest.raises(CommandRefused):
        _decide(engine, decision='reopen', reason='x')  # not closed
    _decide(engine)
    with pytest.raises(CommandRefused):
        _decide(engine, decision='reopen', expected_version=4)
    assert _state(engine) == ('closed', 4)


@needs_runtime
def test_there_is_nothing_to_close_without_an_open_request(engine) -> None:
    from jup.leadership.actions import CommandRefused

    with pytest.raises(CommandRefused, match='no closure request'):
        _decide(engine, action_id='act-2', expected_version=2, evidence_id=None)
    assert _state(engine, 'act-2') == ('in_progress', 2)


@needs_runtime
def test_an_unknown_decision_is_refused(engine) -> None:
    from jup.leadership.actions import CommandRefused

    with pytest.raises(CommandRefused):
        _decide(engine, decision='approve')


@needs_runtime
def test_a_stale_version_writes_nothing(engine) -> None:
    from jup.leadership.repository import VersionConflict

    with pytest.raises(VersionConflict):
        _decide(engine, expected_version=2)
    assert _state(engine) == ('awaiting_bod_closure', 3)
    assert _decisions(engine) == []


@needs_runtime
def test_a_double_submitted_decision_replays(engine) -> None:
    from jup.leadership.repository import IdempotencyKeyReused

    first = _decide(engine, policy=COLLECTIVE, idempotency_key='k1')
    second = _decide(engine, policy=COLLECTIVE, idempotency_key='k1')
    assert second.replayed is True
    assert (second.decision_id, second.outcome, second.close_votes) == (first.decision_id, 'vote_recorded', 1)
    assert len(_decisions(engine)) == 1
    with pytest.raises(IdempotencyKeyReused):
        _decide(engine, policy=COLLECTIVE, idempotency_key='k1', decision='return', reason='x', return_to='blocked')


@needs_runtime
def test_a_failed_decision_leaves_nothing(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    from jup.leadership import models as module

    def broken(**_: object):
        raise RuntimeError('decision insert failed')

    real_insert = module.closure_decision.insert
    monkeypatch.setattr(module.closure_decision, 'insert', broken, raising=False)
    try:
        with pytest.raises(RuntimeError):
            _decide(engine)
    finally:
        monkeypatch.setattr(module.closure_decision, 'insert', real_insert, raising=False)
    assert _state(engine) == ('awaiting_bod_closure', 3)
    assert _requests(engine)[0]['status'] == 'open'


@needs_runtime
def test_a_reopened_action_cannot_be_reopened_again(engine) -> None:
    from jup.leadership.actions import CommandRefused

    _decide(engine)
    _decide(engine, decision='reopen', expected_version=4, reason='x')
    # Its earlier closure is still on record; that does not make it closed.
    with pytest.raises(CommandRefused, match='only a closed action'):
        _decide(engine, decision='reopen', expected_version=5, reason='again')
    assert _state(engine) == ('in_progress', 5)


@needs_runtime
def test_a_stale_version_conflicts_before_any_state_is_judged(engine) -> None:
    from jup.leadership.repository import VersionConflict

    seen = _latest_evidence(engine)
    _decide(engine, reviewer=BOD_B)  # closed at version 4
    # BOD_A still holds version 3: the answer is "reload", not a refusal about a state never seen.
    with pytest.raises(VersionConflict):
        _decide(engine, expected_version=3, evidence_id=seen)
