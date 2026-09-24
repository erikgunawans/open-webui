"""The HTTP surface for Ruang Pimpinan: P1's reads and P2's recorded workflow.

Thin by design, like `jup_portfolio`: validation, variance and view reachability live in
`jup.leadership`, and are tested without a server. This module resolves configuration, applies
the leadership read policy per request, and serialises.

Three properties hold for every route:

- **Default deny, admins included.** Access comes only from the reader's group permissions,
  resolved on every request through the host's `get_permissions`, so a revoked grant stops the
  very next read. Being an app admin is Portfolio's operating layer; it is not BOD or BOC
  membership and grants nothing here.
- **Authorisation before data.** A reader without the grant learns 403 and nothing about whether
  the feature is configured or the dataset readable.
- **Nothing cached.** Every response, errors included, carries `Cache-Control: private, no-store`.
  The route class adds it after the handler runs, so a 401 raised inside the host's own
  authentication dependency gets it too.

P2 adds the records store (ADR-0014): reading one action and its event history, the PIC's
progress and evidence (`actions.submit`), and the BOD's closure decisions (`bod.review`, and only
while `JUP_LEADERSHIP_BOD_POLICY` is configured). Each write is its own capability, and a read
grant implies none of them. Every P2 read and write leaves a `jup.governance` audit line naming
the user, the operation, the record ids and the result, never content.

The feature is off unless `JUP_LEADERSHIP_ENABLED` is set, and P1 serves only the labelled
illustrative dataset named by `JUP_LEADERSHIP_SAMPLE_FILE`. Neither can be chosen by a request.
"""

import copy
import datetime as dt
import logging
import os
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from jup.governance import audit
from jup.leadership import closure, migrate
from jup.leadership import evidence as evidence_commands
from jup.leadership.actions import REPORTING_TZ, CommandRefused, derive_flags, fold_history, latest_progress
from jup.leadership.evidence_store import (
    EvidenceRejected,
    EvidenceStore,
    check_file,
    configured_store,
    max_bytes,
    read_bounded,
)
from jup.leadership.policy import DEFAULT_PERMISSIONS, SCOPES, allowed_operations, allowed_views, may, may_read
from jup.leadership.reader import DatasetUnavailable, load_dataset, read_overview, read_source
from jup.leadership.repository import (
    ActionNotFound,
    IdempotencyKeyReused,
    VersionConflict,
    read_action,
    read_events,
    unit_of_work,
)
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

NO_STORE = {'Cache-Control': 'private, no-store'}

View = Literal['board', 'rka']
Scope = Literal['jup-consolidated']


class _NoStoreRoute(APIRoute):
    """Stamps the no-store header on every response this router produces, errors included."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def _handler(request: Request) -> Response:
            try:
                response = await handler(request)
            except HTTPException as error:
                response = JSONResponse({'detail': error.detail}, status_code=error.status_code, headers=error.headers)
            except RequestValidationError as error:
                # Not an HTTPException, so it would otherwise leave through the app's handler
                # without the header. Same body FastAPI would send.
                response = JSONResponse(
                    {'detail': jsonable_encoder(error.errors())},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            response.headers.update(NO_STORE)
            return response

        return _handler


router = APIRouter(route_class=_NoStoreRoute)


def _enabled() -> bool:
    """Read per request, so a test or a restarted container needs no reimport."""
    return os.environ.get('JUP_LEADERSHIP_ENABLED', '').strip().lower() in ('1', 'true')


def _sample_file() -> Path | None:
    value = os.environ.get('JUP_LEADERSHIP_SAMPLE_FILE', '').strip()
    return Path(value) if value else None


async def leadership_permissions(user=Depends(get_verified_user)) -> dict[str, Any]:
    """The reader's merged group permissions, seeded with the all-false leadership defaults."""
    return await get_permissions(user.id, copy.deepcopy(DEFAULT_PERMISSIONS))


def _refuse() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Ruang Pimpinan is restricted. This account is signed in but has no access to this view.',
    )


def _unavailable(reason: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=reason)


async def _dataset() -> dict[str, Any]:
    """The configured dataset, or a 503 whose detail is safe to show."""
    if not _enabled():
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    path = _sample_file()
    if path is None:
        raise _unavailable('No leadership dataset is configured on this server.')
    try:
        return await run_in_threadpool(load_dataset, path)
    except DatasetUnavailable as error:
        log.exception('refused to serve Ruang Pimpinan: the dataset could not be trusted')
        raise _unavailable(str(error)) from error


