"""Risk Classes, and the gate's decision for one tool call (ADR-0013, A5 + E5).

Every tool the assistant can call has a **Risk Class**: `read`, `write_own` or `external`
(glossary: `CONTEXT.md`). This module is the whole of that policy, so that the vendor patches at
tool dispatch stay one call each and every rule is tested here rather than inside `middleware.py`.

**Where a tool's class comes from**, in order:

1. A native JUP tool declares it in its own source file's frontmatter (`risk_class: read`). The
   vendor copies frontmatter into the stored tool's `meta.manifest` on create and update, which
   is how `deploy/gcp/sync-tools.ts` carries it into the DB, and `utils/tools.py:get_tools` puts
   it on the tool entry. That declaration is trusted because tool authoring is admin-only on this
   deployment (`workspace.tools*` is false for users); if that ever changes, so does this trust.
2. A vendor built-in is looked up in `BUILTIN_CLASSES`, by its `builtin:<name>` id. A built-in
   cannot declare a class of its own.
3. Anything else is `external`: an unlisted built-in, an undeclared or misdeclared native tool, a
   tool server, a terminal. A tool nobody classified is gated, never waved through.

MCP server classes (the per-server class and per-tool override) arrive with A5 + E5 ticket 6/7.

**What happens to an `external` call** in a chat with a person present: it pauses for that person
through the vendor's approval card, whatever the chat's `tool_approval_mode` (`must_pause`), and
runs only with a verified approval (`jup.approval`, ticket 3/7). Without one it is refused as
`rejected`, and the model is told why, so it can say so instead of retrying or hanging.

**Where nobody is present to approve** (ADR-0013 §4, ticket 2/7): an automation run, a channel
chat and a subagent are unattended **paths**. There an `external` call is refused as
`rejected_unattended`, and stays refused once the card exists, because there is no one to show it
to. The vendor forces automations and channels to `full` mode; that is why the gate never reads
`tool_approval_mode` at all. A subagent is not even offered `external` tools (`offered_tools`).
"""

from dataclasses import dataclass
from typing import Any

# The attribute `utils/subagents.py` stamps on a subagent's request; it is what marks the path.
from jup.governance import PARENT_CHAT_STATE_ATTR

READ = 'read'
WRITE_OWN = 'write_own'
EXTERNAL = 'external'
RISK_CLASSES = frozenset({READ, WRITE_OWN, EXTERNAL})

#: Every vendor built-in, classified once and reviewed by an admin (ADR-0013 amendment §2, the
#: A5 + E5 spec's table). Checked against `open_webui/tools/builtin.py` on 2026-09-26. A built-in
#: that is not here is `external`, so one that arrives in a vendor upgrade is gated until someone
#: adds a row; the quarterly rebase (ADR-0007) is where they surface. `kb_exec` is deliberately
#: absent: it is off on this deployment (`ENABLE_KB_EXEC`) and has not been reviewed.
BUILTIN_CLASSES: dict[str, str] = {
    # time
    'get_current_timestamp': READ,
    'calculate_timestamp': READ,
    # web: search is the named exception (amendment §1); a fetch reaches any URL the model picks
    'search_web': READ,
    'fetch_url': EXTERNAL,
    # images: the prompt goes to an image provider outside the model funnel (amendment §3)
    'generate_image': EXTERNAL,
    'edit_image': EXTERNAL,
    # the model asking the user a question
    'ask_user': READ,
    # code runs in the browser under Pyodide (ADR-0013)
    'execute_code': READ,
    # memory
    'list_memory_paths': READ,
    'read_memory_path': READ,
    'search_memories': READ,
    'list_memories': READ,
    'add_memory': WRITE_OWN,
    'update_memory': WRITE_OWN,
    'replace_memory_content': WRITE_OWN,
    'delete_memory': WRITE_OWN,
    # notes: a write can edit a note someone else shares with the user (amendment §3)
    'search_notes': READ,
    'view_note': READ,
    'write_note': EXTERNAL,
    'replace_note_content': EXTERNAL,
    # chats and channels
    'search_chats': READ,
    'view_chat': READ,
    'search_channels': READ,
    'search_channel_messages': READ,
    'view_channel_message': READ,
    'view_channel_thread': READ,
    # knowledge and chat files
    'list_knowledge_bases': READ,
    'search_knowledge_bases': READ,
    'query_knowledge_bases': READ,
    'list_knowledge': READ,
    'search_knowledge_files': READ,
    'grep_knowledge_files': READ,
    'query_knowledge_files': READ,
    'view_knowledge_file': READ,
    'list_chat_files': READ,
    'grep_chat_files': READ,
    'query_chat_files': READ,
    'view_file': READ,
    'view_skill': READ,
    # tasks and automations: the user's own; an `external` call inside a run is refused anyway
    'create_tasks': WRITE_OWN,
    'update_task': WRITE_OWN,
    'list_automations': READ,
    'create_automation': WRITE_OWN,
    'update_automation': WRITE_OWN,
    'toggle_automation': WRITE_OWN,
    'delete_automation': WRITE_OWN,
    # calendar: a write can touch a calendar someone else shares (amendment §3)
    'search_calendar_events': READ,
    'create_calendar_event': EXTERNAL,
    'update_calendar_event': EXTERNAL,
    'delete_calendar_event': EXTERNAL,
    # the user's own webhook
    'notify': READ,
    # a subagent's own tools are filtered separately (`offered_tools`)
    'delegate_task': READ,
    'timer': READ,
}

