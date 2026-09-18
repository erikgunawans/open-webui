"""The JUP portfolio projection: gate assessment records in, domain objects out.

ADR-0003 is the rule this module exists to enforce — gate state is a set of assessments,
not a status field. A project's current gate is derived on every read and has no setter,
so a board cannot forget that it stopped a project in August, or why.

ADR-0004 puts those records in markdown under `~/jup` rather than in our own database, so
this module's whole job is to read a directory and refuse anything it cannot vouch for.
"""

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml

GATES: tuple[str, ...] = ('G1', 'G2', 'G3', 'G4')
VERDICTS: tuple[str, ...] = ('pass', 'fail')

# The Engagement Stage ladder (ADR-0008), lowest rung first. It replaces the informal
# vocabulary in `~/jup/kb/partners.md` — Initiate, Follow-up, Strengthen — in which two
# rungs differed in tone rather than in stage and none said what would advance them. Each
# rung here requires a document to stand on, exactly as a gate does.
STAGES: tuple[str, ...] = ('no-contact', 'contacted', 'in-discussion', 'written-intent', 'executed')

# How each rung is written for a reader. The record holds the slug so that renaming a label
# is a presentation change and never a data migration.
STAGE_LABELS: dict[str, str] = {
    'no-contact': 'No contact',
    'contacted': 'Contacted',
    'in-discussion': 'In discussion',
    'written-intent': 'Written intent',
    'executed': 'Executed',
}

# ADR-0009: there is no field for likelihood, probability of closing, expected close date
# or confidence — in *any* record, at any depth. The ADR predicts its own violation ("the
# next engineer will read its absence as an oversight and add one"), so the schema refuses
# the key rather than ignoring it. Matched as substrings because `win_probability` and
# `probability_pct` are the same forecast wearing a longer name.
#
# `certainty` is deliberately absent from this list: Certainty Tier (D11) is the legitimate
# concept that labels a figure's basis, and banning it would refuse the very field that
# keeps FAKTA and POTENSI apart.
_BANNED_KEY_FRAGMENTS: tuple[str, ...] = (
    'likelihood',
    'probability',
    'confidence',
    'expected_close',
    'expected_closing',
    'close_date',
    'closing_date',
)

# The three certainty tiers (D11), strongest basis first. A figure states which of these it
# rests on, or it is not surfaced at all: "mixing these is how boards get misled" is the
# decision verbatim, and a figure with no stated basis is the easiest way to mix them.
TIERS: tuple[str, ...] = ('FAKTA', 'POTENSI', 'ILUSTRATIF')

TIER_LABELS: dict[str, str] = {
    'FAKTA': 'Tier 1 · FAKTA',
    'POTENSI': 'Tier 2 · POTENSI',
    'ILUSTRATIF': 'Tier 3 · ILUSTRATIF',
}

# What each tier is, in the words of the decision, so a reader never has to have read it.
TIER_MEANINGS: dict[str, str] = {
    'FAKTA': 'Feasibility economics — NPV, IRR and payback from the business plan.',
    'POTENSI': 'Top-line revenue potential. Never margin: B-to-G prices are government-set.',
    'ILUSTRATIF': 'Order-of-magnitude sizing from capacity targets and unit costs.',
}

# POTENSI is revenue, never margin (D11). A POTENSI figure labelled NPV, margin or profit is
# the precise misreading the tier exists to prevent — a revenue potential dressed as money
# the company would keep — so the label is refused rather than rendered with a caveat.
# Both languages: these records are written by people who work in Bahasa and in English.
_MARGIN_WORDS: tuple[str, ...] = (
    'margin',
    'marjin',
    'profit',
    'laba',
    'keuntungan',
    'npv',
    'irr',
    'ebitda',
    'payback',
)

