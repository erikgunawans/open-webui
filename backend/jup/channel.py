"""A Channel Turn: one message from Teams or WhatsApp, answered for the mapped user (E7, spec #84).

The gateway (`gateway/`) proves where a message came from, maps the sender to one JUP user and
asks ent-os for the answer on that user's behalf (ADR-0012 amendment 2026-10-04). By the time a
request reaches this module, `jup.iap_identity` has already admitted it: the gateway principal,
the kill switch on, an existing non-`pending` user holding `jup.channel.use`. This module owns what
happens next, and the route in `routers/jup_channel.py` is a thin shell around it.

**The turn is governed like a typed one.** It runs through `jup.turn.run_turn`, so the vendor
pipeline persists both messages and every fork hook (funnel, contract, tool policy, audit) applies.
It runs with `CHANNEL_TURN_STATE_ATTR` on the built request's state, which `tool_policy.path_of`
reads as an unattended path: nobody is present to approve, so an `external` tool is refused
(ADR-0013). That mark is on the request state, never the body.

**What a caller gets back** is channel-ready text and the link to the chat in the web app, behind
IAP. The audit line names the Channel, the identity hash as the gateway sent it, a hash of the
conversation key and the chat; never an email.

This is the tracer bullet (#86): a new chat for every turn and the answer as it stands. Chat reuse,
`baru` and ordering (#87) and the answer's shaping (#88) build on the same entry point.

Every dependency is injected (store, turn runner, audit, clock), so this imports the standard
library and `jup.*` only, and its tests run under `--only-group dev`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from jup.governance import CHANNEL_TURN_STATE_ATTR
from jup.turn import TurnResult

DEFAULT_PERMISSIONS: dict[str, Any] = {'jup': {'channel': {'use': False}}}

#: The Channels a turn can come from, and how a chat title names them.
CHANNELS: dict[str, str] = {'teams': 'Teams', 'whatsapp': 'WhatsApp'}

#: In `chat.meta`: where the chat came from, so a Channel chat is never mistaken for a typed one.
CHAT_KEY = 'jup_channel'

#: Longer than any message a director types in a chat app; a longer one is not a question.
TEXT_MAX_CHARS = 4000
CONVERSATION_KEY_MAX_CHARS = 512

#: How long the route waits for the answer before replying with the link instead (spec #84).
TURN_SECONDS = 120.0

ANSWERED = 'answered'
PROCESSING = 'processing'
FAILED = 'failed'

#: Product copy decided by Erik (spec #84); changing it is a product change.
PROCESSING_TEXT = 'Jawaban masih diproses — lihat di {link}'

JAKARTA = dt.timezone(dt.timedelta(hours=7))

_HMAC_HEX = re.compile(r'[0-9a-f]{64}')
_FIELDS = frozenset({'channel', 'identity_hash', 'conversation_key', 'text', 'has_attachment'})


def may_use_channel(permissions: Any) -> bool:
    """True only for an exact boolean `jup.channel.use` grant."""
    try:
        return permissions['jup']['channel']['use'] is True
    except (KeyError, TypeError):
        return False


class ChannelRequestInvalid(ValueError):
    """The body is not a Channel Turn request. The route answers 422."""


@dataclass(frozen=True)
class ChannelTurnRequest:
    channel: str
    #: HMAC-SHA256 of the Channel Identity, computed in the gateway. Raw channel ids never reach ent-os.
    identity_hash: str
    conversation_key: str
    text: str
    has_attachment: bool


@dataclass(frozen=True)
class ChannelReply:
    reply: str
    chat_url: str
    outcome: str


def parse_request(body: Any) -> ChannelTurnRequest:
    """The request, checked field by field. Raises `ChannelRequestInvalid` naming the first problem."""
    if not isinstance(body, Mapping):
        raise ChannelRequestInvalid('body must be an object')
    if set(body) != _FIELDS:
        raise ChannelRequestInvalid(f'body must have exactly: {", ".join(sorted(_FIELDS))}')
    if body['channel'] not in CHANNELS:
        raise ChannelRequestInvalid('unknown channel')
    identity_hash = body['identity_hash']
    if not isinstance(identity_hash, str) or not _HMAC_HEX.fullmatch(identity_hash):
        raise ChannelRequestInvalid('identity_hash must be a lowercase hex HMAC-SHA256')
    key = body['conversation_key']
    if not isinstance(key, str) or not key or len(key) > CONVERSATION_KEY_MAX_CHARS:
        raise ChannelRequestInvalid('conversation_key is missing or too long')
    text = body['text']
    if not isinstance(text, str) or not text.strip() or len(text) > TEXT_MAX_CHARS:
        raise ChannelRequestInvalid('text is missing or too long')
    if not isinstance(body['has_attachment'], bool):
        raise ChannelRequestInvalid('has_attachment must be a boolean')
    return ChannelTurnRequest(
        channel=body['channel'],
        identity_hash=identity_hash,
        conversation_key=key,
        text=text.strip(),
        has_attachment=body['has_attachment'],
    )


def hash_key(value: str) -> str:
    """The conversation key as the audit line and chat meta carry it."""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]


def chat_title(channel: str, now: dt.datetime) -> str:
    """`Teams · 2026-10-04 16:30`, in Jakarta time."""
    return f'{CHANNELS[channel]} · {now.astimezone(JAKARTA):%Y-%m-%d %H:%M}'


def chat_url(base_url: str, chat_id: str) -> str:
    return f'{base_url.rstrip("/")}/c/{chat_id}'


class ChatStore(Protocol):
    async def create_chat(self, chat_id: str, user_id: str, title: str, meta: dict) -> None: ...


#: Runs `text` in `chat_id` with `request_state` on the built request: `jup.turn.run_turn`, bound
#: by the route to the user, Asisten JUP and its defaults.
TurnRunner = Callable[[str, str, Mapping[str, Any]], Awaitable[TurnResult]]
Audit = Callable[..., None]


async def run_channel_turn(
    *,
    user_id: str,
    request: ChannelTurnRequest,
    store: ChatStore,
    run: TurnRunner,
    base_url: str,
    audit: Audit,
    now: Callable[[], dt.datetime],
) -> ChannelReply:
    """Runs one Channel Turn for `user_id` and returns the reply for the Channel.

    A chat that cannot be created or a turn that raises is audited as `failed` and re-raised: the
    route answers with an error and the gateway sends its fixed outage reply, never a retry.
    """
    chat_id = str(uuid.uuid4())
    conversation = hash_key(request.conversation_key)
    meta = {
        CHAT_KEY: {
            'channel': request.channel,
            'identity_hash': request.identity_hash,
            'conversation': conversation,
        }
    }
    link = chat_url(base_url, chat_id)
    fields = {
        'channel': request.channel,
        'identity_hash': request.identity_hash,
        'conversation': conversation,
        'chat': chat_id,
    }
    try:
        await store.create_chat(chat_id, user_id, chat_title(request.channel, now()), meta)
        result = await run(chat_id, request.text, {CHANNEL_TURN_STATE_ATTR: request.channel})
    except Exception:
        audit('channel_turn', **fields, outcome=FAILED, reason='turn_error')
        raise
    if result.finished:
        reply = ChannelReply(reply=result.content, chat_url=link, outcome=ANSWERED)
    else:
        reply = ChannelReply(reply=PROCESSING_TEXT.format(link=link), chat_url=link, outcome=PROCESSING)
    audit('channel_turn', **fields, outcome=reply.outcome, reason=None)
    return reply


__all__ = [
    'ANSWERED',
    'CHANNELS',
    'CHAT_KEY',
    'DEFAULT_PERMISSIONS',
    'FAILED',
    'PROCESSING',
    'PROCESSING_TEXT',
    'TEXT_MAX_CHARS',
    'TURN_SECONDS',
    'ChannelReply',
    'ChannelRequestInvalid',
    'ChannelTurnRequest',
    'chat_title',
    'chat_url',
    'hash_key',
    'may_use_channel',
    'parse_request',
    'run_channel_turn',
]
