"""Derive the Strategy KB's partner and gate claims from `records/`, and check them.

Ticket #9, which is story 17 of #1: *"the dashboard reads the same files the board pack is
built from, so the two can never disagree."* It did not. `records/` was read by the
portfolio projection and by nothing else, while partner and gate state also lived in
`kb/partners.md`, `kb/gas.md` and `kb/governance.md`. They agreed because someone typed the
same thing twice.

That matters more than ordinary duplication because `kb/partners.md` is loaded **whole** by
the deployed strategy assistant. A drift there is not a stale document; it is what a
commissioner is told when they ask where PGN stands.

Three mechanisms, in descending order of strength:

1. **Generate.** The partner state table and the stage ladder line in `kb/partners.md` are
   rendered from `records/engagements/`. Everything outside the marked regions is
   untouched, byte for byte, so the strategic argument survives regeneration.
2. **Refuse a second home for the vocabulary.** A stage claim outside a generated region is
   drift by construction, whether or not it happens to be right today, because nothing
   holds it to the records. The check names it.
3. **Check what cannot be generated.** `kb/gas.md` and `kb/governance.md` argue in prose
   that the 5 mmscfd allocation is unsecured. Prose cannot be rendered from a record, but
   the claim underneath it can be tested against one — in both directions, so that removing
   the caveat fails as loudly as contradicting it.

Run it:

    python -m jup.kb_sync --jup-root ~/jup            # write
    python -m jup.kb_sync --jup-root ~/jup --check    # report drift, exit 1
"""

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from jup.portfolio import GATES, STAGE_LABELS, STAGES, Engagement, Portfolio, RecordError, project_portfolio

# Machine markers for the regions this module owns. HTML comments because markdown has no
# native way to say "a program wrote this"; they render as nothing, and the note between
# them tells a human editor the same thing in prose.
#
# The name is part of the contract: a region is found by name, so reordering the file or
# adding new regions never makes the generator write to the wrong place.
_BEGIN = '<!-- BEGIN generated:{name} -->'
_END = '<!-- END generated:{name} -->'

_PARTNER_STATE = 'partner-state'
_STAGE_LADDER = 'stage-ladder'

# Said inside the region rather than only in a commit message, because the person most
# likely to hand-edit a generated table is the one who never reads the generator.
_NOTE = '*Generated from `records/engagements/` by `jup.kb_sync`. Edits here are overwritten; edit the record instead.*'

# The claim `kb/gas.md` and `kb/governance.md` both rest on, matched loosely enough to
# survive rewording of the sentence around it and tightly enough to mean only one thing.
# Checked in both directions: contradicting it fails, and so does quietly deleting it.
_ALLOCATION_UNSECURED = re.compile(r'allocation is\s+\*{0,2}not\s+secured', re.IGNORECASE)

# Files whose gate claims are checked rather than generated, and the pillar each speaks for.
_GATE_CLAIM_FILES: tuple[str, ...] = ('gas.md', 'governance.md')
_GAS_PILLAR = 'gas'

# Reported in drift messages so the fix is a path someone can open, not a record id.
_ENGAGEMENTS_DIR = 'records/engagements'


class KbSyncError(Exception):
    """The KB tree is not shaped the way this module needs. Names the path."""


@dataclass(frozen=True)
class Drift:
    """One disagreement between `records/` and `kb/`, named precisely enough to fix.

    `path` and `field` mirror `RecordError`'s contract deliberately: every refusal in this
    system says which file and which field, because a governance check that reports only
    "out of date" sends someone to read four documents looking for the difference.
    """

    path: Path
    field: str
    problem: str

    def __str__(self) -> str:
        return f'{self.path}: {self.field}: {self.problem}'


def render_stage_ladder() -> str:
    """The ladder as one line of prose, from `STAGE_LABELS` rather than a second copy.

    `kb/partners.md` states the ladder in words directly above the table. Left by hand it is
    a copy of the vocabulary that a rename would silently strand, which is the same class of
    duplication this ticket exists to remove — one rung lower down.
    """
    return '**' + ' → '.join(STAGE_LABELS[stage] for stage in STAGES) + '.**'


