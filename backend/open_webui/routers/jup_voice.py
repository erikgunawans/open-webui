"""Voice calls: the switch, the grant, the disclosure acknowledgement and the only door into a
voice chat (ADR-0017, spec #25).

- **Capabilities** tell the call UI whether to show the call button and the disclosure.
- **Acknowledge** stores a signed record of the current disclosure version in `user.info` and
  writes a `voice_ack` audit line.
- **Start a call** needs the switch, an exact boolean `jup.voice.call` grant from the caller's
  groups (admins included) and a genuine acknowledgement of the current version. It creates a chat
  on the voice model whose `meta` carries a mark signed over the chat id and the caller. Each
  attempt writes a `voice_call` audit line, refusals included. The vendor's `chat.call` is not the
  grant: it defaults to on and was only a UI switch (ADR-0017).

The rules live in `jup.voice`; this module only reads and writes the vendor tables.
"""

from __future__ import annotations

import copy
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from jup import voice
from jup.governance import audit
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

NO_STORE = {'Cache-Control': 'private, no-store'}

# Indonesian first, like the rest of the app. Renamed by the user as they like.
CALL_TITLE = 'Panggilan suara'


class _NoStoreRoute(APIRoute):
    """Every response carries `no-store`, errors included: capabilities are per user."""

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


def _refuse(refusal: voice.Refusal) -> HTTPException:
    return HTTPException(status_code=refusal.status, detail={'code': refusal.code, 'message': refusal.message})


_MISCONFIGURED = voice.Refusal(503, 'voice_misconfigured', 'Voice is not configured on this server.')


class VoiceStore:
    """The vendor tables this router touches. Faked in `tests/test_jup_voice_endpoint.py`."""

    async def user_info(self, user_id: str) -> dict | None:
        from open_webui.models.users import Users

        user = await Users.get_user_by_id(user_id)
        return user.info if user else None

    async def set_user_info_key(self, user_id: str, key: str, value: Any) -> None:
        # Merged over a fresh read rather than the auth-time snapshot, which narrows (does not close)
        # the window in which a concurrent `/users/user/info/update` drops it. A lost record only
        # asks the user to acknowledge again.
        from open_webui.models.users import Users

        user = await Users.get_user_by_id(user_id)
        if user is None:
            raise _refuse(voice.Refusal(404, 'voice_user_missing', 'User not found.'))
        await Users.update_user_by_id(user_id, {'info': {**(user.info or {}), key: value}})

    async def create_chat(self, chat_id: str, user_id: str, title: str, models: list[str], meta: dict) -> None:
        from open_webui.models.chats import ChatForm, Chats

        form = ChatForm(chat={'title': title, 'models': models, 'history': {'messages': {}, 'currentId': None}})
        created = await Chats.insert_new_chat(chat_id, user_id, form, internal_meta=meta)
        if created is None:
            raise _refuse(voice.Refusal(500, 'voice_call_failed', 'The call could not start.'))


def voice_store() -> VoiceStore:
    return VoiceStore()


def voice_secret() -> str:
    from open_webui.env import WEBUI_SECRET_KEY

    return WEBUI_SECRET_KEY


async def voice_permissions(user=Depends(get_verified_user)) -> dict[str, Any]:
    """The caller's merged group permissions, seeded with the all-false `jup.voice` defaults."""
    return await get_permissions(user.id, copy.deepcopy(voice.DEFAULT_PERMISSIONS))


class AcknowledgeForm(BaseModel):
    version: str


@router.get('/capabilities')
async def get_capabilities(
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, Any]:
    if not voice.enabled():
        return {
            'enabled': False,
            'granted': False,
            'acknowledged': False,
            'disclosure_version': voice.DISCLOSURE_VERSION,
        }
    return {
        'enabled': True,
        'granted': voice.may_call(permissions),
        'acknowledged': voice.acknowledged(await store.user_info(user.id), user.id, secret=secret),
        'disclosure_version': voice.DISCLOSURE_VERSION,
    }


@router.post('/acknowledge')
async def acknowledge(
    form: AcknowledgeForm,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, Any]:
    refusal = voice.access_refusal(switched_on=voice.enabled(), granted=voice.may_call(permissions))
    if refusal is not None:
        raise _refuse(refusal)
    if not secret:
        raise _refuse(_MISCONFIGURED)
    if form.version != voice.DISCLOSURE_VERSION:
        # The UI showed an older text than the one in force; the user has not read this one.
        raise _refuse(voice.Refusal(409, 'voice_disclosure_changed', 'The disclosure has changed. Read it again.'))
    record = voice.acknowledgement(user.id, voice.DISCLOSURE_VERSION, at=int(time.time()), secret=secret)
    await store.set_user_info_key(user.id, voice.ACK_KEY, record)
    audit('voice_ack', user=user.id, version=voice.DISCLOSURE_VERSION)
    return {'acknowledged': True, 'disclosure_version': voice.DISCLOSURE_VERSION}


@router.post('/calls')
async def start_call(
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, Any]:
    switched_on = voice.enabled()
    granted = switched_on and voice.may_call(permissions)
    if granted and not secret:
        refusal = _MISCONFIGURED
    else:
        acknowledged = granted and voice.acknowledged(await store.user_info(user.id), user.id, secret=secret)
        refusal = voice.start_refusal(switched_on=switched_on, granted=granted, acknowledged=acknowledged)
    if refusal is not None:
        audit('voice_call', user=user.id, outcome=refusal.code, chat=None)
        raise _refuse(refusal)
    chat_id = str(uuid.uuid4())
    mark = voice.voice_mark(chat_id, user.id, at=int(time.time()), secret=secret)
    await store.create_chat(chat_id, user.id, CALL_TITLE, [voice.VOICE_MODEL_ID], {voice.CHAT_KEY: mark})
    audit('voice_call', user=user.id, outcome='started', chat=chat_id)
    return {'chat_id': chat_id, 'model': voice.VOICE_MODEL_ID}
