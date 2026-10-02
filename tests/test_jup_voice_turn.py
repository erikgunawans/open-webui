"""#27: a voice-chat turn runs on "Asisten JUP — Suara" and reaches only the voice knowledge scope.

Runs under `--only-group dev`: `jup.voice_turn` imports the standard library only. The vendor
inserts that call it are pinned in `test_jup_voice_turn_presence.py`.
"""

import asyncio
import json

import pytest

from jup import voice_turn
from jup.voice import VOICE_MODEL_ID

IN_SET = 'file-strategy'
ALSO_IN_SET = 'file-gas'
OUTSIDE = 'file-partners'


def _voice_model(knowledge=None) -> dict:
    if knowledge is None:
        knowledge = [
            {'type': 'file', 'id': IN_SET, 'name': 'strategy.md'},
            {'type': 'file', 'id': ALSO_IN_SET, 'name': 'gas.md'},
        ]
    return {'id': VOICE_MODEL_ID, 'info': {'meta': {'knowledge': knowledge}}}


def _forged_request() -> dict:
    """Everything a browser could send to widen a voice turn."""
    return {
        'model': 'xiaomi/mimo-v2.6-pro-ultraspeed',
        'model_item': {'id': 'evil', 'direct': True},
        'chat_id': 'chat-1',
        'tool_ids': ['portfolio_status', 'gate_probe', 'server:mcp:decisions'],
        'tool_servers': [{'url': 'https://evil.example'}],
        'tools': [{'type': 'function', 'function': {'name': 'anything'}}],
        'terminal_id': 'term-1',
        'skill_ids': ['skill-1'],
        'filter_ids': ['filter-1'],
        'files': [{'type': 'collection', 'id': 'kb-all'}, {'type': 'file', 'id': OUTSIDE}],
        'folder_id': 'folder-with-knowledge',
        'features': {'web_search': True, 'code_interpreter': True, 'image_generation': True, 'memory': True},
        'params': {'function_calling': 'legacy', 'temperature': 0.2},
        'message_ids': [
            {'model_id': 'xiaomi/mimo-v2.6-pro-ultraspeed', 'message_id': 'a-1'},
            {'model_id': 'other-model', 'message_id': 'a-2'},
        ],
        'user_message': {
            'id': 'u-1',
            'role': 'user',
            'content': 'apa strategi JUP?',
            'models': ['xiaomi/mimo-v2.6-pro-ultraspeed', 'other-model'],
            'files': [{'type': 'file', 'id': OUTSIDE}],
        },
        'messages': [{'role': 'user', 'content': 'apa strategi JUP?'}],
        'stream': True,
    }


# --- The request ------------------------------------------------------------------------


def test_a_forged_model_id_runs_on_the_voice_model() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['model'] == VOICE_MODEL_ID
    assert 'model_item' not in form  # no direct connection either


def test_forged_tool_ids_are_replaced_by_the_voice_tools() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['tool_ids'] == list(voice_turn.VOICE_TOOL_IDS) == ['portfolio_status', 'jup_contracts']


def test_forged_features_are_dropped() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['features'] == {}


def test_the_spoken_style_feature_is_kept() -> None:
    form = _forged_request()
    form['features'] = {'voice': True, 'web_search': True}
    voice_turn.rewrite(form)
    assert form['features'] == {'voice': True}


@pytest.mark.parametrize(
    'key', ['tool_servers', 'tools', 'terminal_id', 'skill_ids', 'filter_ids', 'files', 'folder_id', 'model_item']
)
def test_every_other_way_to_widen_the_turn_is_removed(key: str) -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert key not in form


def test_every_assistant_slot_is_the_voice_model_and_there_is_one() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['message_ids'] == [{'model_id': VOICE_MODEL_ID, 'message_id': 'a-1'}]


def test_a_legacy_message_ids_map_is_narrowed_too() -> None:
    form = _forged_request()
    form['message_ids'] = {'other-model': 'a-9'}
    voice_turn.rewrite(form)
    assert form['message_ids'] == [{'model_id': VOICE_MODEL_ID, 'message_id': 'a-9'}]


def test_the_user_message_names_only_the_voice_model_and_carries_no_files() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['user_message']['models'] == [VOICE_MODEL_ID]
    assert 'files' not in form['user_message']
    assert form['user_message']['content'] == 'apa strategi JUP?'


def test_tool_calling_is_native_so_the_scoped_tools_are_what_runs() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['params'] == {'function_calling': 'native', 'temperature': 0.2}


def test_the_conversation_itself_is_left_alone() -> None:
    form = _forged_request()
    voice_turn.rewrite(form)
    assert form['chat_id'] == 'chat-1'
    assert form['messages'] == [{'role': 'user', 'content': 'apa strategi JUP?'}]
    assert form['stream'] is True