_BUILTIN_PREFIX = 'builtin:'

#: The paths a tool call can arrive on. Only `CHAT` has a person present who could approve.
CHAT = 'chat'
AUTOMATION = 'automation'
CHANNEL = 'channel'
SUBAGENT = 'subagent'
UNATTENDED = frozenset({AUTOMATION, CHANNEL, SUBAGENT})


@dataclass(frozen=True)
class Ruling:
    """The gate's answer for one call (not a register Decision, which is `jup.decisions.Decision`).

    `approval` is the value the audit line records.
    """

    runs: bool
    risk_class: str
    approval: str
    message: str | None = None
    approved_by: str | None = None
    approval_wait_ms: int = 0


def classify(tool: Any) -> str:
    """The Risk Class of a tool entry from the vendor's tools dict. Never raises."""
    if not isinstance(tool, dict):
        return EXTERNAL
    tool_id = tool.get('tool_id')
    if not isinstance(tool_id, str) or not tool_id:
        return EXTERNAL
    if tool_id.startswith(_BUILTIN_PREFIX):
        return BUILTIN_CLASSES.get(tool_id[len(_BUILTIN_PREFIX) :], EXTERNAL)
    if ':' in tool_id:
        # `server:…` (OpenAPI and MCP) and `terminal:…`. Their classes are not declared yet.
        return EXTERNAL
    declared = tool.get('risk_class')
    return declared if declared in RISK_CLASSES else EXTERNAL


def path_of(metadata: Any, state: Any = None) -> str:
    """The path a request's tool calls arrive on, from the vendor's chat `metadata` and request state.

    An automation is checked first: a channel automation is both, and either is unattended. The
    chat's `tool_approval_mode` is deliberately not read: the vendor sets it to `full` on exactly
    the paths where nobody can approve.
    """
    metadata = metadata if isinstance(metadata, dict) else {}
    if metadata.get('automation_id'):
        return AUTOMATION
    chat_id = metadata.get('chat_id')
    if isinstance(chat_id, str) and chat_id.startswith('channel:'):
        return CHANNEL
    if state is not None and getattr(state, PARENT_CHAT_STATE_ATTR, None):
        return SUBAGENT
    return CHAT


