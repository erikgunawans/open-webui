"""Voice calls: the switch, the grant, the disclosure acknowledgement and the only door into a
voice chat (ADR-0017, spec #25).

- **Capabilities** tell the call UI whether to show the call button and the disclosure.
- **Acknowledge** stores a signed record of the current disclosure version in `user.info` and
  writes a `voice_ack` audit line.
- **Acknowledge GPT-Live** (#34, ADR-0018) stores a separate signed record of the GPT-Live
  disclosure, for callers with both `jup.voice.call` and `jup.voice.live`, and writes `voice_live_ack`.
- **Start a GPT-Live session** (#35) in the caller's own voice call: our server posts the browser's
  WebRTC offer with the fixed config (`jup.voice_live`) to OpenAI and returns only the SDP answer
  (`voice_live`).
- **Start a call** needs the switch, an exact boolean `jup.voice.call` grant from the caller's
  groups (admins included) and a genuine acknowledgement of the current version. It creates a chat
  on the voice model whose `meta` carries a mark signed over the chat id and the caller. Each
  attempt writes a `voice_call` audit line, refusals included. The vendor's `chat.call` is not the
  grant: it defaults to on and was only a UI switch (ADR-0017).

- **The audio boundary** (#28): `routers/audio.py`'s `transcribe` calls `stt_admit` first and
  `stt_audit` last (OpenAI speech-to-text needs the grant; `voice_stt`), and `speech` takes its body
  from `speech_body` (OpenAI or Google reads a stored assistant answer from the caller's own voice
  chat, never free text; `voice_tts`). `GET /speech/parts` tells the call UI how many parts an
  answer has. `tts_google` is the `google` engine the vendor lacks (#32, D23).
- **The Ruang Pimpinan panel** asks in the caller's own voice call without leaving the page: a
  typed or transcribed question runs through the same governed turn GPT-Live delegations use
  (`jup_voice_live.live_turn`), so `enforce_voice_turn` holds it to the voice model and scope
  (`voice_panel_turn`). The panel also records which tab is open (`leadership_context`), signed on
  the chat, once the caller's own leadership grant for that tab is checked.
- **A turn in a voice chat** (#27): `main.py`'s completion entry calls `enforce_voice_turn`, which
  forces the request onto the voice model and tools (`jup.voice_turn`) and writes a `voice_turn`
  audit line naming what it changed.

The rules live in `jup.voice` and `jup.voice_turn`; this module only reads and writes the vendor
tables.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import logging
import os
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from jup import voice, voice_audio, voice_live, voice_turn
from jup.governance import audit
from jup.leadership import policy as leadership_policy
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import get_verified_user
from open_webui.utils.chat_id import is_saved_chat_id
from open_webui.utils.session_pool import get_session

log = logging.getLogger(__name__)

NO_STORE = {'Cache-Control': 'private, no-store'}

#: `main.py` marks a voice turn in its `metadata` under this key (`jup.voice_turn`).
VOICE_TURN_KEY = voice_turn.METADATA_KEY

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

    async def get_chat(self, chat_id: str) -> Any:
        from open_webui.models.chats import Chats

        return await Chats.get_chat_by_id(chat_id)

    async def get_message(self, chat_id: str, message_id: str) -> dict | None:
        from open_webui.models.chats import Chats

        return await Chats.get_message_by_id_and_message_id(chat_id, message_id)

    async def set_message_meta_key(self, chat_id: str, message_id: str, key: str, value: Any) -> None:
        # Into `meta`, merged over a fresh read: the `chat_message` table keeps only its own
        # columns, and a `meta` in the payload replaces the stored one whole.
        from open_webui.models.chats import Chats

        message = await Chats.get_message_by_id_and_message_id(chat_id, message_id) or {}
        meta = {**(message.get('meta') or {}), key: value}
        await Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, message_id, {'meta': meta}, touch=False)

    async def append_chat_meta_items(self, chat_id: str, key: str, items: list) -> None:
        """Appends to a list in `chat.meta[key]`, under a row lock (GPT-Live's unrelayed speech, #36)."""
        from open_webui.internal.db import get_async_db_context
        from open_webui.models.chats import Chat
        from sqlalchemy.orm.attributes import flag_modified

        async with get_async_db_context() as session:
            chat = await session.get(Chat, chat_id, with_for_update=session.bind.dialect.name == 'postgresql')
            if chat is None:
                return
            meta = dict(chat.meta or {})
            meta[key] = [*(meta.get(key) or []), *items]
            chat.meta = meta
            flag_modified(chat, 'meta')
            await session.commit()

    async def set_chat_meta_key(self, chat_id: str, key: str, value: Any) -> None:
        """Sets `chat.meta[key]`, under a row lock, keeping every other key (the voice mark above all)."""
        from open_webui.internal.db import get_async_db_context
        from open_webui.models.chats import Chat
        from sqlalchemy.orm.attributes import flag_modified

        async with get_async_db_context() as session:
            chat = await session.get(Chat, chat_id, with_for_update=session.bind.dialect.name == 'postgresql')
            if chat is None:
                return
            chat.meta = {**(chat.meta or {}), key: value}
            flag_modified(chat, 'meta')
            await session.commit()

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
            'live': _live_capabilities(granted=False, acknowledged=False),
        }
    info = await store.user_info(user.id)
    return {
        'enabled': True,
        'granted': voice.may_call(permissions),
        'acknowledged': voice.acknowledged(info, user.id, secret=secret),
        'disclosure_version': voice.DISCLOSURE_VERSION,
        'live': _live_capabilities(
            granted=voice.may_go_live(permissions),
            acknowledged=voice.live_acknowledged(info, user.id, secret=secret),
        ),
    }


