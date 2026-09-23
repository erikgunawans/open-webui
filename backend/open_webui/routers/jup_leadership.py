"""Read-only HTTP surface for Ruang Pimpinan (P1).

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

There is deliberately no write route. Action progress, BOD closure and report publication are P2,
each with its own capability; a read grant implies none of them.

The feature is off unless `JUP_LEADERSHIP_ENABLED` is set, and P1 serves only the labelled
illustrative dataset named by `JUP_LEADERSHIP_SAMPLE_FILE`. Neither can be chosen by a request.
"""

import copy
import logging
import os
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from jup.leadership.policy import DEFAULT_PERMISSIONS, SCOPES, allowed_views, may_read
from jup.leadership.reader import DatasetUnavailable, load_dataset, read_overview, read_source
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
        # P1 is read-only. Closure, publication and execution are separate capabilities (P2/P3).
        'operations': [],
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
