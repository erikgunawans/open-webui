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

P2 adds the records store (ADR-0014): reading one action and its event history, the PIC's progress
and evidence (`actions.submit`), the BOD's closure decisions (`bod.review`, and only while
`JUP_LEADERSHIP_BOD_POLICY` is configured), and meeting snapshots (`snapshots.publish`; publishing
only while `JUP_LEADERSHIP_PUBLICATION_POLICY` is configured) with the RKA records beside them, and
reviewed imports of a deck's candidate file (`imports.review`). Each write is its own capability,
and a read grant implies none of them. Every P2 read and write leaves a `jup.governance` audit line
naming the user, the operation, the record ids and the result, never content.

The feature is off unless `JUP_LEADERSHIP_ENABLED` is set, and P1 serves only the labelled
illustrative dataset named by `JUP_LEADERSHIP_SAMPLE_FILE`. Neither can be chosen by a request.
"""

import copy
import datetime as dt
import json
import logging
import os
from collections.abc import Awaitable, Callable, Coroutine
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
from jup.leadership import closure, imports, migrate, snapshots
from jup.leadership import evidence as evidence_commands
from jup.leadership.actions import (
    REPORTING_TZ,
    CommandRefused,
    Due,
    assign_pic,
    derive_flags,
    fold_history,
    latest_progress,
)
from jup.leadership.evidence_store import (
    EvidenceRejected,
    EvidenceStore,
    check_file,
    configured_store,
    max_bytes,
    read_bounded,
)
from jup.leadership.kpi import read_kpi
from jup.leadership.policy import DEFAULT_PERMISSIONS, SCOPES, allowed_operations, allowed_views, may, may_read
from jup.leadership.reader import (
    ACTIONS_SOURCES,
    DatasetUnavailable,
    load_dataset,
    read_overview,
    read_source,
    recorded_actions,
)
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
            if (operation != 'bod.review' or closure.configured_policy() is not None)
            and (operation != 'snapshots.publish' or snapshots.configured_publication_policy() is not None)
        ],
        'reason': None if views else 'This account has no Ruang Pimpinan view.',
    }


def leadership_engine() -> Any:
    """The app database, where the leadership records live (ADR-0014). A dependency so tests can swap it."""
    from open_webui.internal.db import engine

    return engine


def _actions_source() -> str:
    """`sample` (the default) or `records`, from the server's configuration; anything else is refused."""
    value = os.environ.get('JUP_LEADERSHIP_ACTIONS_SOURCE', '').strip().lower() or 'sample'
    if value not in ACTIONS_SOURCES:
        raise _unavailable('The Ruang Pimpinan actions source is misconfigured on this server.')
    return value


@router.get('/overview')
async def get_overview(
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """One view's context, metrics, actions, assumptions and module states, naming where its actions came from."""

    def _audit(result: str, **fields: Any) -> None:
        audit('leadership_read', user=user.id, operation='overview', view=view, result=result, **fields)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    try:
        dataset = await _dataset()
        source = _actions_source()
        if source == 'records' and not migrate.schema_ready():
            raise _unavailable('The Ruang Pimpinan records store is not ready on this server.')
    except HTTPException:
        _audit('unavailable')
        raise
    if source == 'sample':
        overview = read_overview(dataset, view)
    else:

        def _register() -> list[dict[str, Any]]:
            with engine.connect() as connection:
                return recorded_actions(connection)

        overview = read_overview(dataset, view, await run_in_threadpool(_register))
    _audit('served', actions_source=source, actions=len(overview['actions']))
    return overview


@router.get('/kpi')
async def get_kpi(
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
) -> dict[str, Any]:
    """The corporate KPI catalogue (targets, weights, definitions) and its illustrative realisasi.

    KPI is performance against the plan, so it rides on the RKA read grant rather than a grant of
    its own. Targets are company figures: refused before anything is read, like every view.
    """

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='kpi', view='rka', result=result)

    if not may_read(permissions, 'rka', scope_id):
        _audit('refused')
        raise _refuse()
    if not _enabled():
        _audit('unavailable')
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    _audit('served')
    return read_kpi()


