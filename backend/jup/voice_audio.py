"""The audio boundary: who may send speech to OpenAI, and what OpenAI may be asked to read (#28).

Standard library only, so the rules run under `--only-group dev`. The HTTP seam is in
`open_webui/routers/jup_voice.py` (`stt_admit`, `stt_audit`, `speech_body`), which two vendor
inserts in `routers/audio.py` call (`deploy/gcp/VENDOR-PATCHES.md`).

- **Speech to text.** With the OpenAI engine, a transcription needs the voice switch and the
  `jup.voice.call` grant, on every path that transcribes: the transcription route and an audio
  file upload alike. Other engines stay as the vendor gates them (`chat.stt`); only OpenAI sends
  speech out of the country (D16, D21). Every transcription writes `voice_stt`.
- **Text to speech.** With the OpenAI engine, the request names a message, never text: an
  assistant answer in the caller's own voice chat, whose content still matches the seal written
  as its voice turn finished (`jup.voice.answer_sealed`), so an answer edited or added through
  the chat API is not read. The server drops the tool and reasoning blocks and sends that, so what
  is heard is the stored governed answer (ADR-0017). A long answer is read in parts. Every
  request writes `voice_tts`.
- **The key.** OpenAI's key lives in Secret Manager (`openai-live-key`, ADR-0017) and reaches the
  service as `JUP_VOICE_OPENAI_API_KEY`. The vendor's own key rows are seeded into the app DB on
  first boot and then win over any env var, so the key is swapped in at the two call sites
  instead, and only for `https://api.openai.com` (#30).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from jup.voice import Refusal, access_refusal

#: OpenAI's `/audio/speech` takes at most 4096 characters; parts stay well under it.
SPEECH_PART_LIMIT = 4000

OPENAI = 'openai'

#: The env var the service gets from Secret Manager (`deploy/gcp/deploy.sh`).
OPENAI_KEY_ENV = 'JUP_VOICE_OPENAI_API_KEY'


def openai_api_key(configured: str | None, base_url: str | None, *, secret: str | None) -> str | None:
    """The key to send with an OpenAI audio request: the secret, but only to OpenAI itself.

    An admin can point the vendor's base URL anywhere; the secret never follows it there.
    """
    # A pasted secret carries trailing newlines (openai-live-key had two), and aiohttp refuses
    # them in a header as a header-injection attempt.
    secret = (secret or '').strip()
    if not secret:
        return configured
    try:
        parts = urlsplit(base_url or '')
    except ValueError:
        return configured
    if parts.scheme == 'https' and parts.netloc == 'api.openai.com':
        return secret
    return configured


_DETAILS = re.compile(r'<details\b[^>]*>.*?</details>', re.DOTALL | re.IGNORECASE)
_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+')


# --- Speech to text ---------------------------------------------------------------------


def stt_refusal(engine: Any, *, switched_on: bool, granted: bool) -> Refusal | None:
    """Why this transcription may not go to OpenAI, or `None`. Other engines are not ours to gate."""
    if engine != OPENAI:
        return None
    return access_refusal(switched_on=switched_on, granted=granted)


def provider(engine: Any) -> str:
    """The name the audit line gives the engine; the vendor's empty engine is local Whisper."""
    return str(engine) if engine else 'local'


def detected_language(results: Any, requested: str | None = None) -> str | None:
    """The language a transcription reported, else the one asked for, else unknown."""
    for result in results or []:
        if isinstance(result, Mapping) and result.get('language'):
            return str(result['language'])
    return requested or None


# --- Text to speech ---------------------------------------------------------------------

MESSAGE_REQUIRED = Refusal(400, 'voice_tts_message_required', 'Send a chat id and a message id; free text is not read.')
BAD_PART = Refusal(400, 'voice_tts_message_required', 'The part must be a whole number from 0.')
#: Someone else's chat reads as missing too, so a chat id cannot be probed.
ANSWER_NOT_FOUND = Refusal(404, 'voice_tts_not_found', 'No answer to read.')
NOT_READY = Refusal(409, 'voice_tts_not_ready', 'The answer is still being written.')
NOT_A_VOICE_CHAT = Refusal(403, 'voice_tts_not_voice', 'Only answers in a voice call are read by voice.')
UNSEALED = Refusal(409, 'voice_tts_unsealed', 'This answer is not the one the assistant wrote in the call.')
NO_SUCH_PART = Refusal(404, 'voice_tts_no_part', 'The answer has no such part.')
PASSTHROUGH_CLOSED = Refusal(403, 'voice_tts_passthrough_closed', 'Use the voice call to hear answers.')


def speech_request(payload: Any) -> tuple[str, str, int] | Refusal:
    """The `(chat_id, message_id, part)` a speech request names, or why it is refused.

    Free text is refused outright, even next to a message id: OpenAI reads stored answers only.
    """
    if not isinstance(payload, Mapping) or 'input' in payload:
        return MESSAGE_REQUIRED
    chat_id, message_id, part = payload.get('chat_id'), payload.get('message_id'), payload.get('part', 0)
    if not isinstance(chat_id, str) or not chat_id or not isinstance(message_id, str) or not message_id:
        return MESSAGE_REQUIRED
    if isinstance(part, bool) or not isinstance(part, int) or part < 0:
        return BAD_PART
    return chat_id, message_id, part


def message_refusal(message: Any) -> Refusal | None:
    """Why this stored message may not be read aloud, or `None`."""
    if not isinstance(message, Mapping) or message.get('role') != 'assistant' or not message.get('content'):
        return ANSWER_NOT_FOUND
    if message.get('done') is False:
        return NOT_READY
    return None


def answer_refusal(*, own_chat: bool, voice_chat: bool, message: Any, sealed: bool) -> Refusal | None:
    """Why this answer may not be read by OpenAI, or `None`: whose chat, what kind, what message."""
    if not own_chat:
        return ANSWER_NOT_FOUND
    if not voice_chat:
        return NOT_A_VOICE_CHAT
    refusal = message_refusal(message)
    if refusal is None and not sealed:
        refusal = UNSEALED
    return refusal


def part_refusal(part: int, count: int) -> Refusal | None:
    return NO_SUCH_PART if part >= count else None


def speakable_text(content: str) -> str:
    """The answer as heard: tool-call and reasoning blocks removed, nothing else changed."""
    return _DETAILS.sub('', content or '').strip()


def speech_parts(text: str, limit: int = SPEECH_PART_LIMIT) -> list[str]:
    """`text` split into parts of at most `limit` characters, at sentence ends where it can be."""
    parts: list[str] = []
    current = ''
    for sentence in _SENTENCE_END.split(text.strip()):
        while len(sentence) > limit:
            if current:
                parts.append(current)
                current = ''
            parts.append(sentence[:limit])
            sentence = sentence[limit:]
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limit:
            current = f'{current} {sentence}'
        else:
            parts.append(current)
            current = sentence
    if current:
        parts.append(current)
    return parts
