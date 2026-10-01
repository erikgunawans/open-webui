"""A collection attached to a model is searchable by anyone allowed to use that model (ADR-0015 §1).

The vendor's knowledge tools let a user read a model-attached *file* without a grant, but checked a
model-attached *collection* against admin / owner / read grant. Both JUP collections (Strategy KB,
Staff Contributions) have no grants on purpose, so every non-admin got empty results from Asisten
JUP and the voice model, while admins saw answers — found 2026-10-02. `_can_read_knowledge` in
`tools/builtin.py` closes that for `source == 'model'` only: a collection a user attaches to their
own chat still needs a grant.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job. A skip here is not a pass.
See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import asyncio
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

BUILTIN = Path(__file__).parent.parent / 'backend' / 'open_webui' / 'tools' / 'builtin.py'

_RUNTIME_MODULES = ('fastapi', 'sqlalchemy', 'aiosqlite')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)
needs_runtime = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under --only-group dev',
)

KB = 'kb-strategy'
STAFF = {
    'id': 'user-staff',
    'role': 'user',
    'name': 'Staff',
    'email': 'staff@example.com',
    'last_active_at': 0,
    'updated_at': 0,
    'created_at': 0,
}
ATTACHED = [{'type': 'collection', 'id': KB, 'name': 'JUP Strategy KB', 'source': 'model'}]
CHAT_ATTACHED = [{'type': 'collection', 'id': KB, 'name': 'JUP Strategy KB', 'source': 'chat'}]


def test_every_model_knowledge_check_uses_the_helper() -> None:
    """Static guard for the rebase: the patch must still be wired into each tool."""
    source = BUILTIN.read_text(encoding='utf-8')
    assert 'def _model_attached_collection_ids(' in source
    assert "item.get('source') == 'model'" in source, 'chat-attached collections must not bypass grants'
    for tool in (
        'search_knowledge_files',
        'grep_knowledge_files',
        'view_knowledge_file',
        'list_knowledge',
        'query_knowledge_files',
    ):
        body = re.search(rf'async def {tool}\((.*?)\n(?:async )?def ', source, re.S)
        assert body, f'{tool} not found'
        assert '_can_read_knowledge(' in body.group(1), f'{tool} no longer uses _can_read_knowledge'
    view = re.search(r'async def view_knowledge_file\((.*?)\) -> str:', source, re.S)
    assert '__model_knowledge__' in view.group(1), 'view_knowledge_file must receive the model knowledge'


@pytest.fixture
def builtin(monkeypatch):
    from open_webui.models import access_grants, knowledge
    from open_webui.tools import builtin as module

    kb = SimpleNamespace(id=KB, user_id='user-admin', name='JUP Strategy KB', description='', meta={})

    async def get_knowledge_by_id(id, db=None):
        return kb if id == KB else None

    async def get_knowledges_by_file_id(file_id, db=None):
        return [kb] if file_id == 'file-in-kb' else []

    async def no_grant(**kwargs):
        return False

    async def no_groups(user_id, db=None):
        return []

    monkeypatch.setattr(knowledge.Knowledges, 'get_knowledge_by_id', get_knowledge_by_id)
    monkeypatch.setattr(knowledge.Knowledges, 'get_knowledges_by_file_id', get_knowledges_by_file_id)
    monkeypatch.setattr(access_grants.AccessGrants, 'has_access', no_grant)
    monkeypatch.setattr(module.Groups, 'get_groups_by_member_id', no_groups)
    return SimpleNamespace(module=module, kb=kb)


@needs_runtime
def test_only_model_attached_collections_count(builtin) -> None:
    ids = builtin.module._model_attached_collection_ids
    assert ids(ATTACHED) == {KB}
    assert ids(CHAT_ATTACHED) == set()
    assert ids([{'type': 'file', 'id': 'f1', 'source': 'model'}]) == set()
    assert ids(None) == set()


@needs_runtime
def test_staff_without_grant_can_read_a_model_attached_collection(builtin) -> None:
    can = builtin.module._can_read_knowledge
    assert asyncio.run(can(builtin.kb, STAFF, [], ATTACHED)) is True
    assert asyncio.run(can(builtin.kb, STAFF, [], CHAT_ATTACHED)) is False
    assert asyncio.run(can(builtin.kb, STAFF, [], None)) is False
    assert asyncio.run(can(builtin.kb, {**STAFF, 'role': 'admin'}, [], None)) is True


@needs_runtime
def test_query_knowledge_files_searches_the_attached_collection_for_staff(builtin, monkeypatch) -> None:
    from open_webui.retrieval import utils as retrieval_utils

    searched: list[list[str]] = []

    async def fake_query_collection(request, collection_names, queries, embedding_function, k):
        searched.append(list(collection_names))
        return {
            'documents': [['isi']],
            'metadatas': [[{'source': 'strategy.md', 'file_id': 'f1'}]],
            'distances': [[0.1]],
        }

    monkeypatch.setattr(retrieval_utils, 'query_collection', fake_query_collection)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(EMBEDDING_FUNCTION=lambda *a, **k: None)))

    run = builtin.module.query_knowledge_files
    attached = json.loads(
        asyncio.run(run('apa itu JUP', __request__=request, __user__=STAFF, __model_knowledge__=ATTACHED))
    )
    assert searched == [[KB]]
    assert attached and attached[0]['source'] == 'strategy.md'

    searched.clear()
    asyncio.run(run('apa itu JUP', __request__=request, __user__=STAFF, __model_knowledge__=CHAT_ATTACHED))
    assert searched == [], 'a chat-attached collection without a grant must stay unsearchable'


@needs_runtime
def test_view_file_reads_a_file_inside_an_attached_collection(builtin) -> None:
    file = SimpleNamespace(id='file-in-kb', user_id='user-admin')
    other = SimpleNamespace(id='file-elsewhere', user_id='user-admin')
    has = builtin.module._has_read_access_to_file

    async def deny(**kwargs):
        return False

    import open_webui.utils.access_control.files as files_acl

    original = files_acl.has_access_to_file
    files_acl.has_access_to_file = deny
    try:
        assert asyncio.run(has(file, STAFF, ATTACHED)) is True
        assert asyncio.run(has(file, STAFF, CHAT_ATTACHED)) is False
        assert asyncio.run(has(other, STAFF, ATTACHED)) is False
    finally:
        files_acl.has_access_to_file = original


def test_image_bakes_the_multilingual_embedding_model_with_its_prefixes() -> None:
    """The Indonesian KB needs a multilingual embedding model; e5 needs its query/passage prefixes."""
    root = Path(__file__).parent.parent
    dockerfile = (root / 'Dockerfile').read_text(encoding='utf-8')
    deploy = (root / 'deploy' / 'gcp' / 'deploy.sh').read_text(encoding='utf-8')
    assert 'ARG USE_EMBEDDING_MODEL=intfloat/multilingual-e5-small' in dockerfile
    assert "SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'" in dockerfile, (
        'keep MiniLM baked for rollback'
    )
    assert 'RAG_EMBEDDING_QUERY_PREFIX: "query: "' in deploy
    assert 'RAG_EMBEDDING_CONTENT_PREFIX: "passage: "' in deploy
