"""The Notion read tools (D25, #40): admin gate, token handling, error mapping, rendering, wrapper.

No network: every test hands `jup.notion` a stub transport that records what it was asked and
answers from a script. The tool code stored in the app is exec'd untested, so it may only delegate.
"""

import ast
import asyncio
from pathlib import Path

import pytest

from jup import notion
from jup.portfolio import OPERATING_LAYER_ROLE

TOOL_SOURCE = Path(__file__).resolve().parent.parent / 'tools' / 'notion.py'
PAGE_ID = '1a2b3c4d5e6f47a8b9c0d1e2f3a4b5c6'
PAGE_UUID = '1a2b3c4d-5e6f-47a8-b9c0-d1e2f3a4b5c6'
PAGE_URL = f'https://www.notion.so/erik/Rapat-Direksi-{PAGE_ID}'


class Stub:
    """A transport that answers each request from `routes` (method, url prefix) → (status, json)."""

    def __init__(self, routes: dict[tuple[str, str], object]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict, dict | None]] = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        for (m, prefix), answer in self.routes.items():
            if m == method and url.startswith(prefix):
                if isinstance(answer, list):
                    return answer.pop(0)
                return answer
        raise AssertionError(f'unexpected request {method} {url}')


def rt(text: str) -> list[dict]:
    return [{'type': 'text', 'plain_text': text}]


def page(title: str = 'Rapat Direksi 12 September', id_: str = PAGE_UUID) -> dict:
    return {
        'object': 'page',
        'id': id_,
        'url': f'https://www.notion.so/Rapat-Direksi-{id_.replace("-", "")}',
        'last_edited_time': '2026-09-12T08:00:00.000Z',
        'properties': {'Name': {'type': 'title', 'title': rt(title)}},
    }


def block(type_: str, text: str = '', has_children: bool = False, id_: str = 'b1', **extra) -> dict:
    return {
        'object': 'block',
        'id': id_,
        'type': type_,
        'has_children': has_children,
        type_: {'rich_text': rt(text), **extra},
    }


def children(*blocks: dict, next_cursor: str | None = None) -> tuple[int, dict]:
    return 200, {
        'object': 'list',
        'results': list(blocks),
        'has_more': next_cursor is not None,
        'next_cursor': next_cursor,
    }


API = notion.API_BASE


@pytest.fixture(autouse=True)
def token(monkeypatch):
    # Secret Manager values arrive with trailing newlines; the tool must trim them.
    monkeypatch.setenv('JUP_NOTION_TOKEN', 'ntn_secret\n\n')


# --------------------------------------------------------------------------- the admin gate


@pytest.mark.parametrize('role', ['user', 'pending', None, ''])
def test_non_admins_are_refused_before_any_network_call(role):
    stub = Stub({})
    assert notion.search(role, 'rapat', transport=stub) == notion.REFUSAL
    assert notion.read_page(role, PAGE_URL, transport=stub) == notion.REFUSAL
    assert stub.calls == []


def test_the_refusal_is_not_worded_as_an_absence():
    assert 'Refused' in notion.REFUSAL
    assert 'not found' not in notion.REFUSAL.lower()


# --------------------------------------------------------------------------- the token


def test_the_token_is_trimmed_and_the_version_pinned():
    stub = Stub({('POST', API + 'search'): (200, {'results': [page()], 'has_more': False})})
    notion.search(OPERATING_LAYER_ROLE, 'rapat', transport=stub)
    _, url, headers, body = stub.calls[0]
    assert url == API + 'search'
    assert headers['Authorization'] == 'Bearer ntn_secret'
    assert headers['Notion-Version'] == notion.NOTION_VERSION
    assert body['query'] == 'rapat'
    assert body['filter'] == {'property': 'object', 'value': 'page'}


@pytest.mark.parametrize('value', [None, '', '  \n'])
def test_a_missing_token_says_not_configured(monkeypatch, value):
    if value is None:
        monkeypatch.delenv('JUP_NOTION_TOKEN', raising=False)
    else:
        monkeypatch.setenv('JUP_NOTION_TOKEN', value)
    stub = Stub({})
    for text in (
        notion.search(OPERATING_LAYER_ROLE, 'rapat', transport=stub),
        notion.read_page(OPERATING_LAYER_ROLE, PAGE_URL, transport=stub),
    ):
        assert text == notion.NOT_CONFIGURED
    assert stub.calls == []


