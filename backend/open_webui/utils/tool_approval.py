import asyncio
import logging
import time
from typing import Any, Literal

from fastapi import HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from jup import approval as jup_approval
from jup import governance as jup_governance
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import WEBUI_SECRET_KEY
from open_webui.models.chats import Chats
from open_webui.models.users import Users
from open_webui.socket.main import get_event_emitter
from open_webui.utils.json_codec import JSONCodec

log = logging.getLogger(__name__)


class ResolveToolCallForm(BaseModel):
    call_id: str
    action: Literal['approve', 'reject', 'answer']
    answers: Any | None = None
    timed_out: bool = False


async def resolve_tool_call_output(
    chat_id: str,
    message_id: str,
    form_data: ResolveToolCallForm,
    user,
    db: AsyncSession | None = None,
) -> dict:
    chat = await Chats.get_chat_by_id(chat_id, db=db)
    # JUP: only the user whose turn produced the call decides it; an admin cannot approve for them
    # (ADR-0013 §3; VENDOR-PATCHES.md). The vendor also let an admin resolve any chat's calls.
    if not chat or chat.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    message = await Chats.get_message_by_id_and_message_id(chat_id, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    output = message.get('output') or []
    if not isinstance(output, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Message has no resolvable output.')

    function_call = next(
        (
            item
            for item in output
            if item.get('type') == 'function_call' and (item.get('call_id') or item.get('id')) == form_data.call_id
        ),
        None,
    )
    if not function_call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tool call not found.')
    function_call.setdefault('call_id', form_data.call_id)
    tool_name = function_call.get('name')

    if any(
        item.get('type') == 'function_call_output' and item.get('call_id') == form_data.call_id for item in output
    ) or function_call.get('status') not in {'pending', 'queued', 'requires_approval'}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Tool call has already been resolved.')

    if jup_approval.is_gated(function_call) and form_data.action in ('approve', 'reject'):
        # JUP: a gated External Call is decided by jup.approval: signed on approve, refused on
        # reject, and `timed_out` past its 10 minutes whatever was clicked (VENDOR-PATCHES.md).
        try:
            resolution = jup_approval.resolve(
                function_call,
                form_data.action,
                chat_id=chat_id,
                message_id=message_id,
                user_id=user.id,
                now_ms=int(time.time() * 1000),
                secret=WEBUI_SECRET_KEY,
            )
        except jup_approval.AlreadyResolved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Tool call has already been resolved.')
        _jup_record_refusal(output, function_call, resolution, chat_id=chat_id, user_id=chat.user_id)
    elif form_data.action == 'approve':
        if tool_name == 'ask_user':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='ask_user requires an answer or deny.')
        function_call['status'] = 'queued'
        function_call['approved'] = True
    elif form_data.action == 'reject':
        function_call['status'] = 'rejected'
        output.append(
            {
                'type': 'function_call_output',
                'id': f'fco_{form_data.call_id}',
                'call_id': form_data.call_id,
                'output': [{'type': 'input_text', 'text': 'Error: tool call rejected by user.'}],
                'status': 'rejected',
            }
        )
    else:
        if tool_name != 'ask_user':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Tool call does not accept answers.')
        if form_data.answers is None and not form_data.timed_out:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Answers are required for ask_user.')
        function_call['status'] = 'completed'
        answer_payload = (
            {'status': 'cancelled', 'answers': {}, 'timed_out': True}
            if form_data.timed_out
            else {'status': 'answered', 'answers': form_data.answers or {}}
        )
        output.append(
            {
                'type': 'function_call_output',
                'id': f'fco_{form_data.call_id}',
                'call_id': form_data.call_id,
                'output': [{'type': 'input_text', 'text': JSONCodec.dumps(answer_payload)}],
                'status': 'completed',
            }
        )

    await Chats.upsert_message_to_chat_by_id_and_message_id(
        chat_id,
        message_id,
        {
            'done': False,
            'output': output,
        },
        touch=False,
    )

    event_emitter = await get_event_emitter(
        {
            'user_id': chat.user_id,
            'chat_id': chat_id,
            'message_id': message_id,
        },
        update_db=False,
    )
    if event_emitter:
        await event_emitter({'type': 'chat:completion', 'data': {'output': output}})

    result_call_ids = {
        item.get('call_id') for item in output if item.get('type') == 'function_call_output' and item.get('call_id')
    }
    paused = any(
        item.get('type') == 'function_call'
        and item.get('call_id')
        and item.get('status') in {'pending', 'queued', 'requires_approval'}
        and item.get('call_id') not in result_call_ids
        for item in output
    )
    return {'chat': chat, 'message': message, 'output': output, 'paused': paused}


def _jup_record_refusal(output: list, function_call: dict, resolution, *, chat_id: str, user_id: str) -> None:
    """Give the model a refused gated call's reason, and write the decision to the audit line.

    An approval is audited where the call runs (the drain), with its outcome; a refusal never runs,
    so it is audited here, where it is decided. Nothing is written for an approval.
    """
    if resolution.message is None:
        return
    call_id = function_call.get('call_id')
    output.append(
        {
            'type': 'function_call_output',
            'id': f'fco_{call_id}',
            'call_id': call_id,
            'output': [{'type': 'input_text', 'text': resolution.message}],
            'status': 'rejected',
        }
    )
    jup_governance.audit_tool_call(
        name=function_call.get('name', ''),
        arguments=function_call.get('arguments'),
        tool={'tool_id': resolution.tool_id},
        result=resolution.message,
        error=False,
        user_id=user_id,
        chat_id=chat_id,
        mode='approval',
        approval=resolution.approval,
        approved_by=resolution.approved_by,
        approval_wait_ms=resolution.wait_ms,
    )


#: Pending timeout tasks, held so they are not garbage-collected before they fire.
_jup_timeouts: set[asyncio.Task] = set()


def arm_jup_approval_timeout(chat_id: str, message_id: str, call_id: str) -> None:
    """JUP: refuse a shown gated call as `timed_out` once its 10 minutes pass, tab open or not.

    Scheduled on this instance when the card is shown. Nothing is lost if it never fires (an
    instance restart): the deadline is also enforced when anyone next resolves the call, and an
    approval cannot be signed after it (`jup.approval.resolve`). It does nothing if the call was
    decided meanwhile, on this instance or another, because it re-reads the stored message.
    """
    try:
        task = asyncio.get_running_loop().create_task(_jup_time_out(chat_id, message_id, call_id))
    except RuntimeError:
        log.warning('jup: no event loop to time out tool call %s; it times out on its next resolve', call_id)
        return
    _jup_timeouts.add(task)
    task.add_done_callback(_jup_timeouts.discard)


async def _jup_time_out(chat_id: str, message_id: str, call_id: str) -> None:
    try:
        await asyncio.sleep(jup_approval.TIMEOUT_MS / 1000 + 1)
        chat = await Chats.get_chat_by_id(chat_id)
        message = await Chats.get_message_by_id_and_message_id(chat_id, message_id)
        output = message.get('output') if message else None
        if not chat or not isinstance(output, list):
            return
        if any(item.get('type') == 'function_call_output' and item.get('call_id') == call_id for item in output):
            return
        function_call = next(
            (item for item in output if item.get('type') == 'function_call' and item.get('call_id') == call_id), None
        )
        resolution = jup_approval.time_out(function_call, now_ms=int(time.time() * 1000))
        if resolution is None:
            return
        _jup_record_refusal(output, function_call, resolution, chat_id=chat_id, user_id=chat.user_id)
        await Chats.upsert_message_to_chat_by_id_and_message_id(
            chat_id, message_id, {'done': False, 'output': output}, touch=False
        )
        event_emitter = await get_event_emitter(
            {'user_id': chat.user_id, 'chat_id': chat_id, 'message_id': message_id}, update_db=False
        )
        if event_emitter:
            await event_emitter({'type': 'chat:completion', 'data': {'output': output}})

        # Resume the turn so the model is told, as the resolve route does after a reject.
        user = await Users.get_user_by_id(chat.user_id)
        if not user:
            return
        from open_webui.main import app  # deferred: main imports this module

        payload = await build_tool_approval_resume_payload(chat_id, message_id)
        request = Request(
            {
                'type': 'http',
                'asgi': {'version': '3.0', 'spec_version': '2.0'},
                'method': 'POST',
                'path': f'/api/v1/chats/{chat_id}/messages/{message_id}/resolve',
                'query_string': b'',
                'headers': Headers({}).raw,
                'client': ('127.0.0.1', 0),
                'server': ('127.0.0.1', 80),
                'scheme': 'http',
                'app': app,
            }
        )
        request.state.token = None
        request.state.enable_api_keys = False
        await app.state.CHAT_COMPLETION_HANDLER(request, payload, user=user)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception('jup: could not time out tool call %s in chat %s', call_id, chat_id)


async def build_tool_approval_resume_payload(chat_id: str, message_id: str, chat=None) -> dict:
    chat = chat or await Chats.get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    assistant_message = await Chats.get_message_by_id_and_message_id(chat_id, message_id)
    if not assistant_message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    user_message_id = assistant_message.get('parentId')
    user_message = await Chats.get_message_by_id_and_message_id(chat_id, user_message_id) if user_message_id else None
    if not user_message:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Tool call parent message is missing.')

    chat_data = chat.chat or {}
    message_meta = assistant_message.get('meta') if isinstance(assistant_message.get('meta'), dict) else {}
    chat_params = chat_data.get('params') if isinstance(chat_data.get('params'), dict) else {}
    params = {
        **chat_params,
        **(message_meta.get('params') if isinstance(message_meta.get('params'), dict) else {}),
    }
    current_approval_mode = chat_params.get('tool_approval_mode')
    if current_approval_mode in {'ask', 'full'}:
        params['tool_approval_mode'] = current_approval_mode
    if 'tool_approval_mode' not in params:
        params['tool_approval_mode'] = 'ask'

    model_id = assistant_message.get('model') or next(iter(chat_data.get('models') or []), None)
    if not model_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Tool call message model is missing.')

    messages = []
    if params.get('system'):
        messages.append({'role': 'system', 'content': params.get('system')})

    return {
        'stream': params.get('stream_response', True),
        'model': model_id,
        'messages': messages,
        'params': params,
        'files': message_meta.get('files') or chat_data.get('files') or None,
        'filter_ids': message_meta.get('filter_ids') or None,
        'tool_ids': message_meta.get('tool_ids') or None,
        'skill_ids': message_meta.get('skill_ids') or None,
        'terminal_id': message_meta.get('terminal_id') or None,
        'tool_servers': message_meta.get('tool_servers') or None,
        'features': message_meta.get('features') or {},
        'variables': message_meta.get('variables') or {},
        'chat_variables': chat.variables,
        'session_id': message_meta.get('session_id'),
        'chat_id': chat_id,
        'id': message_id,
        'parent_id': user_message.get('parentId'),
        'user_message': user_message,
        'assistant_message_id': message_id,
    }
