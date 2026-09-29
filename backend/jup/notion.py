"""Read-only access to Erik's own Notion for Asisten JUP: the `search_notion` and `read_notion_page` tools.

D25 (2026-09-29), first integration under I1 (#39, #40). What the decision requires, and where it holds:

- **Admin-only, checked here.** A non-admin gets `REFUSAL` before any network call. The tool's
  docstring says nothing about identity (a docstring gate made the model refuse admins).
- **Read-only.** Only `POST /search`, `GET /pages/{id}` and `GET /blocks/{id}/children` on
  `https://api.notion.com/v1/`, with `Notion-Version` pinned. `_call` refuses any other URL.
- **Never stored.** Page text is fetched per question and returned; nothing is written to disk,
  the DB or a knowledge base.
- **Cited.** Every search hit and every page read starts with the page title and its Notion URL.
- **Audited.** The E1 `tool_call` line is written for every call by the middleware
  (`jup.governance.audit_tool_call`), like any other tool.

Failure is never an absence: a missing token, a Notion error or an unreachable API each returns a
message the model is told to relay, so "Notion said 404" cannot become "there is no such note".

The integration token comes from `JUP_NOTION_TOKEN` (Secret Manager `notion-integration-token`),
trimmed, because secret values carry trailing newlines and a header with one is rejected.

The HTTP is blocking stdlib `urllib`, so the tool's entry points (`search_notion`,
`read_notion_page`) run it in a worker thread: the app calls a sync tool function inline on its
event loop, where a slow Notion would stall every user. The pure functions (`search`,
`read_page`) take an injectable transport so the tests need no network.
"""

import asyncio
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from jup.portfolio import OPERATING_LAYER_ROLE

API_BASE = 'https://api.notion.com/v1/'
NOTION_VERSION = '2022-06-28'
TIMEOUT_S = 20

SEARCH_LIMIT = 10
MAX_CHARS = 20_000
MAX_REQUESTS = 30
MAX_DEPTH = 3

#: (method, url, headers, json body or None) -> (HTTP status, parsed JSON body)
Transport = Callable[[str, str, dict[str, str], dict | None], tuple[int, dict]]

REFUSAL = (
    'Refused: Notion is readable only by the operating layer, and this account is not a member of it. '
    'Tell the user that plainly; do not answer from other sources instead.'
)
NOT_CONFIGURED = (
    'Notion is not configured on this deployment (no integration token). '
    'Tell the user Notion is unavailable; do not answer as if no such note exists.'
)
BAD_PAGE = (
    'That is not a Notion page id or page URL. Pass the page id shown by search_notion '
    '(or a notion.so page link); do not guess one.'
)


class NotionUnreachable(Exception):
    """The request never got an HTTP answer (DNS, TLS, timeout)."""


class NotionError(Exception):
    def __init__(self, status: int, code: str = '', message: str = ''):
        super().__init__(f'{status} {code}: {message}')
        self.status, self.code, self.message = status, code, message


# --------------------------------------------------------------------------- entry points


async def search_notion(role: str | None, query: str) -> str:
    return await asyncio.to_thread(search, role, query)


async def read_notion_page(role: str | None, page: str) -> str:
    return await asyncio.to_thread(read_page, role, page)


def search(role: str | None, query: str, *, transport: Transport | None = None) -> str:
    if role != OPERATING_LAYER_ROLE:
        return REFUSAL
    token = _token()
    if not token:
        return NOT_CONFIGURED
    query = (query or '').strip()
    if not query:
        return 'Give a search query: words from the note title or text.'
    body = {'query': query, 'filter': {'property': 'object', 'value': 'page'}, 'page_size': SEARCH_LIMIT}
    try:
        result = _call('POST', API_BASE + 'search', token, body, transport=transport)
    except (NotionError, NotionUnreachable) as error:
        return _error_text(error)

    pages = [r for r in result.get('results', []) if r.get('object') == 'page']
    if not pages:
        return (
            f'No Notion page shared with the integration matches {query!r}. Notion only shows the '
            'integration the pages Erik has shared with it, so a note can exist and still not be found here. '
            'Say that, rather than that the note does not exist.'
        )
    lines = [f'# Notion search: {query}', '', 'Cite the page title and URL for anything taken from a page.', '']
    for p in pages:
        lines.append(
            f'- **{_title(p)}**, {p.get("url", "")} (page id `{p.get("id", "")}`, edited {p.get("last_edited_time", "?")})'
        )
    if result.get('has_more'):
        lines += ['', f'More than {SEARCH_LIMIT} pages match; narrow the query to see others.']
    lines += ['', 'Read a page with read_notion_page before quoting it; search results carry titles only.']
    return '\n'.join(lines)