# Named Non-Coverage: what each view does NOT prove, published beside the view itself.
#
# Held here rather than written into the page so that there is one source of truth and so
# that it can be tested. A non-coverage statement that lives only in markup is one nobody
# notices going stale, and a clean dashboard mistaken for a safe portfolio is the specific
# failure this system exists to prevent.
PORTFOLIO_NON_COVERAGE: tuple[str, ...] = (
    'This shows what was assessed, not whether the assessment was right. It cannot detect a '
    'record that is well-formed and wrong.',
    'A project with no assessment has not been evaluated. It has not passed, and it has not failed.',
    'Current Gate says a gate was passed on the day it was signed. It is not a statement about the project today.',
    'Figures carry the basis they rest on and are never combined across bases (D11). Nothing here totals a portfolio.',
)

ENGAGEMENT_NON_COVERAGE: tuple[str, ...] = (
    'An engagement sits on the rung its artefact evidences. This states where it stands — never '
    'whether it will close (ADR-0009).',
    "A rung records a document, not a counterparty's intent. Judgement about intent stays with "
    'the Director and outside this system.',
)

_PROJECTS_SUBDIR = 'projects'
_ASSESSMENTS_SUBDIR = 'gate-assessments'
_ENGAGEMENTS_SUBDIR = 'engagements'
_DELIMITER = '---'


class RecordError(Exception):
    """A record that cannot be trusted. Names the file and the field.

    Raised rather than skipped. A governance dashboard that quietly drops a record it
    could not parse renders confident blank space exactly where a refusal belongs, which
    is the failure mode fail-closed discipline exists to prevent.
    """

    def __init__(self, path: Path, field: str, problem: str) -> None:
        self.path = Path(path)
        self.field = field
        super().__init__(f'{self.path.name}: {field}: {problem}')


@dataclass(frozen=True)
class EvidenceItem:
    """One requirement a gate asked for, and whether the record says it was met.

    `satisfied` is recorded, never inferred. A citation — an artefact path or an
    Engagement id — is mandatory in both directions: a satisfied requirement must say what
    satisfies it, and an unsatisfied one must say where the evidence is expected to come
    from. A requirement with neither is an assertion, and an assertion is what this
    projection exists to refuse.

    The Engagement is cited by id and never embedded (ADR-0008). Resolving that id against
    the Engagement records is ticket #5's job; this module only holds the citation.
    """

    requirement: str
    satisfied: bool
    artefact: str | None
    engagement: str | None


@dataclass(frozen=True)
class Figure:
    """A number the dashboard surfaces, inseparable from the basis it rests on (D11).

    `value` is held as the string the record wrote. Parsing it into a number would invite
    the dashboard to add two of them up, and the one arithmetic this system must never do
    is arithmetic across tiers — which is exactly what "mixing these is how boards get
    misled" names.

    `basis` is mandatory. A figure whose source cannot be opened is an assertion, and this
    projection refuses assertions in every other field for the same reason.
    """

    label: str
    value: str
    tier: str
    basis: str

    @property
    def tier_label(self) -> str:
        """`Tier 2 · POTENSI` — the ordinal travels with the name, as D11 writes it."""
        return TIER_LABELS[self.tier]

    @property
    def tier_meaning(self) -> str:
        """What the tier means, so a board member need not have read the decision log."""
        return TIER_MEANINGS[self.tier]


@dataclass(frozen=True)
class TierGroup:
    """Every figure resting on one basis, kept together and never merged with another.

    Grouping is the structural half of D11. A caller cannot render two tiers in one
    statement by accident, because the only thing it is handed is a group that has exactly
    one tier — and there is deliberately no total, no sum and no blended figure anywhere in
    this module for it to reach for instead.
    """

    tier: str
    figures: tuple[Figure, ...]

    @property
    def label(self) -> str:
        return TIER_LABELS[self.tier]

    @property
    def meaning(self) -> str:
        return TIER_MEANINGS[self.tier]


