"""Saving a group in the admin editor keeps permission keys the editor does not know.

`EditGroupModal.svelte` rebuilt a group's `permissions` from the six vendor keys only (workspace,
sharing, access_grants, chat, features, settings) and saved that object whole. A Ruang Pimpinan
grant lives under `jup`, so opening a group and pressing Save with no change deleted it: reproduced
locally 2026-09-24, the board-only reader's capabilities went from Board to `views: []`. Reset to
defaults dropped it the same way.

Nothing fails when this patch is lost: the reader just loses access. This test is what notices.
See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

MODAL = (
    Path(__file__).parent.parent / 'src' / 'lib' / 'components' / 'admin' / 'Users' / 'Groups' / 'EditGroupModal.svelte'
)


def _body(name: str) -> str:
    source = MODAL.read_text(encoding='utf-8')
    match = re.search(rf'const {name} = (?:async )?\(\) => \{{(.*?)\n\t\}};', source, re.S)
    assert match, f'{name}() not found'
    return match.group(1)


def _rebuild(body: str) -> str:
    match = re.search(r'permissions = \{(.*?)\n\t+\};', body, re.S)
    assert match, 'the permissions rebuild was not found'
    return match.group(1)


def test_opening_a_group_carries_unknown_permission_keys() -> None:
    rebuild = _rebuild(_body('init'))
    assert rebuild.lstrip().startswith('...loadedPermissions,'), 'init() drops keys it does not know, such as jup'


def test_reset_to_defaults_carries_unknown_permission_keys() -> None:
    rebuild = _rebuild(_body('resetToDefaultsHandler'))
    assert rebuild.lstrip().startswith('...permissions,'), 'reset drops keys it does not know, such as jup'
