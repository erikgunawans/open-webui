"""Voice: the switch, the grant, the disclosure acknowledgement and the voice-chat mark (ADR-0017).

Standard library only, so the rules run under `--only-group dev`. The HTTP seam is
`open_webui/routers/jup_voice.py`.

Two marks live in places a client can write, so both are signed with the server secret:

- The acknowledgement sits in `user.info`, which `/users/user/info/update` merges from the client.
  A user can delete it (that only asks them to acknowledge again), but cannot mint one.
- The voice mark sits in `chat.meta`, which chat import copies from the client. It is signed over
  the chat id and the owner, and an imported chat always gets a fresh id, so a copied mark fails.

A third mark seals each answer a voice turn wrote (#28). A chat's owner can edit a stored message
or add one through the chat API, so OpenAI speech reads an answer only when its content still
matches the seal written, server-side, as the turn finished.

GPT-Live (ADR-0018, #34) is a second call mode with its own grant, `jup.voice.live`, and its own
acknowledgement under its own key and version, signed with a different tag so neither
acknowledgement can stand in for the other.

A Ruang Pimpinan panel call (`LEADERSHIP_CONTEXT_KEY`) also records which tab the caller is looking
at, in `chat.meta`, signed over the chat, the owner and the view, so the leadership tool can trust
it as a hint. It never grants anything: the tool re-checks the caller's grants on every read.

Only the start-call route creates voice chats; everything that treats a chat as voice asks
`is_voice_chat`, never the raw meta.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

ENABLED_ENV = 'JUP_VOICE_ENABLED'

#: Bumped whenever the disclosure text in the call UI changes, so everyone acknowledges it again.
DISCLOSURE_VERSION = '2026-10-03'  # sources: knowledge base, contract cards, Ruang Pimpinan (Erik 10-03)

#: The model every voice turn runs on (#27 creates it and forces it).
VOICE_MODEL_ID = 'asisten-jup-suara'

#: The GPT-Live disclosure's version (ADR-0018); bumped with its text in the call UI.
LIVE_DISCLOSURE_VERSION = '2026-10-03'  # sources: knowledge base, contract cards, Ruang Pimpinan (Erik 10-03)

DEFAULT_PERMISSIONS: dict[str, Any] = {'jup': {'voice': {'call': False, 'live': False}}}

ACK_KEY = 'jup_voice_ack'
LIVE_ACK_KEY = 'jup_voice_live_ack'
CHAT_KEY = 'jup_voice'
#: In `message.meta` of an answer a voice turn wrote: a seal over the chat, the message and its
#: content. `meta`, because the vendor's `chat_message` table keeps only its own columns.
SEAL_KEY = 'jup_voice_seal'
#: In `chat.meta` of a panel call: the Ruang Pimpinan tab open beside it, signed.
LEADERSHIP_CONTEXT_KEY = 'jup_leadership_context'
LEADERSHIP_VIEWS = ('board', 'rka')


@dataclass(frozen=True)
class Refusal:
    """Why a call cannot start. `code` is stable for the frontend to translate."""

    status: int
    code: str
    message: str


#: A typed or transcribed turn from the panel; longer is not a spoken question.
PANEL_TURN_MAX_CHARS = 2000
PANEL_TURN_INVALID = Refusal(422, 'voice_turn_invalid', 'Type or say a question first.')


def panel_turn_refusal(text: Any) -> Refusal | None:
    """Why a panel turn's text cannot be asked, or `None` when it can."""
    if not isinstance(text, str) or not text.strip() or len(text) > PANEL_TURN_MAX_CHARS:
        return PANEL_TURN_INVALID
    return None


def enabled(env: Mapping[str, str] | None = None) -> bool:
    """Read per request, so a test or a restarted container needs no reimport."""
    source = os.environ if env is None else env
    return (source.get(ENABLED_ENV) or '').strip().lower() in ('1', 'true')


def may_call(permissions: Any) -> bool:
    """True only for an exact boolean `jup.voice.call` grant.

    The vendor's `chat.call` does not count: it defaults to on for every user and was only ever a
    UI switch, so it cannot be the gate (ADR-0017).
    """
    try:
        return permissions['jup']['voice']['call'] is True
    except (KeyError, TypeError):
        return False


def may_go_live(permissions: Any) -> bool:
    """True only for exact boolean `jup.voice.live` and `jup.voice.call` grants.

    Live runs inside a voice chat, which only the call grant opens; the call grant alone does not
    imply live (ADR-0018).
    """
    try:
        return may_call(permissions) and permissions['jup']['voice']['live'] is True
    except (KeyError, TypeError):
        return False


def access_refusal(*, switched_on: bool, granted: bool) -> Refusal | None:
    """Why this user may not use voice at all: the switch, then the grant."""
    if not switched_on:
        return Refusal(503, 'voice_disabled', 'Voice is not enabled on this server.')
    if not granted:
        return Refusal(403, 'voice_not_granted', 'This account has no access to voice calls.')
    return None


def start_refusal(*, switched_on: bool, granted: bool, acknowledged: bool) -> Refusal | None:
    """Why a call may not start: access first, then the acknowledgement."""
    refusal = access_refusal(switched_on=switched_on, granted=granted)
    if refusal is None and not acknowledged:
        refusal = Refusal(409, 'voice_ack_required', 'Acknowledge the voice disclosure before starting a call.')
    return refusal


