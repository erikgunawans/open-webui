# Plan — turn on Open WebUI's agentic capabilities (checkpoint 2026-09-23-brand, item 1)

Status: **APPROVED by Erik 2026-09-23.** His decisions:
- **Knowledge base content:** `kb/` **and records**. See the D17-scope note in Phase 1.
- **Memory:** kept on for staff, with background review off.
- **"JUP Staff" membership:** not yet named.

## Progress
- **Phase 0 is live.** It shipped as `990c26c39` on revision `ent-os-00018-6g2`. Checks on the live app:
  - `/openai/responses` returns 403.
  - The Ollama `/v1/chat/completions` and `/api/generate` routes return 403.
  - Each refusal writes a `refused` audit line.
  - Normal chat is still `admitted` with the contract attached.
  - The 0e baseline was written and read back. The before-values are in `.planning/0e-before-values-2026-09-23.json`.
- **Phase 1 is live.**
  - `deploy/gcp/sync-kb.ts` (`07a784f95`) loaded 12 files from `~/jup` `1e1d4b6` into "JUP Strategy KB" (`82f7d2f7-d7f4-4042-968a-64cbc958b98c`). Grants are empty, so it is admin only. `--check` shows 12 unmodified.
  - The knowledge base is attached to Asisten JUP through `meta.knowledge`. The model's before-value is in `.planning/phase1-model-before-2026-09-23.json`.
  - Live test: asking the SKK Migas stage question returned "Contacted" with 4 sources, `partners.md`, `gas.md` and both records.
  - The audit log shows two `admitted`/`attached` turns (the question and the continuation after the tool call) and no query-generation call, because native mode skips that exempt call.
- **The Phase 3 precondition is met.** MiMo on OpenRouter returned a correct native `tool_calls` entry.

Correction found during execution: `ollama.enable` is DB-seeded, so the deploy.sh env var only seeds a fresh DB. The live switch belongs in the 0e DB write.

How to read the tables:
- **Traffic** says whether the capability's model traffic goes through `generate_chat_completion`, where the contract, audit and fail-closed guard (ADR-0002) apply.
- **Change** says where the switch lives. **DB** is a config write on prod and needs Erik's OK for each change, with the before-value recorded. **deploy** is an env var in `deploy/gcp/deploy.sh` plus a deploy.
- Every claim was traced in code on 2026-09-23. File:line references are kept in the session transcript.

## Phase 0 — Close the gaps first (before any capability, and before any non-admin grant)

Today these gaps are masked because non-admins can't see any model. **The first read grant on "Asisten JUP" makes all of them live.**

| # | Gap (verified) | Fix | Change |
|---|---|---|---|
| 0a | `POST /openai/responses` (`routers/openai.py:1853`) forwards straight to OpenRouter `/responses` with no governance guard; its only check is model access. | Apply the same `refuse_if_ungoverned` insert used at `:1473`. Test that an ungoverned `/responses` call returns 403. | code + deploy |
| 0b | The Ollama routes `/api/generate`, `/v1/completions`, `/v1/chat/completions`, `/v1/messages` and `/v1/responses` are unguarded. There's no Ollama backend today, but `ENABLE_OLLAMA_API` defaults to True. | Set `ENABLE_OLLAMA_API=False` in deploy.sh. Also guard those routes so the gap stays closed even if Ollama is ever re-enabled. | deploy (+ code) |
| 0c | `POST /api/v1/tasks/moa/completions` gives any verified user an **exempt** completion with their own `prompt`/`responses` (`tasks.py:608-655`). The rule that only funnel-stamped turns are exempt doesn't help, because the stamp is added inside that same funnel. | Remove `moa_response_generation` from `EXEMPT_TASKS`, so the contract attaches and the turn is governed. MoA is unused here. `queries`, `image_prompt` and `auto` wrap user text in a server template, so the risk is lower; record them as accepted. | code + deploy |
| 0d | `POST /api/v1/retrieval/process/web` fetches any URL for any verified user, with no feature flag and no permission check (`retrieval.py:2361`). | Require `web.search.enable`, or admin, at the head of the route. | code (vendor patch) + deploy |
| 0e | The defaults leave a latent capability surface for users: `features.code_interpreter`, `web_search`, `image_generation`, `memories`, `notes`, `calendar`, `channels`, and `chat.stt`/`tts`/`call` are all **True**. | Write `user.permissions` once as a deny-by-default baseline. Each later phase turns on only what it needs. | DB |
| 0f | Tools run arbitrary Python on the server (`exec`, `utils/plugin.py:241`), and saving a tool can `pip install`. | Set `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False`. Keep `workspace.tools*` False, so only admins author tools. | deploy |
| 0g | At boot, `RAG_EMBEDDING_MODEL_AUTO_UPDATE` calls HuggingFace even though MiniLM is baked into the image. | Set `RAG_EMBEDDING_MODEL_AUTO_UPDATE=False` so there's no egress at boot. | deploy |
| 0h | ADR-0002 names only two guarded routes. | Amend it with the full route list above, plus the MoA decision. | doc |

This is one commit for the code items (0a–0d, each with a pytest), one deploy.sh commit (0b, 0f, 0g), and one DB write (0e). The DB write needs its own OK.

Then the **access model** (Erik): a "JUP Staff" group, and a read grant on "Asisten JUP" to that group, not to `*`. The group size counts against the 50-seat ceiling (ADR-0001).

## Phase 1 — Knowledge bases / RAG (most value)