@dataclass(frozen=True)
class Engagement:
    """A relationship with a named counterparty, held at a rung a document evidences.

    Its own record, cited by every gate that depends on it (ADR-0008), because the 5 mmscfd
    allocation is simultaneously an engagement with SKK Migas and PGN/Pertagas *and* the
    binding evidence requirement for G1 across the whole gas pillar. State embedded in each
    gate would go stale in two places the first time a counterparty replied to anything.

    There is no likelihood, probability or expected-close field, and there is no room for
    one: ADR-0009 makes that a property of the schema rather than an instruction a prompt
    can drop. This record says where an engagement *stands*, never whether it will close.
    """

    id: str
    # A list in the record: one engagement routinely faces several counterparties at once,
    # and splitting it per counterparty would reintroduce the duplication ADR-0008 removes.
    counterparty: tuple[str, ...]
    pillar: str | None
    purpose: str
    stage: str
    # The document the rung stands on. Mandatory: a rung without one is a claim about a
    # counterparty's position, which is exactly what ADR-0009 keeps out of the record.
    artefact: str
    source: str

    @property
    def stage_label(self) -> str:
        """The rung written for a reader — the parser has already refused anything else."""
        return STAGE_LABELS[self.stage]


@dataclass(frozen=True)
class GateAssessment:
    """One recorded attempt to pass a gate — a refusal exactly as much as a pass."""

    project: str
    gate: str
    verdict: str
    assessed_on: dt.date
    signed_by: str
    source: str
    evidence: tuple[EvidenceItem, ...] = ()

    @property
    def unsatisfied(self) -> tuple[EvidenceItem, ...]:
        """The requirements this assessment records as unmet, in the order recorded.

        This is the field that replaces the conversation: "what is blocking this" is read
        off the record rather than reconstructed from the prose body beneath it.
        """
        return tuple(item for item in self.evidence if not item.satisfied)

    @property
    def awaiting_engagements(self) -> tuple[str, ...]:
        """The Engagement ids this gate is waiting on, in the order recorded.

        Only unsatisfied requirements count. A satisfied one cites the engagement that
        already delivered, which is provenance rather than something anyone is waiting for.
        """
        seen: dict[str, None] = {}
        for item in self.unsatisfied:
            if item.engagement is not None:
                seen.setdefault(item.engagement, None)
        return tuple(seen)


@dataclass(frozen=True)
class Project:
    """A project and every assessment recorded against it, in ladder order."""

    id: str
    name: str
    pillar: str | None
    assessments: tuple[GateAssessment, ...]
    figures: tuple[Figure, ...] = ()

    @property
    def current_gate(self) -> str | None:
        """The highest gate holding a passing assessment, or None when none does.

        Derived on every read so that no caller can assign one. A later refusal cannot
        revoke an earlier pass because only passes are considered here at all — a pass is
        a durable record of something that was true on the day it was signed.
        """
        passed = [assessment.gate for assessment in self.assessments if assessment.verdict == 'pass']
        if not passed:
            return None
        return max(passed, key=GATES.index)

    @property
    def has_assessments(self) -> bool:
        """Whether anything has been recorded against this project at all.

        Separates a project nobody has assessed from one that has been refused. Both have
        no current gate, and only the second is evidence that anyone tried.
        """
        return bool(self.assessments)

    @property
    def blocking_requirements(self) -> tuple[EvidenceItem, ...]:
        """What the refusals say is missing — the project's blockers, named.

        Only refused assessments contribute. An unsatisfied requirement under a *passing*
        verdict is a waiver the board granted on the record, and calling it a blocker
        would overrule a decision that was actually taken.

        Deduplicated by requirement and kept in ladder order, so a pillar refused three
        times on one missing allocation names that allocation once rather than three
        times. The first citation recorded for a requirement is the one kept.
        """
        blocking: dict[str, EvidenceItem] = {}
        for assessment in self.assessments:
            if assessment.verdict != 'fail':
                continue
            for item in assessment.unsatisfied:
                blocking.setdefault(item.requirement, item)
        return tuple(blocking.values())

    @property
    def figures_by_tier(self) -> tuple[TierGroup, ...]:
        """This project's figures, grouped by basis, in D11's order.

        Grouped rather than listed because a flat list is an invitation to render two tiers
        side by side as though they were comparable. Only tiers that actually have figures
        appear, so an empty group never implies a basis nobody claimed.
        """
        return tuple(
            TierGroup(tier=tier, figures=tuple(figure for figure in self.figures if figure.tier == tier))
            for tier in TIERS
            if any(figure.tier == tier for figure in self.figures)
        )

    @property
    def awaiting_engagements(self) -> tuple[str, ...]:
        """Every Engagement id this project's refusals are waiting on, each named once.

        "Whose reply am I waiting for" across the whole project, deduplicated for the same
        reason `blocking_requirements` is: one counterparty blocking three gates is one
        thing to chase, not three.
        """
        seen: dict[str, None] = {}
        for item in self.blocking_requirements:
            if item.engagement is not None:
                seen.setdefault(item.engagement, None)
        return tuple(seen)