def _live_capabilities(*, granted: bool, acknowledged: bool) -> dict[str, Any]:
    """GPT-Live's own grant and acknowledgement (ADR-0018); the call UI offers the mode only when granted."""
    return {'granted': granted, 'acknowledged': acknowledged, 'disclosure_version': voice.LIVE_DISCLOSURE_VERSION}


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


@router.post('/live/acknowledge')
async def acknowledge_live(
    form: AcknowledgeForm,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, Any]:
    """Stores the caller's acknowledgement of the GPT-Live disclosure (#34), apart from the call's."""
    refusal = voice.live_refusal(
        switched_on=voice.enabled(),
        call_granted=voice.may_call(permissions),
        live_granted=voice.may_go_live(permissions),
    )
    if refusal is not None:
        raise _refuse(refusal)
    if not secret:
        raise _refuse(_MISCONFIGURED)
    if form.version != voice.LIVE_DISCLOSURE_VERSION:
        raise _refuse(
            voice.Refusal(409, 'voice_live_disclosure_changed', 'The GPT-Live disclosure has changed. Read it again.')
        )
    record = voice.live_acknowledgement(user.id, voice.LIVE_DISCLOSURE_VERSION, at=int(time.time()), secret=secret)
    await store.set_user_info_key(user.id, voice.LIVE_ACK_KEY, record)
    audit('voice_live_ack', user=user.id, version=voice.LIVE_DISCLOSURE_VERSION)
    return {'acknowledged': True, 'disclosure_version': voice.LIVE_DISCLOSURE_VERSION}


class LiveSessionForm(BaseModel):
    chat_id: str
    sdp: Any = None


LIVE_ACK_REQUIRED = voice.Refusal(409, 'voice_live_ack_required', 'Acknowledge the GPT-Live disclosure first.')
LIVE_CHAT_NOT_FOUND = voice.Refusal(404, 'voice_live_chat_not_found', 'GPT-Live runs only in your own voice call.')
LIVE_UNAVAILABLE = voice.Refusal(503, 'voice_live_unavailable', 'GPT-Live is not configured on this server.')


async def _live_create(body: dict, key: str) -> tuple[int, Any]:
    """POST `body` to OpenAI's `/v1/live/sessions`; the status and the JSON body (or `None`)."""
    from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL

    session = await get_session()
    async with session.post(
        voice_live.LIVE_URL,
        json=body,
        headers={'Authorization': f'Bearer {key}'},
        ssl=AIOHTTP_CLIENT_SESSION_SSL,
    ) as response:
        try:
            return response.status, await response.json(content_type=None)
        except ValueError:
            return response.status, None