def read_page(role: str | None, page: str, *, transport: Transport | None = None) -> str:
    if role != OPERATING_LAYER_ROLE:
        return REFUSAL
    token = _token()
    if not token:
        return NOT_CONFIGURED
    pid = page_id(page)
    if not pid:
        return BAD_PAGE

    budget = _Budget()
    try:
        meta = _call('GET', API_BASE + f'pages/{pid}', token, transport=transport, budget=budget)
        lines: list[str] = []
        truncated = _render_children(pid, token, transport, budget, lines, depth=0)
    except (NotionError, NotionUnreachable) as error:
        return _error_text(error)

    head = [
        f'# {_title(meta)}',
        f'Source: {meta.get("url", "")} (Notion, edited {meta.get("last_edited_time", "?")})',
        '',
    ]
    text = '\n'.join(head + lines)
    if len(text) > MAX_CHARS:
        text, truncated = text[:MAX_CHARS], True
    if truncated:
        text += '\n\n[Truncated: the page is longer than this tool returns. Say the answer may be incomplete.]'
    return text


# --------------------------------------------------------------------------- page ids

_HEX32 = re.compile(r'^[0-9a-f]{32}$')
_SEGMENT_ID = re.compile(r'(?:^|-)([0-9a-f]{32})$|^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$')


def page_id(ref: str) -> str | None:
    """The dashed UUID of a page from an id, a dashed UUID or a notion.so/notion.site link; else None.

    Only a validated id ever reaches a request URL, so a crafted reference cannot steer the path.
    """
    ref = (ref or '').strip()
    if not ref:
        return None
    if '://' in ref:
        parsed = urllib.parse.urlparse(ref)
        host = (parsed.hostname or '').lower()
        if not (host in ('notion.so', 'notion.site') or host.endswith(('.notion.so', '.notion.site'))):
            return None
        segments = [s for s in parsed.path.split('/') if s]
        if not segments:
            return None
        ref = segments[-1]
    match = _SEGMENT_ID.search(ref.lower())
    if not match:
        return None
    compact = (match.group(1) or match.group(2)).replace('-', '')
    if not _HEX32.match(compact):
        return None
    return f'{compact[:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:]}'


# --------------------------------------------------------------------------- rendering

_PREFIX = {
    'heading_1': '# ',
    'heading_2': '## ',
    'heading_3': '### ',
    'bulleted_list_item': '- ',
    'numbered_list_item': '1. ',
    'toggle': '- ',
    'quote': '> ',
    'callout': '> ',
    'paragraph': '',
}
_MEDIA = ('image', 'file', 'pdf', 'video', 'audio')
_LINKS = ('bookmark', 'embed', 'link_preview')


class _Budget:
    def __init__(self) -> None:
        self.requests = 0
        self.chars = 0

    @property
    def spent(self) -> bool:
        return self.requests >= MAX_REQUESTS or self.chars >= MAX_CHARS


def _render_children(block_id: str, token: str, transport, budget: _Budget, out: list[str], depth: int) -> bool:
    """Append the rendered children of a block to `out`. Returns True when something was cut."""
    cursor: str | None = None
    while True:
        if budget.spent:
            return True
        query = '?page_size=100' + (f'&start_cursor={urllib.parse.quote(cursor)}' if cursor else '')
        result = _call(
            'GET', API_BASE + f'blocks/{block_id}/children{query}', token, transport=transport, budget=budget
        )
        for b in result.get('results', []):
            line = _block_line(b)
            if line is not None:
                indented = '\n'.join('  ' * depth + part for part in line.split('\n'))
                out.append(indented)
                budget.chars += len(indented) + 1
            if b.get('has_children') and b.get('type') not in ('child_page', 'child_database'):
                if depth + 1 >= MAX_DEPTH:
                    out.append('  ' * (depth + 1) + '[nested content not shown]')
                elif _render_children(b['id'], token, transport, budget, out, depth + 1):
                    return True
            if budget.spent:
                return True
        if not result.get('has_more'):
            return False
        cursor = result.get('next_cursor')