@dataclass(frozen=True)
class Portfolio:
    """Every project found in a records directory, or the reason there are none."""

    projects: tuple[Project, ...]
    unavailable_reason: str | None
    # One record per engagement, however many gates cite it (ADR-0008). Ordered by id so
    # the projection never varies with how the filesystem lists files.
    engagements: tuple[Engagement, ...] = ()

    @property
    def non_coverage(self) -> tuple[str, ...]:
        """What the portfolio view does not prove, published alongside it."""
        return PORTFOLIO_NON_COVERAGE

    @property
    def engagement_non_coverage(self) -> tuple[str, ...]:
        """What the engagements view does not prove. A separate view states its own."""
        return ENGAGEMENT_NON_COVERAGE

    @property
    def available(self) -> bool:
        """Whether the records directory was read at all.

        An empty portfolio that is available means JUP records no projects. An
        unavailable one means we could not look, which the page must say instead.
        """
        return self.unavailable_reason is None


def project_portfolio(records_dir: Path | str | None) -> Portfolio:
    """Project a directory of markdown records into the portfolio the dashboard renders.

    Pure over its argument: the same directory yields the same portfolio, with no
    database, network, environment or global state involved.

    Two failure modes are deliberately different. A directory we cannot read is an
    availability problem and returns an empty portfolio carrying a reason, so the page can
    say why it is blank. A record we can read but cannot trust raises `RecordError`,
    because rendering around it would publish a governance claim nobody signed.

    Args:
        records_dir: The records root holding `projects/` and `gate-assessments/`.

    Returns:
        The projected portfolio, available or reasoned-empty.

    Raises:
        RecordError: A record was readable but could not be trusted.
    """
    if records_dir is None:
        return Portfolio(
            projects=(),
            unavailable_reason='No records directory is configured, so no projects were read.',
        )

    root = Path(records_dir)
    unavailable = _unavailable_reason(root)
    if unavailable is not None:
        return Portfolio(projects=(), unavailable_reason=unavailable)

    engagements_dir = root / _ENGAGEMENTS_SUBDIR
    try:
        projects = _load_projects(root / _PROJECTS_SUBDIR)
        engagements = _load_engagements(engagements_dir)
        assessments = _load_assessments(root / _ASSESSMENTS_SUBDIR, set(projects))
    except OSError as error:
        return Portfolio(projects=(), unavailable_reason=f'The records directory {root} could not be read: {error}.')

    _resolve_citations(assessments, engagements, engagements_dir)

    return Portfolio(
        projects=_attach(projects, assessments),
        unavailable_reason=None,
        engagements=tuple(engagements[identifier] for identifier in sorted(engagements)),
    )


def _unavailable_reason(root: Path) -> str | None:
    """Name why a records directory cannot be projected, or None when it can be.

    Every branch names the path, because a dashboard that says only "no data" gives a PMO
    nothing to go and fix.
    """
    try:
        if not root.exists():
            return f'The records directory {root} does not exist, so no projects were read.'
        if not root.is_dir():
            return f'The records path {root} is a file rather than a directory, so no projects were read.'
        if not (root / _PROJECTS_SUBDIR).is_dir():
            return f'The records directory {root} has no {_PROJECTS_SUBDIR}/ subdirectory, so no projects were read.'
        if not (root / _ASSESSMENTS_SUBDIR).is_dir():
            return (
                f'The records directory {root} has no {_ASSESSMENTS_SUBDIR}/ subdirectory, '
                f'so no gate assessments were read.'
            )
    except OSError as error:
        return f'The records directory {root} could not be read: {error}.'
    return None