@router.get('/sources/{source_id}')
async def get_source(
    source_id: str,
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
) -> dict[str, Any]:
    """Citation metadata for a source the requested view declares; 404 for anything else."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='source', view=view, source_id=source_id, result=result)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    try:
        dataset = await _dataset()
    except HTTPException:
        _audit('unavailable')
        raise
    source = read_source(dataset, view, source_id)
    if source is None:
        _audit('not_found')
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No such source in this view.')
    _audit('served')
    return source


def _due(row: dict[str, Any], prefix: str) -> dict[str, str] | None:
    value = row[f'{prefix}_due']
    return None if value is None else {'precision': row[f'{prefix}_due_precision'], 'value': value}


def _read_action_record(engine: Any, action_id: str) -> dict[str, Any] | None:
    row = read_action(engine, action_id)
    if row is None:
        return None
    events = read_events(engine, action_id)
    with engine.connect() as connection:
        revisions = evidence_commands.list_evidence(connection, action_id)
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
        'history': _without_storage_keys(fold_history(events), events, revisions),
        # Every revision in the evidence route's shape, so a reviewer can open the one they judge.
        'evidence': [_evidence_view(row) for row in revisions],
    }


def _without_storage_keys(
    history: list[dict[str, Any]], events: list[Any], revisions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The history with each evidence event naming its revision's id; the bucket key stays the server's."""
    evidence_by_event = {row['event_id']: row['id'] for row in revisions}
    evidence_by_version = {event.version: evidence_by_event.get(event.id) for event in events}
    for entry in history:
        item = entry['payload'].get('evidence') if entry['kind'] == 'evidence_submitted' else None
        if isinstance(item, dict):
            entry['payload'] = entry['payload'] | {
                'evidence': {key: value for key, value in item.items() if key != 'storage_key'}
                | {'evidence_id': evidence_by_version.get(entry['version'])}
            }
    return history


def leadership_user_names() -> Callable[[list[str]], Awaitable[dict[str, str]]]:
    """The host's user directory, id to display name. A dependency so tests can swap it."""
    from open_webui.models.users import Users

    async def names(user_ids: list[str]) -> dict[str, str]:
        return {person.id: person.name for person in await Users.get_users_by_user_ids(user_ids) if person.name}

    return names


