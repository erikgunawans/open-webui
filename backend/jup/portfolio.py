"""The JUP portfolio projection: gate assessment records in, domain objects out.

ADR-0003 is the rule this module exists to enforce — gate state is a set of assessments,
not a status field. A project's current gate is derived on every read and has no setter,
so a board cannot forget that it stopped a project in August, or why.

ADR-0004 puts those records in markdown under `~/jup` rather than in our own database, so
this module's whole job is to read a directory and refuse anything it cannot vouch for.
"""

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

GATES: tuple[str, ...] = ('G1', 'G2', 'G3', 'G4')
VERDICTS: tuple[str, ...] = ('pass', 'fail')

_PROJECTS_SUBDIR = 'projects'
_ASSESSMENTS_SUBDIR = 'gate-assessments'
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
class GateAssessment:
    """One recorded attempt to pass a gate — a refusal exactly as much as a pass."""

    project: str
    gate: str
    verdict: str
    assessed_on: dt.date
    signed_by: str
    source: str


@dataclass(frozen=True)
class Project:
    """A project and every assessment recorded against it, in ladder order."""

    id: str
    name: str
    pillar: str | None
    assessments: tuple[GateAssessment, ...]

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


@dataclass(frozen=True)
class Portfolio:
    """Every project found in a records directory, or the reason there are none."""

    projects: tuple[Project, ...]
    unavailable_reason: str | None

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

    try:
        projects = _load_projects(root / _PROJECTS_SUBDIR)
        assessments = _load_assessments(root / _ASSESSMENTS_SUBDIR, set(projects))
    except OSError as error:
        return Portfolio(projects=(), unavailable_reason=f'The records directory {root} could not be read: {error}.')

    return Portfolio(projects=_attach(projects, assessments), unavailable_reason=None)


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
            )
        )
    return assessments


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