def _load_projects(directory: Path) -> dict[str, Project]:
    """Read every project record, refusing a second record that claims a taken id.

    Two records claiming one id makes the projection depend on read order, which is the
    ambiguity a derived dashboard must never resolve silently.
    """
    projects: dict[str, Project] = {}
    for path in sorted(directory.glob('*.md')):
        frontmatter = _frontmatter(path)
        identifier = _text(frontmatter, 'id', path)
        if identifier in projects:
            raise RecordError(path, 'id', f'is {identifier!r}, which another project record already declares')
        projects[identifier] = Project(
            id=identifier,
            name=_text(frontmatter, 'name', path),
            pillar=_optional_text(frontmatter, 'pillar', path),
            assessments=(),
            figures=_figures(frontmatter, path),
        )
    return projects


def _load_assessments(directory: Path, known_projects: set[str]) -> list[GateAssessment]:
    """Read every assessment record, refusing one that cites a project we do not hold.

    An assessment whose project is missing is not an orphan to be shown alone; it means
    the records directory is incomplete, and half a governance trail is worse than none.
    """
    assessments: list[GateAssessment] = []
    for path in sorted(directory.glob('*.md')):
        frontmatter = _frontmatter(path)
        project = _text(frontmatter, 'project', path)
        if project not in known_projects:
            raise RecordError(path, 'project', f'cites {project!r}, for which there is no project record')
        assessments.append(
            GateAssessment(
                project=project,
                gate=_choice(frontmatter, 'gate', GATES, path),
                verdict=_choice(frontmatter, 'verdict', VERDICTS, path),
                assessed_on=_date(frontmatter, 'assessed_on', path),
                signed_by=_text(frontmatter, 'signed_by', path),
                source=path.name,
                evidence=_evidence(frontmatter, path),
            )
        )
    return assessments


def _load_engagements(directory: Path) -> dict[str, Engagement]:
    """Read every engagement record, refusing a second record that claims a taken id.

    An absent `engagements/` directory is permitted and yields none. It is not an
    availability failure: a records root that cites no engagement is perfectly readable,
    and darkening the whole portfolio over a directory nobody references would be a wildly
    disproportionate response. A citation into the void is caught precisely, and loudly,
    by `_resolve_citations` instead.
    """
    if not directory.is_dir():
        return {}

    engagements: dict[str, Engagement] = {}
    for path in sorted(directory.glob('*.md')):
        frontmatter = _frontmatter(path)
        identifier = _text(frontmatter, 'id', path)
        if identifier in engagements:
            raise RecordError(path, 'id', f'is {identifier!r}, which another engagement record already declares')
        engagements[identifier] = Engagement(
            id=identifier,
            counterparty=_counterparties(frontmatter, path),
            pillar=_optional_text(frontmatter, 'pillar', path),
            purpose=_text(frontmatter, 'purpose', path),
            stage=_choice(frontmatter, 'stage', STAGES, path),
            artefact=_text(frontmatter, 'artefact', path),
            source=path.name,
        )
    return engagements


def _resolve_citations(
    assessments: list[GateAssessment],
    engagements: dict[str, Engagement],
    directory: Path,
) -> None:
    """Refuse any evidence item citing an Engagement id no record declares.

    Resolution is a check, not a copy: the assessment keeps the id and the projection keeps
    one `Engagement`, which is what makes a counterparty's stage impossible to have current
    in one place and stale in another (ADR-0008).

    The message distinguishes a missing record from a missing directory, because those send
    an operator to two completely different places — one to write a record, the other to fix
    a mount.
    """
    missing_directory = not directory.is_dir()
    for assessment in assessments:
        for item in assessment.evidence:
            if item.engagement is None or item.engagement in engagements:
                continue
            problem = (
                f'cites the engagement {item.engagement!r}, and there is no {_ENGAGEMENTS_SUBDIR}/ '
                f'directory at {directory} for it to live in'
                if missing_directory
                else f'cites the engagement {item.engagement!r}, for which there is no engagement record'
            )
            raise RecordError(Path(assessment.source), f'evidence.{item.requirement}', problem)


