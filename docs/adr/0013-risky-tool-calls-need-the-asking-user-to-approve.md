# Risky tool calls need the asking user to approve them

**Status: Accepted 2026-09-24 — Erik Gunawan Supriatna, Director, Operation & Business
Development.** Settled in one grilling session (E5 in `.planning/agent-depth-plan.md`). Nothing is
built yet: the gate ships with whichever of E3 (terminal), E4 (browser) or A5 (MCP) goes live first,
so no tool with an outside effect is ever live without it.

Today no risky tool exists. `portfolio_status` reads, KB search reads, subagents delegate, and the
code interpreter runs in the user's browser. The tools that can act on the world — a terminal, a
browser that submits forms, an MCP server that sends — are all ahead of us. This decision fixes the
rules before the first of them arrives, rather than after.

## Why the vendor's `ask` mode is not the gate

Open WebUI already has a tool-approval flow (`utils/tool_approval.py`). It is not enough, on four
counts:

| Property | Vendor behaviour | Where |
|---|---|---|
| Granularity | `ask` pauses **every** tool call except `ask_user`; there is no notion of a risky one | `utils/middleware.py:3276`, `:5642` |
| Who controls it | The client sends `params.tool_approval_mode` per chat; the user can set it back to `full` | `main.py:1250`, `Chat.svelte:419` |
| Unattended paths | Automations and `channel:` chats are forced to `full` — they never pause | `main.py:1251` |
| Record | The approve/reject lands only in the chat's `output`, which the user can delete | `tool_approval.py:64` |

A user preference that the user can turn off, and that is skipped exactly where nobody is watching,
is a convenience. The gate below is a control. The vendor's pause-and-resume machinery
(`pause_for_tool_approval`, `resolve_tool_call_output`) is the mechanism we build on; the policy of
*which* calls pause is ours.

## Decision

### 1. Every tool declares a risk class

| Class | Meaning | Gated |
|---|---|---|
| `read` | Reads only | no |
| `write_own` | Writes inside JUP, scoped to the calling user's own data (memory, their notes) | no — audited only |
| `external` | Anything with an effect outside the user's own space: outbound network, sends, form submits, terminal commands, writes to shared data or another user's data | **yes** |

- A tool with no declared class is `external`. A new tool cannot slip through unmarked.
- An MCP or OpenAPI server gets one class for all its tools, set by an admin, overridable per tool.
  An unclassified server defaults to `external`.
- Only admins set or change a class.

### 2. The gate is server-side and cannot be switched off

An `external` call pauses for approval whatever the chat's `tool_approval_mode` says. `ask`/`full`
remains a user preference for ungated tools only.

### 3. The asking user approves, one call at a time

- The approver is the user whose turn produced the call. While everything is admin-only an admin
  approver would be Erik approving himself; revisit when staff get `external` tools.
- One approval covers exactly the call shown. There is no "allow for this chat" and no "always".
- The approval card shows the full call arguments, with secret-looking values (tokens, keys,
  passwords) masked, and the tool's class as a label. The user is approving their own call and needs
  to see the real thing.
- An unanswered approval is rejected as `timed_out` after **10 minutes**, and the model is told.
  Nothing stays pending overnight.

### 4. Every path with nobody present fails closed

| Path | Behaviour |
|---|---|
| Automations (A1) | An `external` call is rejected as `rejected_unattended`, the model is told why, and the owner sees it in the run's chat. Pre-approving tools per automation can come later if a real automation needs it. |
| Subagents (A2) | A subagent's tool set excludes `external` tools. Delegation stays read-and-reason. |
| Channels (E7) | `external` calls are denied. Approving by channel reply is deferred to E7's own ADR, because it needs identity binding E7 does not have yet. |

### 5. The decision is in the audit line

The E1 `jup.governance` `tool_call` line gains:

- `approval`: `approved`, `rejected`, `timed_out`, `rejected_unattended` or `not_required`
- `approved_by`: the deciding user's id
- `approval_wait_ms`: how long the call waited

It still never carries argument content. The audit line is the record of the decision; the chat is
not, because the user can delete it.

## Today's tools

| Tool | Class | Note |
|---|---|---|
| `portfolio_status` | `read` | |
| KB search | `read` | |
| Subagents | `read` | Delegation itself; the subagent's own tools are filtered per §4 |
| Code interpreter (Pyodide) | `read` | See below |
| Vendor memory tools | `write_own` | |

**The code interpreter is `read`, with a caveat.** Pyodide can reach the network from the browser
through `pyfetch`, so strictly it has an outbound path. But the sandbox is the user's own browser,
and nothing it can fetch is out of the user's reach by hand, while a card on every code run would
end A3. If code execution ever moves to the server-side Jupyter engine, that engine is `external`
by default and this line must be revisited.

## Consequences

- E3, E4 and A5 are blocked on E5 in the ledger. Whichever ships first carries the gate.
- The vendor surface grows at the tool-dispatch point in `utils/middleware.py`, and in
  `main.py:1250` where automations and channels are forced to `full`. Each patch needs a
  lost-patch test and a `VENDOR-PATCHES.md` entry, and under ADR-0007 is re-paid every quarter.
- Tool metadata gains a `risk_class` field. `tools/*.py` and `skills/` stay the source of truth
  for the DB rows, so the class is declared in the file, not in the DB.
- The ADR for E7 must decide channel-reply approval before channels get any `external` tool.
