"""The contract knowledge base's HTTP seam.

Thin by design, like `jup_kb_review`: the rules live in `jup.contracts.*` and are tested without a
server. This module checks who is asking, reaches the tables, and serialises.

- **Titles** (D3, `/titles`): admins only. Every other signed-in account is refused with **403, not
  401** (a 401 bounces a signed-in member to a sign-in page that cannot help). A missing managed group
  is created on first use with its title's grants, and a managed group whose `jup.contracts` grants
  were edited by hand is put back before anyone is moved into it.
- **Import** (`/import`): admins only; reads a drafting run's cards from the read-only bucket mount
  (`JUP_CONTRACTS_DIR`) into the Jakarta database.
- **PDF** (`/{ref}/pdf`): the `fulltext` grant, checked here like the tool checks it. Served under
  `kontrak-<ref>.pdf`, never the OneDrive file name, which can carry an individual's name.
- **Names** (`/parties/resolve`): code → name for display after an answer, with the `names` grant
  only (D2). The model never reads a name.
- **Review** (`/review/…`, phase 2): the `review` grant (Legal) — the queue, one card with its events
  and OCR pages, and every change Legal makes (`jup.contracts.review`). Stale versions are 409.
- **Every write, PDF read and resolve writes one `jup.governance` audit line**, refusals included:
  ids, references and counts only.
"""

import asyncio
import logging
from typing import Any

import copy
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from jup.contracts import access as contract_access
from jup.contracts import imports as contract_imports
from jup.contracts import review as contract_review
from jup.contracts import titles as rules
from jup.contracts import tool as contract_tool
from jup.contracts.migrate import schema_ready
from jup.governance import audit
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

_ADMIN_ONLY = {
    'code': 'admin_only',
    'message': 'Contract titles are set by admins. This account is signed in but is not one.',
}


class ContractTitleStore:
    """The vendor group and user tables the title column touches. A dependency, so tests can swap it."""

    async def all_groups(self) -> list[Any]:
        from open_webui.models.groups import Groups

        return await Groups.get_all_groups()

    async def member_ids(self, group_id: str) -> list[str]:
        from open_webui.models.groups import Groups

        return await Groups.get_group_user_ids_by_id(group_id)

    async def user_exists(self, user_id: str) -> bool:
        from open_webui.models.users import Users

        return await Users.get_user_by_id(user_id) is not None

    async def create_group(self, owner_id: str, form: dict[str, Any]) -> Any:
        from open_webui.models.groups import GroupForm, Groups

        return await Groups.insert_new_group(owner_id, GroupForm(**form))

    async def set_permissions(self, group: Any, permissions: dict[str, Any]) -> Any:
        from open_webui.models.groups import Groups, GroupUpdateForm

        form = GroupUpdateForm(name=group.name, description=group.description, permissions=permissions)
        return await Groups.update_group_by_id(group.id, form)

    async def add(self, group_id: str, user_id: str) -> bool:
        from open_webui.models.groups import Groups

        return await Groups.add_users_to_group(group_id, [user_id]) is not None

    async def remove(self, group_id: str, user_id: str) -> bool:
        from open_webui.models.groups import Groups

        return await Groups.remove_users_from_group(group_id, [user_id]) is not None


def contract_title_store() -> ContractTitleStore:
    return ContractTitleStore()


def _require_admin(user: Any) -> None:
    if getattr(user, 'role', None) != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ADMIN_ONLY)


def _titles_payload() -> list[dict[str, str]]:
    return [{'key': title, 'label': rules.LABELS[title]} for title in rules.TITLES]


async def _assignments(store: ContractTitleStore, managed: dict[str, str]) -> dict[str, list[str]]:
    held: dict[str, list[str]] = {}
    for title in rules.TITLES:
        if title not in managed:
            continue
        for user_id in await store.member_ids(managed[title]):
            held.setdefault(user_id, []).append(title)
    return held