def decide(name: str, tool: Any, *, path: str, approval: Any = None) -> Ruling:
    """Whether the call to `name` runs on `path`. `name` is only used to word the refusal.

    `path` is required so that no dispatch site can forget it and be taken for an attended chat.
    An unknown path is treated as unattended. `approval` is a `jup.approval.Approval` that
    `jup.approval.verified` returned for this very call; only an attended chat can use one.
    """
    risk_class = classify(tool)
    if risk_class != EXTERNAL:
        return Ruling(runs=True, risk_class=risk_class, approval='not_required')
    if path != CHAT:
        return Ruling(
            runs=False, risk_class=risk_class, approval='rejected_unattended', message=_unattended_refusal(name, path)
        )
    if approval is not None:
        return Ruling(
            runs=True,
            risk_class=risk_class,
            approval='approved',
            approved_by=approval.approved_by,
            approval_wait_ms=approval.wait_ms,
        )
    return Ruling(runs=False, risk_class=risk_class, approval='rejected', message=_refusal(name))


def must_pause(name: str, tool: Any, *, mode: Any, path: str) -> bool:
    """Whether a call waits for a card: every attended `external` call, whatever `mode` says.

    `mode` is the chat's `tool_approval_mode`. In `ask` the vendor pauses every call except
    `ask_user`, and that preference is kept for ungated tools; it can add cards, never remove one.
    """
    if path == CHAT and classify(tool) == EXTERNAL:
        return True
    return mode == 'ask' and name != 'ask_user'


def preapprove_ungated(output: list, call_ids: Any, tools: dict, *, path: str) -> None:
    """In `full` mode, let this batch's ungated calls through while its gated ones wait.

    The vendor resumes a paused message by running the calls marked approved, so an ungated call in
    the same batch is marked approved (it would have run anyway in `full`) and runs alongside the
    gated ones once they are decided. Only the items of this batch (`call_ids`) are touched.
    """
    call_ids = set(call_ids)
    for item in output:
        if (
            isinstance(item, dict)
            and item.get('type') == 'function_call'
            and (item.get('call_id') or item.get('id')) in call_ids
            and not must_pause(item.get('name', ''), tools.get(item.get('name', '')), mode='full', path=path)
        ):
            item['status'] = 'queued'
            item['approved'] = True


def offered_tools(tools: dict, path: str) -> dict:
    """The tools a model on `path` may be offered: a subagent gets no `external` tool at all."""
    if path != SUBAGENT:
        return tools
    return {name: tool for name, tool in tools.items() if classify(tool) != EXTERNAL}


def _refusal(name: str) -> str:
    # Worded for the model to relay, like `portfolio_status.REFUSAL`: "I could not do it" would
    # misstate a policy refusal as a failure, and invite a retry by another route.
    return (
        f"Refused by JUP's approval gate: `{name}` is an External Call (risk class `external`), "
        "meaning it can act outside the user's own space, and it runs only after the user approves it "
        'on the approval card, and no approval came with this call (the card cannot be shown in a '
        'temporary chat or in prompt-based tool calling). The tool did not run. Tell the user '
        'plainly that this action was refused by policy; do not attempt it another way.'
    )


_WHERE = {
    AUTOMATION: 'an automation run',
    CHANNEL: 'a channel conversation',
    SUBAGENT: 'a subagent task',
}


def _unattended_refusal(name: str, path: str) -> str:
    where = _WHERE.get(path, 'an unattended conversation')
    return (
        f"Refused by JUP's approval gate: `{name}` is an External Call (risk class `external`), "
        f'and this is {where}, where nobody is present to approve it (reason: `rejected_unattended`). '
        'The tool did not run. State plainly in your reply that this step was refused by policy '
        'because it needs a person to approve it; do not attempt it another way.'
    )


__all__ = [
    'AUTOMATION',
    'BUILTIN_CLASSES',
    'CHANNEL',
    'CHAT',
    'EXTERNAL',
    'READ',
    'RISK_CLASSES',
    'SUBAGENT',
    'UNATTENDED',
    'WRITE_OWN',
    'Ruling',
    'classify',
    'decide',
    'must_pause',
    'offered_tools',
    'path_of',
    'preapprove_ungated',
]
