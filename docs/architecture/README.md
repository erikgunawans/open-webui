# Open WebUI Architecture Notes

Notes on the **vendor codebase** this repo is a fork of: Open WebUI v0.11.3 at commit `0a7c158`.
Produced by reading all 1,017 source files (348,002 lines) in full, 2026-09-18.

At the time of writing `HEAD` was byte-identical to `upstream/main` — these describe upstream's
code, not ours. As we diverge, prefer `git diff upstream/main...HEAD` over these notes for
anything we've changed, and record **our** decisions in `docs/adr/` (see `docs/agents/domain.md`).

## Index

| File | Scope | Lines read |
|---|---|---|
| [01-backend-core.md](01-backend-core.md) | `main.py`, `config.py`, `env.py`, `internal/`, `socket/`, `tasks.py`, `events.py` | ~12K |
| [02-backend-models.md](02-backend-models.md) | `models/` — **the domain vocabulary** | 16.5K |
| [03-backend-routers-a.md](03-backend-routers-a.md) | retrieval, knowledge, chats, openai, channels, auths, ollama, audio | 17K |
| [04-backend-routers-b.md](04-backend-routers-b.md) | the other 23 routers; the plugin system | 16K |
| [05-backend-utils-a-PIPELINE.md](05-backend-utils-a-PIPELINE.md) | **`middleware.py` — the chat pipeline**, auth, oauth, tools | 15K |
| [06-backend-utils-b.md](06-backend-utils-b.md) | access control, plugin loading, templates, telemetry, audit | 10.4K |
| [07-backend-retrieval-rag.md](07-backend-retrieval-rag.md) | the whole RAG stack: 13 vector stores, loaders, 22 search providers | 16K |
| [08-backend-tools-migrations.md](08-backend-tools-migrations.md) | builtin tools; **the 58-revision migration chain** | 11K |
| [09-fe-apis-stores.md](09-fe-apis-stores.md) | the API client layer and all global state | 17K |
| [10-fe-utils-routes.md](10-fe-utils-routes.md) | routing, bootstrap, utils, workers, build | 12K |
| [11-fe-chat-core.md](11-fe-chat-core.md) | **`Chat.svelte`** — submit/stream/render and the message tree | 30K |
| [12-fe-chat-periphery.md](12-fe-chat-periphery.md) | markdown rendering pipeline, citations, artifacts | 17K |
| [13-fe-admin-GOVERNANCE.md](13-fe-admin-GOVERNANCE.md) | **the entire governance surface + permission matrix** | 23K |
| [14-fe-workspace.md](14-fe-workspace.md) | models/knowledge/prompts/tools/skills authoring; access-control UI | 20K |
| [15-fe-common-primitives.md](15-fe-common-primitives.md) | the shared UI primitive layer and icon set | 17K |
| [16-fe-layout-channels.md](16-fe-layout-channels.md) | app shell, sidebar, search, real-time channels | 15K |

## The five things that matter most

1. **`utils/middleware.py` is the product.** 6,400 lines carrying every chat request from raw
   payload to persisted message. Read [05](05-backend-utils-a-PIPELINE.md) before changing anything
   in the request path.
2. **`access_grants` is the single authorization authority.** The legacy `access_control` JSON
   columns are gone. `has_permission_filter` (`models/access_grants.py:723`) backs every list
   endpoint. See [02](02-backend-models.md) and [06](06-backend-utils-b.md).
3. **Migrations run at `config.py` import time.** A fork revision that collides with an upstream
   one produces two alembic heads, and the app will not boot at all. See [08](08-backend-tools-migrations.md).
4. **Anyone holding the `workspace.tools` permission has RCE on the server.** `exec()` with no
   sandbox, plus `pip install` from user-supplied frontmatter. `ENABLE_PLUGINS=false` is the only
   kill switch. See [04](04-backend-routers-b.md) and [06](06-backend-utils-b.md).
5. **Every frontend guard is cosmetic.** Admin routes, permission checks and hidden controls are
   client-side `goto('/')` calls. The backend must re-assert everything. See [13](13-fe-admin-GOVERNANCE.md).

## Where governance hooks belong

`publish_event` / `EVENTS` (`open_webui/events.py`) is already called on nearly every mutation and
is the cleanest audit/SIEM seam — a sink class appended to `EVENT_SINKS` needs no router changes.
Beyond that: `process_chat_payload`'s exit (`middleware.py:3115`) is the last point where the full
resolved payload exists; `execute_tool_call` (`:5671`) is the single tool-execution chokepoint;
`filter_accessible_collections` (`retrieval/utils.py:1268`) is the single retrieval authorization
chokepoint; `merge_usage` (`utils/response.py:100`) already aggregates per-model/per-user/per-group
token usage for chargeback.

**Caveat:** timers, automations, subagents, memory review and context compaction all forge a
synthetic `Request` and call `app.state.CHAT_COMPLETION_HANDLER` directly. Policy that lives in HTTP
middleware will not run for them.