@router.get('/titles')
async def list_titles(
    user=Depends(get_verified_user), store: ContractTitleStore = Depends(contract_title_store)
) -> dict[str, Any]:
    """The four titles and every user's current title(s). Users with none are left out."""
    _require_admin(user)
    managed = rules.managed_groups(await store.all_groups())
    return {'titles': _titles_payload(), 'users': await _assignments(store, managed)}


class TitleForm(BaseModel):
    # None clears the user's title.
    title: str | None = None


# One process sets up the managed groups at a time, so two first moves cannot each create a group.
# Across instances the race remains; `managed_groups` then takes the oldest.
_setup_lock = asyncio.Lock()


async def _ensure_groups(store: ContractTitleStore, owner_id: str) -> dict[str, str]:
    async with _setup_lock:
        groups = await store.all_groups()
        managed = rules.managed_groups(groups)
        by_id = {group.id: group for group in groups}
        for title in rules.TITLES:
            if title not in managed:
                created = await store.create_group(owner_id, rules.group_form(title))
                if created is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={'code': 'group_create_failed', 'message': f'The {title} group could not be created.'},
                    )
                managed[title] = created.id
                continue
            repaired = rules.with_grants(by_id[managed[title]].permissions, title)
            if repaired is not None:
                await store.set_permissions(by_id[managed[title]], repaired)
        return managed


@router.put('/titles/{user_id}')
async def set_title(
    user_id: str,
    form: TitleForm,
    user=Depends(get_verified_user),
    store: ContractTitleStore = Depends(contract_title_store),
) -> dict[str, Any]:
    """Give `user_id` exactly the title in the form, or none."""

    def _audit(result: str, **fields: Any) -> None:
        audit('contract_title', user=user.id, target=user_id, title=form.title, result=result, **fields)

    if getattr(user, 'role', None) != 'admin':
        _audit('refused', code='admin_only')
        _require_admin(user)
    if form.title is not None and form.title not in rules.TITLES:
        _audit('refused', code='unknown_title')
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={'code': 'unknown_title', 'message': f'The titles are {", ".join(rules.TITLES)}.'},
        )
    if not await store.user_exists(user_id):
        _audit('refused', code='user_not_found')
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={'code': 'user_not_found', 'message': 'No such user.'},
        )

    managed = await _ensure_groups(store, user.id)
    held = (await _assignments(store, managed)).get(user_id, [])
    move = rules.plan_move(held, form.title, managed)
    # Remove before adding: a failure in between leaves the user with less access, never more.
    for group_id in move.remove:
        if not await store.remove(group_id, user_id):
            _audit('failed', code='remove_failed')
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={'code': 'remove_failed', 'message': 'The user could not be removed from a title group.'},
            )
    if move.add is not None and not await store.add(move.add, user_id):
        _audit('failed', code='add_failed')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={'code': 'add_failed', 'message': 'The user could not be added to the title group.'},
        )

    now_held = (await _assignments(store, managed)).get(user_id, [])
    _audit('recorded', before=held, after=now_held)
    return {'user_id': user_id, 'titles': now_held}


# --- Import, PDF and names ------------------------------------------------------------------------

NO_STORE = {'Cache-Control': 'private, no-store'}


def contracts_engine() -> Any:
    from open_webui.internal.db import engine

    return engine


def contracts_root() -> Path | None:
    configured = (os.environ.get('JUP_CONTRACTS_DIR') or '').strip()
    return Path(configured) if configured else None


async def contract_reader(user=Depends(get_verified_user)) -> contract_access.Access:
    """The caller's contract access, from their groups; exact-True grants only."""
    return contract_access.Access.from_permissions(
        await get_permissions(user.id, copy.deepcopy(rules.DEFAULT_PERMISSIONS))
    )


def _require_schema() -> None:
    if not schema_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={'code': 'schema_not_ready', 'message': 'The contract tables are not ready.'},
        )


class ImportForm(BaseModel):
    run: str = 'full'