| | |
|---|---|
| Does | Makes `~/jup` kb and records answerable from chat, with citations. |
| Traffic | **Governed.** RAG context is added before the funnel, and the contract is appended to the system message after it. Retrieval query generation is **exempt** (`task=query_generation`), so recent messages go to MiMo without the contract. That is the same provider as D17, so there is no new egress. |
| Data | Vectors go to pgvector `document_chunk` in the existing Cloud SQL, raw files to the existing GCS bucket, and embeddings are computed locally with MiniLM in-process. **No new egress, so no new D-decision**, provided 0g is done. |
| Who | Admins curate the knowledge base (`workspace.knowledge` stays False). Staff get a read grant on the KB, and the KB is attached to the "Asisten JUP" model. |
| Change | DB: the KB itself plus the model's `knowledge` and `builtinTools` meta. Code: a `sync-kb` step next to `sync-records.sh` that pushes the generated `kb/` (ADR-0011) through the knowledge API, so it can't drift from records. |
| Verify live | Ask a question only the kb can answer, and check the cited source chip. Check that the audit line reads `admitted`/`attached` for that turn. |
| Open question for Erik | Which content goes in: `kb/` only, or records too? Records contain engagement data that is currently admin-only (ADR-0010 disclosure). |

## Phase 2 — Skills (cheap, zero egress)

| | |
|---|---|
| Does | Prompt-only markdown loaded into the system message, or pulled on demand through `view_skill`. No code execution. |
| Traffic | **Governed.** It is added before the funnel. |
| Data | None new. |
| Who | Admins author skills (`workspace.skills*` stays False). Staff get read grants. |
| Change | DB: skill rows and grants. Candidate skills: gate-assessment walkthrough, tier discipline (D11 revenue-not-margin), Indonesian briefing format. |
| Verify live | Mention `<$skill>` in chat and check that the answer follows it and the audit line is admitted. |

## Phase 3 — Tools / native function calling

| | |
|---|---|
| Does | The model calls tools in a loop. `function_calling` defaults to `native`. |
| Traffic | **Governed**, every loop turn, re-entering at `middleware.py:5994`. Legacy mode's selection call is exempt (`function_calling`), so keep native. **Caveat:** tool code is server-side Python and can bypass the funnel, so the governance boundary is **who authors tools**, which is admin only. |
| Data | Whatever each tool calls. Each tool that reaches outside needs its own egress D-decision. |
| Who | Admins author tools, and each tool gets its own grants. Turn on `ENABLE_TOOL_PERMISSIONS` (DB `chat.tool_permissions.enable`) so calls need approval. |
| Precondition | Confirm live that MiMo via OpenRouter supports native tool calls. If it doesn't, this phase and Phase 1's built-in KB tools fall back to plain RAG injection. |
| Verify live | Run one read-only JUP tool (e.g. a portfolio lookup) and check that each loop turn has an audit line. |

## Phase 4 — Memory (privacy decision, not engineering)

It is already **on for admins** by default (`memories.enable=True`, injected into the system message). Background review is off.
- **Traffic:** memory injection has no model call. Background review, if turned on, is governed (`memory_review` is not exempt).
- **Data:** the `memory` table plus pgvector `user-memory-{id}`, in Cloud SQL, with no egress.
- **Erik decides:** keep it for staff, or turn `features.memories` off (DB). My recommendation is to keep it on, keep review off, and state it in the staff onboarding note.

## Phase 5 — Automations (scheduled runs)

- **Traffic:** **Governed.** Runs go through `CHAT_COMPLETION_HANDLER` into the funnel, with no task name set.
- **Data:** the `automation`/`automation_run` tables, and each run creates a chat.
- **Who:** already on globally, and `features.automations` is False for users, so it is admin only.
- **Candidate:** a weekly portfolio digest to Erik.
- **Verify:** the first run's chat and audit line.

## Keep off, or defer (each needs a decision it doesn't yet have)

| Capability | Why it waits |
|---|---|
| **Web search** | Needs an engine choice, which is a new egress D-decision, because queries leave for Tavily, Brave, etc. The query-generation call is exempt. After 0d it can be switched on cleanly. |
| **MCP servers** | None exist yet. Each server is remote egress from Cloud Run and needs its own D-decision plus `access_grants`. Revisit once there's a concrete server, for example exposing the jup-kb worker. |
| **Image generation** | **The image call bypasses the funnel entirely**: it posts straight to `/images/generations`. Enabling it needs a new governance attach point and an ADR-0002 amendment. Low value for JUP. |
| **Channels** | Governed, but it adds a public token-only webhook endpoint. There's no point with fewer than two users. |
| **Subagents** | Governed and never exempt. Low value until tools and KB exist. Could follow Phase 3. |
| **Terminals** | Keep off. It's arbitrary command execution on a remote server. |
| **Voice** | ADR-0005/0006 are decided, but **no code exists**. That's a separate build, not a configuration change. Default STT is local whisper. Browser STT sends audio to the browser vendor, and `chat.call` is enforced only in the UI. |
| **Code interpreter** | pyodide runs in the user's browser and its turns are governed. It's currently on for everyone; the 0e baseline decides whether staff keep it. |
| **Notes / calendar** | No ungoverned model path. Note that `notes.enable` isn't enforced in the notes router, only `features.notes`. Fine to leave on for admins. |

## Execution order once approved

Phase 0 (code, then deploy, then the 0e DB write, then the access group) → 1 → 2 → 3 → 4 decision → 5. That is one capability per commit and deploy, each verified live on `ops.axiara.ai` via Interceptor with host-guarded evals and audit-line evidence.
