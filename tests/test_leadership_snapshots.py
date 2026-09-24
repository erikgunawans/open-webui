"""Meeting snapshots and RKA baselines (P2 T5, SNAP-01).

The policy parser and the freezing rules are pure and always run. The records run against a real
SQLite database brought to the leadership head by the migration graph, so they need the runtime.
The HTTP half (publication capability, revocation) is in `test_jup_leadership_endpoint.py`.
"""

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jup.leadership.snapshots import PublicationPolicy, parse_publication_policy

_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ('alembic', 'sqlalchemy'))
needs_runtime = pytest.mark.skipif(not _RUNTIME, reason='the runtime tree is not installed')

SECRETARY = 'sec-1'
PUBLISHER = 'pub-1'
OPEN = PublicationPolicy(four_eyes=False)
FOUR_EYES = PublicationPolicy(four_eyes=True)


# --- the publication policy -----------------------------------------------------------------


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [('{"four_eyes": true}', FOUR_EYES), ('{"four_eyes": false}', OPEN)],
)
def test_a_valid_publication_policy_is_read(raw: str, expected: PublicationPolicy) -> None:
    assert parse_publication_policy(raw) == expected


@pytest.mark.parametrize(
    'raw', ['', ' ', '{}', 'true', '{"four_eyes": 1}', '{"four_eyes": "true"}', '{"four_eyes": true, "x": 1}']
)
def test_an_unset_or_invalid_publication_policy_means_everything_stays_draft(raw: str) -> None:
    assert parse_publication_policy(raw) is None


# --- snapshots ------------------------------------------------------------------------------


@pytest.fixture
def dataset(fixture_path: Callable[..., Path]) -> dict:
    from jup.leadership.reader import load_dataset

    return load_dataset(fixture_path('leadership', 'illustrative-seed.json'))


@pytest.fixture
def engine(tmp_path: Path, leadership_db_url: str):
    """One recorded action sharing an id with the seed's gas action, in progress (version 2)."""
    from sqlalchemy import create_engine

    from jup.leadership import actions, migrate
    from jup.leadership.repository import unit_of_work

    engine = create_engine(leadership_db_url)
    assert migrate.run_leadership_migrations(engine) is True
    with unit_of_work(engine) as uow:
        actions.create_action(
            uow,
            action_id='example-action-gas',
            title='Finalisasi alokasi gas',
            pic_label='Pak Deco',
            pic_user_id='pic-1',
            author='imp',
        )
    with unit_of_work(engine) as uow:
        actions.change_state(
            uow, action_id='example-action-gas', expected_version=1, to_state='in_progress', author='pic-1'
        )
    yield engine
    engine.dispose()


def _draft(engine, dataset, view: str = 'board', author: str = SECRETARY):
    from jup.leadership.snapshots import create_draft, view_content

    with engine.begin() as connection:
        content = view_content(connection, dataset, view)
        return create_draft(
            connection,
            view=view,
            meeting_label='RUPS Sep 2026',
            meeting_date='2026-09-28',
            content=content,
            author=author,
        )


def _publish(engine, version, publisher: str = PUBLISHER, policy=OPEN):
    from jup.leadership.snapshots import publish

    with engine.begin() as connection:
        return publish(
            connection,
            snapshot_id=version.snapshot_id,
            expected_version=version.version,
            content_hash=version.content_hash,
            publisher=publisher,
            policy=policy,
        )


def _versions(engine, snapshot_id: str):
    from jup.leadership.snapshots import read_versions

    with engine.connect() as connection:
        return read_versions(connection, snapshot_id)


@needs_runtime
def test_a_draft_freezes_the_view_with_a_content_hash(engine, dataset) -> None:
    import hashlib

    draft = _draft(engine, dataset)
    assert (draft.version, draft.state, draft.change_kind, draft.previous_version_id) == (1, 'draft', 'draft', None)
    assert draft.content_hash == hashlib.sha256(draft.content_bytes).hexdigest()
    content = json.loads(draft.content_bytes)
    assert content['view'] == 'board' and content['data_mode'] == 'illustrative'
    assert [a['id'] for a in content['actions']] == dataset['views']['board']['action_ids']
    gas = content['actions'][0]
    # A recorded action is frozen at its event version; a seed-only one says it has no record.
    assert (gas['record']['version'], gas['record']['state']) == (2, 'in_progress')
    assert content['actions'][1]['record'] is None
    # Cited sources travel with the snapshot, so it stands alone.
    assert {s['id'] for s in content['sources']} >= set(dataset['views']['board']['context']['source_ids'])


