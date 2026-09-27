"""A turn in a voice chat: the voice model, the voice tools, the named document set (#27, ADR-0006).

Standard library only, so the rules run under `--only-group dev`. Three vendor inserts call it
(`deploy/gcp/VENDOR-PATCHES.md`):

1. `main.py`'s `chat_completion` asks `routers/jup_voice.py` whether the chat is a voice chat
   (`jup.voice.is_voice_chat`, never the raw meta) and, if so, calls `rewrite` before it reads
   anything else from the request, then marks the turn in the server-built `metadata` under
   `METADATA_KEY`.
2. `utils/middleware.py` passes four things through a hook that changes them only on a marked
   turn: the folder (`folder_for`), the skills (`skills_for`: a `<$skill|label>` mention in the
   text would put the skill's content in the prompt), the resolved tools (`tools_for`) and the
   tools inlet filters added (`filter_tools_for`).

**What a browser can send to widen a turn, and what happens to it.** Another model or a direct
connection: replaced by the voice model. Extra tool ids, tool servers, a caller-supplied `tools`
list, a terminal, skills, filters: replaced by the voice tools or removed. Features (web search,
code interpreter, image generation, memory): removed, except `voice`, which only asks for a
spoken style. Attached files and a folder, both of which add knowledge: removed.
Prompt-based tool calling: set to native, so the scoped tools are the ones that run. An
`automation_id`: removed, a voice turn is never an automation run.

**The document set** is the voice model's `{type:'file'}` knowledge items, kept in step with the
named list by `deploy/gcp/sync-voice-model.ts`. Anything else there (a whole collection, a note)
or nothing at all means the set is misconfigured, and no retrieval tool is offered: with empty
knowledge the vendor would offer every knowledge base the user can read.

**The retrieval tools** take their scope from the model's knowledge, except where they accept an
id: `view_file`, `view_knowledge_file` and `grep_knowledge_files` pass any `file_id` on admin role
or ownership, and `knowledge_id(s)` points a search at a whole base. The guard answers those
before the vendor code runs.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from typing import Any

from jup.voice import VOICE_MODEL_ID

#: The key in the server-built chat `metadata` that marks a voice turn. A client cannot set it:
#: `main.py` builds `metadata` itself and overwrites any `metadata` in the request.
METADATA_KEY = 'jup_voice'

#: The model's own tools, forced as the turn's `tool_ids` and the only non-builtin tools offered.
VOICE_TOOL_IDS: tuple[str, ...] = ('portfolio_status',)

#: The builtin retrieval tools that stay scoped to the model's knowledge (checked against
#: `open_webui/tools/builtin.py` on 2026-09-27). The KB-wide variants (`*_knowledge_bases`) and
#: `kb_exec` (off here, unreviewed) are not in it.
KNOWLEDGE_TOOLS: frozenset[str] = frozenset(
    {
        'list_knowledge',
        'search_knowledge_files',
        'grep_knowledge_files',
        'query_knowledge_files',
        'view_file',
        'view_knowledge_file',
    }
)

#: The only feature a voice turn keeps: it asks for a spoken style and reaches nothing.
KEPT_FEATURES: frozenset[str] = frozenset({'voice'})

#: Request fields removed outright. `model_item` carries a direct connection.
REMOVED_FIELDS: tuple[str, ...] = (
    'model_item',
    'automation_id',
    'tool_servers',
    'tools',
    'terminal_id',
    'skill_ids',
    'filter_ids',
    'files',
    'folder_id',
)

_EMPTY = (None, '', [], {}, ())


def _given(value: Any) -> bool:
    """Whether a tool argument is a real value rather than the model's way of saying "none"."""
    if isinstance(value, str):
        return value.strip().lower() not in ('', 'none', 'null')
    return value not in _EMPTY


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _force_model_and_tools(form_data: dict) -> list[str]:
    changed = []
    if form_data.get('model') != VOICE_MODEL_ID:
        changed.append('model')
    form_data['model'] = VOICE_MODEL_ID

    changed += [key for key in REMOVED_FIELDS if key in form_data and form_data.pop(key) not in _EMPTY]

    tool_ids = form_data.get('tool_ids')
    if tool_ids not in _EMPTY and list(tool_ids) != list(VOICE_TOOL_IDS):
        changed.append('tool_ids')
    form_data['tool_ids'] = list(VOICE_TOOL_IDS)
    return changed


def _force_features_and_params(form_data: dict) -> list[str]:
    changed = []
    features = _dict(form_data.get('features'))
    if any(value for name, value in features.items() if name not in KEPT_FEATURES):
        changed.append('features')
    form_data['features'] = {name: True for name in KEPT_FEATURES if features.get(name)}

    params = _dict(form_data.get('params'))
    if params.get('function_calling') not in (None, 'native'):
        changed.append('params.function_calling')
    form_data['params'] = {**params, 'function_calling': 'native'}
    return changed


