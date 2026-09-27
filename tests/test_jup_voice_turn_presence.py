"""#27: the vendor inserts that hold a voice turn to the voice model, tools and document set.

Losing one fails nothing visible: the turn still answers, just from more than the named documents.
So a lost patch must break this test instead (ADR-0007, `deploy/gcp/VENDOR-PATCHES.md`).
"""

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / 'backend' / 'open_webui'
MAIN_PY = BACKEND / 'main.py'
MIDDLEWARE_PY = BACKEND / 'utils' / 'middleware.py'


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def _chat_completion() -> str:
    return _between(MAIN_PY.read_text(encoding='utf-8'), 'async def chat_completion(', 'async def process_chat(')


def test_the_entry_forces_a_voice_turn_before_it_reads_the_request():
    body = _chat_completion()
    force = body.index('jup_voice_turn = await jup_voice.enforce_voice_turn(form_data, user)')
    assert force < body.index("model_id = form_data.get('model', None)")
    assert force < body.index("model_item = form_data.pop('model_item', {})")
    assert force < body.index("tool_servers = form_data.pop('tool_servers', None)")


def test_the_entry_marks_the_turn_in_the_server_built_metadata():
    body = _chat_completion()
    metadata = _between(body, 'metadata = {\n', "'params': {")
    assert 'jup_voice.VOICE_TURN_KEY: jup_voice_turn,' in metadata


def test_the_entry_uses_the_voice_router_module():
    assert 'jup_voice,' in _between(MAIN_PY.read_text(encoding='utf-8'), 'from open_webui.routers import (', ')')


def _payload() -> str:
    source = MIDDLEWARE_PY.read_text(encoding='utf-8')
    assert 'from jup import voice_turn as jup_voice_turn' in source
    return _between(source, 'async def process_chat_payload(', '\nasync def ')


def test_the_tool_offer_narrows_a_voice_turn_after_every_tool_is_resolved():
    body = _between(_payload(), 'if payload_tools is None:', "metadata['tools'] = tools_dict")
    narrow = body.index('tools_dict = jup_voice_turn.tools_for(metadata, tools_dict, model)')
    assert body.index('builtin_tools = await get_builtin_tools(') < narrow
    assert body.index('jup_tool_policy.offered_tools(tools_dict') < narrow


def test_a_voice_turn_takes_no_tool_an_inlet_filter_added():
    body = _payload()
    drop = body.index('inlet_filter_tools = jup_voice_turn.filter_tools_for(metadata, inlet_filter_tools)')
    assert drop < body.index("form_data['tools'].extend(inlet_filter_tools)")


def test_a_voice_turn_loads_no_skill_not_even_a_mentioned_one():
    body = _payload()
    hook = body.index('skill_ids = jup_voice_turn.skills_for(metadata, skill_ids)')
    assert body.index('| mentioned_skill_ids') < hook < body.index('if skill_ids:')


def test_a_voice_turn_reads_no_folder_knowledge():
    body = _between(_payload(), '# Folder "Project" handling', 'if folder_id and user:')
    assert 'folder_id = jup_voice_turn.folder_for(metadata, folder_id)' in body


def test_every_insert_has_a_vendor_patches_entry():
    patches = (BACKEND.parent.parent / 'deploy' / 'gcp' / 'VENDOR-PATCHES.md').read_text(encoding='utf-8')
    assert 'backend/jup/voice_turn.py' in patches
    assert 'enforce_voice_turn' in patches
    assert 'test_jup_voice_turn_presence.py' in patches