def render_partner_state(engagements: Sequence[Engagement]) -> str:
    """The partner state table, one row per Engagement record.

    One row per *record*, not per counterparty: the 5 mmscfd allocation is a single
    engagement facing SKK Migas and PGN/Pertagas at once, and splitting it in the table
    would reintroduce exactly the duplication ADR-0008 removed from the records.

    The Evidence column is not decoration. `artefact` is mandatory on an Engagement, so
    every generated row cites the document its rung stands on, and a reader can tell a rung
    with a filed document from one placed on somebody's account without leaving the table.
    """
    header = '| Pillar | Counterparty | What for | Stage | Evidence |\n|---|---|---|---|---|'
    if not engagements:
        return f'{header}\n| — | — | *No engagement record is filed.* | — | — |'
    rows = '\n'.join(
        '| {pillar} | {counterparty} | {purpose} | **{stage}** | `{artefact}` |'.format(
            pillar=_pillar_label(engagement.pillar),
            counterparty=' · '.join(f'**{name}**' for name in engagement.counterparty),
            purpose=engagement.purpose,
            stage=engagement.stage_label,
            artefact=engagement.artefact,
        )
        for engagement in engagements
    )
    return f'{header}\n{rows}'


def _pillar_label(pillar: str | None) -> str:
    """A pillar slug written for a reader, or an em dash when the record names none.

    Derived rather than mapped. A lookup table here would be a second vocabulary to keep in
    step with the records — the precise problem one directory up — and a pillar is a free
    string in the schema, so any map would need a fallback that eventually does this anyway.
    """
    if pillar is None:
        return '—'
    return pillar.replace('-', ' ').capitalize()


def sync_partners(text: str, engagements: Sequence[Engagement]) -> str:
    """Return `partners.md` with both generated regions refreshed and nothing else changed.

    Pure over its arguments, so the check mode and the write mode cannot disagree about what
    the file should say: one renders and compares, the other renders and writes.
    """
    text = _replace_region(text, _STAGE_LADDER, render_stage_ladder())
    return _replace_region(text, _PARTNER_STATE, f'{render_partner_state(engagements)}\n\n{_NOTE}')


def _replace_region(text: str, name: str, body: str) -> str:
    """Swap one named region's body, leaving every byte outside it alone.

    A missing region raises rather than appending. Silently adding a region would put a
    generated table wherever the file happened to end, which in a document that argues a
    case is never where it belongs.
    """
    begin, end = _BEGIN.format(name=name), _END.format(name=name)
    start, stop = text.find(begin), text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise KbSyncError(f'no generated:{name} region found — expected {begin} ... {end}')
    return f'{text[: start + len(begin)]}\n{body}\n{text[stop:]}'


def _region_body(text: str, name: str) -> str:
    """The current contents of a named region, stripped of its surrounding blank lines."""
    begin, end = _BEGIN.format(name=name), _END.format(name=name)
    start, stop = text.find(begin), text.find(end)
    if start == -1 or stop == -1 or stop < start:
        raise KbSyncError(f'no generated:{name} region found — expected {begin} ... {end}')
    return text[start + len(begin) : stop].strip('\n')


def _outside_regions(text: str) -> str:
    """Everything the generator does not own, with each region blanked out in place.

    Blanked rather than removed so that line numbers still mean something when a drift is
    reported against this text.
    """
    for name in (_PARTNER_STATE, _STAGE_LADDER):
        begin, end = _BEGIN.format(name=name), _END.format(name=name)
        start, stop = text.find(begin), text.find(end)
        if start == -1 or stop == -1 or stop < start:
            continue
        blanked = '\n' * text.count('\n', start, stop)
        text = f'{text[:start]}{blanked}{text[stop + len(end) :]}'
    return text


_EMPHASIS = re.compile(r'[*_`]+')
_STAGE_LABEL_TEXTS = frozenset(label.casefold() for label in STAGE_LABELS.values())


def _stage_claims_outside_regions(path: Path, text: str) -> list[Drift]:
    """Refuse a stage-ladder label used as a table cell anywhere the generator does not own.

    Scoped to table cells on purpose. The ladder is also *described* in prose — "No contact →
    Contacted → ..." is the definition, and banning the words outright would refuse the
    sentence that teaches a reader what the table means. A cell, by contrast, is a claim
    about a named counterparty, and a claim nothing holds to a record is drift already: it
    is correct today only by coincidence, and nothing will say when that stops being true.

    The remedy is always the same and is worth stating in the message, because the obvious
    fix — deleting the row — is the wrong one.
    """
    drifts: list[Drift] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue
        for cell in stripped.strip('|').split('|'):
            plain = _EMPHASIS.sub('', cell).strip()
            if plain.casefold() in _STAGE_LABEL_TEXTS:
                drifts.append(
                    Drift(
                        path,
                        f'line {number}',
                        f'states the rung {plain!r} in a table outside the generated region, where nothing '
                        f'holds it to a record — file an engagement record for this counterparty so the row '
                        f'is generated, or drop the stage claim',
                    )
                )
    return drifts


