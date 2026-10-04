"""The GPT-Live relay: our server's side of a live call (#36, ADR-0018 as amended 2026-09-28).

It runs inside the request that minted the session (`jup_voice.start_live_session`), so Cloud Run
keeps CPU allocated for the whole call and only one owner answers the session's delegations.

- **The sideband** is a WebSocket to `wss://api.openai.com/v1/live/sessions/{id}/attach`. It
  carries both transcripts and every `session.delegation.created`; the browser's data channel sees
  them too but never answers them.
- **A delegation** carries an id and a time, no text. The question is rebuilt from the caller's
  transcript (`jup.voice_live.LiveLedger`), run as an ordinary turn in the caller's voice chat on
  "Asisten JUP — Suara" through the vendor's chat pipeline, so `enforce_voice_turn` forces the voice
  model and scope and the answer is sealed as in a governed call. The sealed answer goes back with
  `session.commentary.append`, in parts under GPT-Live's 500-token limit.
- **The record.** When the call ends, each turn of GPT-Live's speech is written against the
  governed answer it relayed (`message.meta.jup_voice_live`), or kept in the chat's
  `meta.jup_voice_live` as `self_answered` or `pending`, with one `voice_live_turn` audit line each
  (sizes, never text).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from jup import voice, voice_live
from jup.governance import audit
from jup.turn import run_turn

log = logging.getLogger(__name__)

ATTACH_URL = 'wss://api.openai.com/v1/live/sessions/{session_id}/attach'

#: Transcript fragments arrive unevenly; wait this long after a delegation before reading the question.
SETTLE_SECONDS = 0.7
#: How long a governed turn may take before the caller is told the documents did not answer.
TURN_SECONDS = 90.0

ASK_AGAIN = 'Maaf, pertanyaannya belum terdengar jelas. Mohon ulangi pertanyaan Anda.'
NO_ANSWER = 'Maaf, jawaban dari dokumen belum bisa diambil saat ini. Silakan coba lagi sebentar lagi.'

Ask = Callable[[str], Awaitable[tuple[str, str]]]
Send = Callable[[dict], Awaitable[None]]


# --- The governed turn ------------------------------------------------------------------------


async def live_turn(
    app: Any,
    user: Any,
    chat_id: str,
    question: str,
    *,
    store: Any,
    secret: str,
    handler: Callable[..., Awaitable[Any]] | None = None,
    build_request: Callable[[Any], Any] | None = None,
    wait_seconds: float = TURN_SECONDS,
    poll_seconds: float = 0.5,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Runs `question` as a turn in the caller's voice chat and returns `(message_id, sealed answer)`.

    The request is the one the call UI sends for a follow-up (`jup.turn.run_turn`), so the vendor
    persists both messages and `enforce_voice_turn` holds the turn to the voice model and scope. Only
    a sealed answer counts as finished. Raises `TimeoutError` when none appears in time.
    """
    if build_request is None:
        from open_webui.utils.automations import _build_request as build_request

    result = await run_turn(
        user=user,
        chat_id=chat_id,
        text=question,
        model_id=voice.VOICE_MODEL_ID,
        store=store,
        handler=handler or app.state.CHAT_COMPLETION_HANDLER,
        build_request=lambda: build_request(app),
        session_id=session_id or f'voice-live:{chat_id}',
        accept=lambda message, message_id: voice.answer_sealed(message, chat_id, message_id, secret=secret),
        wait_seconds=wait_seconds,
        poll_seconds=poll_seconds,
    )
    if not result.finished:
        raise TimeoutError(f'no sealed answer for {result.message_id}')
    return result.message_id, result.content


# --- The relay --------------------------------------------------------------------------------


