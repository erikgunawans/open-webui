"""Read-only HTTP surface for the JUP portfolio projection.

Thin by design. Every domain rule — above all the derivation of Current Gate — lives in
`jup.portfolio`, which is a pure function over a directory and is tested without a server.
This module only resolves configuration, applies authentication, and serialises.

There is deliberately no write endpoint. Gate Assessments are markdown in the JUP repo
(ADR-0004); a correction is an edit and a commit there, which is what supplies the author,
the date and the diff that an audited governance artefact needs.
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from jup.portfolio import Portfolio, RecordError, project_portfolio
from open_webui.utils.auth import get_verified_user
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter()

# The JUP working tree is mounted read-only at deployment. Unset is a legitimate state, not an
# error: it yields the empty-with-reason projection below rather than a silent empty page.
JUP_RECORDS_DIR = os.environ.get('JUP_RECORDS_DIR', '').strip() or None


class GateAssessmentResponse(BaseModel):
    gate: str
    verdict: str
    assessed_on: str
    signed_by: str
    source: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    pillar: str | None
    # Derived, never stored, and with no setter anywhere in the system (ADR-0003). `null` means the
    # project holds no passing assessment — which is not the same claim as holding no assessment.
    current_gate: str | None
    has_assessments: bool
    assessments: list[GateAssessmentResponse]


class PortfolioResponse(BaseModel):
    projects: list[ProjectResponse]
    # Populated only when the records could not be read. The frontend renders the sentence rather
    # than an empty table, so a misconfiguration is visible instead of looking like a clean portfolio.
    unavailable_reason: str | None


def _serialise(portfolio: Portfolio) -> PortfolioResponse:
    return PortfolioResponse(
        projects=[
            ProjectResponse(
                id=project.id,
                name=project.name,
                pillar=project.pillar,
                current_gate=project.current_gate,
                has_assessments=project.has_assessments,
                assessments=[
                    GateAssessmentResponse(
                        gate=assessment.gate,
                        verdict=assessment.verdict,
                        assessed_on=assessment.assessed_on.isoformat(),
                        signed_by=assessment.signed_by,
                        source=assessment.source,
                    )
                    for assessment in project.assessments
                ],
            )
            for project in portfolio.projects
        ],
        unavailable_reason=portfolio.unavailable_reason,
    )


@router.get('/', response_model=PortfolioResponse)
async def get_portfolio(user=Depends(get_verified_user)) -> PortfolioResponse:
    """Return every project with its Gate Assessments and its derived Current Gate.

    A malformed record raises rather than being skipped: a gate that cannot verify its own
    records must stop, not render a confident blank around the hole.
    """
    records_dir = Path(JUP_RECORDS_DIR) if JUP_RECORDS_DIR else None

    try:
        portfolio = await run_in_threadpool(project_portfolio, records_dir)
    except RecordError as error:
        log.exception('refused to render the portfolio: an unreadable gate record')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    return _serialise(portfolio)
