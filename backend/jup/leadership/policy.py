"""Who may read a Ruang Pimpinan view: a pure, default-deny predicate.

The input is the permission dictionary the host resolves from the reader's group memberships
(`open_webui.utils.access_control.get_permissions`, seeded with `DEFAULT_PERMISSIONS`). It is
never a claim the request makes about itself.

There is deliberately no role in here. Portfolio treats `admin` as the operating layer, and that
is right for Portfolio; it says nothing about who sits on the BOD or the BOC, so being an app
admin grants no leadership view. A reader needs an explicit grant for the view *and* for the
scope, each an exact boolean `True`. The host combines group grants with `or`, so a group row
holding `"true"` or `1` arrives here unchanged; counting it would let a typo in a group editor
open board records.

This module decides reading only. Submitting evidence, BOD closure and report publication are
separate capabilities that arrive with the workflows that need them (P2), and none of them follows
from a read grant.
"""

from typing import Any

# The workspaces a reader can be granted, in the order the section offers them. Board opens first
# for a reader granted both.
VIEWS: tuple[str, ...] = ('board', 'rka')

# The only reporting scope P1 knows. The grant key uses an underscore because group permission
# keys are identifiers; the scope id the API speaks keeps its hyphen.
SCOPES: dict[str, str] = {'jup-consolidated': 'jup_consolidated'}

DEFAULT_PERMISSIONS: dict[str, Any] = {
    'jup': {
        'ruang_pimpinan': {
            'board': {'view': False},
            'rka': {'view': False},
            'scopes': {'jup_consolidated': False},
        }
    }
}


def may_read(permissions: dict[str, Any], view: str, scope_id: str) -> bool:
    """True only for an exact boolean grant of both `view` and `scope_id`."""
    if view not in VIEWS or scope_id not in SCOPES:
        return False
    try:
        grants = permissions['jup']['ruang_pimpinan']
        return grants[view]['view'] is True and grants['scopes'][SCOPES[scope_id]] is True
    except (KeyError, TypeError):
        return False


def allowed_views(permissions: dict[str, Any], scope_id: str = 'jup-consolidated') -> list[str]:
    """The views this reader may open for `scope_id`, in section order."""
    return [view for view in VIEWS if may_read(permissions, view, scope_id)]
