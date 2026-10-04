"""Run one assistant turn for a user in a chat, from the server, and wait for the answer (E7.1, #85).

Two callers run a turn with nobody's browser in the loop: the voice panel and live call
(`routers/jup_voice_live.live_turn`) and, from E7, a Channel Turn. Both need the same thing: the
request the chat UI would send for a follow-up — so the vendor pipeline persists both messages and
every fork hook (funnel, contract, tool policy, audit) runs exactly as for a typed turn — and then
the finished assistant message, read back from the store, within a time limit.

What differs per caller is injected rather than branched on here:

- `defaults` carries the model's default tools, features and filters. Automations resolve them
  from the model's meta (`resolve_defaults` reuses that resolver); the voice turn sends none, because
  `enforce_voice_turn` fixes its tools itself.
- `request_state` is set on the built request. Marks that decide policy travel there, never in the
  body: any HTTP caller can write the body (governance.py explains why for the parent chat).
- `accept` is an extra test the finished message must pass — the voice turn's seal check.

The vendor handler, the request builder and the store are injected too, so this module imports the
standard library only and its tests run under `--only-group dev`.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

#: How much earlier conversation a turn carries.
CONTEXT_MESSAGES = 6

Handler = Callable[..., Awaitable[Any]]
Accept = Callable[[dict, str], bool]
Resolver = Callable[[Any, str], Awaitable[tuple[list[str], dict, list[str], str | None]]]


@dataclass(frozen=True)
class TurnDefaults:
    """A model's default tools, features and filters, as the chat UI would send them."""

    tool_ids: tuple[str, ...] = ()
    features: dict = field(default_factory=dict)
    filter_ids: tuple[str, ...] = ()
    terminal_id: str | None = None

    def as_form(self) -> dict[str, Any]:
        """The non-empty defaults, under the keys the chat pipeline reads from the request body."""
        form: dict[str, Any] = {}
        if self.tool_ids:
            form['tool_ids'] = list(self.tool_ids)
        if self.features:
            form['features'] = dict(self.features)
        if self.filter_ids:
            form['filter_ids'] = list(self.filter_ids)
        if self.terminal_id:
            form['terminal_id'] = self.terminal_id
        return form


@dataclass(frozen=True)
class TurnResult:
    """The assistant message a turn produced. `finished` is False when the time limit ran out first;
    the turn itself is not cancelled, and `message_id` still names the message it will finish in."""

    message_id: str
    content: str
    finished: bool


async def resolve_defaults(app: Any, model_id: str, *, resolver: Resolver | None = None) -> TurnDefaults:
    """The model's defaults, resolved exactly as automations resolve them (model meta + admin config).

    The resolver is the vendor's private `_resolve_model_defaults`, unpacked by position; a rebase
    that renames it or reorders its tuple breaks here, so the live Channel Turn check (#86) is what
    proves it after each rebase.
    """
    if resolver is None:
        from open_webui.utils.automations import _resolve_model_defaults as resolver
    tool_ids, features, filter_ids, terminal_id = await resolver(app, model_id)
    return TurnDefaults(
        tool_ids=tuple(tool_ids or ()),
        features=dict(features or {}),
        filter_ids=tuple(filter_ids or ()),
        terminal_id=terminal_id or None,
    )


def context_branch(history: dict, current_id: str | None, limit: int) -> list[dict]:
    """The last `limit` messages on the branch ending at `current_id`, oldest first."""
    messages = history.get('messages') or {}
    found: list[dict] = []
    seen: set[str] = set()
    while current_id and current_id in messages and current_id not in seen and len(found) < limit:
        seen.add(current_id)
        message = messages[current_id]
        if message.get('role') in ('user', 'assistant') and message.get('content'):
            found.append({'role': message['role'], 'content': message['content']})
        current_id = message.get('parentId')
    return list(reversed(found))


async def run_turn(
    *,
    user: Any,
    chat_id: str,
    text: str,
    model_id: str,
    store: Any,
    handler: Handler,
    build_request: Callable[[], Any],
    session_id: str | None = None,
    defaults: TurnDefaults | None = None,
    request_state: Mapping[str, Any] | None = None,
    accept: Accept | None = None,
    context_messages: int = CONTEXT_MESSAGES,
    wait_seconds: float = 90.0,
    poll_seconds: float = 0.5,
) -> TurnResult:
    """Runs `text` as the next turn in `chat_id` for `user` and waits for the finished answer."""
    chat = await store.get_chat(chat_id)
    history = ((chat.chat if chat is not None else None) or {}).get('history') or {}
    parent_id = history.get('currentId')
    user_message_id, message_id = str(uuid.uuid4()), str(uuid.uuid4())
    form_data: dict[str, Any] = {
        'model': model_id,
        'messages': [*context_branch(history, parent_id, context_messages), {'role': 'user', 'content': text}],
        'stream': True,
        'chat_id': chat_id,
        'id': message_id,
        'parent_id': parent_id,
        'user_message': {
            'id': user_message_id,
            'parentId': parent_id,
            'role': 'user',
            'content': text,
            'models': [model_id],
            'timestamp': int(time.time()),
        },
        'session_id': session_id or f'turn:{chat_id}',
        'background_tasks': {},
    }
    if defaults is not None:
        form_data.update(defaults.as_form())

    request = build_request()
    for name, value in (request_state or {}).items():
        setattr(request.state, name, value)
    await handler(request, form_data, user=user)

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        message = await store.get_message(chat_id, message_id)
        if (
            isinstance(message, dict)
            and message.get('done') is not False
            and message.get('content')
            and (accept is None or accept(message, message_id))
        ):
            return TurnResult(message_id=message_id, content=message['content'], finished=True)
        await asyncio.sleep(poll_seconds)
    return TurnResult(message_id=message_id, content='', finished=False)
