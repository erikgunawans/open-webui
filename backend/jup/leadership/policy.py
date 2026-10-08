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

Reading is decided here, and so is each P2 capability as its workflow arrives. A capability is
its own exact boolean under `jup.ruang_pimpinan`, and every one of them also needs the read grant
for the view and scope: a capability never opens a view the reader could not see. None of them
follows from a read grant, and none from the admin role.

- `actions.submit`: progress and evidence, on actions whose recorded PIC is the caller (the PIC
  check is the action's own, in `jup.leadership.evidence`).
- `bod.review`: taking part in closure, return and reopening decisions. It opens nothing by itself:
  the BOD policy (`JUP_LEADERSHIP_BOD_POLICY`, read in `jup.leadership.closure`) must also be
  configured, and an action's own PIC never reviews it (both checked in `closure.py`).
- `snapshots.publish`: freezing a view into a meeting draft and publishing it. Publishing also
  needs the publication policy (`JUP_LEADERSHIP_PUBLICATION_POLICY`, in `snapshots.py`).
- `imports.review`: uploading a deck's candidate file, reading the review queue, and accepting,
  linking or rejecting candidates (`jup.leadership.imports`).
- `rapat.write`: writing the Notulen of a Rapat Direksi (`jup.leadership.meetings`), held by the
  Corsec. Reading meetings is the board read grant; writing them is this grant on top of it.
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
            'actions': {'submit': False, 'assign': False},
            'bod': {'review': False},
            'snapshots': {'publish': False},
            'imports': {'review': False},
            'rapat': {'write': False},
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


# Capability keys, as `capabilities.operations` names them, mapped to their place in the grants.
CAPABILITIES: dict[str, tuple[str, str]] = {
    'actions.submit': ('actions', 'submit'),
    # Naming who an action's PIC is. Its own grant: whoever holds it decides who may submit evidence.
    'actions.assign': ('actions', 'assign'),
    'bod.review': ('bod', 'review'),
    'snapshots.publish': ('snapshots', 'publish'),
    'imports.review': ('imports', 'review'),
    'rapat.write': ('rapat', 'write'),
}


def may(permissions: dict[str, Any], capability: str, view: str, scope_id: str) -> bool:
    """True only for an exact boolean grant of `capability`, on top of the read grant."""
    if capability not in CAPABILITIES or not may_read(permissions, view, scope_id):
        return False
    group, key = CAPABILITIES[capability]
    try:
        return permissions['jup']['ruang_pimpinan'][group][key] is True
    except (KeyError, TypeError):
        return False


def allowed_operations(permissions: dict[str, Any], scope_id: str = 'jup-consolidated') -> list[str]:
    """The capabilities this reader holds in at least one view they may read."""
    return [c for c in CAPABILITIES if any(may(permissions, c, view, scope_id) for view in VIEWS)]