@router.post('/import')
async def import_run(
    form: ImportForm,
    user=Depends(get_verified_user),
    engine: Any = Depends(contracts_engine),
    root: Path | None = Depends(contracts_root),
) -> dict[str, Any]:
    """Read a drafting run's cards into the contract tables. Idempotent; Legal's work is kept."""
    if getattr(user, 'role', None) != 'admin':
        audit('contract_import', user=user.id, run=form.run, result='refused', code='admin_only')
        _require_admin(user)
    _require_schema()
    if root is None or not (root / form.run / 'cards').is_dir():
        audit('contract_import', user=user.id, run=form.run, result='refused', code='run_not_found')
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={'code': 'run_not_found', 'message': 'No such run in the contract bucket mount.'},
        )
    try:
        counts = await run_in_threadpool(contract_imports.import_run, engine, root, form.run, actor=user.id)
    except ValueError:
        audit('contract_import', user=user.id, run=form.run, result='refused', code='bad_run')
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={'code': 'bad_run', 'message': 'Not a run name.'},
        )
    audit('contract_import', user=user.id, run=form.run, result='recorded', **counts)
    return {'run': form.run, **counts}


@router.get('/capabilities')
async def capabilities(reader: contract_access.Access = Depends(contract_reader)) -> dict[str, bool]:
    """What the caller may see. Presentation only: every route and the tool re-check."""
    return {grant: getattr(reader, grant) for grant in rules.CONTRACT_GRANTS}


class ResolveForm(BaseModel):
    codes: list[str] = Field(default_factory=list, max_length=50)


def _resolve(engine: Any, codes: list[str]) -> list[dict[str, str]]:
    from sqlalchemy import select

    from jup.contracts.models import party

    with engine.connect() as connection:
        rows = connection.execute(select(party.c.code, party.c.name).where(party.c.code.in_(codes))).mappings()
        return [dict(row) for row in rows]


@router.post('/parties/resolve')
async def resolve_parties(
    form: ResolveForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    """Names for the codes in an answer, for a reader holding `names` (D2). Anyone else gets none."""
    codes = sorted({code for code in form.codes if code.startswith('Perorangan ')})
    if not reader.names or not codes:
        audit('contract_names', user=user.id, asked=len(codes), result='withheld' if codes else 'empty')
        return JSONResponse({'names': {}}, headers=NO_STORE)
    _require_schema()
    parties = await run_in_threadpool(_resolve, engine, codes)
    names = contract_access.resolve_codes(codes, reader, parties)
    audit('contract_names', user=user.id, asked=len(codes), resolved=len(names), result='ok')
    return JSONResponse({'names': names}, headers=NO_STORE)


@router.get('/{ref}/pdf')
async def contract_pdf(
    ref: str,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
    root: Path | None = Depends(contracts_root),
) -> Any:
    """The scanned PDF, for a reader holding `fulltext`."""
    if not reader.fulltext:
        audit('contract_pdf', user=user.id, ref=ref, result='refused', code='fulltext_required')
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={'code': 'fulltext_required', 'message': contract_access.WITHHELD_FULLTEXT},
        )
    _require_schema()
    source = contract_tool.Source(engine=engine, root=root)
    loaded = await run_in_threadpool(contract_tool.load_contract, source, ref)
    path = root / loaded[0]['run'] / 'src' / f'{loaded[0]["number"]}.pdf' if loaded and root else None
    if path is None or not path.is_file():
        audit('contract_pdf', user=user.id, ref=ref, result='refused', code='not_found')
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={'code': 'not_found', 'message': 'No such contract PDF.'},
        )
    reference = contract_tool.reference(loaded[0])
    audit('contract_pdf', user=user.id, ref=reference, result='ok')
    return FileResponse(
        path,
        media_type='application/pdf',
        filename=f'kontrak-{reference}.pdf',
        content_disposition_type='inline',
        headers=NO_STORE,
    )


# --- Review (phase 2, the "Kartu Kontrak" tab) ----------------------------------------------------
#
# The `review` grant only (Legal). Admin is not Legal (ADR-0012), so an admin without the grant is
# refused like anyone else, with 403. Every write names the version it was made against: a stale one
# is 409 and the screen reloads. A reader without `names` gets the card masked, as the tool would.