def _narrow_message_ids(form_data: dict) -> list[str]:
    if 'message_ids' not in form_data:
        return []
    entries = form_data['message_ids']
    if isinstance(entries, dict):
        entries = [{'model_id': model_id, 'message_id': message_id} for model_id, message_id in entries.items()]
    entries = [entry for entry in entries or [] if isinstance(entry, dict)]
    narrowed = [{**entries[0], 'model_id': VOICE_MODEL_ID}] if entries else []
    form_data['message_ids'] = narrowed
    return [] if entries == narrowed else ['message_ids']


def _narrow_messages(form_data: dict) -> list[str]:
    changed = []
    for key in ('user_message', 'parent_message'):
        message = form_data.get(key)
        if not isinstance(message, dict):
            continue
        widened = message.pop('files', None) not in _EMPTY
        if 'models' in message:
            widened = widened or message['models'] != [VOICE_MODEL_ID]
            message['models'] = [VOICE_MODEL_ID]
        if widened:
            changed.append(key)
    return changed


def rewrite(form_data: dict) -> list[str]:
    """Force a voice chat's completion request onto the voice model and tools, in place.

    Returns the names of the fields it changed, for the audit line; never their content.
    """
    return [
        *_force_model_and_tools(form_data),
        *_force_features_and_params(form_data),
        *_narrow_message_ids(form_data),
        *_narrow_messages(form_data),
    ]


def document_set(model: Mapping[str, Any] | None) -> frozenset[str] | None:
    """The file ids a voice turn may read, or `None` when the model's knowledge is not only files."""
    meta = ((model or {}).get('info') or {}).get('meta') or {}
    knowledge = meta.get('knowledge')
    if not isinstance(knowledge, list) or not knowledge:
        return None
    ids = set()
    for item in knowledge:
        if not isinstance(item, dict) or item.get('type') != 'file' or not item.get('id'):
            return None
        ids.add(item['id'])
    return frozenset(ids)


def _refusal(reason: str) -> str:
    # Worded for the model to relay: the question is outside what voice answers from.
    return json.dumps(
        {
            'error': f'Outside the voice scope: {reason} Voice answers only from its named documents. '
            'Tell the user plainly that this is outside the voice scope and that the typed '
            'assistant can answer it.'
        }
    )


def _widening(kwargs: Mapping[str, Any], files: frozenset[str]) -> str | None:
    file_id = kwargs.get('file_id')
    if _given(file_id) and file_id not in files:
        return 'that file is not in the voice document set.'
    if _given(kwargs.get('knowledge_id')) or _given(kwargs.get('knowledge_ids')):
        return 'voice cannot search a whole knowledge base.'
    return None


def _held_to(function: Callable[..., Any], files: frozenset[str]) -> Callable[..., Any]:
    # Deliberately not `functools.wraps`: that copies the vendor partial's `__function__` and
    # `__extra_params__`, and `utils/tools.py:get_updated_tool_function` would rebuild the raw
    # tool from them, dropping this guard. The knowledge tools read neither `__messages__` nor
    # `__files__`, which that refresh supplies, so nothing is lost.
    async def guarded(**kwargs: Any) -> Any:
        reason = _widening(kwargs, files)
        if reason is not None:
            return _refusal(reason)
        result = function(**kwargs)
        return await result if inspect.isawaitable(result) else result

    guarded.__name__ = getattr(function, '__name__', 'guarded')
    guarded.__doc__ = getattr(function, '__doc__', None)
    return guarded


def offered_tools(tools: Mapping[str, Any], model: Mapping[str, Any] | None) -> dict[str, Any]:
    """The tools a voice turn is offered: the voice tools, and scoped retrieval held to the set.

    A tool is matched by its `tool_id`, so a tool server that names a function like a builtin is
    not mistaken for it. A new dict; the vendor's is left alone.
    """
    files = document_set(model)
    offered: dict[str, Any] = {}
    for name, tool in tools.items():
        tool_id = tool.get('tool_id') if isinstance(tool, dict) else None
        if tool_id in VOICE_TOOL_IDS:
            offered[name] = tool
        elif files is not None and name in KNOWLEDGE_TOOLS and tool_id == f'builtin:{name}':
            offered[name] = {**tool, 'callable': _held_to(tool['callable'], files)}
    return offered


# --- The vendor's hooks: each returns its input unchanged unless the turn is a voice turn ---------


def is_voice_turn(metadata: Any) -> bool:
    return isinstance(metadata, Mapping) and metadata.get(METADATA_KEY) is True


def tools_for(metadata: Any, tools: dict, model: Mapping[str, Any] | None) -> dict:
    return offered_tools(tools, model) if is_voice_turn(metadata) else tools


def filter_tools_for(metadata: Any, tools: Any) -> Any:
    return None if is_voice_turn(metadata) else tools


def skills_for(metadata: Any, skill_ids: list[str]) -> list[str]:
    return [] if is_voice_turn(metadata) else skill_ids


def folder_for(metadata: Any, folder_id: Any) -> Any:
    return None if is_voice_turn(metadata) else folder_id
