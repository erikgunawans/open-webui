"""The Channel API: one endpoint the gateway calls for a Channel Turn (E7, spec #84, ADR-0012 amendment).

Thin on purpose. Every rule lives in `jup.channel` (the turn) and `jup.iap_identity` (who may call):
this file reads the admitted user off the request state, checks the body's shape, binds the turn
runner to Asisten JUP and its defaults, and maps the outcome to HTTP.

**Authentication is the request state, not a session.** The gateway holds no session token, so the
vendor's `get_verified_user` cannot serve this route. The IAP middleware admits the gateway only on
behalf of an existing, non-`pending`, granted user, and only then sets `CHANNEL_TURN_STATE_ATTR` and
`CHANNEL_USER_STATE_ATTR`. Request state cannot be written over HTTP, so a request without both,
a signed-in browser included, is refused here.

Mounted at `/api/jup/channel` (`main.py`), which is `jup.iap_identity.CHANNEL_API_PREFIX`.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from jup import channel, conversation_lock
from jup.governance import CHANNEL_TURN_STATE_ATTR, CHANNEL_USER_STATE_ATTR, audit
from jup.iap_identity import REFUSED_DETAIL
from jup.turn import resolve_defaults, run_turn

log = logging.getLogger(__name__)

router = APIRouter()

#: Overrides the model a Channel Turn runs on; otherwise the deployment's default model, Asisten JUP.
MODEL_ENV = 'JUP_CHANNEL_MODEL'
#: Where the chat link points when the deployment has no `WEBUI_URL` configured.
FALLBACK_BASE_URL = 'https://non-jupe.jup.co.id'


class ChannelStore:
    """The vendor tables a Channel Turn touches: its new chat, and the answer read back."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    async def create_chat(self, chat_id: str, user_id: str, title: str, meta: dict) -> None:
        from open_webui.models.chats import ChatForm, Chats

        form = ChatForm(
            chat={'title': title, 'models': [self.model_id], 'history': {'messages': {}, 'currentId': None}}
        )
        if await Chats.insert_new_chat(chat_id, user_id, form, internal_meta=meta) is None:
            raise RuntimeError('the Channel chat could not be created')

    async def latest_chat(self, user_id: str, channel_id: str, conversation: str) -> channel.ChannelChat | None:
        from sqlalchemy import select

        from open_webui.internal.db import get_async_db_context
        from open_webui.models.chats import Chat

        marker = Chat.meta[(channel.CHAT_KEY, 'conversation')].as_string()
        source = Chat.meta[(channel.CHAT_KEY, 'channel')].as_string()
        stmt = (
            select(Chat.id, Chat.updated_at)
            .where(Chat.user_id == user_id, Chat.archived.is_not(True), marker == conversation, source == channel_id)
            .order_by(Chat.created_at.desc())
            .limit(1)
        )
        async with get_async_db_context() as session:
            row = (await session.execute(stmt)).first()
        return channel.ChannelChat(id=row[0], updated_at=int(row[1] or 0)) if row else None

    async def turn_restricted(self, chat_id: str, message_id: str) -> bool:
        from jup import office_floor

        chat = await self.get_chat(chat_id)
        if chat is None:
            raise office_floor.MarkUnreadable('the Channel chat is gone')
        return office_floor.turn_restricted(chat.meta, message_id)

    async def get_chat(self, chat_id: str) -> Any:
        from open_webui.models.chats import Chats

        return await Chats.get_chat_by_id(chat_id)

    async def get_message(self, chat_id: str, message_id: str) -> dict | None:
        from open_webui.models.chats import Chats

        return await Chats.get_message_by_id_and_message_id(chat_id, message_id)


_lock_engine: Any = None


async def _lock_connection() -> Any:
    """A connection of its own for one conversation lock: `NullPool`, so closing it ends the session
    and releases the lock (`jup.conversation_lock`). Built on first use, beside the app's engine."""
    global _lock_engine
    if _lock_engine is None:
        from sqlalchemy.pool import NullPool

        from open_webui.internal.db import ASYNC_SQLALCHEMY_DATABASE_URL, _create_async_engine, enable_iam_token_auth

        _lock_engine = _create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
        enable_iam_token_auth(_lock_engine)
    return await _lock_engine.connect()


def conversation_locks() -> channel.ConversationLocks:
    """Per conversation, in-process and, on Postgres, across instances (live ent-os scales to 4)."""
    from open_webui.internal.db import ASYNC_SQLALCHEMY_DATABASE_URL

    if not ASYNC_SQLALCHEMY_DATABASE_URL.startswith('postgresql'):
        return channel.ConversationLocks()  # SQLite: one process, so in-process is exact
    return channel.ConversationLocks(shared=conversation_lock.AdvisoryLocks(_lock_connection).hold)


LOCKS = conversation_locks()


async def channel_user(request: Request) -> Any:
    """The user the IAP middleware admitted the gateway for, or a 403 exactly like the middleware's."""
    user_id = getattr(request.state, CHANNEL_USER_STATE_ATTR, None)
    if getattr(request.state, CHANNEL_TURN_STATE_ATTR, None) is not True or not user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, REFUSED_DETAIL)
    from open_webui.models.users import Users

    user = await Users.get_user_by_id(user_id)
    if user is None or user.role == 'pending':
        raise HTTPException(status.HTTP_403_FORBIDDEN, REFUSED_DETAIL)
    return user


async def channel_model() -> str:
    """`JUP_CHANNEL_MODEL`, else the first of the deployment's default models (Asisten JUP).

    Settings are read through the vendor's `Config` store (`ui.default_models`, as `configs.py`
    does): this vendor version keeps no config object on the app state.
    """
    configured = (os.environ.get(MODEL_ENV) or '').strip()
    if configured:
        return configured
    from open_webui.models.config import Config

    defaults = await Config.get('ui.default_models') or ''
    return next((part.strip() for part in str(defaults).split(',') if part.strip()), '')


async def base_url() -> str:
    from open_webui.models.config import Config

    return str(await Config.get('webui.url') or '').strip() or FALLBACK_BASE_URL


@router.post('/turn')
async def channel_turn(request: Request) -> dict[str, Any]:
    user = await channel_user(request)
    try:
        turn_request = channel.parse_request(await request.json())
    except (channel.ChannelRequestInvalid, ValueError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f'channel_request_invalid: {error}') from None

    app = request.app
    model_id = await channel_model()
    if not model_id:
        log.error('jup.channel has no model: set %s or the default model', MODEL_ENV)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'channel_unavailable')
    store = ChannelStore(model_id)

    from open_webui.utils.automations import _build_request

    async def run(chat_id: str, text: str, request_state: Any):
        # Resolved inside the turn, so a failure here is audited as `failed` like any other.
        defaults = await resolve_defaults(app, model_id)
        return await run_turn(
            user=user,
            chat_id=chat_id,
            text=text,
            model_id=model_id,
            store=store,
            handler=app.state.CHAT_COMPLETION_HANDLER,
            build_request=lambda: _build_request(app),
            session_id=f'channel-turn:{chat_id}',
            defaults=defaults,
            request_state=request_state,
            wait_seconds=channel.TURN_SECONDS,
        )

    try:
        reply = await channel.run_channel_turn(
            user_id=user.id,
            request=turn_request,
            store=store,
            run=run,
            base_url=await base_url(),
            audit=audit,
            now=lambda: dt.datetime.now(dt.UTC),
            locks=LOCKS,
        )
    except Exception:
        log.exception('jup.channel turn failed')
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, 'channel_turn_failed') from None
    return {'reply': reply.reply, 'chat_url': reply.chat_url, 'outcome': reply.outcome}