@router.get('/actions/{action_id}')
async def get_action(
    action_id: str,
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
    user_names: Callable[[list[str]], Awaitable[dict[str, str]]] = Depends(leadership_user_names),
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
    # Events store the author's user id; the reader sees who that is. The id stays alongside, and a
    # person no longer in the directory keeps no name rather than a guessed one.
    names = await user_names(sorted({entry['author'] for entry in record['history']}))
    for entry in record['history']:
        entry['author_name'] = names.get(entry['author'])
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
    if isinstance(error, closure.OwnerCannotReviseDue):
        return HTTPException(status.HTTP_403_FORBIDDEN, "An action's PIC cannot move its due date.")
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
    closure.OwnerCannotReviseDue,
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


class StateIn(BaseModel):
    expected_version: int
    # Any string: the domain names what an owner may not do, which a Literal would only reject.
    to_state: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=10_000)
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.post('/actions/{action_id}/state')
async def post_state(
    action_id: str,
    view: View,
    scope_id: Scope,
    form: StateIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """The PIC starts, blocks (with a reason) or unblocks the action. Closing stays the BOD's."""

    def _audit(result: str) -> None:
        audit('leadership_write', user=user.id, operation='state', action_id=action_id, result=result)

    _writable(permissions, view, scope_id, _audit)
    command = form.model_dump()

    def _run() -> Any:
        with unit_of_work(engine) as uow:
            return evidence_commands.submit_state(uow, action_id=action_id, actor=user.id, **command)

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
    closure_kind: Literal['completed', 'cancelled', 'superseded'] | None = Form(None),
    reason: str | None = Form(None, max_length=10_000),
    replacement_action_id: str | None = Form(None, max_length=64),
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

    With `completion` (or a `closure_kind` of cancelled, with a reason, or superseded, naming the
    replacement), the action moves to awaiting BOD closure and a closure request is opened on this
    revision. The action is never closed here.
    """

    def _audit(result: str, **fields: Any) -> None:
        audit(
            'leadership_write',
            user=user.id,
            operation='evidence_submit',
            action_id=action_id,
            completion=completion,
            closure_kind=closure_kind,
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
                    closure_kind=closure_kind,
                    reason=reason,
                    replacement_action_id=replacement_action_id,
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


# --- Who the PIC is (T8 follow-up) ---------------------------------------------------------


def leadership_user_lookup() -> Callable[[str], Awaitable[Any]]:
    """The host's user directory by email. A dependency so tests can swap it."""
    from open_webui.models.users import Users

    return Users.get_user_by_email


class PicAssignIn(BaseModel):
    expected_version: int
    # The person, by the email they sign in with; stored as their user id.
    pic_email: str = Field(min_length=3, max_length=320)
    pic_label: str | None = Field(default=None, max_length=500)
    # Required when replacing a PIC; optional on a first assignment.
    reason: str | None = Field(default=None, max_length=10_000)
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.post('/actions/{action_id}/pic')
async def post_pic_assignment(
    action_id: str,
    view: View,
    scope_id: Scope,
    form: PicAssignIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
    lookup: Callable[[str], Awaitable[Any]] = Depends(leadership_user_lookup),
) -> dict[str, Any]:
    """Name the user who is this action's PIC. Needs `actions.assign`; the PIC's evidence rights follow."""

    def _audit(result: str, **fields: Any) -> None:
        audit('leadership_write', user=user.id, operation='pic_assign', action_id=action_id, result=result, **fields)

    if not may(permissions, 'actions.assign', view, scope_id):
        _audit('refused')
        raise _refuse()
    _records_ready(_audit)
    person = await lookup(form.pic_email.strip())
    if person is None:
        _audit('unknown_person')
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, 'No account has that email.')

    def _run() -> Any:
        with unit_of_work(engine) as uow:
            return assign_pic(
                uow,
                action_id=action_id,
                expected_version=form.expected_version,
                pic_user_id=person.id,
                pic_label=(form.pic_label or '').strip() or None,
                author=user.id,
                reason=(form.reason or '').strip() or None,
                idempotency_key=form.idempotency_key,
            )

    try:
        result = await run_in_threadpool(_run)
    except _REFUSALS as error:
        _audit(type(error).__name__)
        raise _write_error(error) from error
    _audit('replayed' if result.replayed else 'recorded', pic_user_id=person.id)
    return {'action_id': action_id, 'version': result.event.version, 'replayed': result.replayed}


# --- The BOD's decisions (P2 T4) ----------------------------------------------------------


class ClosureDecisionIn(BaseModel):
    expected_version: int
    decision: Literal['close', 'return', 'reopen']
    # The evidence revision the reviewer looked at; required to close or return.
    evidence_id: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=10_000)
    return_to: Literal['in_progress', 'blocked'] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class DueIn(BaseModel):
    # The precision vocabulary and value shape are `actions.Due`'s to judge; a bad one is a 422.
    precision: str = Field(min_length=1, max_length=16)
    value: str = Field(min_length=1, max_length=16)