def _counterparties(frontmatter: dict[str, object], path: Path) -> tuple[str, ...]:
    """Read the counterparties, accepting a single name or a list of them.

    One engagement routinely faces several counterparties at once — the 5 mmscfd allocation
    is SKK Migas *and* PGN/Pertagas — and splitting it per counterparty would reintroduce
    the duplication ADR-0008 exists to remove.
    """
    value = frontmatter.get('counterparty')
    if isinstance(value, str) or value is None:
        return (_text(frontmatter, 'counterparty', path),)
    if not isinstance(value, list) or not value:
        raise RecordError(path, 'counterparty', 'must be a name or a non-empty list of names')
    for position, name in enumerate(value, start=1):
        if not isinstance(name, str) or not name.strip():
            raise RecordError(path, f'counterparty[{position}]', 'must be a non-empty string')
    return tuple(name.strip() for name in value)


def _attach(projects: dict[str, Project], assessments: list[GateAssessment]) -> tuple[Project, ...]:
    """Hang each assessment on its project, ordered so the projection never varies."""
    by_project: dict[str, list[GateAssessment]] = {identifier: [] for identifier in projects}
    for assessment in assessments:
        by_project[assessment.project].append(assessment)
    return tuple(
        Project(
            id=project.id,
            name=project.name,
            pillar=project.pillar,
            assessments=tuple(sorted(by_project[project.id], key=_ladder_position)),
            figures=project.figures,
        )
        for project in sorted(projects.values(), key=lambda project: project.id)
    )


def _ladder_position(assessment: GateAssessment) -> tuple[int, dt.date, str]:
    """Sort key that pins assessment order regardless of how the filesystem lists files."""
    return (GATES.index(assessment.gate), assessment.assessed_on, assessment.source)


def _frontmatter(path: Path) -> dict[str, object]:
    """Parse a record's YAML frontmatter, ignoring the free prose body beneath it."""
    lines = path.read_text(encoding='utf-8').splitlines()
    opening = _opening_delimiter(lines, path)
    closing = _closing_delimiter(lines, opening, path)
    block = '\n'.join(lines[opening + 1 : closing])
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as error:
        raise RecordError(path, 'frontmatter', f'is not valid YAML: {error}') from error
    if not isinstance(parsed, dict):
        raise RecordError(path, 'frontmatter', 'is not a YAML mapping')
    _refuse_forecast_keys(parsed, path)
    return parsed


def _opening_delimiter(lines: list[str], path: Path) -> int:
    """Locate the opening `---`, which must be the record's first non-blank line."""
    for index, line in enumerate(lines):
        if line.strip() == _DELIMITER:
            return index
        if line.strip():
            break
    raise RecordError(path, 'frontmatter', 'is absent — the record must open with a --- delimited block')


def _closing_delimiter(lines: list[str], opening: int, path: Path) -> int:
    """Locate the closing `---`, without which the body would be read as fields."""
    for index in range(opening + 1, len(lines)):
        if lines[index].strip() == _DELIMITER:
            return index
    raise RecordError(path, 'frontmatter', 'is unterminated — the opening --- has no closing ---')


def _text(frontmatter: dict[str, object], field: str, path: Path) -> str:
    """Read a required string field, refusing blanks as firmly as absences."""
    value = frontmatter.get(field)
    if value is None:
        raise RecordError(path, field, 'is missing')
    if not isinstance(value, str) or not value.strip():
        raise RecordError(path, field, 'must be a non-empty string')
    return value.strip()


def _optional_text(frontmatter: dict[str, object], field: str, path: Path) -> str | None:
    """Read an optional string field, holding a stated value to the same standard."""
    if frontmatter.get(field) is None:
        return None
    return _text(frontmatter, field, path)