def _block_line(b: dict) -> str | None:
    kind = b.get('type', '')
    data = b.get(kind) or {}
    text = _plain(data.get('rich_text', []))
    if kind in _PREFIX:
        return _PREFIX[kind] + text
    if kind == 'to_do':
        return ('- [x] ' if data.get('checked') else '- [ ] ') + text
    if kind == 'code':
        return f'```{data.get("language", "")}\n{text}\n```'
    if kind == 'divider':
        return '---'
    if kind == 'child_page':
        return f'[Sub-page: {data.get("title", "")}, not read; open it separately if needed]'
    if kind == 'child_database':
        return f'[Database: {data.get("title", "")}, not read]'
    if kind == 'table':
        return None  # its rows arrive as children
    if kind == 'table_row':
        return '| ' + ' | '.join(_plain(cell) for cell in data.get('cells', [])) + ' |'
    if kind in _LINKS:
        return f'[{kind}: {data.get("url", "")}]'
    if kind in _MEDIA:
        caption = _plain(data.get('caption', []))
        return f'[{kind}{": " + caption if caption else ""}]'
    return f'[{kind or "unknown"} block not shown]'


def _plain(rich: list[dict]) -> str:
    return ''.join(part.get('plain_text', '') for part in rich or [])


def _title(p: dict) -> str:
    for prop in (p.get('properties') or {}).values():
        if isinstance(prop, dict) and prop.get('type') == 'title':
            return _plain(prop.get('title', [])) or 'Untitled'
    return 'Untitled'


# --------------------------------------------------------------------------- HTTP


def _token() -> str:
    return os.environ.get('JUP_NOTION_TOKEN', '').strip()


def _call(
    method: str,
    url: str,
    token: str,
    body: dict | None = None,
    *,
    transport: Transport | None = None,
    budget: _Budget | None = None,
) -> dict:
    if not url.startswith(API_BASE):
        raise ValueError(f'refusing a request outside the Notion API: {url}')
    if budget is not None:
        budget.requests += 1
    headers = {
        'Authorization': f'Bearer {token}',
        'Notion-Version': NOTION_VERSION,
        'Content-Type': 'application/json',
    }
    status, payload = (transport or _urllib_transport)(method, url, headers, body)
    if status != 200:
        raise NotionError(status, str(payload.get('code', '')), str(payload.get('message', '')))
    return payload


def _urllib_transport(method: str, url: str, headers: dict[str, str], body: dict | None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (URL checked in _call)
            return response.status, json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as error:
        try:
            payload: Any = json.loads(error.read() or b'{}')
        except ValueError:
            payload = {}
        return error.code, payload if isinstance(payload, dict) else {}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise NotionUnreachable(str(getattr(error, 'reason', error))) from error


_STATUS_TEXT = {
    401: 'Notion rejected the integration token (401). The token is wrong or was revoked; an admin must replace it.',
    403: 'The integration is not allowed to do this (403). Its capabilities in Notion may be too narrow.',
    404: (
        'Notion returned 404: the page does not exist, or it has not been shared with the integration. '
        "Erik can share it with the integration from the page's Connections menu in Notion."
    ),
    429: 'Notion is rate-limiting the integration (429). Try again in a minute.',
}


def _error_text(error: Exception) -> str:
    if isinstance(error, NotionUnreachable):
        detail = f'Notion could not be reached ({error}).'
    elif isinstance(error, NotionError):
        detail = _STATUS_TEXT.get(error.status) or f'Notion answered {error.status} ({error.code}: {error.message}).'
    else:  # pragma: no cover
        detail = str(error)
    return f'Notion error: {detail} Do not tell the user the note does not exist; say Notion could not be read.'
