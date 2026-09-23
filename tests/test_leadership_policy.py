"""Who may read a Ruang Pimpinan view.

The policy is default-deny and knows nothing about roles. An app admin is the operating layer for
Portfolio (ADR-0012's single identity), but that says nothing about who sits on the BOD or BOC, so
an `admin` label must never open a leadership view. Only an explicit, exact-boolean group grant
for both the view and the scope does.
"""

import copy

import pytest

from jup.leadership.policy import DEFAULT_PERMISSIONS, allowed_views, may_read

SCOPE = 'jup-consolidated'


def _grants(board: object = False, rka: object = False, scope: object = False) -> dict:
    return {
        'jup': {
            'ruang_pimpinan': {
                'board': {'view': board},
                'rka': {'view': rka},
                'scopes': {'jup_consolidated': scope},
            }
        }
    }


def test_the_defaults_grant_nothing() -> None:
    assert allowed_views(DEFAULT_PERMISSIONS) == []
    assert not may_read(DEFAULT_PERMISSIONS, 'board', SCOPE)
    assert not may_read(DEFAULT_PERMISSIONS, 'rka', SCOPE)


def test_the_defaults_are_all_false_and_complete() -> None:
    grants = DEFAULT_PERMISSIONS['jup']['ruang_pimpinan']
    assert grants == {
        'board': {'view': False},
        'rka': {'view': False},
        'scopes': {'jup_consolidated': False},
    }


@pytest.mark.parametrize('permissions', [{}, {'jup': {}}, {'jup': None}, None, {'role': 'admin'}])
def test_missing_or_role_shaped_permissions_are_denied(permissions: object) -> None:
    assert not may_read(permissions, 'board', SCOPE)  # type: ignore[arg-type]
    assert allowed_views(permissions) == []  # type: ignore[arg-type]


def test_an_admin_label_is_not_a_grant() -> None:
    permissions = {'role': 'admin', **_grants()}
    assert not may_read(permissions, 'board', SCOPE)


def test_a_board_grant_does_not_grant_rka() -> None:
    permissions = _grants(board=True, scope=True)
    assert allowed_views(permissions) == ['board']
    assert may_read(permissions, 'board', SCOPE)
    assert not may_read(permissions, 'rka', SCOPE)


def test_both_views_come_back_in_a_fixed_order() -> None:
    assert allowed_views(_grants(board=True, rka=True, scope=True)) == ['board', 'rka']


def test_a_view_grant_without_the_scope_grant_is_denied() -> None:
    permissions = _grants(board=True, rka=True, scope=False)
    assert allowed_views(permissions) == []
    assert not may_read(permissions, 'board', SCOPE)


@pytest.mark.parametrize('truthy', ['true', 'True', 1, [True], {'value': True}])
def test_only_an_exact_boolean_true_counts(truthy: object) -> None:
    # The host combines group grants with `or`, so a group row holding the string "true" passes
    # straight through to here. Treating it as a grant would let a typo in a group editor open
    # board records.
    assert not may_read(_grants(board=truthy, scope=True), 'board', SCOPE)
    assert not may_read(_grants(board=True, scope=truthy), 'board', SCOPE)


@pytest.mark.parametrize('view', ['Board', 'overview', '', 'board ', None])
def test_an_unsupported_view_is_denied(view: object) -> None:
    assert not may_read(_grants(board=True, rka=True, scope=True), view, SCOPE)  # type: ignore[arg-type]


@pytest.mark.parametrize('scope', ['jup_consolidated', 'JUP-CONSOLIDATED', 'jup-spbg', '', None])
def test_an_unsupported_scope_is_denied(scope: object) -> None:
    assert not may_read(_grants(board=True, rka=True, scope=True), 'board', scope)  # type: ignore[arg-type]


def test_revocation_takes_effect_on_the_next_decision() -> None:
    # Nothing is cached between calls: the next dictionary the host resolves is the whole truth.
    permissions = _grants(board=True, scope=True)
    assert may_read(permissions, 'board', SCOPE)
    revoked = copy.deepcopy(permissions)
    revoked['jup']['ruang_pimpinan']['board']['view'] = False
    assert not may_read(revoked, 'board', SCOPE)
    assert allowed_views(revoked) == []


def test_the_defaults_are_not_mutated_by_a_decision() -> None:
    before = copy.deepcopy(DEFAULT_PERMISSIONS)
    allowed_views(DEFAULT_PERMISSIONS)
    may_read(DEFAULT_PERMISSIONS, 'board', SCOPE)
    assert before == DEFAULT_PERMISSIONS