def _date(frontmatter: dict[str, object], field: str, path: Path) -> dt.date:
    """Read a required calendar date.

    A YAML timestamp arrives as a `date` subclass, and accepting one would silently drop a
    time the record went to the trouble of stating, so it is refused rather than truncated.
    """
    value = frontmatter.get(field)
    if value is None:
        raise RecordError(path, field, 'is missing')
    if not isinstance(value, dt.date) or isinstance(value, dt.datetime):
        raise RecordError(path, field, 'is not a date — expected a plain YAML date such as 2026-09-19')
    return value


def _choice(frontmatter: dict[str, object], field: str, permitted: tuple[str, ...], path: Path) -> str:
    """Read a field constrained to a closed set, naming that set when it is missed.

    The permitted values go in the message because the author of a rejected record is a
    PMO analyst editing markdown, not someone who will go and read this module.
    """
    value = _text(frontmatter, field, path)
    if value not in permitted:
        raise RecordError(path, field, f'is {value!r}, which is not one of {", ".join(permitted)}')
    return value


def _evidence(frontmatter: dict[str, object], path: Path) -> tuple[EvidenceItem, ...]:
    """Read the evidence a gate required, refusing any item that cannot be checked.

    Absent `evidence` is permitted and means the record states no requirements — not that
    it met none. Present-but-not-a-list is refused, because a record that meant to state
    requirements and stated something else is exactly the case where guessing is worst.
    """
    raw = frontmatter.get('evidence')
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise RecordError(path, 'evidence', 'must be a list of requirement entries')
    return tuple(_evidence_item(entry, position, path) for position, entry in enumerate(raw, start=1))


def _evidence_item(entry: object, position: int, path: Path) -> EvidenceItem:
    """Read one evidence entry, naming its position so the author can find it.

    The entry is identified by its ordinal rather than its requirement, because the field
    most likely to be missing is the requirement itself.
    """
    field = f'evidence[{position}]'
    if not isinstance(entry, dict):
        raise RecordError(
            path,
            field,
            'must be a mapping with a requirement, a satisfied flag and an artefact or engagement citation',
        )

    with _within(field):
        requirement = _text(entry, 'requirement', path)
        artefact = _optional_text(entry, 'artefact', path)
        engagement = _optional_text(entry, 'engagement', path)
        satisfied = _flag(entry, 'satisfied', path)

    if artefact is None and engagement is None:
        raise RecordError(
            path,
            f'{field}.{requirement}',
            'cites neither an artefact nor an engagement, so nothing can be checked against it',
        )

    return EvidenceItem(
        requirement=requirement,
        satisfied=satisfied,
        artefact=artefact,
        engagement=engagement,
    )


@contextmanager
def _within(field: str) -> Iterator[None]:
    """Re-raise any refusal raised inside as a refusal against a nested field.

    `requirement: is missing` is unactionable in a record with four requirements;
    `evidence[3].requirement: is missing` sends the author straight to the entry.
    """
    try:
        yield
    except RecordError as error:
        raise RecordError(error.path, f'{field}.{error.field}', _problem(error)) from error


def _problem(error: RecordError) -> str:
    """Recover the problem clause from a refusal, so re-raising does not duplicate it."""
    return str(error).split(f'{error.field}: ', 1)[-1]


def _flag(frontmatter: dict[str, object], field: str, path: Path) -> bool:
    """Read a required boolean, refusing a missing one rather than choosing a default.

    Either default invents a claim: true manufactures evidence nobody presented, false
    manufactures a blocker nobody reported. The record has to say.
    """
    value = frontmatter.get(field)
    if value is None:
        raise RecordError(path, field, 'is missing — an unstated requirement is neither met nor unmet')
    if not isinstance(value, bool):
        raise RecordError(path, field, f'is {value!r}, which is not true or false')
    return value


