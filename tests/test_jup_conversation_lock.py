"""The cross-instance conversation lock (`jup.conversation_lock`): what it asks of the database, and
that every way out of a hold closes its connection, which is what releases the lock.

The fake connection records the SQL. The last two tests run against a real Postgres when
`JUP_TEST_POSTGRES_URL` names one (`postgresql+psycopg://…`): two engines stand for two ent-os
instances. Without it, or without sqlalchemy (`--only-group dev`), they skip.
"""

import asyncio
import os

import pytest

from jup import channel, conversation_lock
from jup.conversation_lock import NAMESPACE, AdvisoryLocks, advisory_key


class FakeConnection:
    def __init__(self, fail_on: str | None = None, block_on: str | None = None) -> None:
        self.sql: list[tuple[str, tuple]] = []
        self.committed = False
        self.closed = False
        self.fail_on = fail_on
        self.block_on = block_on

    async def exec_driver_sql(self, statement: str, params: tuple) -> None:
        self.sql.append((statement, params))
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError('canceling statement due to lock timeout')
        if self.block_on and self.block_on in statement:
            await asyncio.Event().wait()

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        self.closed = True


def connecting(conn: FakeConnection):
    async def connect():
        return conn

    return connect


def test_the_key_is_a_stable_int4_per_conversation():
    key = advisory_key('u-erik:teams:abc')
    assert key == advisory_key('u-erik:teams:abc')
    assert key != advisory_key('u-erik:teams:abd')
    assert -(2**31) <= key < 2**31
    assert -(2**31) <= NAMESPACE < 2**31


async def test_a_hold_caps_the_wait_takes_the_session_lock_and_closes_after():
    conn = FakeConnection()
    async with AdvisoryLocks(connecting(conn), wait_seconds=280).hold('k'):
        assert conn.sql == [
            ("SELECT set_config('lock_timeout', %s, false)", ('280000ms',)),
            ('SELECT pg_advisory_lock(%s, %s)', (NAMESPACE, advisory_key('k'))),
        ]
        assert conn.committed and not conn.closed

    assert conn.closed


def test_the_default_wait_is_the_gateway_turn_timeout():
    source = open(os.path.join(os.path.dirname(__file__), '..', 'gateway', 'src', 'entos.ts')).read()
    assert f'TURN_TIMEOUT_MS = {conversation_lock.WAIT_SECONDS}_000;' in source


async def test_an_error_inside_the_hold_still_closes_the_connection():
    conn = FakeConnection()
    with pytest.raises(ValueError):
        async with AdvisoryLocks(connecting(conn)).hold('k'):
            raise ValueError('turn failed')
    assert conn.closed


async def test_a_wait_that_times_out_closes_the_connection_and_raises():
    conn = FakeConnection(fail_on='pg_advisory_lock')
    with pytest.raises(RuntimeError, match='lock timeout'):
        async with AdvisoryLocks(connecting(conn)).hold('k'):
            pytest.fail('the body must not run')
    assert conn.closed


async def test_a_wait_cancelled_mid_way_closes_the_connection():
    conn = FakeConnection(block_on='pg_advisory_lock')

    async def wait():
        async with AdvisoryLocks(connecting(conn)).hold('k'):
            pytest.fail('the body must not run')

    task = asyncio.create_task(wait())
    for _ in range(5):
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert conn.closed


# --- against a real Postgres ------------------------------------------------------------------------


def postgres_engines(count: int):
    url = os.environ.get('JUP_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('JUP_TEST_POSTGRES_URL is not set')
    pytest.importorskip('psycopg')
    asyncio_ext = pytest.importorskip('sqlalchemy.ext.asyncio')
    from sqlalchemy.pool import NullPool

    return [asyncio_ext.create_async_engine(url, poolclass=NullPool) for _ in range(count)]


async def test_two_instances_run_one_conversations_turns_one_at_a_time_in_arrival_order():
    engines = postgres_engines(2)
    # Two instances, each with its own in-process layer, sharing the database layer.
    instances = [channel.ConversationLocks(shared=AdvisoryLocks(engine.connect).hold) for engine in engines]
    running, order, peak = set(), [], [0]

    async def turn(instance: int, name: str) -> None:
        async with instances[instance].hold('u-erik:teams:conv'):
            running.add(name)
            peak[0] = max(peak[0], len(running))
            order.append(name)
            await asyncio.sleep(0.3)
            running.discard(name)

    try:
        tasks = []
        for i, name in enumerate(['satu', 'dua', 'tiga', 'empat']):
            tasks.append(asyncio.create_task(turn(i % 2, name)))
            await asyncio.sleep(0.1)  # arrival order: each reaches the database after the one before
        await asyncio.gather(*tasks)
    finally:
        for engine in engines:
            await engine.dispose()

    assert peak[0] == 1
    assert order == ['satu', 'dua', 'tiga', 'empat']


async def test_a_cancelled_wait_leaves_the_conversation_free():
    engines = postgres_engines(2)
    holder, waiter = (AdvisoryLocks(engine.connect) for engine in engines)
    try:
        release = asyncio.Event()

        async def hold_until_released():
            async with holder.hold('conv'):
                await release.wait()

        held = asyncio.create_task(hold_until_released())
        await asyncio.sleep(0.3)

        async def wait():
            async with waiter.hold('conv'):
                pytest.fail('the lock is held elsewhere')

        waiting = asyncio.create_task(wait())
        await asyncio.sleep(0.3)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        release.set()
        await held

        # Nothing holds it now: a fresh hold gets it at once.
        async with asyncio.timeout(5):
            async with AdvisoryLocks(engines[1].connect, wait_seconds=2).hold('conv'):
                pass
    finally:
        for engine in engines:
            await engine.dispose()


def test_the_route_uses_the_database_layer_on_its_own_unpooled_connections():
    """The route module imports the vendor app, so it is read, not imported (`--only-group dev`)."""
    route = os.path.join(os.path.dirname(__file__), '..', 'backend', 'open_webui', 'routers', 'jup_channel.py')
    source = open(route).read()
    assert 'poolclass=NullPool' in source
    assert 'AdvisoryLocks(_lock_connection).hold' in source
    assert 'locks=LOCKS,' in source