@router.get('/capabilities')
async def get_capabilities(permissions: dict[str, Any] = Depends(leadership_permissions)) -> dict[str, Any]:
    """What this reader may open. No business records, whatever the grant."""
    if not _enabled():
        return {
            'enabled': False,
            'views': [],
            'scope_ids': [],
            'operations': [],
            'reason': 'Ruang Pimpinan is not enabled on this server.',
        }
    views = allowed_views(permissions)
    return {
        'enabled': True,
        'views': views,
        'scope_ids': [scope for scope in SCOPES if allowed_views(permissions, scope)],
        # Each capability is its own grant on top of a view grant (policy.py). BOD review is
        # listed only while a BOD policy is configured: without one nobody can close.
        # Publication and execution arrive with their own P2/P3 tasks.
        'operations': [
            operation
            for operation in allowed_operations(permissions)
            if operation != 'bod.review' or closure.configured_policy() is not None
        ],
        'reason': None if views else 'This account has no Ruang Pimpinan view.',
    }


@router.get('/overview')
async def get_overview(
    view: View,
    scope_id: Scope,
    permissions: dict[str, Any] = Depends(leadership_permissions),
) -> dict[str, Any]:
    """One view's context, metrics, actions, assumptions and module states."""
    if not may_read(permissions, view, scope_id):
        raise _refuse()
    return read_overview(await _dataset(), view)


@router.get('/sources/{source_id}')
async def get_source(
    source_id: str,
    view: View,
    scope_id: Scope,
    permissions: dict[str, Any] = Depends(leadership_permissions),
) -> dict[str, Any]:
    """Citation metadata for a source the requested view declares; 404 for anything else."""
    if not may_read(permissions, view, scope_id):
        raise _refuse()
    source = read_source(await _dataset(), view, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No such source in this view.')
    return source


def leadership_engine() -> Any:
    """The app database, where the leadership records live (ADR-0014). A dependency so tests can swap it."""
    from open_webui.internal.db import engine

    return engine


def _due(row: dict[str, Any], prefix: str) -> dict[str, str] | None:
    value = row[f'{prefix}_due']
    return None if value is None else {'precision': row[f'{prefix}_due_precision'], 'value': value}


def _read_action_record(engine: Any, action_id: str) -> dict[str, Any] | None:
    row = read_action(engine, action_id)
    if row is None:
        return None
    events = read_events(engine, action_id)
    progress = latest_progress(events)
    # No staleness threshold is recorded yet, so `stale` stays None with its reason; an assumed
    # one would quietly mark actions fresh.
    flags = derive_flags(
        row,
        today=dt.datetime.now(REPORTING_TZ).date(),
        last_update_at_ms=progress.created_at if progress else None,
    )
    return {
        'action': {
            'id': row['id'],
            'title': row['title'],
            'pic_label': row['pic_label'],
            'pic_user_id': row['pic_user_id'],
            'state': row['state'],
            'original_due': _due(row, 'original'),
            'current_due': _due(row, 'current'),
            'version': row['version'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        },
        'flags': {
            'overdue': flags.overdue,
            'days_overdue': flags.days_overdue,
            'due_before_next_meeting': flags.due_before_next_meeting,
            'stale': flags.stale,
            'reasons': flags.reasons,
        },
        'history': fold_history(events),
    }


@router.get('/actions/{action_id}')
async def get_action(
    action_id: str,
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """One action, its derived flags and its full event history, for a reader of either view.

    Actions are shared by both views (ACT-01), so a grant for the view named in the request is
    enough. Access is rechecked on every request: a revoked reader loses the history too.
    """

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='action', action_id=action_id, view=view, result=result)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    if not _enabled():
        _audit('unavailable')
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    if not migrate.schema_ready():
        _audit('unavailable')
        raise _unavailable('The Ruang Pimpinan records store is not ready on this server.')
    record = await run_in_threadpool(_read_action_record, engine, action_id)
    if record is None:
        _audit('not_found')
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No such action.')
    _audit('served')
    return record


# --- The PIC's writes (P2 T3) -------------------------------------------------------------


def leadership_evidence_store() -> EvidenceStore | None:
    """Where evidence files go, per the host's storage configuration. A dependency so tests can swap it."""
    return configured_store()


class ProgressIn(BaseModel):
    expected_version: int
    narrative: str = Field(min_length=1, max_length=10_000)
    milestones_completed: list[str] = Field(default_factory=list, max_length=50)
    remaining_work: str | None = Field(default=None, max_length=10_000)
    blocker: str | None = Field(default=None, max_length=10_000)
    next_step: str | None = Field(default=None, max_length=10_000)
    reported_at: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=128)


def _write_error(error: Exception) -> HTTPException:
    """The HTTP answer for a refused write. Nothing was written in any of these cases."""
    if isinstance(error, evidence_commands.NotThePic):
        return HTTPException(status.HTTP_403_FORBIDDEN, "Only this action's recorded PIC can submit on it.")
    if isinstance(error, closure.OwnerCannotReview):
        return HTTPException(status.HTTP_403_FORBIDDEN, "An action's PIC cannot review its closure.")
    if isinstance(error, closure.StaleEvidence):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {
                'message': 'The evidence changed since you reviewed it. Review the latest revision.',
                'evidence_id': error.latest,
            },
        )
    if isinstance(error, ActionNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, 'No such action.')
    if isinstance(error, VersionConflict):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            {'message': 'This action changed since you opened it. Reload and try again.', 'version': error.actual},
        )
    if isinstance(error, IdempotencyKeyReused):
        return HTTPException(status.HTTP_409_CONFLICT, 'This submission key was already used for a different change.')
    if isinstance(error, EvidenceRejected):
        return HTTPException(error.status, str(error))
    if isinstance(error, (CommandRefused, ValueError)):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))
    raise error