def _refuse_forecast_keys(value: object, path: Path, trail: str = '') -> None:
    """Refuse any forecast key anywhere in a record, at any depth (ADR-0009).

    Enforced here, at the one door every record type passes through, rather than in each
    loader — a rule that has to be remembered in five places is a rule that will be missed
    in the sixth. Nested mappings and lists are walked because an evidence item is a
    mapping inside a list, and a `probability` smuggled in there would otherwise be a field
    the schema quietly tolerated.

    Refused rather than ignored, and deliberately so: dropping the key silently would let a
    record carry a forecast that the dashboard simply declined to show, which is worse than
    either refusing it or rendering it. The author would believe it had been recorded.
    """
    if isinstance(value, dict):
        for key, nested in value.items():
            here = f'{trail}.{key}' if trail else str(key)
            if isinstance(key, str) and _is_forecast_key(key):
                raise RecordError(
                    path,
                    here,
                    'is a forecast field, and this schema has none — an engagement records where it '
                    'stands, never whether it will close (ADR-0009)',
                )
            _refuse_forecast_keys(nested, path, here)
    elif isinstance(value, list):
        for position, entry in enumerate(value, start=1):
            _refuse_forecast_keys(entry, path, f'{trail}[{position}]')


def _is_forecast_key(key: str) -> bool:
    """Whether a key names a forecast, normalising hyphens and spacing to underscores."""
    normalised = key.strip().lower().replace('-', '_').replace(' ', '_')
    return any(fragment in normalised for fragment in _BANNED_KEY_FRAGMENTS)


def _figures(frontmatter: dict[str, object], path: Path) -> tuple[Figure, ...]:
    """Read the figures a record surfaces, refusing any that cannot name its basis.

    Absent `figures` is permitted and means the record surfaces none — which is the correct
    default. A dashboard with no numbers on it proves less than one with numbers, and is
    honest; a dashboard with numbers whose basis nobody stated is worse than both.
    """
    raw = frontmatter.get('figures')
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise RecordError(path, 'figures', 'must be a list of figure entries')
    return tuple(_figure(entry, position, path) for position, entry in enumerate(raw, start=1))


def _figure(entry: object, position: int, path: Path) -> Figure:
    """Read one figure, refusing a POTENSI number labelled as money anyone would keep."""
    field = f'figures[{position}]'
    if not isinstance(entry, dict):
        raise RecordError(path, field, 'must be a mapping with a label, a value, a tier and a basis')

    with _within(field):
        label = _text(entry, 'label', path)
        value = _value(entry, path)
        tier = _choice(entry, 'tier', TIERS, path)
        basis = _text(entry, 'basis', path)

    if tier == 'POTENSI':
        offending = _margin_word(label)
        if offending is not None:
            raise RecordError(
                path,
                f'{field}.label',
                f'is {label!r}, and a POTENSI figure is top-line revenue — labelling it {offending!r} '
                f'presents a revenue potential as money the company would keep (D11)',
            )

    return Figure(label=label, value=value, tier=tier, basis=basis)


def _value(frontmatter: dict[str, object], path: Path) -> str:
    """Read a figure's value as written, accepting a number but keeping it as text.

    Deliberately never a float. A parsed number is a number something will eventually add
    up, and the one sum this system must never compute is one that crosses tiers.
    """
    value = frontmatter.get('value')
    if value is None:
        raise RecordError(path, 'value', 'is missing')
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise RecordError(path, 'value', f'is {value!r}, which is not a number or a string')
    text = str(value).strip()
    if not text:
        raise RecordError(path, 'value', 'must not be blank')
    return text


def _margin_word(label: str) -> str | None:
    """The margin-or-profit word in a label, or None — matched on whole words.

    Whole words, not substrings, so a legitimate label is not refused for containing one by
    accident. The cost of a false refusal here is a PMO analyst blocked from recording a
    true figure, which is a worse failure than the narrower ban missing an exotic synonym.
    """
    words = {word.strip('"\'()[]:;,.') for word in label.lower().replace('-', ' ').replace('/', ' ').split()}
    for banned in _MARGIN_WORDS:
        if banned in words:
            return banned
    return None
