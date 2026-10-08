"""Who may read a Ruang Pimpinan view.

The policy is default-deny and knows nothing about roles. An app admin is the operating layer for
Portfolio (ADR-0012's single identity), but that says nothing about who sits on the BOD or BOC, so
an `admin` label must never open a leadership view. Only an explicit, exact-boolean group grant
for both the view and the scope does.
"""

import copy

import pytest

from jup.leadership.policy import DEFAULT_PERMISSIONS, allowed_operations, allowed_views, may, may_read

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
        'actions': {'submit': False, 'assign': False},
        'bod': {'review': False},
        'snapshots': {'publish': False},
        'imports': {'review': False},
        'rapat': {'write': False},
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


# --- Capabilities (P2) ----------------------------------------------------------------


def _with(board: bool = True, submit: object = True, scope: bool = True) -> dict:
    return {
        'jup': {
            'ruang_pimpinan': {
                'board': {'view': board},
                'rka': {'view': False},
                'scopes': {'jup_consolidated': scope},
                'actions': {'submit': submit},
            }
        }
    }


def test_submit_needs_its_own_grant_and_the_read_grant() -> None:
    assert may(_with(), 'actions.submit', 'board', SCOPE)
    assert not may(_with(submit=False), 'actions.submit', 'board', SCOPE)
    # A capability never opens a view the reader cannot read.
    assert not may(_with(board=False), 'actions.submit', 'board', SCOPE)
    assert not may(_with(scope=False), 'actions.submit', 'board', SCOPE)
    assert not may(_with(), 'actions.submit', 'rka', SCOPE)


@pytest.mark.parametrize('truthy', ['true', 1, 'yes', {'x': 1}])
def test_only_a_boolean_true_grants_submit(truthy: object) -> None:
    assert not may(_with(submit=truthy), 'actions.submit', 'board', SCOPE)


def test_unknown_capabilities_and_the_defaults_grant_nothing() -> None:
    assert not may(_with(), 'bod.review', 'board', SCOPE)
    assert not may(DEFAULT_PERMISSIONS, 'actions.submit', 'board', SCOPE)
    assert allowed_operations(DEFAULT_PERMISSIONS) == []
    assert allowed_operations(_with()) == ['actions.submit']
    assert allowed_operations(_with(board=False)) == []


def test_bod_review_needs_its_own_grant_and_the_read_grant() -> None:
    def _bod(review: object = True, board: bool = True) -> dict:
        grants = _with(board=board, submit=False)
        grants['jup']['ruang_pimpinan']['bod'] = {'review': review}
        return grants

    assert may(_bod(), 'bod.review', 'board', SCOPE)
    assert not may(_bod(review=False), 'bod.review', 'board', SCOPE)
    assert not may(_bod(review='true'), 'bod.review', 'board', SCOPE)
    assert not may(_bod(board=False), 'bod.review', 'board', SCOPE)
    # Neither capability implies the other.
    assert not may(_bod(), 'actions.submit', 'board', SCOPE)
    assert not may(_with(), 'bod.review', 'board', SCOPE)
    assert allowed_operations(_bod()) == ['bod.review']


def test_rapat_write_needs_its_own_grant_and_the_board_read_grant() -> None:
    def _corsec(write: object = True, board: bool = True, scope: bool = True) -> dict:
        grants = _with(board=board, scope=scope, submit=False)
        grants['jup']['ruang_pimpinan']['rapat'] = {'write': write}
        return grants

    assert may(_corsec(), 'rapat.write', 'board', SCOPE)
    assert not may(_corsec(write=False), 'rapat.write', 'board', SCOPE)
    assert not may(_corsec(write='true'), 'rapat.write', 'board', SCOPE)
    # Writing meetings never opens a view the reader cannot read.
    assert not may(_corsec(board=False), 'rapat.write', 'board', SCOPE)
    assert not may(_corsec(scope=False), 'rapat.write', 'board', SCOPE)
    # The board read grant alone writes nothing.
    assert 'rapat.write' not in allowed_operations(_with(submit=False))
    assert allowed_operations(_corsec()) == ['rapat.write']
