"""The portfolio projection, rendered for a model to read: the `portfolio_status` tool.

Agentic-capabilities plan, Phase 3, and its first tool. The Knowledge Base already holds the
records as text, so the model can find a record. It cannot *compute* anything from one: which
gate a project holds is derived (ADR-0003), never written down, and text retrieval hands the
model the raw frontmatter to reason over. This tool hands it the derivation instead: the same
`project_portfolio` the Portfolio page renders, so the page and the chat cannot disagree.

Read-only by construction. It reads the records mount and nothing else; there is no write
path, no network call and no vendor import, so it runs under the pure-module test job.

The Open WebUI tool that calls this (`tools/portfolio_status.py`) is a wrapper of a few lines,
because tool code lives in the database and is `exec`'d, where nothing tests it. Every rule
that matters is here.
"""

import os
from pathlib import Path

from jup.portfolio import (
    OPERATING_LAYER_ROLE,
    Engagement,
    Portfolio,
    Project,
    RecordError,
    project_portfolio,
)

#: Returned to a caller outside the operating layer. Worded for the model to relay rather than
#: to paraphrase, because "I could not find it" would misstate a refusal as an absence.
REFUSAL = (
    'Refused: gate state is restricted to the operating layer, and this account is not a member of it. '
    'Tell the user that plainly; do not answer from other sources instead.'
)


def _records_dir() -> Path | None:
    value = os.environ.get('JUP_RECORDS_DIR', '').strip()
    return Path(value) if value else None


def _artefact_root() -> Path | None:
    value = os.environ.get('JUP_ARTEFACT_ROOT', '').strip()
    return Path(value) if value else None


def portfolio_status(role: str | None, project: str = '') -> str:
    """The tool's whole behaviour: refuse, or project the mounted records and render them."""
    if role != OPERATING_LAYER_ROLE:
        return REFUSAL
    try:
        portfolio = project_portfolio(_records_dir(), _artefact_root())
    except RecordError as error:
        # Fail closed. A record that cannot be trusted is not rendered around, and the model is
        # told not to fill the gap from the Knowledge Base's copy of the same file.
        return (
            f'The records could not be read as a trustworthy portfolio: {error}. '
            'Say that gate state is unavailable until the record is fixed. Do not reconstruct it from other sources.'
        )
    return render(portfolio, project)


def render(portfolio: Portfolio, project: str = '') -> str:
    """Markdown for the model. Pure: the same portfolio renders the same text."""
    if not portfolio.available:
        return f'Portfolio unavailable: {portfolio.unavailable_reason}'

    wanted = project.strip().lower()
    projects = [p for p in portfolio.projects if not wanted or wanted in p.id.lower() or wanted in p.name.lower()]
    if not projects:
        known = ', '.join(f'{p.id} ({p.name})' for p in portfolio.projects) or 'none'
        return f'No project matches {project!r}. Projects on record: {known}.'

    cited = {e for p in projects for e in p.awaiting_engagements}
    engagements = [e for e in portfolio.engagements if not wanted or e.id in cited]

    lines = [
        '# JUP portfolio status',
        '',
        'Computed from the gate-assessment records by the same projection the Portfolio page uses. '
        'Current Gate is derived as the highest gate holding a PASSING assessment (ADR-0003); it is never stored.',
    ]
    for p in projects:
        lines += ['', *_project_lines(p)]
    if engagements:
        lines += ['', '## Engagements', '']
        lines += [_engagement_line(e) for e in engagements]
        lines += ['', 'What the engagement view does not prove:']
        lines += [f'- {statement}' for statement in portfolio.engagement_non_coverage]
    lines += ['', '## What this does not prove', '']
    lines += [f'- {statement}' for statement in portfolio.non_coverage]
    return '\n'.join(lines)


def _project_lines(p: Project) -> list[str]:
    if p.current_gate:
        gate = f'passed {p.current_gate}'
    elif p.has_assessments:
        gate = 'has not passed G1 (assessed and refused)'
    else:
        gate = 'never assessed: it has not passed and it has not failed'
    lines = [f'## {p.name} (`{p.id}`)', '', f'- Pillar: {p.pillar or "not recorded"}', f'- Current Gate: {gate}']

    for a in p.assessments:
        lines.append(
            f'- {a.gate} assessment: **{a.verdict}**, {a.assessed_on.isoformat()}, signed by {a.signed_by} ({a.source})'
        )

    if p.blocking_requirements:
        lines.append('- Blocking requirements (from refused assessments):')
        for item in p.blocking_requirements:
            where = f'engagement `{item.engagement}`' if item.engagement else f'artefact {item.artefact}'
            lines.append(f'  - {item.requirement}: not satisfied; evidence expected from {where}')

    for group in p.figures_by_tier:
        lines.append(f'- Figures, {group.label}: {group.meaning} Never combine with another tier.')
        for figure in group.figures:
            lines.append(f'  - {figure.label}: {figure.value} ({group.label}; basis: {figure.basis})')
    return lines


def _engagement_line(e: Engagement) -> str:
    parties = ', '.join(e.counterparty)
    pillar = f', {e.pillar} pillar' if e.pillar else ''
    return (
        f'- `{e.id}` with {parties}{pillar}: **{e.stage_label}**. Purpose: {e.purpose}. Rung evidenced by {e.artefact}.'
    )