@router.post('/live/sessions')
async def start_live_session(
    form: LiveSessionForm,
    request: Request,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> StreamingResponse:
    """Mints a GPT-Live session for the caller's own voice call and returns only the SDP answer (#35).

    The browser sends its WebRTC offer; our server posts it with the fixed config
    (`jup.voice_live.session_config`) and the key from Secret Manager, so no credential of any kind
    reaches the browser. Every attempt writes `voice_live`, refusals included.
    """
    chat_id = form.chat_id
    refusal = voice.live_refusal(
        switched_on=voice.enabled(),
        call_granted=voice.may_call(permissions),
        live_granted=voice.may_go_live(permissions),
    )
    if refusal is None and not secret:
        refusal = _MISCONFIGURED
    if refusal is None and not voice.live_acknowledged(await store.user_info(user.id), user.id, secret=secret):
        refusal = LIVE_ACK_REQUIRED
    if refusal is None and await _own_voice_chat(chat_id, user.id, store, secret) is None:
        refusal = LIVE_CHAT_NOT_FOUND
    if refusal is None:
        refusal = voice_live.offer_refusal(form.sdp)
    key = (os.environ.get(voice_audio.OPENAI_KEY_ENV) or '').strip()
    if refusal is None and not key:
        refusal = LIVE_UNAVAILABLE
    if refusal is not None:
        audit('voice_live', user=user.id, chat=chat_id, outcome=refusal.code, session=None)
        raise _refuse(refusal)

    try:
        status_code, body = await _live_create(voice_live.session_request(form.sdp), key)
    except Exception as error:  # the network, not a refusal: still one audit line, never a bare 500
        log.warning('GPT-Live session creation failed: %s', type(error).__name__)
        status_code, body = None, None
    answer = voice_live.session_answer(body) if status_code in (200, 201) else voice_live.UPSTREAM
    if isinstance(answer, voice.Refusal):
        audit('voice_live', user=user.id, chat=chat_id, outcome=answer.code, session=None, upstream_status=status_code)
        raise _refuse(answer)
    session_id, sdp = answer
    audit('voice_live', user=user.id, chat=chat_id, outcome='started', session=session_id)
    relay = _live_relay(
        app=request.app, user=user, chat_id=chat_id, session_id=session_id, key=key, store=store, secret=secret
    )
    return StreamingResponse(_live_stream(session_id, sdp, relay), media_type='application/x-ndjson')


#: How often the open call stream says it is alive, well inside any proxy's idle timeout.
LIVE_PING_SECONDS = 15.0


async def _live_relay(**kwargs: Any) -> None:
    """The sideband for one session, answering its delegations until the call ends (#36)."""
    from open_webui.routers import jup_voice_live

    app, user, store, secret = kwargs['app'], kwargs['user'], kwargs['store'], kwargs['secret']
    chat_id = kwargs['chat_id']

    async def ask(question: str) -> tuple[str, str]:
        return await jup_voice_live.live_turn(app, user, chat_id, question, store=store, secret=secret)

    relay = jup_voice_live.LiveRelay(session_id=kwargs['session_id'], user_id=user.id, chat_id=chat_id, ask=ask)
    await jup_voice_live.run_sideband(relay, kwargs['key'], store=store)


async def _live_stream(session_id: str, sdp: str, relay: Any):
    """The call-long response: the SDP answer, pings while the relay runs, then `ended`.

    Holding this request open is what keeps Cloud Run's CPU allocated for the sideband (ADR-0018,
    Option A). When the browser goes away the generator is cancelled, which cancels the relay; the
    relay still closes the session and writes its record.
    """
    yield json.dumps({'type': 'session', 'session_id': session_id, 'sdp': sdp}) + '\n'
    task = asyncio.ensure_future(relay)
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=LIVE_PING_SECONDS)
            if not done:
                yield json.dumps({'type': 'ping'}) + '\n'
        yield json.dumps({'type': 'ended'}) + '\n'
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


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


# --- The Ruang Pimpinan panel ----------------------------------------------------------

CALL_NOT_FOUND = voice.Refusal(404, 'voice_call_not_found', 'This is not your voice call.')
VIEW_REFUSED = voice.Refusal(403, 'leadership_view_refused', 'You cannot read this Ruang Pimpinan view.')
TURN_TIMEOUT = voice.Refusal(504, 'voice_turn_timeout', 'The answer took too long. Try again.')

#: The leadership view the panel's tab hint names (`jup.leadership.policy.SCOPES`).
LEADERSHIP_SCOPE = 'jup-consolidated'


