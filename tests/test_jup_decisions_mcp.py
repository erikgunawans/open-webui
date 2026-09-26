"""A5+E5 #19: the decisions-register MCP server, started the way `backend/start.sh` starts it.

One end-to-end test runs `python -m jup_mcp.decisions` against the fixture register and calls both
tools through the `mcp` client over streamable HTTP, the transport the app's own MCP client uses.
The rest check that it binds to 127.0.0.1 only, and that `start.sh` starts it before the app.
The register's behaviour is tested in `test_jup_decisions.py`; this is the plumbing.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip('mcp')

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests' / 'fixtures' / 'decisions' / 'DECISIONS.md'
START_SH = ROOT / 'backend' / 'start.sh'


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _non_loopback_ip() -> str | None:
    """This machine's outward address, if it has one. A UDP connect sends nothing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 9))  # TEST-NET-1, never routed
            ip = s.getsockname()[0]
    except OSError:
        return None
    return None if ip.startswith('127.') else ip


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture
def server(tmp_path):
    """The real entry point, in its own process, reading `register` (the fixture unless replaced)."""

    def start(register: Path = FIXTURE):
        port = _free_port()
        env = {
            **os.environ,
            'PYTHONPATH': str(ROOT / 'backend'),
            'JUP_DECISIONS_FILE': str(register),
            'JUP_DECISIONS_MCP_PORT': str(port),
        }
        proc = subprocess.Popen(
            [sys.executable, '-m', 'jup_mcp.decisions'],
            env=env,
            cwd=tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        started.append(proc)
        deadline = time.monotonic() + 20
        while not _reachable('127.0.0.1', port):
            if proc.poll() is not None:
                raise AssertionError(f'the server exited: {proc.stderr.read().decode()}')
            if time.monotonic() > deadline:
                raise AssertionError('the server did not start listening within 20s')
            time.sleep(0.1)
        return port

    started: list[subprocess.Popen] = []
    yield start
    for proc in started:
        proc.terminate()
        proc.wait(timeout=10)


async def _call(port: int, tool: str, arguments: dict):
    async with streamablehttp_client(f'http://127.0.0.1:{port}/mcp') as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = sorted(t.name for t in (await session.list_tools()).tools)
            return names, await session.call_tool(tool, arguments)


async def test_both_tools_answer_through_an_mcp_client(server):
    port = server()

    names, found = await _call(port, 'search_decisions', {'query': 'voice'})
    assert names == ['get_decision', 'search_decisions']
    assert not found.isError
    text = found.content[0].text
    assert '**D16**' in text and '**D21**' in text and '**D7**' not in text

    _, d20 = await _call(port, 'get_decision', {'id': 'D20'})
    assert not d20.isError
    text = d20.content[0].text
    assert text.startswith('# D20: MCP tool servers')
    assert 'DECIDED — standing rule' in text and 'asserted at attach time' in text


async def test_an_unreadable_register_is_an_mcp_error_not_an_empty_answer(server, tmp_path):
    port = server(tmp_path / 'missing' / 'DECISIONS.md')
    _, result = await _call(port, 'search_decisions', {'query': 'voice'})
    assert result.isError
    assert 'decisions register is unavailable' in result.content[0].text


def test_it_listens_on_loopback_only(server):
    port = server()
    assert _reachable('127.0.0.1', port)
    outward = _non_loopback_ip()
    if outward is None:
        pytest.skip('this machine has no non-loopback address to try')
    assert not _reachable(outward, port), f'the decisions server answered on {outward}'


def test_the_bind_address_is_fixed_in_code():
    from jup_mcp.decisions import HOST, build

    assert HOST == '127.0.0.1'
    assert build(1).settings.host == '127.0.0.1'


def test_start_sh_starts_it_in_the_background_before_the_app():
    source = START_SH.read_text(encoding='utf-8')
    started = source.index('-m jup_mcp.decisions &')
    assert started < source.index('-m uvicorn open_webui.main:app')
