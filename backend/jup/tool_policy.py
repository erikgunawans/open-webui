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

**What happens to an `external` call.** Until the approval card exists (ticket 3/7), it is
refused, whatever the chat's `tool_approval_mode`: refusing is the safe first state of the gate.
The model is told the call was refused and why, so it can say so instead of retrying or hanging.
"""

from dataclasses import dataclass
from typing import Any

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
    # a subagent's own tools are filtered separately (ticket 2/7)
    'delegate_task': READ,
    'timer': READ,
}

_BUILTIN_PREFIX = 'builtin:'


@dataclass(frozen=True)
class Ruling:
    """The gate's answer for one call (not a register Decision, which is `jup.decisions.Decision`). `approval` is the value the audit line records."""

    runs: bool
    risk_class: str
    approval: str
    message: str | None = None


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


def decide(name: str, tool: Any) -> Ruling:
    """Whether the call to `name` runs. `name` is only used to word the refusal."""
    risk_class = classify(tool)
    if risk_class != EXTERNAL:
        return Ruling(runs=True, risk_class=risk_class, approval='not_required')
    return Ruling(runs=False, risk_class=risk_class, approval='rejected', message=_refusal(name))


def _refusal(name: str) -> str:
    # Worded for the model to relay, like `portfolio_status.REFUSAL`: "I could not do it" would
    # misstate a policy refusal as a failure, and invite a retry by another route.
    return (
        f"Refused by JUP's approval gate: `{name}` is an External Call (risk class `external`), "
        "meaning it can act outside the user's own space, and External Calls need an approval step "
        'that is not available yet. The tool did not run. Tell the user plainly that this action was '
        'refused by policy; do not attempt it another way.'
    )


__all__ = ['BUILTIN_CLASSES', 'EXTERNAL', 'READ', 'RISK_CLASSES', 'WRITE_OWN', 'Ruling', 'classify', 'decide']