def _recorded_counterparties_outside_regions(
    path: Path,
    text: str,
    engagements: Iterable[Engagement],
) -> list[Drift]:
    """Refuse a counterparty that has a record but is still listed by hand.

    This is the check that makes filing a record *move* the row rather than duplicate it.
    Without it the generated table and a hand-written one would both name PGN, and the two
    would disagree the first time either was edited — the original failure, restored inside
    the file that was supposed to end it.

    Table rows only, for the same reason the stage check is: "The critical one" argues its
    case about SKK Migas and PGN/Pertagas by name, and a check that refused a counterparty's
    name in prose would refuse the strategic argument the file exists to make.
    """
    drifts: list[Drift] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue
        plain = _EMPHASIS.sub('', stripped).casefold()
        for engagement in engagements:
            for name in engagement.counterparty:
                if name.casefold() in plain:
                    drifts.append(
                        Drift(
                            path,
                            f'line {number}',
                            f'names {name!r} in a table outside the generated region, but '
                            f'{engagement.source} already records that engagement — remove the '
                            f'hand-written row; the generated table carries it',
                        )
                    )
    return drifts


def _gas_g1_passed(portfolio: Portfolio) -> bool:
    """Whether any gas-pillar project holds a passing G1 assessment.

    The single fact the prose claims in `kb/gas.md` and `kb/governance.md` rest on. Read
    through `current_gate`, which is derived from the assessments on every read (ADR-0003),
    so this cannot be answered by a status field somebody forgot to update.
    """
    return any(
        project.pillar == _GAS_PILLAR
        and project.current_gate is not None
        and GATES.index(project.current_gate) >= GATES.index('G1')
        for project in portfolio.projects
    )


def _gate_claims(kb_dir: Path, portfolio: Portfolio) -> list[Drift]:
    """Check the prose gate claims that cannot be generated, in both directions.

    Both directions is the whole point. Checking only that the caveat is absent once a gate
    passes would let someone delete "the allocation is not secured" today, while it is still
    unsecured, and the check would applaud. A governance caveat is as much a claim as the
    thing it qualifies, so its disappearance is drift too.
    """
    passed = _gas_g1_passed(portfolio)
    drifts: list[Drift] = []
    for name in _GATE_CLAIM_FILES:
        path = kb_dir / name
        if not path.is_file():
            raise KbSyncError(f'expected a Strategy KB file at {path}')
        present = bool(_ALLOCATION_UNSECURED.search(path.read_text(encoding='utf-8')))
        if passed and present:
            drifts.append(
                Drift(
                    path,
                    'gate G1',
                    'says the 5 mmscfd allocation is not secured, but a gas-pillar project now holds a '
                    'passing G1 assessment in records/gate-assessments/',
                )
            )
        elif not passed and not present:
            drifts.append(
                Drift(
                    path,
                    'gate G1',
                    'no longer says the 5 mmscfd allocation is not secured, and no gas-pillar project '
                    'holds a passing G1 — the caveat is still true and removing it is itself the drift',
                )
            )
    return drifts


# The generated table's columns, in order, named for the Engagement field each carries. Used
# only to report *which* field drifted: a check that says a table is stale leaves someone
# diffing five columns by eye, which is how a governance gate turns into a nuisance people
# regenerate past without reading.
_STATE_COLUMNS: tuple[str, ...] = ('pillar', 'counterparty', 'purpose', 'stage', 'artefact')