_REFUSALS = (
    evidence_commands.NotThePic,
    closure.OwnerCannotReview,
    ActionNotFound,
    VersionConflict,
    IdempotencyKeyReused,
    EvidenceRejected,
    CommandRefused,
    ValueError,
)


def _writable(permissions: dict[str, Any], view: str, scope_id: str, audit_refused: Callable[[str], None]) -> None:
    """The capability, then the section and the records store; each refusal is audited."""
    if not may(permissions, 'actions.submit', view, scope_id):
        audit_refused('refused')
        raise _refuse()
    if not _enabled():
        audit_refused('unavailable')
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    if not migrate.schema_ready():
        audit_refused('unavailable')
        raise _unavailable('The Ruang Pimpinan records store is not ready on this server.')


@router.post('/actions/{action_id}/progress')
async def post_progress(
    action_id: str,
    view: View,
    scope_id: Scope,
    form: ProgressIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """An owner update from the action's PIC. Changes no state."""

    def _audit(result: str) -> None:
        audit('leadership_write', user=user.id, operation='progress', action_id=action_id, result=result)

    _writable(permissions, view, scope_id, _audit)
    command = form.model_dump()

    def _run() -> Any:
        with unit_of_work(engine) as uow:
            return evidence_commands.submit_progress(uow, action_id=action_id, actor=user.id, **command)

    try:
        result = await run_in_threadpool(_run)
    except _REFUSALS as error:
        _audit(type(error).__name__)
        raise _write_error(error) from error
    _audit('replayed' if result.replayed else 'recorded')
    return {
        'action_id': action_id,
        'version': result.event.version,
        'event_id': result.event.id,
        'replayed': result.replayed,
    }


@router.post('/actions/{action_id}/evidence')
async def post_evidence(
    action_id: str,
    view: View,
    scope_id: Scope,
    expected_version: int = Form(...),
    completion: bool = Form(False),
    note: str | None = Form(None, max_length=10_000),
    idempotency_key: str | None = Form(None, max_length=128),
    url: str | None = Form(None, max_length=2_000),
    file: UploadFile | None = File(None),
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
    evidence_store: EvidenceStore | None = Depends(leadership_evidence_store),
) -> dict[str, Any]:
    """One evidence revision, a file or an https link, from the action's PIC.

    With `completion`, the action moves to awaiting BOD closure and a closure request is opened on
    this revision. The action is never closed here.
    """

    def _audit(result: str, **fields: Any) -> None:
        audit(
            'leadership_write',
            user=user.id,
            operation='evidence_submit',
            action_id=action_id,
            completion=completion,
            result=result,
            **fields,
        )

    _writable(permissions, view, scope_id, _audit)
    if (file is None) == (url is None):
        _audit('invalid')
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, 'Send exactly one of a file or a link.')

    try:
        if url is not None:
            item = evidence_commands.link_evidence(url)
            checked = None
        else:
            if evidence_store is None:
                _audit('unavailable')
                raise _unavailable('Evidence storage is not configured on this server.')
            content = await run_in_threadpool(read_bounded, file.file, max_bytes())
            checked = check_file(content, file.filename or '', file.content_type)
            item = evidence_commands.file_evidence(checked)

        def _pic_check() -> None:
            with engine.connect() as connection:
                evidence_commands.ensure_pic(connection, action_id, user.id)

        def _record() -> Any:
            with unit_of_work(engine) as uow:
                return evidence_commands.submit_evidence(
                    uow,
                    action_id=action_id,
                    expected_version=expected_version,
                    actor=user.id,
                    item=item,
                    completion=completion,
                    note=note,
                    idempotency_key=idempotency_key,
                )

        # Refuse a non-PIC before anything reaches the bucket. The check repeats inside the
        # transaction, which is the one that counts.
        await run_in_threadpool(_pic_check)
        if checked is not None:
            await run_in_threadpool(evidence_store.put, checked.key, checked.content, checked.content_type)
        submission = await run_in_threadpool(_record)
    except _REFUSALS as error:
        _audit(type(error).__name__)
        raise _write_error(error) from error

    stored = submission.evidence
    _audit(
        'replayed' if submission.replayed else 'recorded',
        evidence_id=stored['id'],
        revision=stored['revision'],
        closure_request_id=submission.closure_request_id,
    )
    return {
        'action_id': action_id,
        'version': submission.event.event.version,
        'replayed': submission.replayed,
        'closure_request_id': submission.closure_request_id,
        'evidence': _evidence_view(stored),
    }