# --------------------------------------------------------------------------- search


def test_search_cites_each_page_with_title_and_url():
    stub = Stub({('POST', API + 'search'): (200, {'results': [page(), page('SOP Gas', '9' * 32)], 'has_more': False})})
    text = notion.search(OPERATING_LAYER_ROLE, 'rapat', transport=stub)
    assert 'Rapat Direksi 12 September' in text and 'SOP Gas' in text
    assert f'https://www.notion.so/Rapat-Direksi-{PAGE_ID}' in text
    assert PAGE_UUID in text  # the id the model passes to read_notion_page


def test_an_empty_search_says_what_the_integration_can_see():
    stub = Stub({('POST', API + 'search'): (200, {'results': [], 'has_more': False})})
    text = notion.search(OPERATING_LAYER_ROLE, 'anggaran', transport=stub)
    assert text.startswith('No Notion page shared with the integration matches')
    assert 'shared' in text


def test_an_empty_query_is_refused_without_a_call():
    stub = Stub({})
    assert 'query' in notion.search(OPERATING_LAYER_ROLE, '   ', transport=stub).lower()
    assert stub.calls == []


# --------------------------------------------------------------------------- read


def test_read_starts_with_the_citation_and_renders_blocks():
    stub = Stub(
        {
            ('GET', API + f'pages/{PAGE_UUID}'): (200, page()),
            ('GET', API + f'blocks/{PAGE_UUID}/children'): children(
                block('heading_2', 'Keputusan'),
                block('bulleted_list_item', 'Lanjutkan SPBG'),
                block('to_do', 'Kirim notulen', checked=True),
                block('numbered_list_item', 'Langkah satu'),
                block('quote', 'Kutipan'),
                block('code', 'SELECT 1', language='sql'),
                {'object': 'block', 'id': 'd', 'type': 'divider', 'has_children': False, 'divider': {}},
                {
                    'object': 'block',
                    'id': 'c',
                    'type': 'child_page',
                    'has_children': True,
                    'child_page': {'title': 'Lampiran'},
                },
            ),
        }
    )
    text = notion.read_page(OPERATING_LAYER_ROLE, PAGE_URL, transport=stub)
    first = text.splitlines()[0]
    assert first == '# Rapat Direksi 12 September'
    assert f'https://www.notion.so/Rapat-Direksi-{PAGE_ID}' in text.splitlines()[1]
    for expected in (
        '## Keputusan',
        '- Lanjutkan SPBG',
        '- [x] Kirim notulen',
        '1. Langkah satu',
        '> Kutipan',
        '```sql\nSELECT 1\n```',
        '---',
        'Lampiran',
    ):
        assert expected in text
    # A sub-page is a separate page: named, never fetched.
    assert not any('blocks/c/' in url for _, url, _, _ in stub.calls)


def test_nested_blocks_are_fetched_and_indented():
    stub = Stub(
        {
            ('GET', API + f'pages/{PAGE_UUID}'): (200, page()),
            ('GET', API + f'blocks/{PAGE_UUID}/children'): children(
                block('toggle', 'Detail', has_children=True, id_='t1')
            ),
            ('GET', API + 'blocks/t1/children'): children(block('paragraph', 'Isi toggle')),
        }
    )
    text = notion.read_page(OPERATING_LAYER_ROLE, PAGE_UUID, transport=stub)
    assert '- Detail' in text
    assert '  Isi toggle' in text


def test_block_pages_are_followed_by_cursor():
    stub = Stub(
        {
            ('GET', API + f'pages/{PAGE_UUID}'): (200, page()),
            ('GET', API + f'blocks/{PAGE_UUID}/children'): [
                children(block('paragraph', 'satu'), next_cursor='cur2'),
                children(block('paragraph', 'dua')),
            ],
        }
    )
    text = notion.read_page(OPERATING_LAYER_ROLE, PAGE_UUID, transport=stub)
    assert 'satu' in text and 'dua' in text
    assert 'start_cursor=cur2' in stub.calls[-1][1]


