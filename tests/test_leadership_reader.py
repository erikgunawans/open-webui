"""The shared reader behind both Ruang Pimpinan views.

It is what the human API serves now and what the assistant's tools will read in P3, so the rules
that make the two agree live here: one action record however many views cite it, variance only
where the comparison is like-for-like, and a source reachable only through a view that declares it.
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from jup.leadership.reader import DatasetUnavailable, load_dataset, read_overview, read_source


@pytest.fixture
def seed_path(fixture_path: Callable[..., Path]) -> Path:
    return fixture_path('leadership', 'illustrative-seed.json')


@pytest.fixture
def dataset(seed_path: Path) -> dict:
    return load_dataset(seed_path)


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / 'dataset.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


# --- Loading ------------------------------------------------------------------------


def test_the_seed_loads_and_stays_illustrative(dataset: dict) -> None:
    assert dataset['data_mode'] == 'illustrative'
    assert dataset['coverage'] == 'partial'


@pytest.mark.parametrize('content', ['', '{', 'null', '[]', '{"schema_version": 1}'])
def test_a_malformed_dataset_is_unavailable_not_empty(tmp_path: Path, content: str) -> None:
    path = tmp_path / 'dataset.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(DatasetUnavailable):
        load_dataset(path)


def test_a_missing_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(DatasetUnavailable):
        load_dataset(tmp_path / 'absent.json')


def test_an_unavailable_message_does_not_carry_the_path(tmp_path: Path) -> None:
    # The message reaches the HTTP response. A filesystem path there tells a reader where the
    # server keeps its data, and nothing they could act on.
    secret = tmp_path / 'secret-mount' / 'absent.json'
    with pytest.raises(DatasetUnavailable) as raised:
        load_dataset(secret)
    assert 'secret-mount' not in str(raised.value)
    assert str(tmp_path) not in str(raised.value)


def test_a_dataset_that_claims_to_be_live_is_refused(tmp_path: Path, seed_path: Path) -> None:
    data = json.loads(seed_path.read_text(encoding='utf-8'))
    data['data_mode'] = 'verified'
    with pytest.raises(DatasetUnavailable):
        load_dataset(_write(tmp_path, data))


# --- The overview -------------------------------------------------------------------


def test_the_board_overview_carries_its_context_and_labels(dataset: dict) -> None:
    overview = read_overview(dataset, 'board')
    assert overview['schema_version'] == 1
    assert overview['data_mode'] == 'illustrative'
    assert overview['coverage'] == 'partial'
    assert overview['revision'] == dataset['revision']
    assert overview['context']['id'] == 'example-board-2026-08'
    assert overview['context']['kind'] == 'source_example'


def test_variance_is_served_only_for_a_like_for_like_comparison(dataset: dict) -> None:
    board = {metric['id']: metric for metric in read_overview(dataset, 'board')['metrics']}
    assert board['example-revenue-ytd']['variance'] == '-14.00'
    assert board['example-net-result-ytd']['variance'] == '-2.25'
    assert board['example-gross-margin-ytd']['variance'] == '-0.9'

    rka = read_overview(dataset, 'rka')['metrics']
    # RKA 2027 compares against a 2026 narrative, not a 2027 actual: nothing to subtract.
    assert [metric['variance'] for metric in rka] == [None, None, None]


def test_a_shared_action_is_one_record_in_both_views(dataset: dict) -> None:
    board = {action['id']: action for action in read_overview(dataset, 'board')['actions']}
    rka = {action['id']: action for action in read_overview(dataset, 'rka')['actions']}
    shared = 'example-action-water'
    assert shared in board and shared in rka
    assert board[shared] == rka[shared]


def test_actions_keep_the_order_the_view_lists_them_in(dataset: dict) -> None:
    ids = [action['id'] for action in read_overview(dataset, 'board')['actions']]
    assert ids == dataset['views']['board']['action_ids']


def test_source_status_survives_the_read(dataset: dict) -> None:
    for action in read_overview(dataset, 'board')['actions']:
        assert action['verification_status'] == 'unverified'
        assert action['history_complete'] is False
    for metric in read_overview(dataset, 'board')['metrics']:
        assert metric['verification_status'] == 'unverified'


def test_module_states_are_all_served(dataset: dict) -> None:
    # The roadmap's discussion modules must not vanish just because their data is missing.
    for view in ('board', 'rka'):
        served = read_overview(dataset, view)['module_states']
        assert served == dataset['views'][view]['module_states']


def test_reading_does_not_mutate_the_dataset(dataset: dict) -> None:
    before = copy.deepcopy(dataset)
    overview = read_overview(dataset, 'board')
    overview['metrics'][0]['label'] = 'changed'
    overview['actions'][0]['title'] = 'changed'
    assert dataset == before


def test_an_unknown_view_is_refused(dataset: dict) -> None:
    with pytest.raises(KeyError):
        read_overview(dataset, 'overview')


# --- Sources ------------------------------------------------------------------------


def test_a_source_the_view_declares_is_returned(dataset: dict) -> None:
    source = read_source(dataset, 'board', 'board-financial')
    assert source is not None
    assert source['physical_slides'] == [4]
    assert source['verification_status'] == 'unverified'


def test_a_source_that_belongs_only_to_the_other_view_is_not_returned(dataset: dict) -> None:
    # Knowing an id is not access: rka-cash is cited only by the RKA view.
    assert read_source(dataset, 'board', 'rka-cash') is None
    assert read_source(dataset, 'rka', 'rka-cash') is not None


def test_a_source_both_views_declare_is_returned_by_either(dataset: dict) -> None:
    assert read_source(dataset, 'board', 'board-directions') is not None
    assert read_source(dataset, 'rka', 'board-directions') is not None


def test_an_unknown_source_is_not_returned(dataset: dict) -> None:
    assert read_source(dataset, 'board', 'nope') is None
    assert read_source(dataset, 'board', '../../etc/passwd') is None