@needs_runtime
def test_closing_a_current_action_leaves_the_old_snapshot_hash_unchanged(engine, dataset) -> None:
    from sqlalchemy import update

    from jup.leadership.models import action

    draft = _draft(engine, dataset)
    published = _publish(engine, draft)
    with engine.begin() as connection:
        connection.execute(update(action).where(action.c.id == 'example-action-gas').values(state='closed', version=9))
    later = _draft(engine, dataset)
    assert later.content_hash != draft.content_hash
    stored = {v.id: v for v in _versions(engine, draft.snapshot_id)}
    assert stored[draft.id].content_hash == draft.content_hash
    assert stored[published.id].content_bytes == draft.content_bytes


@needs_runtime
def test_publishing_repeats_the_draft_as_a_new_version(engine, dataset) -> None:
    draft = _draft(engine, dataset)
    published = _publish(engine, draft)
    assert (published.version, published.state, published.change_kind) == (2, 'published', 'publication')
    assert published.previous_version_id == draft.id
    assert (published.content_hash, published.content_bytes) == (draft.content_hash, draft.content_bytes)
    assert [v.state for v in _versions(engine, draft.snapshot_id)] == ['draft', 'published']


@needs_runtime
def test_publication_needs_a_policy(engine, dataset) -> None:
    from jup.leadership.snapshots import PublicationNotConfigured

    draft = _draft(engine, dataset)
    with pytest.raises(PublicationNotConfigured):
        _publish(engine, draft, policy=None)
    assert [v.state for v in _versions(engine, draft.snapshot_id)] == ['draft']


@needs_runtime
def test_four_eyes_keeps_the_author_from_publishing_their_own_draft(engine, dataset) -> None:
    from jup.leadership.snapshots import SnapshotRefused

    draft = _draft(engine, dataset)
    with pytest.raises(SnapshotRefused, match='four-eyes'):
        _publish(engine, draft, publisher=SECRETARY, policy=FOUR_EYES)
    assert _publish(engine, draft, publisher=SECRETARY, policy=OPEN).state == 'published'


@needs_runtime
def test_publishing_names_the_hash_reviewed(engine, dataset) -> None:
    from dataclasses import replace

    from jup.leadership.snapshots import SnapshotConflict

    draft = _draft(engine, dataset)
    with pytest.raises(SnapshotConflict):
        _publish(engine, replace(draft, content_hash='0' * 64))
    with pytest.raises(SnapshotConflict):
        _publish(engine, replace(draft, version=2))
    assert len(_versions(engine, draft.snapshot_id)) == 1


@needs_runtime
def test_only_a_draft_is_published(engine, dataset) -> None:
    from jup.leadership.snapshots import SnapshotRefused

    published = _publish(engine, _draft(engine, dataset))
    with pytest.raises(SnapshotRefused, match='draft'):
        _publish(engine, published)


@needs_runtime
def test_a_correction_is_a_linked_replacement_that_is_published_again(engine, dataset) -> None:
    from jup.leadership.snapshots import latest_published, revise

    draft = _draft(engine, dataset)
    first = _publish(engine, draft)
    corrected_content = json.loads(first.content_bytes) | {'correction_note': 'margin restated'}
    with engine.begin() as connection:
        correction = revise(
            connection,
            snapshot_id=draft.snapshot_id,
            expected_version=2,
            content=corrected_content,
            author=SECRETARY,
        )
    assert (correction.version, correction.state, correction.change_kind) == (3, 'draft', 'correction')
    assert correction.previous_version_id == first.id
    with engine.connect() as connection:
        # Until the correction is published, the record of the meeting is still the first one.
        assert latest_published(connection, draft.snapshot_id).id == first.id
    second = _publish(engine, correction)
    with engine.connect() as connection:
        assert latest_published(connection, draft.snapshot_id).id == second.id
    stored = {v.id: v for v in _versions(engine, draft.snapshot_id)}
    assert stored[first.id].content_hash == draft.content_hash  # the replaced record is kept


@needs_runtime
def test_an_unpublished_draft_cannot_pass_as_published(engine, dataset) -> None:
    from sqlalchemy import update

    from jup.leadership.models import snapshot_version
    from jup.leadership.snapshots import IntegrityFailure, latest_published

    draft = _draft(engine, dataset)
    with engine.connect() as connection:
        assert latest_published(connection, draft.snapshot_id) is None
    # A row flipped to 'published' outside the publication path is refused on read, not served.
    with engine.begin() as connection:
        connection.execute(update(snapshot_version).where(snapshot_version.c.id == draft.id).values(state='published'))
    with engine.connect() as connection, pytest.raises(IntegrityFailure):
        latest_published(connection, draft.snapshot_id)


@needs_runtime
def test_altered_content_fails_its_hash_on_read(engine, dataset) -> None:
    from sqlalchemy import update

    from jup.leadership.models import snapshot_version
    from jup.leadership.snapshots import IntegrityFailure

    published = _publish(engine, _draft(engine, dataset))
    with engine.begin() as connection:
        connection.execute(
            update(snapshot_version)
            .where(snapshot_version.c.id == published.id)
            .values(content=published.content_bytes.decode().replace('illustrative', 'live'))
        )
    with pytest.raises(IntegrityFailure):
        _versions(engine, published.snapshot_id)