def test_a_long_page_is_capped_and_says_so():
    many = [block('paragraph', 'x' * 500, id_=f'p{i}') for i in range(100)]
    stub = Stub(
        {
            ('GET', API + f'pages/{PAGE_UUID}'): (200, page()),
            ('GET', API + f'blocks/{PAGE_UUID}/children'): children(*many),
        }
    )
    text = notion.read_page(OPERATING_LAYER_ROLE, PAGE_UUID, transport=stub)
    assert len(text) <= notion.MAX_CHARS + 400
    assert 'truncated' in text.lower()


@pytest.mark.parametrize(
    'ref',
    [
        PAGE_URL,
        PAGE_ID,
        PAGE_UUID,
        f'https://www.notion.so/erik/Rapat-Direksi-{PAGE_ID}?pvs=4',
        f'https://www.notion.so/{PAGE_ID}?v={"f" * 32}',
    ],
)
def test_page_references_resolve_to_the_same_id(ref):
    assert notion.page_id(ref) == PAGE_UUID


@pytest.mark.parametrize('ref', ['', 'rapat direksi', '../../users/me', 'https://evil.example/x', PAGE_ID[:-1]])
def test_an_unusable_page_reference_is_refused_without_a_call(ref):
    stub = Stub({})
    text = notion.read_page(OPERATING_LAYER_ROLE, ref, transport=stub)
    assert 'page id' in text.lower()
    assert stub.calls == []


# --------------------------------------------------------------------------- errors


@pytest.mark.parametrize('status', [401, 403, 404, 429, 500])
def test_notion_errors_are_never_worded_as_no_such_note(status):
    stub = Stub({('GET', API): (status, {'object': 'error', 'status': status, 'code': 'x', 'message': 'm'})})
    text = notion.read_page(OPERATING_LAYER_ROLE, PAGE_UUID, transport=stub)
    assert text.startswith('Notion error')
    assert 'do not' in text.lower()
    assert str(status) in text


def test_a_404_names_sharing_as_the_likely_cause():
    stub = Stub({('GET', API): (404, {'object': 'error', 'status': 404, 'code': 'object_not_found', 'message': 'm'})})
    assert 'shared with the integration' in notion.read_page(OPERATING_LAYER_ROLE, PAGE_UUID, transport=stub)


def test_an_unreachable_notion_is_an_error_not_an_empty_result():
    def down(method, url, headers, body):
        raise notion.NotionUnreachable('timed out')

    text = notion.search(OPERATING_LAYER_ROLE, 'rapat', transport=down)
    assert text.startswith('Notion error') and 'timed out' in text


def test_only_the_notion_api_is_ever_called():
    with pytest.raises(ValueError):
        notion._call('GET', 'https://evil.example/v1/pages', 'token', transport=Stub({}))


# --------------------------------------------------------------------------- async entry points + wrapper


def test_the_async_entry_points_delegate(monkeypatch):
    monkeypatch.setattr(notion, 'search', lambda role, query: f'search:{role}:{query}')
    monkeypatch.setattr(notion, 'read_page', lambda role, ref: f'read:{role}:{ref}')
    assert asyncio.run(notion.search_notion('admin', 'q')) == 'search:admin:q'
    assert asyncio.run(notion.read_notion_page('admin', 'p')) == 'read:admin:p'


def test_the_stored_wrapper_holds_no_logic_of_its_own():
    """The DB copy is exec'd untested, so it may only delegate. A rule added there escapes CI."""
    source = TOOL_SOURCE.read_text()
    assert 'risk_class: read\n' in source
    tree = ast.parse(source)
    tools = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Tools')
    methods = [n for n in tools.body if isinstance(n, ast.AsyncFunctionDef)]
    assert [m.name for m in methods] == ['search_notion', 'read_notion_page']
    assert not [n for n in tools.body if isinstance(n, ast.FunctionDef)]
    for method in methods:
        body = [n for n in method.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        assert len(body) == 1 and isinstance(body[0], ast.Return)
        assert f'_{method.name}(' in ast.unparse(body[0])
        doc = ast.get_docstring(method) or ''
        assert 'admin' not in doc.lower()  # identity gating lives in code, never in the docstring
