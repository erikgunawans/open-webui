# Fail-closed enforcement attaches at `generate_chat_completion`

Fail-closed behaviour is enforced by patching `backend/open_webui/utils/chat.py:151`
(`generate_chat_completion`) — the only in-process funnel to every provider, reached by all 17 call
sites including every tool-loop turn (`utils/middleware.py:5994`, `:6214`), task generation, memory
and context compaction — plus a guard at the head of the directly-mounted provider routes
`routers/openai.py:1464` and `routers/ollama.py:1091`, which sit behind only `get_verified_user`
and would otherwise let a normal user's API key bypass the pipeline entirely.

We patch vendor code rather than use the extension points because every extension point fails.

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
