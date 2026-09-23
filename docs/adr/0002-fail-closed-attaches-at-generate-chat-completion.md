# Fail-closed enforcement attaches at `generate_chat_completion`

Fail-closed behaviour is enforced by patching `backend/open_webui/utils/chat.py:151`
(`generate_chat_completion`) — the only in-process funnel to every provider, reached by all 17 call
sites including every tool-loop turn (`utils/middleware.py:5994`, `:6214`), task generation, memory
and context compaction — plus a guard at the head of the directly-mounted provider routes
`routers/openai.py:1464` and `routers/ollama.py:1091`, which sit behind only `get_verified_user`
and would otherwise let a normal user's API key bypass the pipeline entirely.

We patch vendor code rather than use the extension points because every extension point fails.

**Policy settled 2026-09-21 — Erik Gunawan Supriatna, Director, Operation & Business Development.**
This ADR fixes *where* enforcement attaches and never what it enforces. The policy is now: **a
governed turn must carry the JUP operating contract in its system message, or it is refused**, and
every turn is audited — admitted, exempt and refused alike. Governed traffic is user-facing chat
turns, including every tool-loop turn; the named internal generations (title, tags, follow-up, emoji,
query, image prompt, autocomplete, native function-calling, MoA) are exempt by a tested allowlist,
and that exemption is honoured only for a turn the funnel stamped, never for one claiming a task name
on a directly-mounted route. Implemented in `backend/jup/governance.py`; issue #16.

`~/jup/kb/serve.ts`'s tier-discipline guard was the obvious candidate to port a third time (D13
records the second port, into the Cloudflare Worker) and it cannot be ported as written: it inspects
the model's *answer*, which it can do because it is non-streaming. Every attachment point here is an
inlet, and the Consequences section below is the reason. So the contract carries D11's
revenue-not-margin rule into the model's context instead, which is the one place that rule can still
change an answer on a streamed turn.

## Considered options

- **`EVENT_SINKS`** (`events.py:1171`) — discards each sink's return value, swallows sink exceptions
  in a `try/except` that logs and continues (`:1198-1202`), three of four sinks are
  `asyncio.create_task` fire-and-forget, and it fires *after* the mutation it describes
  (`main.py:1370` insert → `:1395` publish). A sink can audit. It can never refuse.
- **Filter functions** — disableable by any admin in two clicks
  (`routers/functions.py:287`, `:341`), killed wholesale by `ENABLE_PLUGINS=false`, and `inlet` runs
  only once, so a tool loop re-enters the provider from turn two with only `filter_type='request'`.
- **Pipeline inlet filters** — fail open on connection error (`routers/pipelines.py:123-124`).
- **`outlet_filter_handler`** — runs after delivery on the websocket streaming branch
  (`utils/middleware.py:6278`) and is wrapped in a `try/except` that logs and continues (`:4029`).

## Consequences

**Enforcement is inlet-only.** There is no way to block a websocket-streamed response once the first
token has shipped, so a control that must prevent output has to refuse the request, not correct the
answer. A post-hoc outlet pass can repair the stored record via `chat:outlet`; it is not a control.

`utils/chat.py` is stable — nine touches in twelve months — so that patch is cheap to carry.
`routers/openai.py` is not (59 commits in six months), so the guard there stays a three-line insert
at the function head and is re-checked on every upstream merge.

## Amendment 2026-09-23 — the passthrough routes, and MoA

A code trace for the agentic-capabilities plan found that "all 17 call sites" were not the whole
surface. Six more mounted routes reach a provider without passing the funnel:
`routers/openai.py` `/responses`, and `routers/ollama.py` `/api/generate`, `/v1/completions`,
`/v1/chat/completions`, `/v1/messages` and `/v1/responses`. Nothing inside the app calls any of
them: the pipeline's own use of the Responses API happens inside the governed
`generate_chat_completion`. Their payloads carry instructions outside `messages` (`instructions`,
`system`, `prompt`), so `refuse_if_ungoverned`'s contract check cannot be applied soundly, and a
caller could satisfy it with a field the provider ignores. They are therefore **refused outright**
by `jup.governance.refuse_passthrough`, as the first statement of each handler, and the refusal is
audited. `tests/test_jup_governance.py` checks each insert is present and comes first.

The task exemption had a second hole. `routers/tasks.py`'s MoA route takes the caller's `prompt`
and `responses` verbatim and sets `task=moa_response_generation` itself, so the "stamped turns
only" rule could not tell it from a real internal generation: any verified user had an exempt,
contract-free completion on their own text. JUP never uses MoA, so it was **removed from
`EXEMPT_TASKS`** and now carries the contract like any other turn. The query, image-prompt and
autocomplete task routes also accept user text, but wrap it in a server-side template; that
residual exposure is accepted and recorded here.

Not a model call, but found in the same trace and closed in the same change:
`routers/retrieval.py` `/process/url` and `/process/web` fetched any URL for any verified user.
They now require the vendor's own `chat.web_upload` permission, which it defined but enforced
only in the UI.

These were all masked while non-admins had no model grant. They are closed before the first
grant, not after.