def _require_review(user: Any, reader: contract_access.Access, action: str, **fields: Any) -> None:
    if not reader.review:
        audit('contract_review', user=user.id, action=action, result='refused', code='review_required', **fields)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                'code': 'review_required',
                'message': 'Tinjauan kartu kontrak memerlukan akses tinjauan (Tim Legal).',
            },
        )
    _require_schema()


def _masked(value: Any, parties: list[dict[str, str]]) -> Any:
    if isinstance(value, str):
        return contract_access.mask(value, parties)
    if isinstance(value, list):
        return [_masked(item, parties) for item in value]
    if isinstance(value, dict):
        return {key: _masked(item, parties) for key, item in value.items()}
    return value


def _review_view(found: dict[str, Any], reader: contract_access.Access) -> dict[str, Any]:
    if reader.names:
        return found
    parties = found['parties']
    return {
        **found,
        'card': _masked(found['card'], parties),
        'draft_card': _masked(found['draft_card'], parties),
        'events': _masked(found['events'], parties),
        'parties': [{'code': p['code'], 'name': None} for p in parties],
    }


@router.get('/review/queue')
async def review_queue(
    state: str | None = None,
    flag: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    _require_review(user, reader, 'queue')
    try:
        page = await run_in_threadpool(
            contract_review.queue, engine, state=state, flag=flag, q=q, limit=limit, offset=offset
        )
    except contract_review.Invalid as error:
        raise HTTPException(status_code=422, detail={'code': 'invalid', 'message': str(error)})
    return JSONResponse(page, headers=NO_STORE)


@router.get('/review/{contract_id}')
async def review_detail(
    contract_id: str,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    _require_review(user, reader, 'detail', contract=contract_id)
    found = await run_in_threadpool(contract_review.detail, engine, contract_id)
    if found is None:
        raise HTTPException(status_code=404, detail={'code': 'not_found', 'message': 'No such contract.'})
    return JSONResponse(_review_view(found, reader), headers=NO_STORE)


@router.get('/review/{contract_id}/pages')
async def review_pages(
    contract_id: str,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
    root: Path | None = Depends(contracts_root),
) -> Any:
    """Every OCR page, for reading beside the card. Masked unless the reader holds `names`."""
    _require_review(user, reader, 'pages', contract=contract_id)
    found = await run_in_threadpool(contract_review.detail, engine, contract_id)
    if found is None:
        raise HTTPException(status_code=404, detail={'code': 'not_found', 'message': 'No such contract.'})
    row = found['contract']
    path = root / row['run'] / 'ocr-text' / f'{row["number"]}.json' if root else None
    try:
        pages = json.loads(await run_in_threadpool(path.read_text, encoding='utf-8')) if path else None
    except (OSError, ValueError):
        pages = None
    if not isinstance(pages, list):
        raise HTTPException(
            status_code=404,
            detail={'code': 'pages_not_found', 'message': 'The OCR text of this contract is not available.'},
        )
    parties = found['parties']
    shown = [
        {
            'halaman': page.get('n'),
            'teks': (page.get('text') or '') if reader.names else contract_access.mask(page.get('text') or '', parties),
            'ocr_rendah': (page.get('conf') or 0) < 0.8,
        }
        for page in pages
        if isinstance(page, dict)
    ]
    audit('contract_review', user=user.id, action='pages', contract=contract_id, pages=len(shown), result='ok')
    return JSONResponse({'pages': shown}, headers=NO_STORE)


class _Versioned(BaseModel):
    version: int


class FieldForm(_Versioned):
    field: str
    text: str
    pages: list[int] = Field(default_factory=list)


class ApproveForm(_Versioned):
    card_sha256: str


class ReturnForm(_Versioned):
    reason: str


class UnitsForm(_Versioned):
    units: list[str] = Field(default_factory=list, max_length=20)


class DatesForm(_Versioned):
    start: str | None = None
    end: str | None = None
    auto_renewal: bool | None = None


class PartiesForm(_Versioned):
    names: list[str] = Field(default_factory=list, max_length=50)


class LinkForm(_Versioned):
    related_id: str
    kind: str = 'addendum'


async def _write(user: Any, reader: contract_access.Access, action: str, contract_id: str, call: Any) -> Any:
    _require_review(user, reader, action, contract=contract_id)
    try:
        result = await run_in_threadpool(call)
    except LookupError:
        audit('contract_review', user=user.id, action=action, contract=contract_id, result='refused', code='not_found')
        raise HTTPException(status_code=404, detail={'code': 'not_found', 'message': 'No such contract.'})
    except contract_review.Conflict:
        audit('contract_review', user=user.id, action=action, contract=contract_id, result='refused', code='conflict')
        raise HTTPException(
            status_code=409,
            detail={'code': 'conflict', 'message': 'Kartu ini sudah berubah sejak dibuka. Muat ulang lalu ulangi.'},
        )
    except contract_review.Invalid as error:
        audit('contract_review', user=user.id, action=action, contract=contract_id, result='refused', code='invalid')
        raise HTTPException(status_code=422, detail={'code': 'invalid', 'message': str(error)})
    audit(
        'contract_review',
        user=user.id,
        action=action,
        contract=contract_id,
        version=result.get('version'),
        result='recorded',
    )
    return result


@router.patch('/review/{contract_id}/field')
async def review_edit_field(
    contract_id: str,
    form: FieldForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'field',
        contract_id,
        lambda: contract_review.edit_field(
            engine,
            contract_id,
            form.field,
            text=form.text,
            pages=form.pages,
            expected_version=form.version,
            actor=user.id,
        ),
    )


@router.post('/review/{contract_id}/approve')
async def review_approve(
    contract_id: str,
    form: ApproveForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'approve',
        contract_id,
        lambda: contract_review.approve(
            engine, contract_id, card_sha256=form.card_sha256, expected_version=form.version, actor=user.id
        ),
    )


@router.post('/review/{contract_id}/return')
async def review_return(
    contract_id: str,
    form: ReturnForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'return',
        contract_id,
        lambda: contract_review.return_card(
            engine, contract_id, reason=form.reason, expected_version=form.version, actor=user.id
        ),
    )


@router.put('/review/{contract_id}/units')
async def review_units(
    contract_id: str,
    form: UnitsForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'units',
        contract_id,
        lambda: contract_review.set_units(
            engine, contract_id, form.units, expected_version=form.version, actor=user.id
        ),
    )


@router.put('/review/{contract_id}/dates')
async def review_dates(
    contract_id: str,
    form: DatesForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'dates',
        contract_id,
        lambda: contract_review.set_dates(
            engine,
            contract_id,
            start=form.start,
            end=form.end,
            auto_renewal=form.auto_renewal,
            expected_version=form.version,
            actor=user.id,
        ),
    )


@router.put('/review/{contract_id}/parties')
async def review_parties(
    contract_id: str,
    form: PartiesForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    """Setting names needs `names` too: a reviewer who cannot see names cannot write them."""
    if reader.review and not reader.names:
        audit(
            'contract_review',
            user=user.id,
            action='parties',
            contract=contract_id,
            result='refused',
            code='names_required',
        )
        raise HTTPException(
            status_code=403,
            detail={'code': 'names_required', 'message': 'Mengubah daftar perorangan memerlukan akses nama.'},
        )
    return await _write(
        user,
        reader,
        'parties',
        contract_id,
        lambda: contract_review.set_parties(
            engine, contract_id, form.names, expected_version=form.version, actor=user.id
        ),
    )


@router.post('/review/{contract_id}/links')
async def review_link(
    contract_id: str,
    form: LinkForm,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'link',
        contract_id,
        lambda: contract_review.link(
            engine, contract_id, form.related_id, kind=form.kind, expected_version=form.version, actor=user.id
        ),
    )


@router.delete('/review/{contract_id}/links/{related_id}')
async def review_unlink(
    contract_id: str,
    related_id: str,
    version: int,
    user=Depends(get_verified_user),
    reader: contract_access.Access = Depends(contract_reader),
    engine: Any = Depends(contracts_engine),
) -> Any:
    return await _write(
        user,
        reader,
        'unlink',
        contract_id,
        lambda: contract_review.unlink(engine, contract_id, related_id, expected_version=version, actor=user.id),
    )
