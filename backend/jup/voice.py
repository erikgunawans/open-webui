"""Voice: the switch, the grant, the disclosure acknowledgement and the voice-chat mark (ADR-0017).

Standard library only, so the rules run under `--only-group dev`. The HTTP seam is
`open_webui/routers/jup_voice.py`.

Two marks live in places a client can write, so both are signed with the server secret:

- The acknowledgement sits in `user.info`, which `/users/user/info/update` merges from the client.
  A user can delete it (that only asks them to acknowledge again), but cannot mint one.
- The voice mark sits in `chat.meta`, which chat import copies from the client. It is signed over
  the chat id and the owner, and an imported chat always gets a fresh id, so a copied mark fails.

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
DISCLOSURE_VERSION = '2026-09-27'

#: The model every voice turn runs on (#27 creates it and forces it).
VOICE_MODEL_ID = 'asisten-jup-suara'

DEFAULT_PERMISSIONS: dict[str, Any] = {'jup': {'voice': {'call': False}}}

ACK_KEY = 'jup_voice_ack'
CHAT_KEY = 'jup_voice'


@dataclass(frozen=True)
class Refusal:
    """Why a call cannot start. `code` is stable for the frontend to translate."""

    status: int
    code: str
    message: str


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


def voice_mark(chat_id: str, user_id: str, *, at: int, secret: str) -> dict[str, Any]:
    """The record stored under `chat.meta[CHAT_KEY]` by the start-call route."""
    return {'user_id': user_id, 'at': at, 'sig': _sign(secret, 'voice', chat_id, user_id, at)}


def is_voice_chat(meta: Any, *, chat_id: str, user_id: str, secret: str) -> bool:
    """True only for a chat the start-call route created for `user_id`."""
    mark = meta.get(CHAT_KEY) if isinstance(meta, dict) else None
    if not isinstance(mark, dict) or mark.get('user_id') != user_id:
        return False
    return _matches(mark.get('sig'), secret, 'voice', chat_id, user_id, mark.get('at'))
