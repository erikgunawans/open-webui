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

**A conversation behaves like a working session (#87).** A turn lands in the chat its conversation
used last, if that chat saw activity in the last `REUSE_HOURS`; otherwise it starts a new one. `baru`
starts a new chat at once and answers without calling the model. Turns on one conversation run one
after another, in arrival order, so a second question is answered after the first.

**The reply is shaped for a Channel (#88).** If this turn read restricted material
(`jup.office_floor.turn_restricted`), the reply is the chat link only; if that cannot be read, the
same. A clean turn in a chat restricted earlier still arrives as text. An answer over
`CUT_CHARS` is cut at a paragraph and ends with the link. An attachment is not read: the reply says
so, and any text beside it is still answered.

Every dependency is injected (store, turn runner, audit, clock), so this imports the standard
library and `jup.*` only, and its tests run under `--only-group dev`.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
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

#: A conversation silent this long starts a new chat on its next turn (spec #84).
REUSE_HOURS = 8

#: The one command (spec #84): exact, any letter case, trimmed. Any other text is a question.
NEW_CHAT_COMMAND = 'baru'

#: A longer answer is cut at a paragraph and links to the rest (spec #84).
CUT_CHARS = 1500

ANSWERED = 'answered'
PROCESSING = 'processing'
NEW_CHAT = 'new_chat'
#: The turn read restricted material; the reply is the link only.
RESTRICTED = 'restricted'
#: An attachment with no text: the notice only, no turn.
ATTACHMENT = 'attachment'
FAILED = 'failed'

#: Product copy decided by Erik (spec #84); changing it is a product change.
PROCESSING_TEXT = 'Jawaban masih diproses — lihat di {link}'
CUT_TEXT = 'Jawaban lengkap: {link}'
ATTACHMENT_TEXT = 'Lampiran belum didukung di {channel} — unggah lewat {link}'
#: The reply to `baru`. Spec #84 asks only for "a short confirmation"; this wording is ours.
NEW_CHAT_TEXT = 'Percakapan baru dimulai. Silakan ajukan pertanyaan Anda.'

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
    if not isinstance(body['has_attachment'], bool):
        raise ChannelRequestInvalid('has_attachment must be a boolean')
    text = body['text']
    # A message that is only an attachment carries no text; it still gets the attachment notice.
    if not isinstance(text, str) or len(text) > TEXT_MAX_CHARS or not (text.strip() or body['has_attachment']):
        raise ChannelRequestInvalid('text is missing or too long')
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


def cut(text: str, link: str, limit: int = CUT_CHARS) -> str:
    """`text` as it stands when it fits; otherwise cut at the last paragraph before `limit`, plus the link.

    No paragraph break before the limit: the last line break, else the limit itself.
    """
    if len(text) <= limit:
        return text
    head = text[:limit]
    for boundary in ('\n\n', '\n'):
        at = head.rfind(boundary)
        if at > 0:
            head = head[:at]
            break
    return f'{head.rstrip()}\n\n{CUT_TEXT.format(link=link)}'


def is_new_chat_command(text: str) -> bool:
    return text.strip().casefold() == NEW_CHAT_COMMAND


@dataclass(frozen=True)
class ChannelChat:
    """The chat a conversation used last, and when anything last happened in it."""

    id: str
    #: Epoch seconds: the vendor's `chat.updated_at`, which every message write moves.
    updated_at: int


class ChatStore(Protocol):
    async def create_chat(self, chat_id: str, user_id: str, title: str, meta: dict) -> None: ...

    async def latest_chat(self, user_id: str, channel: str, conversation: str) -> ChannelChat | None:
        """The user's newest unarchived chat for this Channel and conversation hash, by creation.

        Newest by creation, not by activity: after `baru`, an answer still finishing in the old chat
        must not pull the conversation back into it.
        """
        ...

    async def turn_restricted(self, chat_id: str, message_id: str) -> bool:
        """Whether the turn that wrote `message_id` read restricted material; raises when unreadable."""
        ...


class ConversationLocks:
    """One turn in flight per conversation; later turns wait and run in arrival order.

    `asyncio.Lock` hands itself to its waiters first come, first served, which is the ordering the
    spec asks for. An entry lives only while someone holds or awaits it.

    **This lock is in-process: it assumes one ent-os instance serves the conversation.** Cloud Run
    keeps one warm (min 1) but may scale to four (max 4, checked 2026-10-04), and turns of one
    conversation that land on two instances are not ordered against each other. At director volume
    that is rare; if it starts to matter, the lock moves to the database.
    """

    def __init__(self) -> None:
        self._locks: dict[str, tuple[asyncio.Lock, int]] = {}

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[None]:
        lock, users = self._locks.get(key, (asyncio.Lock(), 0))
        self._locks[key] = (lock, users + 1)
        try:
            async with lock:
                yield
        finally:
            lock, users = self._locks[key]
            if users == 1:
                del self._locks[key]
            else:
                self._locks[key] = (lock, users - 1)

    def __len__(self) -> int:
        return len(self._locks)


#: The process-wide locks the route uses; tests pass their own.
LOCKS = ConversationLocks()


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
    locks: ConversationLocks = LOCKS,
) -> ChannelReply:
    """Runs one Channel Turn for `user_id` and returns the reply for the Channel.

    The turn waits for any earlier turn of the same conversation to finish first. A chat that cannot
    be found or created, or a turn that raises, is audited as `failed` and re-raised: the route
    answers with an error and the gateway sends its fixed outage reply, never a retry.

    A turn that outlives `TURN_SECONDS` releases the conversation when its reply goes back; the
    answer keeps generating in its chat, and the next turn starts from that chat as it then stands.
    """
    conversation = hash_key(request.conversation_key)
    fields = {
        'channel': request.channel,
        'identity_hash': request.identity_hash,
        'conversation': conversation,
    }
    async with locks.hold(f'{user_id}:{request.channel}:{conversation}'):
        new_chat = is_new_chat_command(request.text)
        chat_id = None
        try:
            chat_id = None if new_chat else await _recent_chat(store, user_id, request.channel, conversation, now())
            if chat_id is None:
                chat_id = str(uuid.uuid4())
                meta = {CHAT_KEY: {**fields}}
                await store.create_chat(chat_id, user_id, chat_title(request.channel, now()), meta)
            link = chat_url(base_url, chat_id)
            if new_chat:
                reply = ChannelReply(reply=NEW_CHAT_TEXT, chat_url=link, outcome=NEW_CHAT)
            elif not request.text:
                reply = ChannelReply(reply=_notice(request, link), chat_url=link, outcome=ATTACHMENT)
            else:
                result = await run(chat_id, request.text, {CHANNEL_TURN_STATE_ATTR: request.channel})
                reply = await _shape(request, result, store, chat_id, link)
        except Exception:
            audit('channel_turn', **fields, chat=chat_id, outcome=FAILED, reason='turn_error')
            raise
    audit('channel_turn', **fields, chat=chat_id, outcome=reply.outcome, reason=None)
    return reply


def _notice(request: ChannelTurnRequest, link: str) -> str:
    return ATTACHMENT_TEXT.format(channel=CHANNELS[request.channel], link=link)


async def _shape(
    request: ChannelTurnRequest, result: TurnResult, store: ChatStore, chat_id: str, link: str
) -> ChannelReply:
    """The reply for a turn that ran: the processing text, the link only, or the (cut) answer."""
    if not result.finished:
        text, outcome = PROCESSING_TEXT.format(link=link), PROCESSING
    else:
        try:
            restricted = await store.turn_restricted(chat_id, result.message_id)
        except Exception:
            restricted = True  # an unreadable marker fails closed: the link only
        if restricted:
            text, outcome = link, RESTRICTED
        else:
            text, outcome = cut(result.content, link), ANSWERED
    if request.has_attachment:
        text = f'{_notice(request, link)}\n\n{text}'
    return ChannelReply(reply=text, chat_url=link, outcome=outcome)


async def _recent_chat(store: ChatStore, user_id: str, channel: str, conversation: str, now: dt.datetime) -> str | None:
    """The conversation's chat if it saw activity less than `REUSE_HOURS` ago, else None."""
    chat = await store.latest_chat(user_id, channel, conversation)
    if chat is None:
        return None
    silent = now.timestamp() - chat.updated_at
    return chat.id if silent < REUSE_HOURS * 3600 else None


__all__ = [
    'ANSWERED',
    'ATTACHMENT',
    'ATTACHMENT_TEXT',
    'CHANNELS',
    'CHAT_KEY',
    'CUT_CHARS',
    'CUT_TEXT',
    'DEFAULT_PERMISSIONS',
    'FAILED',
    'LOCKS',
    'NEW_CHAT',
    'NEW_CHAT_COMMAND',
    'NEW_CHAT_TEXT',
    'PROCESSING',
    'PROCESSING_TEXT',
    'RESTRICTED',
    'REUSE_HOURS',
    'TEXT_MAX_CHARS',
    'TURN_SECONDS',
    'ChannelChat',
    'ChannelReply',
    'ChannelRequestInvalid',
    'ChannelTurnRequest',
    'ConversationLocks',
    'chat_title',
    'chat_url',
    'cut',
    'hash_key',
    'is_new_chat_command',
    'may_use_channel',
    'parse_request',
    'run_channel_turn',
]