@needs_runtime
def test_a_draft_holds_no_float(engine, dataset) -> None:
    from jup.leadership.snapshots import create_draft

    with engine.begin() as connection, pytest.raises(ValueError, match='float'):
        create_draft(
            connection, view='board', meeting_label='x', meeting_date=None, content={'margin': 0.1}, author=SECRETARY
        )


@needs_runtime
def test_a_snapshot_is_of_one_known_view(engine) -> None:
    from jup.leadership.snapshots import create_draft

    with engine.begin() as connection, pytest.raises(ValueError):
        create_draft(connection, view='overview', meeting_label='x', meeting_date=None, content={}, author=SECRETARY)


# --- RKA baselines --------------------------------------------------------------------------

RKA_2026 = {'lines': [{'id': 'revenue', 'amount_idr_billion': '144.0'}]}


def _record(engine, kind: str = 'baseline', **overrides):
    from jup.leadership.snapshots import record_rka

    fields = {
        'kind': kind,
        'label': 'RKA 2026',
        'period_start': '2026-01-01',
        'period_end': '2026-12-31',
        'content': RKA_2026,
        'author': SECRETARY,
        'approved_by': 'rups' if kind != 'forecast' else None,
        'approved_at': 1_780_000_000_000 if kind != 'forecast' else None,
    }
    fields.update(overrides)
    with engine.begin() as connection:
        return record_rka(connection, **fields)


def _baseline_row(engine, record_id: str) -> dict:
    from sqlalchemy import select

    from jup.leadership.models import rka_baseline

    with engine.connect() as connection:
        return dict(connection.execute(select(rka_baseline).where(rka_baseline.c.id == record_id)).mappings().one())


@needs_runtime
def test_an_approved_baseline_is_its_own_record(engine) -> None:
    baseline = _record(engine)
    row = _baseline_row(engine, baseline.id)
    assert (row['record_kind'], row['period_start'], row['period_end']) == ('baseline', '2026-01-01', '2026-12-31')
    assert json.loads(row['content']) == RKA_2026


@needs_runtime
def test_a_forecast_write_cannot_touch_a_baseline(engine) -> None:
    from jup.leadership.snapshots import SnapshotRefused

    baseline = _record(engine)
    before = _baseline_row(engine, baseline.id)
    forecast = _record(engine, 'forecast', content={'lines': [{'id': 'revenue', 'amount_idr_billion': '120.0'}]})
    assert forecast.id != baseline.id
    # A forecast cannot claim to replace the approved RKA.
    with pytest.raises(SnapshotRefused):
        _record(engine, 'forecast', supersedes_id=baseline.id)
    assert _baseline_row(engine, baseline.id) == before


@needs_runtime
def test_a_revision_supersedes_a_baseline_as_a_new_record(engine) -> None:
    baseline = _record(engine)
    revision = _record(engine, 'revision', supersedes_id=baseline.id, label='RKA-P 2026')
    assert _baseline_row(engine, revision.id)['supersedes_id'] == baseline.id
    assert _baseline_row(engine, baseline.id)['content'] == json.dumps(RKA_2026, sort_keys=True, separators=(',', ':'))


@needs_runtime
@pytest.mark.parametrize(
    ('kind', 'overrides'),
    [
        ('baseline', {'approved_by': None}),  # an approved record names who approved it
        ('revision', {}),  # a revision names what it revises
        ('revision', {'supersedes_id': 'no-such-record'}),
        ('forecast', {'approved_by': 'rups'}),  # a forecast is never approved RKA
        ('budget', {}),
        ('baseline', {'period_start': '2026-12-31', 'period_end': '2026-01-01'}),
        ('baseline', {'period_start': '2026-13-01'}),
    ],
)
def test_an_rka_record_must_say_what_it_is(engine, kind: str, overrides: dict) -> None:
    from jup.leadership.snapshots import SnapshotRefused

    with pytest.raises((SnapshotRefused, ValueError)):
        _record(engine, kind, **overrides)


@needs_runtime
def test_an_altered_rka_record_is_refused_on_read(engine) -> None:
    from sqlalchemy import update

    from jup.leadership.models import rka_baseline
    from jup.leadership.snapshots import IntegrityFailure, list_rka

    baseline = _record(engine)
    with engine.connect() as connection:
        assert [r['id'] for r in list_rka(connection)] == [baseline.id]
    with engine.begin() as connection:
        connection.execute(update(rka_baseline).where(rka_baseline.c.id == baseline.id).values(content='{"lines":[]}'))
    with engine.connect() as connection, pytest.raises(IntegrityFailure):
        list_rka(connection)