def _evidence_view(row: dict[str, Any]) -> dict[str, Any]:
    keys = ('id', 'action_id', 'revision', 'kind', 'url', 'filename', 'content_type', 'size_bytes', 'sha256')
    return {key: row[key] for key in keys} | {'submitted_by': row['submitted_by'], 'created_at': row['created_at']}


@router.get('/evidence/{evidence_id}')
async def get_evidence(
    evidence_id: str,
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
    evidence_store: EvidenceStore | None = Depends(leadership_evidence_store),
) -> Any:
    """One evidence revision: the file itself, or the link. Access is rechecked on every download."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='evidence', evidence_id=evidence_id, result=result)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    if not _enabled() or not migrate.schema_ready():
        _audit('unavailable')
        raise _unavailable('The Ruang Pimpinan records store is not available on this server.')

    def _row() -> dict[str, Any] | None:
        with engine.connect() as connection:
            return evidence_commands.read_evidence(connection, evidence_id)

    row = await run_in_threadpool(_row)
    if row is None:
        _audit('not_found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such evidence.')
    if row['kind'] == 'link':
        _audit('served')
        return _evidence_view(row)
    if evidence_store is None:
        _audit('unavailable')
        raise _unavailable('Evidence storage is not configured on this server.')
    content = await run_in_threadpool(evidence_store.get, row['storage_key'])
    _audit('served')
    filename = quote(row['filename'] or 'evidence')
    return Response(
        content,
        media_type=row['content_type'],
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{filename}",
            'X-Content-Type-Options': 'nosniff',
        },
    )


# --- The BOD's decisions (P2 T4) ----------------------------------------------------------


class ClosureDecisionIn(BaseModel):
    expected_version: int
    decision: Literal['close', 'return', 'reopen']
    # The evidence revision the reviewer looked at; required to close or return.
    evidence_id: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=10_000)
    return_to: Literal['in_progress', 'blocked'] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.post('/actions/{action_id}/closure')
async def post_closure_decision(
    action_id: str,
    view: View,
    scope_id: Scope,
    form: ClosureDecisionIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """Close, return or reopen, as a BOD reviewer. Never the action's own PIC.

    The capability is checked before anything else, so an unauthorised caller learns 403 and not
    whether closure is configured. With the capability but no BOD policy, the answer is 503: there
    is no closure path, and nothing pretends otherwise.
    """

    def _audit(result: str, **fields: Any) -> None:
        audit(
            'leadership_write',
            user=user.id,
            operation='closure_decision',
            action_id=action_id,
            decision=form.decision,
            result=result,
            **fields,
        )

    if not may(permissions, 'bod.review', view, scope_id):
        _audit('refused')
        raise _refuse()
    if not _enabled():
        _audit('unavailable')
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    if not migrate.schema_ready():
        _audit('unavailable')
        raise _unavailable('The Ruang Pimpinan records store is not ready on this server.')
    policy = closure.configured_policy()
    if policy is None:
        _audit('unavailable')
        raise _unavailable('BOD closure is not configured on this server.')

    command = form.model_dump()

    def _run() -> Any:
        with unit_of_work(engine) as uow:
            return closure.decide(uow, action_id=action_id, reviewer=user.id, policy=policy, **command)

    try:
        decided = await run_in_threadpool(_run)
    except _REFUSALS as error:
        _audit(type(error).__name__)
        raise _write_error(error) from error
    _audit(
        'replayed' if decided.replayed else decided.outcome,
        decision_id=decided.decision_id,
        mode=policy.mode,
        close_votes=decided.close_votes,
        quorum=decided.quorum,
    )
    return {
        'action_id': action_id,
        'version': decided.event.event.version,
        'replayed': decided.replayed,
        'decision_id': decided.decision_id,
        'outcome': decided.outcome,
        'close_votes': decided.close_votes,
        'quorum': decided.quorum,
    }
