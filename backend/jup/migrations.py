"""The alembic revision graph, read without importing the runtime.

This module exists because of one failure mode: a fork migration whose `down_revision`
collides with an upstream one leaves alembic with two heads, migrations run at
config-import time, and the application does not start at all. Not "a feature breaks" —
the process does not come up. It is the cheapest failure to cause during a quarterly
rebase (ADR-0007) and the most expensive to diagnose, because the traceback points at
alembic rather than at the two files that disagree.

The graph is read by parsing each version file's AST rather than by importing it or by
asking alembic. Three reasons, in order of weight:

1. `migrations/env.py` imports `open_webui.env` and the whole model tree, so alembic's own
   `ScriptDirectory` cannot answer this question without the full runtime installed. The
   suite runs under `--only-group dev`, which deliberately omits it.
2. A parse cannot execute a migration, so asking the question is always safe.
3. It works on a tree that is currently broken, which is exactly when it is asked.

`down_revision` is authoritative and the docstring is never consulted:
`d4e5f6a7b8c9`'s `Revises:` line already contradicts its own `down_revision` from a past
hand-fix, and believing the prose there would report a false head.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

_REVISION = 'revision'
_DOWN_REVISION = 'down_revision'


class RevisionError(Exception):
    """A revision file that cannot be read, or a graph that cannot be trusted."""


@dataclass(frozen=True)
class Revision:
    """One migration: what it is called, what it follows, and where it lives."""

    identifier: str
    # Empty for the base revision, one entry normally, several for a merge revision.
    down: tuple[str, ...]
    source: str


def read_revisions(versions_dir: Path | str) -> tuple[Revision, ...]:
    """Read every revision in a versions directory, ordered by filename.

    Args:
        versions_dir: The alembic `versions/` directory holding the migration modules.

    Returns:
        Every revision found, in filename order so the reading never varies.

    Raises:
        RevisionError: The directory is missing, or a file declares no usable `revision`.
    """
    directory = Path(versions_dir)
    if not directory.is_dir():
        raise RevisionError(f'{directory} is not a directory, so the revision graph could not be read')

    revisions = tuple(_read_revision(path) for path in sorted(directory.glob('*.py')))
    if not revisions:
        raise RevisionError(f'{directory} holds no migration files, which is never a healthy alembic tree')
    return revisions


def heads(revisions: tuple[Revision, ...]) -> tuple[str, ...]:
    """The revisions nothing else follows — exactly one in a healthy tree.

    Two heads is the rebase collision this module exists to catch. Zero heads means every
    revision is somebody's parent, which is a cycle.
    """
    claimed = {parent for revision in revisions for parent in revision.down}
    return tuple(revision.identifier for revision in revisions if revision.identifier not in claimed)


def duplicate_identifiers(revisions: tuple[Revision, ...]) -> tuple[str, ...]:
    """Revision ids declared by more than one file.

    Checked before the head count rather than after, because a duplicate id makes the head
    count meaningless: two files claiming one id can hide a head behind the other's parent.
    """
    seen: set[str] = set()
    duplicated: list[str] = []
    for revision in revisions:
        if revision.identifier in seen and revision.identifier not in duplicated:
            duplicated.append(revision.identifier)
        seen.add(revision.identifier)
    return tuple(duplicated)


def dangling_parents(revisions: tuple[Revision, ...]) -> tuple[str, ...]:
    """Parents cited by a `down_revision` that no file in the tree declares.

    The other half of a bad rebase: a revision deleted upstream while a fork revision still
    points at it. Alembic cannot walk the chain, and the application does not start.
    """
    declared = {revision.identifier for revision in revisions}
    cited = {parent for revision in revisions for parent in revision.down}
    return tuple(sorted(cited - declared))


def describe(revisions: tuple[Revision, ...], identifiers: tuple[str, ...]) -> str:
    """Name each of `identifiers` with the file that declares it and what it follows.

    The whole value of this module at the moment it fires is that the message names both
    sides of the collision. "Found 2 head revisions" sends a maintainer to alembic's docs;
    naming the two files and their `down_revision` sends them to the two lines to fix.
    """
    lines = []
    for identifier in identifiers:
        # Every file, not the first: a duplicate id is reported by naming the id once, and
        # the whole value of that report is the several files that claim it.
        declaring = [revision for revision in revisions if revision.identifier == identifier]
        if not declaring:
            lines.append(f'  {identifier} — cited as a parent, but no file declares it')
            continue
        for revision in declaring:
            follows = ', '.join(revision.down) if revision.down else 'nothing (this is the base revision)'
            lines.append(f'  {identifier} — {revision.source}, follows {follows}')
    return '\n'.join(lines)


def _read_revision(path: Path) -> Revision:
    """Parse one migration file's revision identifiers out of its AST."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError) as error:
        raise RevisionError(f'{path.name} could not be parsed: {error}') from error

    assigned = _module_assignments(tree)
    if _REVISION not in assigned:
        raise RevisionError(f'{path.name} declares no `revision`, so it cannot take a place in the graph')

    identifier = assigned[_REVISION]
    if not isinstance(identifier, str) or not identifier:
        raise RevisionError(f'{path.name} declares a `revision` that is not a non-empty string: {identifier!r}')

    return Revision(identifier=identifier, down=_parents(assigned.get(_DOWN_REVISION), path), source=path.name)


def _module_assignments(tree: ast.Module) -> dict[str, object]:
    """Collect module-level constant assignments, annotated or not.

    Upstream uses both `revision = '...'` and `revision: str = '...'`, and a rebase can
    leave either style in the tree, so both have to read the same.
    """
    assigned: dict[str, object] = {}
    for node in tree.body:
        name, value = _assignment(node)
        if name not in (_REVISION, _DOWN_REVISION) or value is None:
            continue
        try:
            assigned[name] = ast.literal_eval(value)
        except ValueError:
            # A computed identifier is not something this module should guess at; leaving
            # it absent surfaces as the clearer "declares no `revision`" refusal below.
            continue
    return assigned


def _assignment(node: ast.stmt) -> tuple[str | None, ast.expr | None]:
    """Reduce a module-level statement to a (name, value) pair, or (None, None)."""
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    return None, None


def _parents(value: object, path: Path) -> tuple[str, ...]:
    """Normalise a `down_revision` to a tuple: absent, one parent, or a merge's several."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)) and all(isinstance(parent, str) for parent in value):
        return tuple(value)
    raise RevisionError(f'{path.name} declares a `down_revision` that is neither a string nor a tuple: {value!r}')