class LiveRelay:
    """Answers one session's delegations and keeps its ledger. The IO is injected (`ask`, `send`)."""

    def __init__(self, *, session_id: str, user_id: str, chat_id: str, ask: Ask, send: Send | None = None) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.ledger = voice_live.LiveLedger()
        self._ask = ask
        self._send = send
        self._tasks: set[asyncio.Task] = set()
        # One governed turn at a time: two at once would branch from the same last message.
        self._turns = asyncio.Lock()
        self.closed = False

    def attach(self, send: Send) -> None:
        """Where commentary goes: the sideband, once it is open."""
        self._send = send

    async def on_event(self, event: Any) -> None:
        if not isinstance(event, dict):
            return
        kind = event.get('type')
        if kind == 'session.input_transcript.delta':
            self.ledger.heard(event.get('start_ms') or 0, event.get('end_ms') or 0, str(event.get('delta') or ''))
        elif kind == 'session.output_transcript.delta':
            self.ledger.said(event.get('start_ms') or 0, event.get('end_ms') or 0, str(event.get('delta') or ''))
        elif kind == 'session.delegation.created':
            delegation = event.get('delegation') or {}
            if delegation.get('target') == 'client' and isinstance(delegation.get('id'), str):
                task = asyncio.create_task(self._delegate(delegation['id'], event.get('offset_ms') or 0))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        elif kind == 'session.closed':
            self.closed = True
        elif kind == 'error':
            log.warning('GPT-Live session %s error: %s', self.session_id, (event.get('error') or {}).get('code'))

    async def _commentary(self, delegation_id: str, content: str) -> None:
        await self._send(
            {
                'type': 'session.commentary.append',
                'event_id': f'jup_{uuid.uuid4().hex[:16]}',
                'delegation_id': delegation_id,
                'content': content,
            }
        )

    async def _delegate(self, delegation_id: str, offset_ms: int) -> None:
        await asyncio.sleep(SETTLE_SECONDS)
        question = self.ledger.question(delegation_id, offset_ms)
        base = {'user': self.user_id, 'chat': self.chat_id, 'session': self.session_id, 'delegation': delegation_id}
        if not question:
            audit('voice_live_delegation', **base, outcome='no_question', message_id=None, chars=0)
            await self._commentary(delegation_id, ASK_AGAIN)
            return
        try:
            async with self._turns:
                message_id, answer = await self._ask(question)
        except Exception as error:
            log.warning('GPT-Live governed turn failed: %s', type(error).__name__)
            audit('voice_live_delegation', **base, outcome='failed', message_id=None, chars=0)
            await self._commentary(delegation_id, NO_ANSWER)
            return
        parts = voice_live.commentary_parts(answer)
        for part in parts:
            await self._commentary(delegation_id, part)
        self.ledger.relayed(delegation_id, message_id, answer)
        audit(
            'voice_live_delegation',
            **base,
            outcome='relayed',
            message_id=message_id,
            chars=len(answer),
            parts=len(parts),
        )

    async def drain(self, timeout: float = TURN_SECONDS) -> None:
        """Waits for delegations still being answered, so their answers are recorded."""
        if self._tasks:
            await asyncio.wait(set(self._tasks), timeout=timeout)

    async def record(self, store: Any) -> list[dict]:
        """Writes each turn of GPT-Live's speech; returns the turns."""
        turns = self.ledger.turns()
        spoken_by_message: dict[str, list[dict]] = {}
        unrelayed: list[dict] = []
        for turn in turns:
            audit(
                'voice_live_turn',
                user=self.user_id,
                chat=self.chat_id,
                session=self.session_id,
                kind=turn['kind'],
                delegation=turn['delegation'],
                message_id=turn['message_id'],
                spoken_chars=len(turn['spoken']),
                matched=turn.get('matched', 'timing'),
            )
            entry = {'session': self.session_id, 'delegation': turn['delegation'], 'spoken': turn['spoken']}
            if turn['kind'] == 'relayed':
                spoken_by_message.setdefault(turn['message_id'], []).append(entry)
            else:
                unrelayed.append({**entry, 'kind': turn['kind']})
        for message_id, entries in spoken_by_message.items():
            try:
                await store.set_message_meta_key(self.chat_id, message_id, 'jup_voice_live', entries)
            except Exception as error:
                log.warning('GPT-Live record on %s failed: %s', message_id, type(error).__name__)
        if unrelayed:
            try:
                await store.append_chat_meta_items(self.chat_id, 'jup_voice_live', unrelayed)
            except Exception as error:
                log.warning('GPT-Live record on chat %s failed: %s', self.chat_id, type(error).__name__)
        return turns


async def run_sideband(relay: LiveRelay, key: str, *, store: Any, connect: Callable[..., Any] | None = None) -> None:
    """Attaches to the session and feeds the relay until the session closes or this task is cancelled.

    On the way out it closes the session, lets pending answers finish, and writes the record, so a
    browser that goes away still leaves the call audited.
    """
    url = ATTACH_URL.format(session_id=relay.session_id)
    headers = {'Authorization': f'Bearer {key}'}
    ws = None
    try:
        if connect is None:
            from open_webui.utils.session_pool import get_session

            session = await get_session()
            ws = await session.ws_connect(url, headers=headers, heartbeat=20)
        else:
            ws = await connect(url, headers=headers)

        async def _send(event: dict) -> None:
            await ws.send_str(json.dumps(event, ensure_ascii=False))

        relay.attach(_send)
        audit('voice_live', user=relay.user_id, chat=relay.chat_id, outcome='attached', session=relay.session_id)
        async for message in ws:
            try:
                event = json.loads(message.data)
            except (TypeError, ValueError):
                continue
            await relay.on_event(event)
            if relay.closed:
                break
    except asyncio.CancelledError:
        raise
    except Exception as error:
        log.warning('GPT-Live sideband for %s failed: %s', relay.session_id, type(error).__name__)
        audit('voice_live', user=relay.user_id, chat=relay.chat_id, outcome='sideband_failed', session=relay.session_id)
    finally:
        await asyncio.shield(_finish(relay, ws, store))


async def _finish(relay: LiveRelay, ws: Any, store: Any) -> None:
    try:
        await relay.drain()
        if ws is not None and not ws.closed and not relay.closed:
            try:
                await ws.send_str(json.dumps({'type': 'session.close', 'event_id': 'jup_close'}))
            except Exception:
                pass
        if ws is not None and not ws.closed:
            await ws.close()
        turns = await relay.record(store)
        audit(
            'voice_live',
            user=relay.user_id,
            chat=relay.chat_id,
            outcome='ended',
            session=relay.session_id,
            relayed=sum(1 for t in turns if t['kind'] == 'relayed'),
            self_answered=sum(1 for t in turns if t['kind'] == 'self_answered'),
            pending=sum(1 for t in turns if t['kind'] == 'pending'),
        )
    except Exception as error:
        log.warning('GPT-Live finish for %s failed: %s', relay.session_id, type(error).__name__)
