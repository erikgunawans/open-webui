"""The classification floor a chat's files inherit from what the chat has read (Track O, O2).

JUP's classification guide says a generated file is never classified below its sources: anything
built from contract cards with money terms or from contract full text is at least TERBATAS.
`office_doc.classification_for` already takes a `floor`; this module supplies it.

**How:** when a source tool returns restricted material into a chat, it calls `mark_restricted`,
which records the level under `chat.meta[KEY]`. The file tools (`create_document`,
`create_spreadsheet`) read it back with `chat_floor` and pass it as the floor. The mark is sticky
for the chat and only ever rises: a later, less restricted read never lowers it.

**Server-side only.** The mark is written here under a row lock and read here; the client never
sets it. It is a labelling control: the content itself is already filtered by the caller's
grants before the model sees it.

Vendor imports stay inside the I/O functions so this module, and its tests, load in CI's
`--only-group dev`, which has no fastapi or sqlalchemy.
"""

from __future__ import annotations

import time
from typing import Any

from jup.office_doc import LEVELS

KEY = 'jup_restricted_source'
TERBATAS = 'TERBATAS'


def floor_from_meta(meta: Any) -> str | None:
    """The level recorded on a chat's meta, or `None` when the chat has read nothing restricted."""
    record = meta.get(KEY) if isinstance(meta, dict) else None
    if not isinstance(record, dict):
        return None
    level = record.get('level')
    return level if level in LEVELS else None


def higher(a: str | None, b: str | None) -> str | None:
    """The more restricted of two levels (either may be `None`)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if LEVELS.index(a) >= LEVELS.index(b) else b


def raised(meta: Any, level: str, source: str, *, at: int) -> dict[str, Any] | None:
    """The record to store, or `None` when the chat already carries this level or higher."""
    if level not in LEVELS:
        raise ValueError(f'unknown classification level: {level!r}')
    current = floor_from_meta(meta)
    if higher(current, level) == current:
        return None
    return {'level': level, 'source': source, 'at': at}


async def chat_floor(chat_id: str) -> str | None:
    """The floor for files created in `chat_id`."""
    from open_webui.models.chats import Chats

    chat = await Chats.get_chat_by_id(chat_id)
    return floor_from_meta(chat.meta) if chat is not None else None


async def mark_restricted(chat_id: str, source: str, level: str = TERBATAS) -> None:
    """Raise `chat.meta[KEY]` to `level` under a row lock, keeping every other meta key."""
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.chats import Chat
    from sqlalchemy.orm.attributes import flag_modified

    async with get_async_db_context() as session:
        chat = await session.get(Chat, chat_id, with_for_update=session.bind.dialect.name == 'postgresql')
        if chat is None:
            return
        record = raised(chat.meta, level, source, at=int(time.time()))
        if record is None:
            return
        chat.meta = {**(chat.meta or {}), KEY: record}
        flag_modified(chat, 'meta')
        await session.commit()


__all__ = ['KEY', 'TERBATAS', 'chat_floor', 'floor_from_meta', 'higher', 'mark_restricted', 'raised']
