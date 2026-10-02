"""Title groups (D3): the one place contract access comes from.

Every user holds at most one title — Direksi, Legal, Manager or Staff — chosen in Admin → Pengguna.
Each title is a managed group whose `jup.contracts` grants are fixed here, so the access a title
gives is decided in code and not by whoever last opened the group editor. Choosing a title moves
the user between the four groups, leaving exactly one.

A managed group is recognised by `group.data[MARKER]`, never by its name: a name is free text any
admin can type. If two groups carry the same marker the oldest wins, so a duplicate created by a
race is harmless and visible in the group list.

Admin is not a title (ADR-0012: the admin role is the operating layer, not the board). An admin
without a title sees no contract card.
"""

import copy
from dataclasses import dataclass
from typing import Any, Iterable

MARKER = 'jup_contract_title'

TITLES: tuple[str, ...] = ('direksi', 'legal', 'manager', 'staff')

LABELS: dict[str, str] = {
    'direksi': 'Direksi',
    'legal': 'Legal',
    'manager': 'Manager',
    'staff': 'Staff',
}

# Every grant under `jup.contracts`, in the order the access module reads them.
# `cards`: a card without its money fields. `money`: value, payment, penalties, damages caps.
# `fulltext`: every contract's OCR pages and PDF. `names`: individual parties unmasked (D2).
# `review`: the Kartu Kontrak review queue.
CONTRACT_GRANTS: tuple[str, ...] = ('cards', 'money', 'fulltext', 'names', 'review')

_HELD: dict[str, frozenset[str]] = {
    'staff': frozenset({'cards'}),
    'manager': frozenset({'cards', 'money'}),
    'legal': frozenset({'cards', 'money', 'fulltext', 'names', 'review'}),
    'direksi': frozenset({'cards', 'money', 'fulltext', 'names'}),
}

DEFAULT_PERMISSIONS: dict[str, Any] = {'jup': {'contracts': {grant: False for grant in CONTRACT_GRANTS}}}


def _check(title: str) -> None:
    if title not in TITLES:
        raise ValueError(f'{title!r} is not a contract title; the titles are {", ".join(TITLES)}')


def grants(title: str) -> dict[str, Any]:
    """The group permissions a title carries: every contract grant, each an explicit boolean."""
    _check(title)
    return {'jup': {'contracts': {grant: grant in _HELD[title] for grant in CONTRACT_GRANTS}}}


def group_form(title: str) -> dict[str, Any]:
    """What a missing managed group is created with."""
    _check(title)
    return {
        'name': f'Kontrak — {LABELS[title]}',
        'description': (
            f'Kelompok jabatan "{LABELS[title]}" untuk basis pengetahuan kontrak. '
            'Dikelola dari kolom Jabatan di Admin → Pengguna; hak aksesnya ditetapkan oleh aplikasi.'
        ),
        'permissions': grants(title),
        'data': {MARKER: title},
    }


def with_grants(permissions: dict[str, Any] | None, title: str) -> dict[str, Any] | None:
    """`permissions` with its `jup.contracts` subtree reset to the title's, or None if it already matches.

    Only that subtree is touched: a managed group may carry other grants an admin gave it.
    """
    expected = grants(title)['jup']['contracts']
    current = permissions or {}
    if isinstance(current.get('jup'), dict) and current['jup'].get('contracts') == expected:
        return None
    repaired = copy.deepcopy(current)
    if not isinstance(repaired.get('jup'), dict):
        repaired['jup'] = {}
    repaired['jup']['contracts'] = dict(expected)
    return repaired


def managed_groups(groups: Iterable[Any]) -> dict[str, str]:
    """Title → group id, for the groups that carry a valid marker; the oldest group wins a title."""
    found: dict[str, Any] = {}
    for group in groups:
        title = (group.data or {}).get(MARKER) if isinstance(group.data, dict) else None
        if title not in TITLES:
            continue
        if title not in found or group.created_at < found[title].created_at:
            found[title] = group
    return {title: group.id for title, group in found.items()}


def titles_held(member_group_ids: Iterable[str], managed: dict[str, str]) -> list[str]:
    """The titles a user holds, in title order. More than one means someone edited a group by hand."""
    member = set(member_group_ids)
    return [title for title in TITLES if managed.get(title) in member]


@dataclass(frozen=True)
class Move:
    """The membership changes that leave a user with exactly the target title."""

    add: str | None
    remove: tuple[str, ...]


def plan_move(held: Iterable[str], target: str | None, managed: dict[str, str]) -> Move:
    """Group ids to add and remove so the user ends with `target` alone (or no title for None)."""
    if target is not None:
        _check(target)
    held = list(held)
    remove = tuple(managed[title] for title in TITLES if title in held and title != target and title in managed)
    add = managed[target] if target is not None and target not in held else None
    return Move(add=add, remove=remove)