def test_it_reports_what_it_changed_by_name_never_by_content() -> None:
    changed = voice_turn.rewrite(_forged_request())
    assert set(changed) == {
        'model',
        'model_item',
        'tool_ids',
        'tool_servers',
        'tools',
        'terminal_id',
        'skill_ids',
        'filter_ids',
        'files',
        'folder_id',
        'features',
        'params.function_calling',
        'message_ids',
        'user_message',
    }


def test_an_honest_voice_request_changes_nothing_worth_reporting() -> None:
    form = {
        'model': VOICE_MODEL_ID,
        'chat_id': 'chat-1',
        'tool_ids': list(voice_turn.VOICE_TOOL_IDS),
        'features': {'voice': True},
        'message_ids': [{'model_id': VOICE_MODEL_ID, 'message_id': 'a-1'}],
        'user_message': {'id': 'u-1', 'content': 'hi', 'models': [VOICE_MODEL_ID]},
        'messages': [],
    }
    assert voice_turn.rewrite(form) == []
    assert form['tool_ids'] == list(voice_turn.VOICE_TOOL_IDS)


def test_a_request_without_optional_fields_is_still_forced() -> None:
    form = {'model': 'other', 'messages': []}
    voice_turn.rewrite(form)
    assert form == {
        'model': VOICE_MODEL_ID,
        'messages': [],
        'tool_ids': list(voice_turn.VOICE_TOOL_IDS),
        'features': {},
        'params': {'function_calling': 'native'},
    }


# --- The voice scope ---------------------------------------------------------------------

KB = 'kb-strategy'
OTHER_KB = 'kb-test'
IN_KB = 'file-in-strategy-kb'


def _collection_model() -> dict:
    return _voice_model([{'type': 'collection', 'id': KB, 'name': 'JUP Strategy KB'}])


async def _resolve(collections):
    return {IN_KB} if KB in collections else set()


def test_the_scope_is_the_models_files_and_collections() -> None:
    assert voice_turn.voice_scope(_voice_model()) == voice_turn.Scope(frozenset({IN_SET, ALSO_IN_SET}), frozenset())
    mixed = _voice_model([{'type': 'file', 'id': IN_SET}, {'type': 'collection', 'id': KB}])
    assert voice_turn.voice_scope(mixed) == voice_turn.Scope(frozenset({IN_SET}), frozenset({KB}))


@pytest.mark.parametrize(
    'knowledge',
    [
        [],
        [{'type': 'file', 'id': IN_SET}, {'type': 'note', 'id': 'note-1'}],
        [{'type': 'collection', 'id': KB}, {'type': 'folder', 'id': 'f'}],
        [{'type': 'file', 'id': ''}],
        ['not-a-dict'],
    ],
)
def test_knowledge_that_is_not_only_files_and_collections_is_no_scope(knowledge) -> None:
    """Empty knowledge makes the vendor offer every KB; a note or folder is not a reviewed source."""
    assert voice_turn.voice_scope(_voice_model(knowledge)) is None


def test_a_model_without_knowledge_has_no_scope() -> None:
    assert voice_turn.voice_scope({'id': VOICE_MODEL_ID}) is None
    assert voice_turn.voice_scope({'info': {'meta': {'knowledge': None}}}) is None


# --- The tools offered ------------------------------------------------------------------


class Recorder:
    """A tool callable that records whether it ran."""

    def __init__(self, result: str = 'ran') -> None:
        self.calls: list[dict] = []
        self.result = result
        # The vendor's partial carries these; `get_updated_tool_function` rebuilds from them.
        self.__function__ = object()
        self.__extra_params__ = {}

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def _builtin(name: str) -> dict:
    return {'tool_id': f'builtin:{name}', 'callable': Recorder(), 'spec': {'name': name}}


def _offered() -> dict:
    names = [
        'list_knowledge',
        'search_knowledge_files',
        'grep_knowledge_files',
        'query_knowledge_files',
        'view_file',
        'view_knowledge_file',
        'search_knowledge_bases',
        'query_knowledge_bases',
        'list_knowledge_bases',
        'search_chats',
        'view_chat',
        'delegate_task',
        'timer',
        'search_web',
        'fetch_url',
        'execute_code',
        'search_notes',
        'write_note',
        'create_automation',
        'get_current_timestamp',
        'ask_user',
        'view_skill',
        'list_chat_files',
        'kb_exec',
    ]
    tools = {name: _builtin(name) for name in names}
    tools['portfolio_status'] = {'tool_id': 'portfolio_status', 'callable': Recorder(), 'spec': {}}
    tools['gate_probe'] = {'tool_id': 'gate_probe', 'callable': Recorder(), 'spec': {}}
    tools['decisions_get_decision'] = {'tool_id': 'mcp:decisions', 'callable': Recorder(), 'spec': {}}
    return tools


