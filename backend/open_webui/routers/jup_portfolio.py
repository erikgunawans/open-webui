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
from collections.abc import Iterable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from jup.portfolio import EvidenceItem, Portfolio, RecordError, project_portfolio
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

# The JUP working tree is mounted read-only at deployment. Unset is a legitimate state, not an
# error: it yields the empty-with-reason projection below rather than a silent empty page.
JUP_RECORDS_DIR = os.environ.get('JUP_RECORDS_DIR', '').strip() or None

# The tree the records' artefact and basis paths are relative to — the JUP working tree,
# mounted read-only (ADR-0004). Defaults to the records root's parent, which is the layout
# `<jup>/records/{projects,gate-assessments,engagements}` produces.
#
# Setting it turns on artefact resolution, which is what makes a rename in the JUP tree a
# loud failure. Unset it and citations are carried but never checked — every gate still
# renders, each one citing a file nobody can open, which is the silent failure ADR-0004's
# cross-repo coupling is most likely to cause.
JUP_ARTEFACT_ROOT = os.environ.get('JUP_ARTEFACT_ROOT', '').strip() or None


class EvidenceItemResponse(BaseModel):
    requirement: str
    satisfied: bool
    # Exactly one of these is set on a well-formed record, and the parser has already refused any
    # item carrying neither. An `engagement` is an id to be resolved against the Engagement records
    # (ticket #5); it is never an embedded copy of that Engagement's state (ADR-0008).
    artefact: str | None
    engagement: str | None


class FigureResponse(BaseModel):
    label: str
    # Held as written text, never a number. A parsed number is one something eventually adds
    # up, and the one sum this system must never compute is one that crosses tiers (D11).
    value: str
    tier: str
    tier_label: str
    tier_meaning: str
    basis: str


class TierGroupResponse(BaseModel):
    tier: str
    label: str
    meaning: str
    figures: list[FigureResponse]


class EngagementResponse(BaseModel):
    id: str
    counterparty: list[str]
    pillar: str | None
    purpose: str
    # The rung slug plus its label. The slug is what a record holds and what a client should
    # branch on; the label is presentation and may be renamed without a data migration.
    stage: str
    stage_label: str
    artefact: str
    # There is deliberately no likelihood, probability, expected-close or confidence field
    # here, and none anywhere else in this response (ADR-0009). Its absence is the schema
    # saying so: an engagement records where it stands, never whether it will close.


class GateAssessmentResponse(BaseModel):
    gate: str
    verdict: str
    assessed_on: str
    signed_by: str
    source: str
    evidence: list[EvidenceItemResponse]
    # The Engagement ids this gate is waiting on — its unsatisfied citations only. A
    # satisfied citation is provenance, not something anyone is waiting for.
    awaiting_engagements: list[str]


class ProjectResponse(BaseModel):
    id: str
    name: str
    pillar: str | None
    # Derived, never stored, and with no setter anywhere in the system (ADR-0003). `null` means the
    # project holds no passing assessment — which is not the same claim as holding no assessment.
    current_gate: str | None
    has_assessments: bool
    assessments: list[GateAssessmentResponse]
    # Derived from the refusals only: what the record says is missing. A requirement left unmet
    # under a *passing* verdict is a waiver the board granted, and is deliberately absent here.
    blocking_requirements: list[EvidenceItemResponse]
    # Whose reply this project is waiting for, across all its refusals, each named once.
    awaiting_engagements: list[str]
    # Deliberately grouped, and deliberately the ONLY shape figures are served in. A flat
    # list would let a client render a feasibility NPV beside a top-line revenue potential
    # as though they were comparable, which is exactly what D11 prohibits. There is no
    # total, no sum and no blended figure anywhere in this response.
    figures_by_tier: list[TierGroupResponse]


class PortfolioResponse(BaseModel):
    projects: list[ProjectResponse]
    # One record per engagement, however many gates cite it (ADR-0008). Gates carry ids;
    # the client resolves them here, so a counterparty's stage exists in exactly one place.
    engagements: list[EngagementResponse]
    # What this view does not prove, published beside it. A clean dashboard mistaken for a
    # safe portfolio is the failure these sentences exist to prevent, so they ship with the
    # payload rather than living in markup that can go stale unnoticed.
    non_coverage: list[str]
    engagement_non_coverage: list[str]
    # Populated only when the records could not be read. The frontend renders the sentence rather
    # than an empty table, so a misconfiguration is visible instead of looking like a clean portfolio.
    unavailable_reason: str | None


def _serialise_evidence(evidence: Iterable[EvidenceItem]) -> list[EvidenceItemResponse]:
    return [
        EvidenceItemResponse(
            requirement=item.requirement,
            satisfied=item.satisfied,
            artefact=item.artefact,
            engagement=item.engagement,
        )
        for item in evidence
    ]


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
                        evidence=_serialise_evidence(assessment.evidence),
                        awaiting_engagements=list(assessment.awaiting_engagements),
                    )
                    for assessment in project.assessments
                ],
                blocking_requirements=_serialise_evidence(project.blocking_requirements),
                awaiting_engagements=list(project.awaiting_engagements),
                figures_by_tier=[
                    TierGroupResponse(
                        tier=group.tier,
                        label=group.label,
                        meaning=group.meaning,
                        figures=[
                            FigureResponse(
                                label=figure.label,
                                value=figure.value,
                                tier=figure.tier,
                                tier_label=figure.tier_label,
                                tier_meaning=figure.tier_meaning,
                                basis=figure.basis,
                            )
                            for figure in group.figures
                        ],
                    )
                    for group in project.figures_by_tier
                ],
            )
            for project in portfolio.projects
        ],
        engagements=[
            EngagementResponse(
                id=engagement.id,
                counterparty=list(engagement.counterparty),
                pillar=engagement.pillar,
                purpose=engagement.purpose,
                stage=engagement.stage,
                stage_label=engagement.stage_label,
                artefact=engagement.artefact,
            )
            for engagement in portfolio.engagements
        ],
        non_coverage=list(portfolio.non_coverage),
        engagement_non_coverage=list(portfolio.engagement_non_coverage),
        unavailable_reason=portfolio.unavailable_reason,
    )


def _artefact_root(records_dir: Path | None) -> Path | None:
    """Where the cited documents live, or None when there is nothing to check them against."""
    if JUP_ARTEFACT_ROOT:
        return Path(JUP_ARTEFACT_ROOT)
    return records_dir.parent if records_dir else None


@router.get('/', response_model=PortfolioResponse)
async def get_portfolio(user=Depends(get_verified_user)) -> PortfolioResponse:
    """Return every project with its Gate Assessments and its derived Current Gate.

    A malformed record raises rather than being skipped: a gate that cannot verify its own
    records must stop, not render a confident blank around the hole.
    """
    records_dir = Path(JUP_RECORDS_DIR) if JUP_RECORDS_DIR else None
    artefact_root = _artefact_root(records_dir)

    try:
        portfolio = await run_in_threadpool(project_portfolio, records_dir, artefact_root)
    except RecordError as error:
        log.exception('refused to render the portfolio: an unreadable gate record')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    return _serialise(portfolio)