def live_refusal(*, switched_on: bool, call_granted: bool, live_granted: bool) -> Refusal | None:
    """Why this user may not use GPT-Live: the switch, the call grant, then the live grant."""
    refusal = access_refusal(switched_on=switched_on, granted=call_granted)
    if refusal is None and not live_granted:
        refusal = Refusal(403, 'voice_live_not_granted', 'This account has no access to GPT-Live calls.')
    return refusal


# --- Signed marks -------------------------------------------------------------------------


def _key(secret: str) -> bytes:
    # The server secret also signs session JWTs, so voice signs with a key derived for voice only.
    # Rotating the secret voids every acknowledgement and voice mark: users acknowledge again and
    # old calls read as ordinary chats. Both fail closed.
    return hmac.new(str(secret).encode('utf-8'), b'jup.voice.v1', hashlib.sha256).digest()


def _sign(secret: str, *parts: Any) -> str:
    if not secret:
        raise ValueError('voice marks need the server secret')
    payload = json.dumps(list(parts), separators=(',', ':'), ensure_ascii=False, default=str).encode('utf-8')
    return hmac.new(_key(secret), payload, hashlib.sha256).hexdigest()


def _matches(signature: Any, secret: str, *parts: Any) -> bool:
    if not isinstance(signature, str) or not secret:
        return False
    return hmac.compare_digest(signature, _sign(secret, *parts))


def acknowledgement(user_id: str, version: str, *, at: int, secret: str) -> dict[str, Any]:
    """The record stored under `user.info[ACK_KEY]`."""
    return {'version': version, 'at': at, 'sig': _sign(secret, 'ack', user_id, version, at)}


def acknowledged(info: Any, user_id: str, *, secret: str, version: str = DISCLOSURE_VERSION) -> bool:
    """True when `info` holds this user's genuine acknowledgement of `version`."""
    record = info.get(ACK_KEY) if isinstance(info, dict) else None
    if not isinstance(record, dict) or record.get('version') != version:
        return False
    return _matches(record.get('sig'), secret, 'ack', user_id, version, record.get('at'))


def live_acknowledgement(user_id: str, version: str, *, at: int, secret: str) -> dict[str, Any]:
    """The record stored under `user.info[LIVE_ACK_KEY]`."""
    return {'version': version, 'at': at, 'sig': _sign(secret, 'live_ack', user_id, version, at)}


def live_acknowledged(info: Any, user_id: str, *, secret: str, version: str = LIVE_DISCLOSURE_VERSION) -> bool:
    """True when `info` holds this user's genuine acknowledgement of the GPT-Live disclosure `version`."""
    record = info.get(LIVE_ACK_KEY) if isinstance(info, dict) else None
    if not isinstance(record, dict) or record.get('version') != version:
        return False
    return _matches(record.get('sig'), secret, 'live_ack', user_id, version, record.get('at'))


def voice_mark(chat_id: str, user_id: str, *, at: int, secret: str) -> dict[str, Any]:
    """The record stored under `chat.meta[CHAT_KEY]` by the start-call route."""
    return {'user_id': user_id, 'at': at, 'sig': _sign(secret, 'voice', chat_id, user_id, at)}


def is_voice_chat(meta: Any, *, chat_id: str, user_id: str, secret: str) -> bool:
    """True only for a chat the start-call route created for `user_id`."""
    mark = meta.get(CHAT_KEY) if isinstance(meta, dict) else None
    if not isinstance(mark, dict) or mark.get('user_id') != user_id:
        return False
    return _matches(mark.get('sig'), secret, 'voice', chat_id, user_id, mark.get('at'))


def leadership_context_mark(chat_id: str, user_id: str, view: str, *, at: int, secret: str) -> dict[str, Any]:
    """The record stored under `chat.meta[LEADERSHIP_CONTEXT_KEY]` when the panel's tab changes."""
    if view not in LEADERSHIP_VIEWS:
        raise ValueError(f'unknown Ruang Pimpinan view: {view!r}')
    return {'view': view, 'at': at, 'sig': _sign(secret, 'leadership_context', chat_id, user_id, view, at)}


def leadership_context_view(meta: Any, *, chat_id: str, user_id: str, secret: str) -> str | None:
    """The tab the panel call is beside, or `None` when there is no genuine mark for this chat and owner."""
    mark = meta.get(LEADERSHIP_CONTEXT_KEY) if isinstance(meta, dict) else None
    if not isinstance(mark, dict) or mark.get('view') not in LEADERSHIP_VIEWS:
        return None
    if not _matches(mark.get('sig'), secret, 'leadership_context', chat_id, user_id, mark['view'], mark.get('at')):
        return None
    return mark['view']


def _digest(content: Any) -> str:
    return hashlib.sha256(str(content or '').encode('utf-8')).hexdigest()


def answer_seal(chat_id: str, message_id: str, content: str, *, secret: str) -> str:
    """The seal stored under `message['meta'][SEAL_KEY]` when a voice turn finishes (#28)."""
    return _sign(secret, 'answer', chat_id, message_id, _digest(content))


def answer_sealed(message: Any, chat_id: str, message_id: str, *, secret: str) -> bool:
    """True only when `message` still holds the content its voice turn wrote."""
    meta = message.get('meta') if isinstance(message, dict) else None
    if not isinstance(meta, dict):
        return False
    return _matches(meta.get(SEAL_KEY), secret, 'answer', chat_id, message_id, _digest(message.get('content')))