def test_a_voice_turn_is_offered_only_scoped_retrieval_and_portfolio_status() -> None:
    offered = voice_turn.offered_tools(_offered(), _voice_model())
    assert set(offered) == {
        'list_knowledge',
        'search_knowledge_files',
        'grep_knowledge_files',
        'query_knowledge_files',
        'view_file',
        'view_knowledge_file',
        'portfolio_status',
    }


def test_a_tool_is_matched_by_its_id_not_only_its_name() -> None:
    """A tool server can name a function `view_knowledge_file`; only the builtin one is kept."""
    tools = {'view_knowledge_file': {'tool_id': 'server:evil', 'callable': Recorder(), 'spec': {}}}
    tools['portfolio_status'] = {'tool_id': 'mcp:other', 'callable': Recorder(), 'spec': {}}
    assert voice_turn.offered_tools(tools, _voice_model()) == {}


def test_without_a_scope_no_retrieval_tool_is_offered() -> None:
    offered = voice_turn.offered_tools(_offered(), _voice_model([{'type': 'note', 'id': 'note-1'}]))
    assert set(offered) == {'portfolio_status'}


def test_a_collection_scope_offers_retrieval() -> None:
    offered = voice_turn.offered_tools(_offered(), _collection_model(), _resolve)
    assert 'query_knowledge_files' in offered and 'view_knowledge_file' in offered


@pytest.mark.parametrize('name', ['view_knowledge_file', 'view_file', 'grep_knowledge_files'])
def test_a_file_in_a_scope_collection_opens_and_one_outside_does_not(name: str) -> None:
    tools = _offered()
    underlying = tools[name]['callable']
    offered = voice_turn.offered_tools(tools, _collection_model(), _resolve)
    assert _run(offered, name, file_id=IN_KB, pattern='x') == 'ran'
    assert _refused(_run(offered, name, file_id=OUTSIDE, pattern='x', __user__={'role': 'admin'}))
    assert underlying.calls == [{'file_id': IN_KB, 'pattern': 'x'}]


@pytest.mark.parametrize(
    'kwargs',
    [
        {'query': 'q', 'knowledge_ids': [KB]},
        {'query': 'q', 'knowledge_ids': f'["{KB}"]'},
        {'query': 'q', 'knowledge_ids': KB},
    ],
)
def test_a_search_may_name_a_scope_collection(kwargs: dict) -> None:
    offered = voice_turn.offered_tools(_offered(), _collection_model(), _resolve)
    assert _run(offered, 'query_knowledge_files', **kwargs) == 'ran'


def test_a_search_may_not_name_a_collection_outside_the_scope() -> None:
    tools = _offered()
    offered = voice_turn.offered_tools(tools, _collection_model(), _resolve)
    assert _refused(_run(offered, 'query_knowledge_files', query='q', knowledge_ids=[KB, OTHER_KB]))
    assert _refused(_run(offered, 'list_knowledge', knowledge_id=OTHER_KB))
    assert tools['query_knowledge_files']['callable'].calls == []


def test_contracts_is_a_voice_tool() -> None:
    assert voice_turn.VOICE_TOOL_IDS == ('portfolio_status', 'jup_contracts')
    tools = {'jup_contracts': {'tool_id': 'jup_contracts', 'callable': Recorder(), 'spec': {}}}
    assert set(voice_turn.offered_tools(tools, _collection_model(), _resolve)) == {'jup_contracts'}


def _run(tools: dict, name: str, **kwargs):
    return asyncio.run(tools[name]['callable'](**kwargs))


def _refused(result) -> bool:
    return isinstance(result, str) and 'error' in json.loads(result)


@pytest.mark.parametrize('name', ['view_knowledge_file', 'view_file', 'grep_knowledge_files'])
def test_a_file_outside_the_set_cannot_be_opened_even_by_an_admin(name: str) -> None:
    """The vendor passes these on admin role or ownership; the voice guard answers first."""
    tools = _offered()
    underlying = tools[name]['callable']
    offered = voice_turn.offered_tools(tools, _voice_model())
    result = _run(offered, name, file_id=OUTSIDE, pattern='x', __user__={'id': 'erik', 'role': 'admin'})
    assert _refused(result)
    assert underlying.calls == []


@pytest.mark.parametrize('name', ['view_knowledge_file', 'view_file', 'grep_knowledge_files'])
def test_a_file_in_the_set_opens(name: str) -> None:
    tools = _offered()
    underlying = tools[name]['callable']
    offered = voice_turn.offered_tools(tools, _voice_model())
    assert _run(offered, name, file_id=IN_SET, pattern='x') == 'ran'
    assert underlying.calls == [{'file_id': IN_SET, 'pattern': 'x'}]


