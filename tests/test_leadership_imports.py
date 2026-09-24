"""Reviewed imports (P2 T6, ACT-01, DATA-01 P2 part, DATA-02).

The candidate-file checks are pure and always run. Ingestion and review run against a real SQLite
database brought to the leadership head by the migration graph, so they need the runtime. The HTTP
half is in `test_jup_leadership_endpoint.py`.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from jup.leadership.imports import InvalidCandidates, parse_candidates

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')

REVIEWER = 'rev-1'
UPLOADER = 'sec-1'

GAS = {
    'key': 's12-r1',
    'slide': '12',
    'external_id': 'GAS-01',
    'title': 'Finalisasi alokasi gas',
    'owner_label': 'Pak Deco',
    'due': {'precision': 'month', 'value': '2026-09'},
    'state': 'in_progress',
    'progress_summary': 'Konsep PJBG disetujui',
    'source_metadata': {'slide_hidden': True, 'draft_note': 'angka sementara', 'old_slide': '9'},
    'missing': {},
}
WATER = {
    'key': 's14-r2',
    'slide': '14',
    'external_id': 'WTR-02',
    'title': 'Kajian air baku',
    'owner_label': None,
    'due': None,
    'state': None,
    'progress_summary': None,
    'source_metadata': {},
    'missing': {
        'owner_label': 'PIC not named on the slide',
        'due': 'deck says TBD',
        'state': 'no status column',
        'progress_summary': 'blank cell',
    },
}


def _file(*candidates: dict, document: str = 'BOD-2026-09.pptx', meeting_date: str = '2026-09-28') -> bytes:
    body = {
        'schema_version': 1,
        'source_document': document,
        'meeting_date': meeting_date,
        'candidates': [copy.deepcopy(c) for c in candidates] or [copy.deepcopy(GAS), copy.deepcopy(WATER)],
    }
    return json.dumps(body).encode('utf-8')


# --- the candidate file ---------------------------------------------------------------------


def test_a_well_formed_file_parses() -> None:
    parsed = parse_candidates(_file())
    assert parsed.source_document == 'BOD-2026-09.pptx'
    assert [c['key'] for c in parsed.candidates] == ['s12-r1', 's14-r2']


def _broken(**changes) -> dict:
    candidate = copy.deepcopy(GAS)
    candidate.update(changes)
    return candidate


@pytest.mark.parametrize(
    'raw',
    [
        b'not json',
        b'[]',
        json.dumps({'schema_version': 2, 'source_document': 'x', 'meeting_date': None, 'candidates': []}).encode(),
        json.dumps({'schema_version': 1, 'source_document': ' ', 'meeting_date': None, 'candidates': [GAS]}).encode(),
        _file(_broken(due=None)),  # a null with no reason
        _file(_broken(missing={'due': 'x'})),  # a reason for a value that is present
        _file(_broken(title=None, missing={'title': 'x'})),  # the title is never optional
        _file(_broken(external_id=None)),  # nothing to match or record a reference by
        _file(_broken(due={'precision': 'day', 'value': '2026-09-30'})),
        _file(_broken(state='completed')),  # not the action lifecycle's vocabulary
        _file(_broken(progress_pct=0.4)),  # unknown field (and a float)
        _file(_broken(source_metadata={'ratio': 0.5})),  # a float anywhere
        _file(GAS, _broken(key='s12-r1', slide='13', external_id='GAS-09')),  # a repeated key
        _file(GAS, _broken(key='s13-r1', slide='13')),  # the same external id twice in one deck
        _file(_broken(slide='')),
    ],
)
def test_a_malformed_candidate_file_is_refused_whole(raw: bytes) -> None:
    with pytest.raises(InvalidCandidates):
        parse_candidates(raw)


# --- ingestion and review -------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path, leadership_db_url: str):
    from sqlalchemy import create_engine

    from jup.leadership import migrate

    engine = create_engine(leadership_db_url)
    assert migrate.run_leadership_migrations(engine) is True
    yield engine
    engine.dispose()


def _ingest(engine, raw: bytes | None = None, filename: str = 'bod-2026-09.json'):
    from jup.leadership.imports import ingest

    with engine.begin() as connection:
        return ingest(connection, raw or _file(), filename=filename, uploader=UPLOADER)


def _candidates(engine, batch_id: str) -> dict[str, dict]:
    from jup.leadership.imports import read_batch

    with engine.connect() as connection:
        return {c['candidate_key']: c for c in read_batch(connection, batch_id)['candidates']}


def _review(engine, candidate_id: str, decision: str = 'accept', reviewer: str = REVIEWER, **kwargs):
    from jup.leadership.imports import review_candidate

    return review_candidate(engine, candidate_id=candidate_id, decision=decision, reviewer=reviewer, **kwargs)


def _actions(engine) -> list[dict]:
    from sqlalchemy import select

    from jup.leadership.models import action

    with engine.connect() as connection:
        return [dict(r) for r in connection.execute(select(action).order_by(action.c.created_at)).mappings()]


@needs_runtime
def test_everything_arrives_as_an_unverified_candidate(engine) -> None:
    batch = _ingest(engine)
    assert batch.created is True
    candidates = _candidates(engine, batch.id)
    assert {c['match_kind'] for c in candidates.values()} == {'new'}
    assert {c['verification'] for c in candidates.values()} == {'unverified'}
    assert {c['review_state'] for c in candidates.values()} == {'pending'}
    assert _actions(engine) == []  # nothing is written to the records until a review


@needs_runtime
def test_reimporting_the_same_file_is_a_no_op(engine) -> None:
    first = _ingest(engine)
    second = _ingest(engine, filename='renamed.json')
    assert (second.id, second.created) == (first.id, False)
    assert len(_candidates(engine, first.id)) == 2


@needs_runtime
def test_draft_hidden_and_old_slide_metadata_survives(engine) -> None:
    batch = _ingest(engine)
    gas = _candidates(engine, batch.id)['s12-r1']
    assert gas['payload']['source_metadata'] == GAS['source_metadata']


@needs_runtime
def test_a_missing_value_stays_null_with_its_reason(engine) -> None:
    batch = _ingest(engine)
    water = _candidates(engine, batch.id)['s14-r2']
    assert water['payload']['due'] is None
    assert water['payload']['missing']['due'] == 'deck says TBD'
    # Accepting it cannot invent an owner: a new action needs its PIC label.
    from jup.leadership.imports import ImportRefused

    with pytest.raises(ImportRefused, match='owner'):
        _review(engine, water['id'])


@needs_runtime
def test_accepting_a_new_candidate_creates_the_action_and_its_reference(engine) -> None:
    from sqlalchemy import select

    from jup.leadership.models import external_ref
    from jup.leadership.repository import read_events

    batch = _ingest(engine)
    gas = _candidates(engine, batch.id)['s12-r1']
    reviewed = _review(engine, gas['id'])
    (created,) = _actions(engine)
    assert reviewed['action_id'] == created['id']
    assert (created['title'], created['pic_label'], created['state']) == (GAS['title'], 'Pak Deco', 'not_started')
    assert (created['current_due'], created['current_due_precision']) == ('2026-09', 'month')
    assert created['pic_user_id'] is None  # the PIC identity mapping is not decided
    event = read_events(engine, created['id'])[0]
    assert (event.kind, event.author) == ('created', REVIEWER)
    assert 'BOD-2026-09.pptx' in event.reason
    with engine.connect() as connection:
        ref = connection.execute(select(external_ref)).mappings().one()
    assert (ref['source_document'], ref['slide'], ref['external_id'], ref['confirmed_by']) == (
        'BOD-2026-09.pptx',
        '12',
        'GAS-01',
        REVIEWER,
    )
    reread = _candidates(engine, batch.id)['s12-r1']
    assert (reread['review_state'], reread['verification']) == ('accepted', 'verified')


@needs_runtime
def test_a_later_deck_matches_through_the_reviewed_reference_and_never_duplicates(engine) -> None:
    first = _ingest(engine)
    _review(engine, _candidates(engine, first.id)['s12-r1']['id'])
    later = _ingest(engine, _file(_broken(slide='7', key='s7-r1'), document='BOD-2026-10.pptx'))
    gas = _candidates(engine, later.id)['s7-r1']
    assert gas['match_kind'] == 'external_ref'
    assert gas['matched_action_id'] == _actions(engine)[0]['id']
    _review(engine, gas['id'])
    assert len(_actions(engine)) == 1


@needs_runtime
def test_an_action_absent_from_a_later_deck_stays_open(engine) -> None:
    first = _ingest(engine)
    _review(engine, _candidates(engine, first.id)['s12-r1']['id'])
    later = _ingest(engine, _file(_broken(key='x', slide='3', external_id='NEW-01', title='Lain'), document='B2.pptx'))
    for candidate in _candidates(engine, later.id).values():
        _review(engine, candidate['id'], 'reject')
    assert [a['state'] for a in _actions(engine)] == ['not_started']


@needs_runtime
def test_a_conflicting_value_is_a_conflict_record_not_an_overwrite(engine) -> None:
    first = _ingest(engine)
    _review(engine, _candidates(engine, first.id)['s12-r1']['id'])
    before = _actions(engine)
    later = _ingest(
        engine,
        _file(
            _broken(key='s7-r1', slide='7', due={'precision': 'month', 'value': '2026-12'}, owner_label='Bu Rina'),
            document='BOD-2026-10.pptx',
        ),
    )
    gas = _candidates(engine, later.id)['s7-r1']
    assert gas['match_kind'] == 'conflict'
    assert gas['conflict'] == {
        'due': {
            'recorded': {'precision': 'month', 'value': '2026-09'},
            'candidate': {'precision': 'month', 'value': '2026-12'},
        },
        'owner_label': {'recorded': 'Pak Deco', 'candidate': 'Bu Rina'},
    }
    # Acknowledging it keeps the recorded values; a change goes through the action's own commands.
    _review(engine, gas['id'])
    assert _actions(engine) == before
    assert _candidates(engine, later.id)['s7-r1']['review_state'] == 'acknowledged'


@needs_runtime
def test_a_new_candidate_can_be_linked_to_an_existing_action(engine) -> None:
    from jup.leadership.imports import ImportRefused

    first = _ingest(engine)
    _review(engine, _candidates(engine, first.id)['s12-r1']['id'])
    action_id = _actions(engine)[0]['id']
    # The same work under a different id in a later deck: the reviewer links it rather than duplicating.
    later = _ingest(engine, _file(_broken(key='s2', slide='2', external_id='GAS-X'), document='B2.pptx'))
    candidate = _candidates(engine, later.id)['s2']
    with pytest.raises(ImportRefused):
        _review(engine, candidate['id'], 'link', action_id='no-such-action')
    _review(engine, candidate['id'], 'link', action_id=action_id)
    assert len(_actions(engine)) == 1
    third = _ingest(engine, _file(_broken(key='s5', slide='5', external_id='GAS-X'), document='B3.pptx'))
    assert _candidates(engine, third.id)['s5']['matched_action_id'] == action_id


@needs_runtime
def test_two_open_batches_cannot_both_create_the_same_action(engine) -> None:
    from jup.leadership.imports import ImportRefused

    first = _ingest(engine)
    second = _ingest(engine, _file(_broken(key='s9', slide='9'), document='BOD-2026-09-rev.pptx'))
    _review(engine, _candidates(engine, first.id)['s12-r1']['id'])
    with pytest.raises(ImportRefused, match='link'):
        _review(engine, _candidates(engine, second.id)['s9']['id'])
    assert len(_actions(engine)) == 1


@needs_runtime
def test_a_candidate_is_reviewed_once(engine) -> None:
    from jup.leadership.imports import AlreadyReviewed

    batch = _ingest(engine)
    gas = _candidates(engine, batch.id)['s12-r1']
    _review(engine, gas['id'], 'reject')
    with pytest.raises(AlreadyReviewed):
        _review(engine, gas['id'])
    assert _actions(engine) == []


@needs_runtime
def test_a_batch_is_reviewed_when_no_candidate_is_pending(engine) -> None:
    from jup.leadership.imports import read_batch

    batch = _ingest(engine)
    candidates = _candidates(engine, batch.id)
    _review(engine, candidates['s12-r1']['id'])
    with engine.connect() as connection:
        assert read_batch(connection, batch.id)['status'] == 'open'
    _review(engine, candidates['s14-r2']['id'], 'reject')
    with engine.connect() as connection:
        assert read_batch(connection, batch.id)['status'] == 'reviewed'


@needs_runtime
@pytest.mark.parametrize(('decision', 'extra'), [('approve', {}), ('link', {})])
def test_an_unknown_or_incomplete_decision_is_refused(engine, decision: str, extra: dict) -> None:
    from jup.leadership.imports import ImportRefused

    batch = _ingest(engine)
    with pytest.raises(ImportRefused):
        _review(engine, _candidates(engine, batch.id)['s12-r1']['id'], decision, **extra)


@needs_runtime
def test_a_failed_review_leaves_nothing(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    from jup.leadership import models

    batch = _ingest(engine)
    gas = _candidates(engine, batch.id)['s12-r1']

    def broken(**_: object):
        raise RuntimeError('reference insert failed')

    real_insert = models.external_ref.insert
    monkeypatch.setattr(models.external_ref, 'insert', broken, raising=False)
    try:
        with pytest.raises(RuntimeError):
            _review(engine, gas['id'])
    finally:
        monkeypatch.setattr(models.external_ref, 'insert', real_insert, raising=False)
    assert _actions(engine) == []
    assert _candidates(engine, batch.id)['s12-r1']['review_state'] == 'pending'


@needs_runtime
def test_a_value_the_later_deck_leaves_out_is_missing_not_a_conflict(engine) -> None:
    first = _ingest(engine)
    _review(engine, _candidates(engine, first.id)['s12-r1']['id'])
    silent = _broken(
        key='s7-r1',
        slide='7',
        owner_label=None,
        due=None,
        missing={'owner_label': 'not on this slide', 'due': 'not on this slide'},
    )
    later = _ingest(engine, _file(silent, document='BOD-2026-10.pptx'))
    gas = _candidates(engine, later.id)['s7-r1']
    assert (gas['match_kind'], gas['conflict']) == ('external_ref', None)