def _table_rows(body: str) -> list[tuple[str, ...]]:
    """The data rows of a markdown table, as tuples of stripped cells.

    Header and separator rows are dropped by shape rather than by position, so a region a
    human has reflowed still parses.
    """
    rows: list[tuple[str, ...]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue
        cells = tuple(cell.strip() for cell in stripped.strip('|').split('|'))
        if all(set(cell) <= {'-', ':'} and cell for cell in cells):
            continue
        rows.append(cells)
    return rows


def _state_table_drift(
    partners: Path,
    actual: str,
    engagements: Sequence[Engagement],
) -> list[Drift]:
    """Name the record and the field behind a stale partner table, not just the table.

    Matched on the counterparty cell rather than on row order, because inserting a record
    shifts every row below it and a positional diff would report the whole table as changed
    when one line moved.
    """
    expected_rows = {row[1]: row for row in _table_rows(render_partner_state(engagements))[1:]}
    actual_rows = {row[1]: row for row in _table_rows(actual)[1:] if len(row) == len(_STATE_COLUMNS)}
    by_counterparty = {
        ' · '.join(f'**{name}**' for name in engagement.counterparty): engagement for engagement in engagements
    }

    drifts: list[Drift] = []
    for key, expected_row in expected_rows.items():
        record = Path(_ENGAGEMENTS_DIR) / by_counterparty[key].source
        actual_row = actual_rows.get(key)
        if actual_row is None:
            drifts.append(Drift(partners, 'generated:partner-state', f'has no row for the record {record}'))
            continue
        for column, field in enumerate(_STATE_COLUMNS):
            if actual_row[column] != expected_row[column]:
                drifts.append(
                    Drift(
                        partners,
                        field,
                        f'reads {actual_row[column]!r}, but {record} records {expected_row[column]!r} — '
                        f'regenerate with `python -m jup.kb_sync`',
                    )
                )
    for key in actual_rows.keys() - expected_rows.keys():
        drifts.append(
            Drift(
                partners,
                'generated:partner-state',
                f'carries a row for {key!r}, for which there is no engagement record',
            )
        )
    if not drifts:
        drifts.append(
            Drift(
                partners,
                'generated:partner-state',
                'disagrees with records/engagements/ outside the table rows — regenerate with `python -m jup.kb_sync`',
            )
        )
    return drifts


def check_tree(jup_root: Path | str) -> list[Drift]:
    """Every disagreement between `records/` and `kb/` in a JUP tree, in reporting order.

    Returns rather than raises, so a caller reports all of them at once. Being told about
    one stale table, fixing it, and being told about the next is how a check trains people
    to distrust it.
    """
    root = Path(jup_root)
    kb_dir, partners = _kb_paths(root)
    portfolio = project_portfolio(root / 'records', root)
    engagements = portfolio.engagements

    text = partners.read_text(encoding='utf-8')
    drifts: list[Drift] = []

    expected = f'{render_partner_state(engagements)}\n\n{_NOTE}'
    actual = _region_body(text, _PARTNER_STATE)
    if actual != expected:
        drifts.extend(_state_table_drift(partners, actual, engagements))
    if _region_body(text, _STAGE_LADDER) != render_stage_ladder():
        drifts.append(
            Drift(
                partners,
                f'generated:{_STAGE_LADDER}',
                'disagrees with the STAGE_LABELS ladder — regenerate with `python -m jup.kb_sync`',
            )
        )

    outside = _outside_regions(text)
    drifts.extend(_stage_claims_outside_regions(partners, outside))
    drifts.extend(_recorded_counterparties_outside_regions(partners, outside, engagements))
    drifts.extend(_gate_claims(kb_dir, portfolio))
    return drifts


def sync_tree(jup_root: Path | str) -> bool:
    """Regenerate the owned regions in place. True when the file changed.

    Only the regions. A rewrite of the whole file from a template would take the strategic
    argument — the channel narrative, "The critical one" — with it, and that argument is the
    reason anyone reads `partners.md` at all.
    """
    root = Path(jup_root)
    _, partners = _kb_paths(root)
    portfolio = project_portfolio(root / 'records', root)

    before = partners.read_text(encoding='utf-8')
    after = sync_partners(before, portfolio.engagements)
    if after == before:
        return False
    partners.write_text(after, encoding='utf-8')
    return True


def _kb_paths(root: Path) -> tuple[Path, Path]:
    """The `kb/` directory and `partners.md` within it, refusing a tree missing either."""
    kb_dir = root / 'kb'
    if not kb_dir.is_dir():
        raise KbSyncError(f'no kb/ directory at {kb_dir}')
    partners = kb_dir / 'partners.md'
    if not partners.is_file():
        raise KbSyncError(f'no partner map at {partners}')
    return kb_dir, partners


def main(argv: Sequence[str] | None = None) -> int:
    """Write or check, and say which records disagree. Exit 1 on drift, 2 on a bad tree.

    The two non-zero codes are kept apart because they mean opposite things to CI: drift is
    a document someone must update, and a malformed tree is a mount or a checkout that never
    arrived. Collapsing them turns a broken runner into a governance alarm.
    """
    parser = argparse.ArgumentParser(prog='jup.kb_sync', description=__doc__.splitlines()[0])
    parser.add_argument('--jup-root', required=True, type=Path, help='the JUP working tree holding records/ and kb/')
    parser.add_argument('--check', action='store_true', help='report drift and exit non-zero; write nothing')
    args = parser.parse_args(argv)
    root = args.jup_root.expanduser()

    try:
        if args.check:
            drifts = check_tree(root)
            for drift in drifts:
                print(f'drift: {drift}', file=sys.stderr)
            if drifts:
                print(f'\n{len(drifts)} disagreement(s) between records/ and kb/.', file=sys.stderr)
                return 1
            print('kb/ agrees with records/.')
            return 0
        changed = sync_tree(root)
        print('kb/partners.md regenerated.' if changed else 'kb/partners.md already current.')
        return 0
    except (KbSyncError, RecordError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