async def leadership_permissions(user=Depends(get_verified_user)) -> dict[str, Any]:
    return await get_permissions(user.id, copy.deepcopy(leadership_policy.DEFAULT_PERMISSIONS))


class ContextForm(BaseModel):
    view: str


class TurnForm(BaseModel):
    text: Any = None


@router.put('/calls/{chat_id}/context')
async def set_call_context(
    chat_id: str,
    form: ContextForm,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(leadership_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, Any]:
    """Records which Ruang Pimpinan tab is open beside the caller's own panel call.

    Only a view the caller may read is recorded; the leadership tool still re-checks the grant on
    every read, so the mark is a hint, never a grant.
    """
    view = form.view
    refusal = None
    if not secret:
        refusal = _MISCONFIGURED
    elif await _own_voice_chat(chat_id, user.id, store, secret) is None:
        refusal = CALL_NOT_FOUND
    elif view not in voice.LEADERSHIP_VIEWS or not leadership_policy.may_read(permissions, view, LEADERSHIP_SCOPE):
        refusal = VIEW_REFUSED
    if refusal is not None:
        audit('leadership_context', user=user.id, chat=chat_id, view=None, outcome=refusal.code)
        raise _refuse(refusal)
    mark = voice.leadership_context_mark(chat_id, user.id, view, at=int(time.time()), secret=secret)
    await store.set_chat_meta_key(chat_id, voice.LEADERSHIP_CONTEXT_KEY, mark)
    audit('leadership_context', user=user.id, chat=chat_id, view=view, outcome='stored')
    return {'view': view}


async def _panel_turn(app: Any, user: Any, chat_id: str, text: str, *, store: Any, secret: str) -> tuple[str, str]:
    from open_webui.routers import jup_voice_live

    return await jup_voice_live.live_turn(
        app, user, chat_id, text, store=store, secret=secret, session_id=f'voice-panel:{chat_id}'
    )


@router.post('/calls/{chat_id}/turns')
async def ask_in_call(
    chat_id: str,
    form: TurnForm,
    request: Request,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, Any]:
    """Asks a typed or transcribed question in the caller's own voice call; the sealed answer comes back.

    The turn is the one GPT-Live delegations run, so the voice model, its tools and its scope are
    forced by `enforce_voice_turn` and the answer is sealed for speech. Sizes are audited, never text.
    """
    text = form.text
    switched_on = voice.enabled()
    granted = switched_on and voice.may_call(permissions)
    if granted and not secret:
        refusal = _MISCONFIGURED
    else:
        acknowledged = granted and voice.acknowledged(await store.user_info(user.id), user.id, secret=secret)
        refusal = voice.start_refusal(switched_on=switched_on, granted=granted, acknowledged=acknowledged)
    if refusal is None and await _own_voice_chat(chat_id, user.id, store, secret) is None:
        refusal = CALL_NOT_FOUND
    if refusal is None:
        refusal = voice.panel_turn_refusal(text)
    chars = len(text) if isinstance(text, str) else 0
    if refusal is not None:
        audit('voice_panel_turn', user=user.id, chat=chat_id, outcome=refusal.code, chars=chars, message_id=None)
        raise _refuse(refusal)
    try:
        message_id, content = await _panel_turn(request.app, user, chat_id, text.strip(), store=store, secret=secret)
    except TimeoutError:
        audit('voice_panel_turn', user=user.id, chat=chat_id, outcome=TURN_TIMEOUT.code, chars=chars, message_id=None)
        raise _refuse(TURN_TIMEOUT)
    audit('voice_panel_turn', user=user.id, chat=chat_id, outcome='answered', chars=chars, message_id=message_id)
    return {'message_id': message_id, 'content': content}


async def enforce_voice_turn(
    form_data: dict, user: Any, *, store: VoiceStore | None = None, secret: str | None = None
) -> bool:
    """Force a completion request in a voice chat onto the voice model and tools, in place.

    Called first thing in `main.py`'s `chat_completion`, before the model is resolved. A chat is a
    voice chat only by its signed mark, checked against the chat's owner, so an admin writing in
    someone's voice chat is held to the same scope. Returns whether the turn is a voice turn, which
    the caller marks in the server-built `metadata` for the tool offer and the folder skip.
    """
    chat_id = form_data.get('chat_id')
    if not isinstance(chat_id, str) or not is_saved_chat_id(chat_id):
        return False
    chat = await (store or voice_store()).get_chat(chat_id)
    if chat is None:
        return False
    secret = voice_secret() if secret is None else secret
    if not voice.is_voice_chat(chat.meta, chat_id=chat.id, user_id=chat.user_id, secret=secret):
        return False
    changed = voice_turn.rewrite(form_data)
    audit('voice_turn', user=user.id, chat=chat_id, changed=changed)
    return True


# --- The audio boundary (#28) -----------------------------------------------------------


def _defaults(store: VoiceStore | None, secret: str | None) -> tuple[VoiceStore, str]:
    return store or voice_store(), voice_secret() if secret is None else secret


async def _permissions_of(user: Any, permissions: dict | None) -> dict:
    if permissions is not None:
        return permissions
    return await get_permissions(user.id, copy.deepcopy(voice.DEFAULT_PERMISSIONS))


async def _vendor_config(key: str) -> Any:
    from open_webui.config import Config

    return await Config.get(key)


async def _own_voice_chat(chat_id: Any, user_id: str, store: VoiceStore, secret: str) -> Any:
    """The chat, when it is `user_id`'s own voice chat; otherwise `None`."""
    if not isinstance(chat_id, str) or not is_saved_chat_id(chat_id):
        return None
    chat = await store.get_chat(chat_id)
    if chat is None or chat.user_id != user_id:
        return None
    return chat if voice.is_voice_chat(chat.meta, chat_id=chat.id, user_id=user_id, secret=secret) else None


def audio_seconds(file_path: str) -> float | None:
    """The recording's length, or `None` when it cannot be read (the line still gets written)."""
    try:
        from pydub import AudioSegment

        return round(AudioSegment.from_file(file_path).duration_seconds, 1)
    except Exception:
        return None


@dataclass(frozen=True)
class SttAdmission:
    """What `stt_admit` learned before transcribing, for the `voice_stt` line `stt_audit` writes."""

    user: str
    chat: str | None
    provider: str
    seconds: float | None
    requested_language: str | None


async def stt_admit(
    request: Any,
    user: Any,
    file_path: str,
    metadata: dict | None = None,
    *,
    engine: str | None = None,
    store: VoiceStore | None = None,
    secret: str | None = None,
    permissions: dict | None = None,
) -> SttAdmission:
    """First thing in `routers/audio.py:transcribe`, on every path that transcribes.

    With the OpenAI engine the caller needs the voice switch and the grant; a refusal is audited
    and raised before any audio leaves. The chat is named only when the call UI sent the caller's
    own voice chat as `?chat_id=`.
    """
    engine = await _vendor_config('audio.stt.engine') if engine is None else engine
    store, secret = _defaults(store, secret)
    query = getattr(request, 'query_params', None) or {}
    chat = await _own_voice_chat(query.get('chat_id'), user.id, store, secret)
    chat_id = chat.id if chat is not None else None
    provider = voice_audio.provider(engine)
    if engine == voice_audio.OPENAI:  # the grant lookup is a DB read; only OpenAI needs it
        granted = voice.may_call(await _permissions_of(user, permissions))
        refusal = voice_audio.stt_refusal(engine, switched_on=voice.enabled(), granted=granted)
        if refusal is not None:
            audit('voice_stt', user=user.id, chat=chat_id, provider=provider, outcome=refusal.code)
            raise _refuse(refusal)
    seconds = await asyncio.to_thread(audio_seconds, file_path)
    return SttAdmission(user.id, chat_id, provider, seconds, (metadata or {}).get('language'))


def stt_audit(admission: SttAdmission, results: Any) -> None:
    """Last thing in `transcribe`: sizes and language, never the transcript.

    OpenAI's `gpt-4o-transcribe` reports no language, so the line then names the one asked for.
    """
    audit(
        'voice_stt',
        user=admission.user,
        chat=admission.chat,
        provider=admission.provider,
        outcome='transcribed',
        seconds=admission.seconds,
        language=voice_audio.detected_language(results, admission.requested_language),
    )


async def seal_answer(metadata: Any, *, store: VoiceStore | None = None, secret: str | None = None) -> None:
    """Seal the answer a voice turn just saved, so OpenAI speech can tell it from an edited one.

    Called at the head of `utils/middleware.py:publish_chat_finished_event`, which both the
    streaming and the non-streaming path reach right after saving the finished answer. The seal
    covers the content as stored, read back rather than taken from the stream.
    """
    if not voice_turn.is_voice_turn(metadata):
        return
    chat_id, message_id = metadata.get('chat_id'), metadata.get('message_id')
    if not chat_id or not message_id:
        return
    store, secret = _defaults(store, secret)
    message = await store.get_message(chat_id, message_id)
    if voice_audio.message_refusal(message) is not None or not secret:
        return
    seal = voice.answer_seal(chat_id, message_id, message['content'], secret=secret)
    await store.set_message_meta_key(chat_id, message_id, voice.SEAL_KEY, seal)


async def _answer_parts(
    chat_id: str, message_id: str, user: Any, store: VoiceStore, secret: str, permissions: dict | None
) -> list[str]:
    """The parts of the caller's own sealed voice-chat answer, or a raised refusal."""
    refusal = voice.access_refusal(
        switched_on=voice.enabled(), granted=voice.may_call(await _permissions_of(user, permissions))
    )
    if refusal is not None:
        raise _refuse(refusal)
    chat = await store.get_chat(chat_id)
    own_chat = chat is not None and chat.user_id == user.id
    voice_chat = own_chat and voice.is_voice_chat(chat.meta, chat_id=chat.id, user_id=user.id, secret=secret)
    message = await store.get_message(chat_id, message_id) if voice_chat else None
    refusal = voice_audio.answer_refusal(
        own_chat=own_chat,
        voice_chat=voice_chat,
        message=message,
        sealed=voice.answer_sealed(message, chat_id, message_id, secret=secret),
    )
    if refusal is not None:
        raise _refuse(refusal)
    return voice_audio.speech_parts(
        voice_audio.speakable_text(message['content']),
        limit=voice_audio.LATER_SPEECH_PART,
        first=voice_audio.FIRST_SPEECH_PART,
    )


async def speech_cached(body: bytes, engine: str) -> bool:
    """Whether `routers/audio.py:speech` will answer this body from its cache, not from the engine.

    Mirrors the vendor's cache name; `tests/test_jup_voice_audio_presence.py` pins that formula.
    """
    from open_webui.routers.audio import SPEECH_CACHE_DIR

    model = await _vendor_config('audio.tts.model')
    name = hashlib.sha256(body + str(engine).encode('utf-8') + str(model).encode('utf-8')).hexdigest()
    return SPEECH_CACHE_DIR.joinpath(f'{name}.mp3').is_file()


async def speech_body(
    request: Any,
    user: Any,
    engine: Any,
    *,
    store: VoiceStore | None = None,
    secret: str | None = None,
    permissions: dict | None = None,
) -> bytes:
    """The body `routers/audio.py:speech` sends on. With OpenAI or Google, built here from a stored answer.

    The request names `{chat_id, message_id, part}`; free text is refused. Every such request
    writes `voice_tts` (sizes, never the text), refusals included; `cached` says whether the
    vendor will answer it from its cache rather than from the engine.
    """
    body = await request.body()
    if not voice_audio.reads_sealed_answers(engine):
        return body
    store, secret = _defaults(store, secret)
    chat_id = message_id = None
    try:
        try:
            payload = json.loads(body)
        except ValueError:
            raise _refuse(voice_audio.MESSAGE_REQUIRED)
        request_or_refusal = voice_audio.speech_request(payload)
        if isinstance(request_or_refusal, voice.Refusal):
            raise _refuse(request_or_refusal)
        chat_id, message_id, part = request_or_refusal
        parts = await _answer_parts(chat_id, message_id, user, store, secret, permissions)
        refusal = voice_audio.part_refusal(part, len(parts))
        if refusal is not None:
            raise _refuse(refusal)
    except HTTPException as error:
        code = error.detail.get('code') if isinstance(error.detail, dict) else 'refused'
        audit('voice_tts', user=user.id, chat=chat_id, message_id=message_id, outcome=code)
        raise
    text = parts[part]
    sent = json.dumps({'input': text}, ensure_ascii=False).encode('utf-8')
    audit(
        'voice_tts',
        user=user.id,
        chat=chat_id,
        message_id=message_id,
        outcome='read',
        chars=len(text),
        part=part,
        parts=len(parts),
        cached=await speech_cached(sent, engine),
    )
    return sent


async def speech_part_count(
    chat_id: str,
    message_id: str,
    user: Any,
    *,
    store: VoiceStore | None = None,
    secret: str | None = None,
    permissions: dict | None = None,
) -> int:
    """How many parts `speech_body` reads this answer in, with the same refusals."""
    store, secret = _defaults(store, secret)
    return len(await _answer_parts(chat_id, message_id, user, store, secret, permissions))


@router.get('/speech/parts')
async def get_speech_parts(
    chat_id: str,
    message_id: str,
    user=Depends(get_verified_user),
    permissions: dict[str, Any] = Depends(voice_permissions),
    store: VoiceStore = Depends(voice_store),
    secret: str = Depends(voice_secret),
) -> dict[str, int]:
    """How many parts `POST /api/v1/audio/speech` will read this answer in (0 to parts - 1)."""
    count = await speech_part_count(chat_id, message_id, user, store=store, secret=secret, permissions=permissions)
    return {'parts': count}


_GOOGLE_SCOPES = ('https://www.googleapis.com/auth/cloud-platform',)
_google_credentials: Any = None


def _google_token_sync() -> str:
    """An access token for the service's own identity (Cloud Run's service account; no key)."""
    global _google_credentials
    import google.auth
    import google.auth.transport.requests

    if _google_credentials is None:
        _google_credentials, _ = google.auth.default(scopes=list(_GOOGLE_SCOPES))
    if not _google_credentials.valid:
        _google_credentials.refresh(google.auth.transport.requests.Request())
    return _google_credentials.token


async def _google_synthesize(body: dict) -> bytes:
    """The MP3 Google Cloud Text-to-Speech makes for one `text:synthesize` body."""
    from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL

    token = await asyncio.to_thread(_google_token_sync)
    session = await get_session()
    async with session.post(
        voice_audio.GOOGLE_SPEECH_URL,
        json=body,
        headers={'Authorization': f'Bearer {token}'},
        ssl=AIOHTTP_CLIENT_SESSION_SSL,
    ) as response:
        if response.status >= 400:
            raise HTTPException(status_code=response.status, detail=f'Google speech: {await response.text()}')
        return base64.b64decode((await response.json())['audioContent'])


async def tts_google(request: Any, payload: dict, file_path: Any, file_body_path: Any, user: Any) -> FileResponse:
    """`routers/audio.py`'s handler for the `google` engine: one sealed part, spoken by Chirp3-HD (#32, D23).

    `payload` is what `speech_body` built from the sealed answer, so it is never free text. The
    voice comes from the vendor's voice row when it names a Google voice, else Kore.
    """
    from open_webui.routers.audio import _write_tts_cache

    voice_name = voice_audio.google_voice(await _vendor_config('audio.tts.voice'))
    body = voice_audio.google_speech_request(str(payload.get('input', '')), voice_name)
    try:
        audio_bytes = await _google_synthesize(body)
    except HTTPException:
        raise
    except Exception as error:
        log.exception(error)
        raise HTTPException(status_code=500, detail='Google speech failed.') from error
    await _write_tts_cache(file_path, audio_bytes, file_body_path, {**payload, 'voice': voice_name})
    return FileResponse(file_path)


def openai_api_key(configured: Any, base_url: Any) -> Any:
    """The key `routers/audio.py` sends to OpenAI: the Secret Manager one when set (#30)."""
    return voice_audio.openai_api_key(configured, base_url, secret=os.environ.get(voice_audio.OPENAI_KEY_ENV))


def refuse_speech_passthrough(user: Any) -> None:
    """`routers/openai.py`'s `/audio/speech` forwards free text to an api.openai.com chat connection.

    Nothing in the app calls it, and OpenAI speech goes through `/api/v1/audio/speech` and
    `speech_body` only, so it is closed rather than gated a second time.
    """
    audit('voice_tts', user=user.id, chat=None, message_id=None, outcome=voice_audio.PASSTHROUGH_CLOSED.code)
    raise _refuse(voice_audio.PASSTHROUGH_CLOSED)
