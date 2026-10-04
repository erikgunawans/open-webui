"""The cross-instance half of a Channel conversation's lock: a Postgres advisory lock (E7.3 follow-up).

`jup.channel.ConversationLocks` orders the turns of one conversation inside one process. Live
ent-os runs up to four instances, so the route adds this layer: the turn holds a session-level
`pg_advisory_lock` for the conversation while it runs, and a turn of the same conversation on
another instance waits for it. Postgres queues lock waiters in arrival order, so the order the spec
asks for (#87) holds across instances too.

**Each hold owns its connection, outside the app's pool.** `connect` must hand out a connection
that is really closed on `close()` (an engine on `NullPool`), because closing is what releases the
lock: the database ends the session, and with it the lock and any wait still in progress. So a
request cancelled while it waits, or an instance that dies while it holds, never leaves a
conversation locked; and a turn that waits never takes a connection the app needs.

**A wait is capped at `WAIT_SECONDS`**, the gateway's own turn timeout: past it nobody is
listening for the answer. The wait then fails, and the turn is audited `failed` (`lock_error`).

This imports the standard library only; the route builds the engine.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

log = logging.getLogger(__name__)

#: The first key of the two-key advisory lock: says the lock is a Channel conversation's, so it
#: cannot collide with another advisory lock on the same database. 'JUPC' as a big-endian int4.
NAMESPACE = int.from_bytes(b'JUPC', 'big', signed=True)

#: `gateway/src/entos.ts` `TURN_TIMEOUT_MS` (280 s): the gateway stops waiting there.
WAIT_SECONDS = 280

#: Opens a connection the hold owns outright: SQLAlchemy `AsyncConnection` from a `NullPool` engine.
Connect = Callable[[], Awaitable[Any]]


def advisory_key(key: str) -> int:
    """The conversation's second lock key: an int4 from its hash. A collision only orders two turns
    that need not be; it never lets two turns of one conversation run at once."""
    return int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:4], 'big', signed=True)


class AdvisoryLocks:
    """`hold(key)` is a `jup.channel.SharedHold`."""

    def __init__(self, connect: Connect, wait_seconds: int = WAIT_SECONDS) -> None:
        self._connect = connect
        self._wait = f'{int(wait_seconds * 1000)}ms'

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[None]:
        conn = await self._connect()
        try:
            await conn.exec_driver_sql("SELECT set_config('lock_timeout', %s, false)", (self._wait,))
            await conn.exec_driver_sql('SELECT pg_advisory_lock(%s, %s)', (NAMESPACE, advisory_key(key)))
            # The lock is the session's, not the transaction's: end the transaction so the
            # connection sits idle, not idle in a transaction, for the length of the turn.
            await conn.commit()
        except BaseException:
            await _close(conn)
            raise
        try:
            yield
        finally:
            await _close(conn)


async def _close(conn: Any) -> None:
    """Ends the session, which releases its advisory locks. A failure here is logged, not raised: the
    turn's outcome is already decided, and a connection that cannot close has lost its session anyway."""
    try:
        await conn.close()
    except Exception:
        log.warning('jup.conversation_lock: closing the lock connection failed', exc_info=True)


__all__ = ['NAMESPACE', 'WAIT_SECONDS', 'AdvisoryLocks', 'advisory_key']