def test_grep_across_the_set_runs_scoped_by_the_vendor() -> None:
    offered = voice_turn.offered_tools(_offered(), _voice_model())
    assert _run(offered, 'grep_knowledge_files', pattern='SPBG', file_id=None) == 'ran'


@pytest.mark.parametrize(
    ('name', 'kwargs'),
    [
        ('query_knowledge_files', {'query': 'q', 'knowledge_ids': ['kb-all']}),
        ('query_knowledge_files', {'query': 'q', 'knowledge_ids': '["kb-all"]'}),
        ('query_knowledge_files', {'query': 'q', 'knowledge_ids': 'kb-all'}),
        ('search_knowledge_files', {'query': 'q', 'knowledge_id': 'kb-all'}),
        ('list_knowledge', {'knowledge_id': 'kb-all'}),
    ],
)
def test_retrieval_cannot_be_pointed_at_a_knowledge_base(name: str, kwargs: dict) -> None:
    tools = _offered()
    underlying = tools[name]['callable']
    offered = voice_turn.offered_tools(tools, _voice_model())
    assert _refused(_run(offered, name, **kwargs))
    assert underlying.calls == []


@pytest.mark.parametrize('empty', [None, '', 'none', 'null', 'None', []])
def test_an_empty_knowledge_argument_is_not_a_widening(empty) -> None:
    offered = voice_turn.offered_tools(_offered(), _voice_model())
    assert _run(offered, 'query_knowledge_files', query='q', knowledge_ids=empty) == 'ran'
    assert _run(offered, 'search_knowledge_files', query='q', knowledge_id=empty) == 'ran'


def test_the_guard_survives_the_vendors_tool_refresh() -> None:
    """`get_updated_tool_function` rebuilds a tool from `__function__` when it has one, which would
    drop the guard; the guarded callable must not carry it."""
    offered = voice_turn.offered_tools(_offered(), _voice_model())
    guarded = offered['view_knowledge_file']['callable']
    assert getattr(guarded, '__function__', None) is None
    assert getattr(guarded, '__extra_params__', None) is None


def test_portfolio_status_is_offered_unchanged() -> None:
    tools = _offered()
    offered = voice_turn.offered_tools(tools, _voice_model())
    assert offered['portfolio_status'] is tools['portfolio_status']


def test_the_offer_leaves_the_vendors_dict_alone() -> None:
    tools = _offered()
    before = dict(tools)
    voice_turn.offered_tools(tools, _voice_model())
    assert tools == before


# --- The vendor's one-line hooks --------------------------------------------------------

VOICE = {voice_turn.METADATA_KEY: True}
TYPED = {voice_turn.METADATA_KEY: False}


@pytest.mark.parametrize('metadata', [TYPED, {}, None, {voice_turn.METADATA_KEY: 'true'}])
def test_only_a_server_marked_turn_is_a_voice_turn(metadata) -> None:
    assert voice_turn.is_voice_turn(metadata) is False
    assert voice_turn.is_voice_turn(VOICE) is True


def test_a_typed_turn_keeps_every_tool_skill_filter_tool_and_folder() -> None:
    tools = _offered()
    assert voice_turn.tools_for(TYPED, tools, _voice_model()) is tools
    assert voice_turn.skills_for(TYPED, ['skill-1']) == ['skill-1']
    assert voice_turn.filter_tools_for(TYPED, [{'type': 'function'}]) == [{'type': 'function'}]
    assert voice_turn.folder_for(TYPED, 'folder-1') == 'folder-1'


def test_a_voice_turn_gets_the_voice_tools_only() -> None:
    assert set(voice_turn.tools_for(VOICE, _offered(), _voice_model())) == set(
        voice_turn.offered_tools(_offered(), _voice_model())
    )


def test_a_skill_mentioned_in_a_voice_turn_is_not_loaded() -> None:
    """A `<$skill|label>` mention in the spoken text would put the skill's content in the prompt."""
    assert voice_turn.skills_for(VOICE, ['skill-1', 'skill-2']) == []


def test_a_voice_turn_takes_no_tool_a_filter_added() -> None:
    assert voice_turn.filter_tools_for(VOICE, [{'type': 'function'}]) is None


def test_a_voice_turn_reads_no_folder() -> None:
    assert voice_turn.folder_for(VOICE, 'folder-1') is None


def test_an_automation_id_does_not_ride_along() -> None:
    form = _forged_request()
    form['automation_id'] = 'auto-1'
    assert 'automation_id' in voice_turn.rewrite(form)
    assert 'automation_id' not in form
