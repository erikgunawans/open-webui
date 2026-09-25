"""The knowledge-base review queue: staff submit documents, an admin approves or rejects them.

Thin by design, like `jup_portfolio`: every rule lives in `jup.kb_review` and is tested without a
server. This module resolves who is asking, reaches the vendor tables through `KbReviewStore`, and
serialises. ADR-0015 records the decisions.

- **No table, no migration.** A submission is a vendor file (uploaded through `POST /api/v1/files/`)
  whose `meta['jup_kb_review']` holds its review. `Files.update_file_metadata_by_id` merges keys, so
  nothing else in `meta` is touched.
- **Submit** needs `jup.kb.submit`, an exact boolean from the caller's groups, admins included.
- **Review** is the `admin` role. Every other account is refused with **403, not 401**: 401 means
  "we do not know who you are" and would bounce a signed-in member to a sign-in page that cannot
  help (see `jup_portfolio.get_operating_layer_user`).
- **Approval reuses the vendor's own add-file handler** (`routers/knowledge.add_file_to_knowledge_by_id`),
  into the separate "JUP Staff Contributions" collection, and marks the file approved only after
  that succeeded. A failure leaves it pending and returns the vendor's error.
- **Every submit, approve and reject writes one `jup.governance` audit line**, refusals included:
  ids and the result, never the document, the note or the reason.
"""

import asyncio
import copy
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from jup import kb_review as rules
from jup.governance import audit
from jup.kb_review import ReviewRefused
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

NO_STORE = {'Cache-Control': 'private, no-store'}


class _NoStoreRoute(APIRoute):
    """Every response carries `no-store`, errors included: a preview is an unreviewed document."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def _handler(request: Request) -> Response:
            try:
                response = await handler(request)
            except HTTPException as error:
                response = JSONResponse({'detail': error.detail}, status_code=error.status_code, headers=error.headers)
            except RequestValidationError as error:
                response = JSONResponse(
                    {'detail': jsonable_encoder(error.errors())},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            response.headers.update(NO_STORE)
            return response

        return _handler


router = APIRouter(route_class=_NoStoreRoute)


def _http(refused: ReviewRefused) -> HTTPException:
    """A refusal with a stable code the frontend translates, and the English sentence beside it."""
    return HTTPException(status_code=refused.status, detail={'code': refused.code, 'message': refused.message})


_SUBMIT_FORBIDDEN = ReviewRefused(
    'submit_forbidden',
    'Submitting to the knowledge base is by grant. This account is signed in but does not hold it.',
    403,
)
_REVIEW_FORBIDDEN = ReviewRefused(
    'review_forbidden',
    'The review queue is restricted to admins. This account is signed in but is not one.',
    403,
)


class KbReviewStore:
    """The vendor tables and handlers the queue touches. A dependency, so tests can swap or scope it.

    `db` is `None` in production, where every vendor call opens its own short-lived session. The
    vendor's knowledge routes avoid holding a request-scoped session across an embedding call for
    the same reason, and this keeps to that.
    """

    def __init__(self, db: Any = None) -> None:
        self.db = db

    async def get_file(self, file_id: str) -> Any:
        from open_webui.models.files import Files

        return await Files.get_file_by_id(file_id, db=self.db)

    async def set_review(self, file_id: str, review: dict[str, Any]) -> bool:
        from open_webui.models.files import Files

        return await Files.update_file_metadata_by_id(file_id, {rules.META_KEY: review}, db=self.db) is not None

    async def submissions(self, *, states: tuple[str, ...], user_id: str | None = None) -> list[Any]:
        """Files whose review is in `states`, filtered in SQL on the `meta` JSON key.

        `Column['a']['b'].as_string()` is `json_extract` on SQLite and `->`/`->>` on Postgres; the
        vendor filters `meta` the same way in `Files.get_pending_files_for_knowledge`. The scratch
        SQLite case is in `tests/test_jup_kb_review_endpoint.py`; production is Postgres 16.
        """
        from sqlalchemy import select

        from open_webui.internal.db import get_async_db_context
        from open_webui.models.files import File, FileModel

        state = File.meta[rules.META_KEY]['state'].as_string()
        statement = select(File).filter(state.in_(states))
        if user_id is not None:
            statement = statement.filter(File.user_id == user_id)
        async with get_async_db_context(self.db) as db:
            result = await db.execute(statement.order_by(File.created_at.desc()))
            return [FileModel.model_validate(row) for row in result.scalars().all()]

    async def find_collection(self) -> str | None:
        """The oldest collection with the exact name, if any."""
        from sqlalchemy import select

        from open_webui.internal.db import get_async_db_context
        from open_webui.models.knowledge import Knowledge

        statement = (
            select(Knowledge.id)
            .filter(Knowledge.name == rules.CONTRIBUTIONS_KB_NAME)
            .order_by(Knowledge.created_at.asc())
            .limit(1)
        )
        async with get_async_db_context(self.db) as db:
            return (await db.execute(statement)).scalars().first()

    async def create_collection(self, request: Request, user: Any) -> str:
        """Create it through the vendor handler, owned by the approving admin, with no access grants."""
        from open_webui.models.knowledge import KnowledgeForm
        from open_webui.routers.knowledge import create_new_knowledge

        knowledge = await create_new_knowledge(
            request,
            KnowledgeForm(
                name=rules.CONTRIBUTIONS_KB_NAME,
                description=rules.CONTRIBUTIONS_KB_DESCRIPTION,
                access_grants=[],
            ),
            user=user,
        )
        return knowledge.id

    async def attach(self, request: Request, knowledge_id: str, file_id: str, user: Any) -> None:
        """The vendor's own add-file route, called as a function: process into the collection, then link."""
        from open_webui.routers.knowledge import KnowledgeFileIdForm, add_file_to_knowledge_by_id

        await add_file_to_knowledge_by_id(
            request, knowledge_id, KnowledgeFileIdForm(file_id=file_id), user=user, db=self.db
        )


