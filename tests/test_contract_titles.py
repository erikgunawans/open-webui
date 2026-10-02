"""The contract title groups (D3): four managed groups, one title per user, grants fixed in code."""

from types import SimpleNamespace

import pytest

from jup.contracts import titles


def _group(group_id: str, title: str | None, created_at: int = 1, permissions: dict | None = None) -> SimpleNamespace:
    data = {'config': {'share': True}}
    if title is not None:
        data[titles.MARKER] = title
    return SimpleNamespace(id=group_id, data=data, created_at=created_at, permissions=permissions or {})


def test_the_titles_are_the_four_decided_on_in_order() -> None:
    assert titles.TITLES == ('direksi', 'legal', 'manager', 'staff')


@pytest.mark.parametrize(
    ('title', 'expected'),
    [
        ('staff', {'cards'}),
        ('manager', {'cards', 'money'}),
        ('legal', {'cards', 'money', 'fulltext', 'names', 'review'}),
        ('direksi', {'cards', 'money', 'fulltext', 'names'}),
    ],
)
def test_each_title_grants_exactly_what_d3_says(title: str, expected: set[str]) -> None:
    grants = titles.grants(title)['jup']['contracts']
    assert {key for key, value in grants.items() if value is True} == expected
    # Every other key is an explicit False, so the group editor shows the whole set.
    assert all(value is True or value is False for value in grants.values())
    assert set(grants) == set(titles.CONTRACT_GRANTS)


def test_direksi_cannot_review_and_admin_is_not_a_title() -> None:
    assert titles.grants('direksi')['jup']['contracts']['review'] is False
    assert 'admin' not in titles.TITLES
    with pytest.raises(ValueError):
        titles.grants('admin')


def test_a_group_form_carries_the_marker_and_the_grants() -> None:
    form = titles.group_form('legal')
    assert form['name'] == 'Kontrak — Legal'
    assert form['data'][titles.MARKER] == 'legal'
    assert form['permissions'] == titles.grants('legal')


def test_managed_groups_are_found_by_marker_and_the_oldest_wins() -> None:
    groups = [
        _group('g-new-legal', 'legal', created_at=9),
        _group('g-legal', 'legal', created_at=2),
        _group('g-staff', 'staff'),
        _group('g-plain', None),
        _group('g-bogus', 'boss'),
    ]
    assert titles.managed_groups(groups) == {'legal': 'g-legal', 'staff': 'g-staff'}


def test_a_group_without_data_is_not_managed() -> None:
    assert titles.managed_groups([SimpleNamespace(id='g', data=None, created_at=1)]) == {}


def test_titles_held_reads_membership_in_title_order() -> None:
    managed = {'legal': 'g-legal', 'staff': 'g-staff', 'direksi': 'g-dir'}
    assert titles.titles_held({'g-staff', 'g-legal', 'g-other'}, managed) == ['legal', 'staff']
    assert titles.titles_held({'g-other'}, managed) == []


def test_a_move_leaves_exactly_one_title() -> None:
    managed = {'direksi': 'd', 'legal': 'l', 'manager': 'm', 'staff': 's'}
    move = titles.plan_move(['legal', 'staff'], 'manager', managed)
    assert move == titles.Move(add='m', remove=('l', 's'))


def test_moving_to_the_title_already_held_alone_changes_nothing() -> None:
    managed = {'direksi': 'd', 'legal': 'l', 'manager': 'm', 'staff': 's'}
    assert titles.plan_move(['staff'], 'staff', managed) == titles.Move(add=None, remove=())


def test_clearing_the_title_removes_every_one() -> None:
    managed = {'direksi': 'd', 'legal': 'l', 'manager': 'm', 'staff': 's'}
    assert titles.plan_move(['direksi', 'staff'], None, managed) == titles.Move(add=None, remove=('d', 's'))


def test_an_unknown_title_is_refused() -> None:
    with pytest.raises(ValueError):
        titles.plan_move([], 'admin', {'staff': 's'})


def test_grants_drift_is_detected_only_in_the_contracts_subtree() -> None:
    other = {'jup': {'kb': {'submit': True}, 'contracts': titles.grants('staff')['jup']['contracts']}}
    assert titles.with_grants(other, 'staff') is None
    drifted = {'jup': {'kb': {'submit': True}, 'contracts': {'cards': True, 'money': True}}}
    repaired = titles.with_grants(drifted, 'staff')
    assert repaired['jup']['contracts'] == titles.grants('staff')['jup']['contracts']
    assert repaired['jup']['kb'] == {'submit': True}
    # The input is not mutated.
    assert drifted['jup']['contracts'] == {'cards': True, 'money': True}
