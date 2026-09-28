"""The office chat tools (Track O, O1 2/3, #45): `document_templates` and `create_document`.

`tools/jup_documents.py` is the copy stored in the app's DB and exec'd there untested, so it only
delegates here. Everything with a rule in it is in this module or in `jup.office_doc`.

**What `create_document` does:** renders the spec with `jup.office_doc.render`, stores the bytes as
an app File **owned by the asking user**, links it to the chat message, and emits a `files` event
so the answer shows it with the app's own preview and download. The download route only serves a
file to its owner (or an admin), so another staff member gets a 404.

**What the model is told** is written so it cannot mistake a refusal for a document: every
refusal starts `Document not created:`, and a success names the file, says it is a **Draf** and
asks the model to tell the user to review it before use.

**Risk class `write_own`** (ADR-0013): the call only creates a file in the caller's own space, so
it is not gated; the E1 audit line records the call like any other.

Vendor imports stay inside `_store` so that this module, and its tests, load in CI's
`--only-group dev`, which has no fastapi or sqlalchemy.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from jup.office_doc import DOCX_MIME, OfficeDocError, Rendered, catalogue, outline, render, template_for

log = logging.getLogger(__name__)

NOT_CREATED = 'Document not created: '
NO_CHAT = NOT_CREATED + 'documents can only be created inside a chat.'
NO_USER = NOT_CREATED + 'the asking user could not be identified.'
STORE_FAILED = NOT_CREATED + 'the server could not save the file. Tell the user to try again later.'

# (request, rendered, user, chat_id, message_id) -> the message file item for the chat.
Store = Callable[[Any, Rendered, dict, str, str], Awaitable[dict]]


def document_templates(template: str = '') -> str:
    """The template list, or one template's structure, as the model's guide."""
    if not str(template or '').strip():
        return (
            'JUP document templates (JUP Template Dokumen 2.0). Pass a code to create_document, and '
            'ask for one template here to see its structure first.\n' + catalogue()
        )
    try:
        return outline(template_for(template).code)
    except OfficeDocError as error:
        return str(error)


async def create_document(
    *,
    request: Any,
    user: dict | None,
    chat_id: str | None,
    message_id: str | None,
    template: str,
    title: str,
    blocks: Any,
    classification: str = '',
    metadata: dict | None = None,
    floor: str | None = None,
    emit: Callable[[dict], Awaitable[Any]] | None = None,
    store: Store | None = None,
) -> str:
    """Render, store, attach. Returns the text the model reads."""
    if not user or not user.get('id'):
        return NO_USER
    if not chat_id or not message_id:
        return NO_CHAT
    try:
        rendered = await asyncio.to_thread(
            render,
            template,
            title,
            blocks,
            classification=classification or None,
            floor=floor,
            metadata={k: v for k, v in (metadata or {}).items() if v not in (None, '')},
            author=str(user.get('name') or ''),
        )
    except OfficeDocError as error:
        return NOT_CREATED + str(error)

    try:
        item = await (store or _store)(request, rendered, user, chat_id, message_id)
    except Exception:
        log.exception('create_document: storing %s failed', rendered.filename)
        return STORE_FAILED

    if emit is not None:
        await emit({'type': 'files', 'data': {'files': [item]}})

    unfilled = ', '.join(rendered.unfilled)
    return (
        f'Created "{rendered.filename}" from the {rendered.template.name} template '
        f'({rendered.template.code}). Status: Draf. Classification: {rendered.classification}. '
        f'It is attached to this answer; only the user who asked can download it. '
        + (f'Left as template prompts for the user to fill: {unfilled}. ' if unfilled else '')
        + 'Tell the user it is a draft to review and complete before use, and do not repeat the '
        'document text in the answer.'
    )


def file_item(file_id: str, rendered: Rendered) -> dict:
    """The message file entry the chat UI shows with its preview and download."""
    return {
        'type': 'file',
        'id': file_id,
        'name': rendered.filename,
        'size': len(rendered.data),
        'content_type': DOCX_MIME,
    }


def file_metadata(rendered: Rendered, chat_id: str, message_id: str) -> dict:
    """What the stored File records about itself (`meta.data`)."""
    return {
        'chat_id': chat_id,
        'message_id': message_id,
        'jup_office': {
            'kind': 'docx',
            'template': rendered.template.code,
            'classification': rendered.classification,
            'status': rendered.status,
        },
    }


async def _store(request: Any, rendered: Rendered, user: dict, chat_id: str, message_id: str) -> dict:
    """Save through the app's own upload path, owned by `user`, and link it to the message."""
    from fastapi import UploadFile
    from starlette.datastructures import Headers

    from open_webui.models.chats import Chats
    from open_webui.models.users import Users
    from open_webui.routers.files import upload_file_handler

    owner = await Users.get_user_by_id(user['id'])
    if owner is None:
        raise LookupError('the asking user no longer exists')
    upload = UploadFile(
        file=io.BytesIO(rendered.data),
        filename=rendered.filename,
        headers=Headers({'content-type': DOCX_MIME}),
    )
    stored = await upload_file_handler(
        request,
        file=upload,
        metadata=file_metadata(rendered, chat_id, message_id),
        process=False,
        user=owner,
    )
    if stored is None or not stored.id:
        raise RuntimeError('the upload returned no file')
    await Chats.insert_chat_files(chat_id=chat_id, message_id=message_id, file_ids=[stored.id], user_id=owner.id)
    return file_item(stored.id, rendered)


__all__ = [
    'NOT_CREATED',
    'NO_CHAT',
    'NO_USER',
    'STORE_FAILED',
    'create_document',
    'document_templates',
    'file_item',
    'file_metadata',
]
