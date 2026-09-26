"""The decisions-register MCP server: `search_decisions` and `get_decision`, on localhost only.

A5 + E5, ticket 5/7. The first MCP server, and deliberately the harmless case: it is hosted by JUP
inside the app's own container, every tool is `read`, and it makes no outbound calls and has no
database access, so it is in D20's pre-approved class. Its job is to prove the MCP path.

A thin wrapper, the same shape as `tools/portfolio_status.py`: every rule is in `jup.decisions`.
The register is re-read on every call, so a records sync is picked up without a restart.

**Bound to 127.0.0.1, and not configurable.** It adds no network surface: only processes in the
same container can reach it. There is deliberately no host setting to widen that by mistake.

    python -m jup_mcp.decisions      # backend/start.sh starts it before the app
"""

import os

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from jup.decisions import DecisionsError, default_path, load_register, render_decision, render_search

HOST = '127.0.0.1'
DEFAULT_PORT = 8765
NAME = 'jup-decisions'


def port() -> int:
    return int(os.environ.get('JUP_DECISIONS_MCP_PORT', '').strip() or DEFAULT_PORT)


def _register():
    try:
        return load_register(default_path())
    except DecisionsError as error:
        # An MCP error, not a result: the model must not read "could not read the register" as
        # "JUP never decided that".
        raise ToolError(
            f'The decisions register is unavailable: {error}. Tell the user the register could not be '
            'read; do not answer from other sources as if it had been.'
        ) from None


def build(listen_port: int) -> FastMCP:
    server = FastMCP(NAME, host=HOST, port=listen_port, stateless_http=True, json_response=True, log_level='WARNING')

    @server.tool()
    def search_decisions(query: str) -> str:
        """Search JUP's decision register by topic (for example "voice" or "gas allocation") or by number. Returns each matching Decision's number, one-line summary and status (a reversed or superseded status is part of the answer), and any matching open items waiting on someone else. Use get_decision for the full text."""
        return render_search(_register(), query)

    @server.tool()
    def get_decision(id: str) -> str:
        """Get one JUP Decision in full by its number, for example "D20": the decision, its status, date, reasoning, what it names as not covered, and the open items blocking it."""
        return render_decision(_register(), id)

    return server


def main() -> None:
    build(port()).run(transport='streamable-http')


if __name__ == '__main__':
    main()