def kb_review_store() -> KbReviewStore:
    return KbReviewStore()


def kb_review_user_names() -> Callable[[list[str]], Awaitable[dict[str, str]]]:
    """The host's user directory, id to display name. A dependency so tests can swap it."""
    from open_webui.models.users import Users

    async def names(user_ids: list[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        return {person.id: person.name for person in await Users.get_users_by_user_ids(user_ids) if person.name}

    return names


async def kb_permissions(user=Depends(get_verified_user)) -> dict[str, Any]:
    """The caller's merged group permissions, seeded with the all-false `jup.kb` defaults."""
    return await get_permissions(user.id, copy.deepcopy(rules.DEFAULT_PERMISSIONS))


# One process finds-or-creates the collection at a time, so two approvals in the same instance
# cannot create it twice. Across instances the race remains; `find_collection` then takes the
# oldest, so a duplicate is harmless and visible in the admin's knowledge list.
_collection_lock = asyncio.Lock()


def _now() -> int:
    # Seconds, like `file.created_at` and `file.updated_at`.
    return int(time.time())


async def _with_names(
    items: list[dict[str, Any]], user_names: Callable[[list[str]], Awaitable[dict[str, str]]]
) -> list[dict[str, Any]]:
    ids = sorted({item[key] for item in items for key in ('submitted_by', 'reviewed_by') if item.get(key)})
    names = await user_names(ids)
    return [
        {
            **item,
            'submitted_by_name': names.get(item.get('submitted_by') or ''),
            'reviewed_by_name': names.get(item.get('reviewed_by') or ''),
        }
        for item in items
    ]


def _serialise(row: Any, content: str | None = None) -> dict[str, Any]:
    return rules.serialise(file_id=row.id, filename=row.filename, meta=row.meta, content=content)


# --- Reads ------------------------------------------------------------------------------


@router.get('/capabilities')
async def get_capabilities(
    user=Depends(get_verified_user), permissions: dict[str, Any] = Depends(kb_permissions)
) -> dict[str, bool]:
    return {'submit': rules.may_submit(permissions), 'review': rules.may_review(user.role)}


@router.get('/submissions/mine')
async def get_my_submissions(
    user=Depends(get_verified_user),
    store: KbReviewStore = Depends(kb_review_store),
    user_names: Callable[[list[str]], Awaitable[dict[str, str]]] = Depends(kb_review_user_names),
) -> dict[str, Any]:
    """The caller's own submissions in every state. Needs no grant: a revoked submitter still sees the outcome."""
    rows = await store.submissions(states=rules.STATES, user_id=user.id)
    items = rules.newest_first([_serialise(row, rules.content_of(row.data)) for row in rows])
    return {'items': await _with_names(items, user_names)}


@router.get('/submissions')
async def get_queue(
    state: str | None = None,
    user=Depends(get_verified_user),
    store: KbReviewStore = Depends(kb_review_store),
    user_names: Callable[[list[str]], Awaitable[dict[str, str]]] = Depends(kb_review_user_names),
) -> dict[str, Any]:
    if not rules.may_review(user.role):
        raise _http(_REVIEW_FORBIDDEN)
    try:
        states = rules.states_for(state)
    except ReviewRefused as refused:
        raise _http(refused) from refused
    rows = await store.submissions(states=states)
    items = rules.newest_first([_serialise(row, rules.content_of(row.data)) for row in rows])
    return {'items': await _with_names(items, user_names)}


@router.get('/submissions/{file_id}')
async def get_submission(
    file_id: str,
    user=Depends(get_verified_user),
    store: KbReviewStore = Depends(kb_review_store),
    user_names: Callable[[list[str]], Awaitable[dict[str, str]]] = Depends(kb_review_user_names),
) -> dict[str, Any]:
    """One submission with its text, for an admin or its submitter; 404 for anyone else."""
    row = await store.get_file(file_id)
    review = rules.review_of(row.meta) if row is not None else None
    if review is None or not (rules.may_review(user.role) or row.user_id == user.id):
        raise _http(ReviewRefused('not_found', 'No such submission.', 404))
    content = rules.content_of(row.data)
    text, truncated = rules.preview(content)
    [item] = await _with_names([_serialise(row, content)], user_names)
    return {
        **item,
        'preview': {'text': text, 'truncated': truncated, 'length': len(content)},
        # What an approval must send back: the text the reviewer is looking at now.
        'content_sha256': rules.digest(content),
    }


# --- Writes -----------------------------------------------------------------------------


class SubmitForm(BaseModel):
    file_id: str
    note: str | None = None


class ApproveForm(BaseModel):
    # The digest from the preview the reviewer opened. Approval is of that text, not of whatever
    # the file holds by the time the button is pressed.
    content_sha256: str


class RejectForm(BaseModel):
    reason: str | None = None


@router.post('/submissions')
async def submit(
    form: SubmitForm,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(kb_permissions),
    store: KbReviewStore = Depends(kb_review_store),
) -> dict[str, Any]:
    def _audit(result: str, **fields: Any) -> None:
        audit('kb_review', user=user.id, operation='submit', file=form.file_id, result=result, **fields)

    try:
        if not rules.may_submit(permissions):
            raise _SUBMIT_FORBIDDEN
        note = rules.clean_note(form.note)
        row = await store.get_file(form.file_id)
        if row is None:
            raise ReviewRefused('not_found', 'No such file.', 404)
        rules.check_submittable(
            filename=row.filename, owner_id=row.user_id, caller_id=user.id, data=row.data, meta=row.meta
        )
    except ReviewRefused as refused:
        _audit('refused', code=refused.code)
        raise _http(refused) from refused

    review = rules.new_submission(user.id, note, rules.digest(rules.content_of(row.data)), now=_now())
    if not await store.set_review(row.id, review):
        _audit('failed', code='record_failed')
        raise _http(ReviewRefused('record_failed', 'The submission could not be recorded.', 500))
    _audit('recorded')
    return rules.serialise(file_id=row.id, filename=row.filename, meta={**(row.meta or {}), rules.META_KEY: review})


async def _pending_submission(store: KbReviewStore, file_id: str) -> tuple[Any, dict[str, Any]]:
    row = await store.get_file(file_id)
    review = rules.review_of(row.meta) if row is not None else None
    if review is None:
        raise ReviewRefused('not_found', 'No such submission.', 404)
    return row, rules.check_pending(review)


@router.post('/submissions/{file_id}/approve')
async def approve(
    file_id: str,
    form: ApproveForm,
    request: Request,
    user=Depends(get_verified_user),
    store: KbReviewStore = Depends(kb_review_store),
) -> dict[str, Any]:
    def _audit(result: str, **fields: Any) -> None:
        audit('kb_review', user=user.id, operation='approve', file=file_id, result=result, **fields)

    try:
        if not rules.may_review(user.role):
            raise _REVIEW_FORBIDDEN
        row, review = await _pending_submission(store, file_id)
        rules.check_unchanged(expected=form.content_sha256, current_content=rules.content_of(row.data))
    except ReviewRefused as refused:
        _audit('refused', code=refused.code)
        raise _http(refused) from refused

    try:
        async with _collection_lock:
            knowledge_id = await store.find_collection() or await store.create_collection(request, user)
    except Exception as error:
        log.exception('kb-review: the contributions collection could not be found or created')
        _audit('failed', code='collection_unavailable')
        message = f'The "{rules.CONTRIBUTIONS_KB_NAME}" collection could not be created: {_reason(error)}'
        raise _http(ReviewRefused('collection_unavailable', message, 502)) from error

    try:
        await store.attach(request, knowledge_id, row.id, user)
    except Exception as error:
        # The submission stays pending: nothing has been written to it yet.
        log.warning('kb-review: adding file %s to %s failed: %s', row.id, knowledge_id, _reason(error))
        _audit('failed', code='attach_failed', knowledge=knowledge_id)
        message = f'The document could not be added to the knowledge base: {_reason(error)}'
        raise _http(ReviewRefused('attach_failed', message, 502)) from error

    decided = rules.approve(review, user.id, knowledge_id, now=_now())
    if not await store.set_review(row.id, decided):
        # The file is in the collection but still reads pending. Loud, because a second approval
        # would add it again; the vendor link is idempotent enough that it is not a data loss.
        log.error('kb-review: file %s was added to %s but its approval could not be recorded', row.id, knowledge_id)
        _audit('failed', code='record_failed', knowledge=knowledge_id)
        raise _http(ReviewRefused('record_failed', 'The document was added but its approval was not recorded.', 500))
    _audit('recorded', knowledge=knowledge_id)
    return rules.serialise(file_id=row.id, filename=row.filename, meta={**(row.meta or {}), rules.META_KEY: decided})


@router.post('/submissions/{file_id}/reject')
async def reject(
    file_id: str,
    form: RejectForm,
    user=Depends(get_verified_user),
    store: KbReviewStore = Depends(kb_review_store),
) -> dict[str, Any]:
    def _audit(result: str, **fields: Any) -> None:
        audit('kb_review', user=user.id, operation='reject', file=file_id, result=result, **fields)

    try:
        if not rules.may_review(user.role):
            raise _REVIEW_FORBIDDEN
        reason = rules.clean_reason(form.reason)
        row, review = await _pending_submission(store, file_id)
        decided = rules.reject(review, user.id, reason, now=_now())
    except ReviewRefused as refused:
        _audit('refused', code=refused.code)
        raise _http(refused) from refused

    if not await store.set_review(row.id, decided):
        _audit('failed', code='record_failed')
        raise _http(ReviewRefused('record_failed', 'The rejection could not be recorded.', 500))
    _audit('recorded')
    return rules.serialise(file_id=row.id, filename=row.filename, meta={**(row.meta or {}), rules.META_KEY: decided})


def _reason(error: Exception) -> str:
    detail = getattr(error, 'detail', None)
    return str(detail) if detail else str(error) or type(error).__name__