class DueRevisionIn(BaseModel):
    expected_version: int
    due: DueIn
    reason: str = Field(max_length=10_000)
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.post('/actions/{action_id}/due')
async def post_due(
    action_id: str,
    view: View,
    scope_id: Scope,
    form: DueRevisionIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """A BOD member moves the due date, with a reason. Needs no closure policy: one member decides."""

    def _audit(result: str) -> None:
        audit('leadership_write', user=user.id, operation='due_revision', action_id=action_id, result=result)

    if not may(permissions, 'bod.review', view, scope_id):
        _audit('refused')
        raise _refuse()
    if not _enabled():
        _audit('unavailable')
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    if not migrate.schema_ready():
        _audit('unavailable')
        raise _unavailable('The Ruang Pimpinan records store is not ready on this server.')

    def _run() -> Any:
        due = Due(form.due.precision, form.due.value)
        with unit_of_work(engine) as uow:
            return closure.revise_due(
                uow,
                action_id=action_id,
                expected_version=form.expected_version,
                reviser=user.id,
                due=due,
                reason=form.reason,
                idempotency_key=form.idempotency_key,
            )

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


# --- Meeting snapshots and RKA records (P2 T5) ---------------------------------------------


class SnapshotDraftIn(BaseModel):
    meeting_label: str = Field(min_length=1, max_length=500)
    meeting_date: str | None = Field(default=None, max_length=10)


class SnapshotPublishIn(BaseModel):
    expected_version: int
    # The hash of the draft the publisher reviewed; anything else is a conflict.
    content_hash: str = Field(min_length=64, max_length=64)


def _records_ready(audit_unavailable: Callable[[str], None]) -> None:
    if not _enabled():
        audit_unavailable('unavailable')
        raise _unavailable('Ruang Pimpinan is not enabled on this server.')
    if not migrate.schema_ready():
        audit_unavailable('unavailable')
        raise _unavailable('The Ruang Pimpinan records store is not ready on this server.')


def _integrity_refusal(error: Exception) -> HTTPException:
    log.error('refused to serve a Ruang Pimpinan record that failed verification: %s', error)
    return _unavailable('A stored meeting record failed its integrity check and is not served.')


def _snapshot_body(versions: list[Any]) -> dict[str, Any]:
    published = [v for v in versions if v.state == 'published']
    latest = versions[-1]

    def _with_content(version: Any) -> dict[str, Any]:
        return version.summary() | {'content': json.loads(version.content_bytes)}

    return {
        'versions': [v.summary() for v in versions],
        # The meeting record. None while everything is draft, never the draft in its place.
        'published': _with_content(published[-1]) if published else None,
        'latest': _with_content(latest),
    }


@router.get('/snapshots')
async def get_snapshots(
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """The meeting snapshots of one view, newest first. Access is rechecked on every request."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='snapshots', view=view, result=result)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    _records_ready(_audit)

    def _list() -> list[dict[str, Any]]:
        with engine.connect() as connection:
            return snapshots.list_snapshots(connection, view)

    try:
        listed = await run_in_threadpool(_list)
    except snapshots.IntegrityFailure as error:
        _audit('integrity_failure')
        raise _integrity_refusal(error) from error
    _audit('served')
    return {'view': view, 'snapshots': listed}


@router.get('/meeting-changes')
async def get_meeting_changes(
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """The last meeting record of this view against the one before it; unavailable until there are two."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='meeting_changes', view=view, result=result)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    _records_ready(_audit)

    def _compare() -> dict[str, Any]:
        with engine.connect() as connection:
            return snapshots.meeting_changes(connection, view)

    try:
        changes = await run_in_threadpool(_compare)
    except snapshots.IntegrityFailure as error:
        _audit('integrity_failure')
        raise _integrity_refusal(error) from error
    _audit('served')
    return {'view': view, **changes}


@router.get('/snapshots/{snapshot_id}')
async def get_snapshot(
    snapshot_id: str,
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """One snapshot through the view it froze: every version's summary, the published record, the latest content.

    A snapshot of the other view is 404 here, so the Board grant never opens an RKA record.
    """

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='snapshot', snapshot_id=snapshot_id, view=view, result=result)

    if not may_read(permissions, view, scope_id):
        _audit('refused')
        raise _refuse()
    _records_ready(_audit)

    def _read() -> list[Any]:
        with engine.connect() as connection:
            return snapshots.read_versions(connection, snapshot_id)

    try:
        versions = await run_in_threadpool(_read)
    except snapshots.SnapshotNotFound:
        versions = None
    except snapshots.IntegrityFailure as error:
        _audit('integrity_failure')
        raise _integrity_refusal(error) from error
    if not versions or versions[0].view != view:
        _audit('not_found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such snapshot in this view.')
    _audit('served')
    return _snapshot_body(versions)


def _publisher(permissions: dict[str, Any], view: str, scope_id: str, audit_result: Callable[[str], None]) -> None:
    if not may(permissions, 'snapshots.publish', view, scope_id):
        audit_result('refused')
        raise _refuse()
    _records_ready(audit_result)


@router.post('/snapshots')
async def post_snapshot_draft(
    view: View,
    scope_id: Scope,
    form: SnapshotDraftIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """Freeze the view as it stands now into a new meeting draft. Nothing is published here."""

    def _audit(result: str, **fields: Any) -> None:
        audit('leadership_write', user=user.id, operation='snapshot_draft', view=view, result=result, **fields)

    _publisher(permissions, view, scope_id, _audit)
    dataset = await _dataset()
    # A draft freezes what the view serves, from the same actions source.
    source = _actions_source()

    def _run() -> Any:
        with engine.begin() as connection:
            content = snapshots.view_content(connection, dataset, view, source)
            return snapshots.create_draft(
                connection,
                view=view,
                meeting_label=form.meeting_label,
                meeting_date=form.meeting_date,
                content=content,
                author=user.id,
            )

    try:
        draft = await run_in_threadpool(_run)
    except ValueError as error:
        _audit('invalid')
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    _audit('recorded', snapshot_id=draft.snapshot_id, version=draft.version, content_hash=draft.content_hash)
    return draft.summary()


@router.post('/snapshots/{snapshot_id}/publish')
async def post_snapshot_publish(
    snapshot_id: str,
    view: View,
    scope_id: Scope,
    form: SnapshotPublishIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """Publish the latest draft, by the hash the publisher reviewed. 503 while no policy is configured."""

    def _audit(result: str, **fields: Any) -> None:
        audit(
            'leadership_write',
            user=user.id,
            operation='snapshot_publish',
            snapshot_id=snapshot_id,
            view=view,
            result=result,
            **fields,
        )

    _publisher(permissions, view, scope_id, _audit)
    policy = snapshots.configured_publication_policy()
    if policy is None:
        _audit('unavailable')
        raise _unavailable('Publication is not configured on this server; every snapshot stays a draft.')

    def _run() -> Any:
        with engine.begin() as connection:
            head = snapshots.read_versions(connection, snapshot_id)
            if head[0].view != view:
                raise snapshots.SnapshotNotFound(snapshot_id)
            return snapshots.publish(
                connection,
                snapshot_id=snapshot_id,
                expected_version=form.expected_version,
                content_hash=form.content_hash,
                publisher=user.id,
                policy=policy,
            )

    try:
        published = await run_in_threadpool(_run)
    except snapshots.SnapshotNotFound as error:
        _audit('not_found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such snapshot in this view.') from error
    except snapshots.SnapshotConflict as error:
        _audit('conflict')
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                'message': 'This snapshot changed since you reviewed it. Reload and try again.',
                'version': error.latest_version,
            },
        ) from error
    except snapshots.SnapshotRefused as error:
        _audit('refused_by_rule')
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    except snapshots.IntegrityFailure as error:
        _audit('integrity_failure')
        raise _integrity_refusal(error) from error
    _audit('published', version=published.version, content_hash=published.content_hash)
    return published.summary()


@router.get('/baselines')
async def get_baselines(
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """Every RKA record (approved baselines, revisions, forecasts), for a reader of the RKA view."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='baselines', result=result)

    if not may_read(permissions, 'rka', scope_id):
        _audit('refused')
        raise _refuse()
    _records_ready(_audit)

    def _list() -> list[dict[str, Any]]:
        with engine.connect() as connection:
            return snapshots.list_rka(connection)

    try:
        records = await run_in_threadpool(_list)
    except snapshots.IntegrityFailure as error:
        _audit('integrity_failure')
        raise _integrity_refusal(error) from error
    _audit('served')
    return {'records': records}


# --- Reviewed imports (P2 T6) ---------------------------------------------------------------


class CandidateReviewIn(BaseModel):
    decision: Literal['accept', 'link', 'reject']
    action_id: str | None = Field(default=None, max_length=64)


def _import_reviewer(
    permissions: dict[str, Any], view: str, scope_id: str, audit_result: Callable[[str], None]
) -> None:
    if not may(permissions, 'imports.review', view, scope_id):
        audit_result('refused')
        raise _refuse()
    _records_ready(audit_result)


@router.post('/imports')
async def post_import(
    view: View,
    scope_id: Scope,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """A deck's candidate file, stored for review. The same bytes again return the first batch."""

    def _audit(result: str, **fields: Any) -> None:
        audit('leadership_write', user=user.id, operation='import_upload', result=result, **fields)

    _import_reviewer(permissions, view, scope_id, _audit)
    try:
        raw = await run_in_threadpool(read_bounded, file.file, imports.MAX_BYTES)
    except EvidenceRejected as error:
        _audit('too_large')
        raise HTTPException(error.status, 'The candidate file is too large.') from error

    def _run() -> Any:
        with engine.begin() as connection:
            return imports.ingest(connection, raw, filename=file.filename or '', uploader=user.id)

    try:
        batch = await run_in_threadpool(_run)
    except imports.InvalidCandidates as error:
        _audit('invalid')
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    _audit('recorded' if batch.created else 'replayed', batch_id=batch.id)
    return {'batch_id': batch.id, 'created': batch.created}


@router.get('/imports')
async def get_imports(
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """Every import batch, newest first. Candidates are unreviewed material, so this is the reviewer's."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='imports', result=result)

    _import_reviewer(permissions, view, scope_id, _audit)

    def _list() -> list[dict[str, Any]]:
        with engine.connect() as connection:
            return imports.list_batches(connection)

    batches = await run_in_threadpool(_list)
    _audit('served')
    return {'batches': batches}


@router.get('/imports/{batch_id}')
async def get_import(
    batch_id: str,
    view: View,
    scope_id: Scope,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """One batch and its candidates, with matches, conflicts and the verification label."""

    def _audit(result: str) -> None:
        audit('leadership_read', user=user.id, operation='import', batch_id=batch_id, result=result)

    _import_reviewer(permissions, view, scope_id, _audit)

    def _read() -> dict[str, Any]:
        with engine.connect() as connection:
            return imports.read_batch(connection, batch_id)

    try:
        batch = await run_in_threadpool(_read)
    except imports.BatchNotFound as error:
        _audit('not_found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such import batch.') from error
    _audit('served')
    return batch


@router.post('/imports/candidates/{candidate_id}/review')
async def post_candidate_review(
    candidate_id: str,
    view: View,
    scope_id: Scope,
    form: CandidateReviewIn,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    engine: Any = Depends(leadership_engine),
) -> dict[str, Any]:
    """Accept, link or reject one candidate. Each candidate is reviewed once."""

    def _audit(result: str, **fields: Any) -> None:
        audit(
            'leadership_write',
            user=user.id,
            operation='import_review',
            candidate_id=candidate_id,
            decision=form.decision,
            result=result,
            **fields,
        )

    _import_reviewer(permissions, view, scope_id, _audit)

    def _run() -> dict[str, Any]:
        return imports.review_candidate(
            engine, candidate_id=candidate_id, decision=form.decision, reviewer=user.id, action_id=form.action_id
        )

    try:
        reviewed = await run_in_threadpool(_run)
    except imports.BatchNotFound as error:
        _audit('not_found')
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such candidate.') from error
    except imports.AlreadyReviewed as error:
        _audit('already_reviewed')
        raise HTTPException(status.HTTP_409_CONFLICT, 'This candidate was already reviewed.') from error
    except imports.ImportRefused as error:
        _audit('refused_by_rule')
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    _audit(reviewed['review_state'], action_id=reviewed['action_id'])
    return reviewed
