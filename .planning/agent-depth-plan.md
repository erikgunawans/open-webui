# Plan — close the agent-depth gap with holaOS by enhancing Asisten JUP, and add ChatGPT Live voice

Status: **Direction approved by Erik 2026-09-23: enhance Asisten JUP as the main path; the Hermes runtime is parked.** Each deploy and each DB write still needs his per-change OK.

Continues `.planning/agentic-capabilities-plan.md`: its Phases 0–4 are live, and its Phase 5 is
carried here as A1.

`/agent-depth` prints the ledger below. **Keep the table's shape**, because
`scripts/agent-depth.ts` parses it. Status is one of `live`, `in-progress`, `ready`, `blocked`,
`planned` or `parked`.

## Why enhance rather than adopt Hermes (decided 2026-09-23)

With Hermes the agent loop lives outside our system, so we would govern its model calls and stay
blind to its tool calls, memory writes and self-written skills. Running it safely would take eight
conditions: one instance per user, all model calls through our funnel, disposable containers,
an egress allowlist, no secrets on the box, reviewed skills, tool-call audit and a pinned version.
That is a second agent platform to secure.

Open WebUI already ships, or has a native slot for, most of what Hermes offers. What it lacks we
build here, inside the funnel, the contract, the audit trail, per-user RBAC and multi-user by
design. The sandbox work for terminal and browser is needed on either path.

## Phase ledger

| ID  | Phase                                                   | Status  | Closes the gap on                  | Waits on                                     |
| --- | ------------------------------------------------------- | ------- | ---------------------------------- | -------------------------------------------- |
| P0  | Governance holes closed                                 | live    | the precondition for everything    | —                                            |
| P1  | JUP Strategy KB (RAG, pgvector)                         | live    | knowledge / memory recall          | —                                            |
| P2  | Skills: 3 JUP + 16 ported holaOS                        | live    | skills                             | —                                            |
| P3  | `portfolio_status` tool                                 | live    | domain tools                       | —                                            |
| P4  | Memory on for staff, review off                         | live    | memory                             | —                                            |
| A1  | Automations: weekly portfolio digest                    | live    | cron                               | first run Mon 2026-09-28 09:00 WIB to verify |
| A2  | Subagents + timers (Open WebUI native)                  | live    | delegation                         | —                                            |
| A3  | Code interpreter for staff (Pyodide, in-browser)        | live    | code execution                     | —                                            |
| E1  | Tool-call audit: one audit line per tool invocation     | live    | the audit trail for every tool     | —                                            |
| A4  | Web search (Brave, D19); URL fetch stays gated          | live    | web search                         | —                                            |
| A5  | MCP tool servers                                        | live    | MCP                                | —                                            |
| V1  | Voice boundary on the server (ADR-0017)                 | in-progress | voice (holaOS has none)        | live 00055 for Erik; #31 acceptance call     |
| V2  | Voice call UI, disclosure and voice chats               | in-progress | voice                          | live (greeting + pantun); #31 acceptance     |
| V3  | Voice speaks with Google Chirp3-HD Kore (D23)           | live    | voice                              | live 00057; #32 closes with the #31 call     |
| V4  | GPT-Live as an opt-in call mode (ADR-0018, D24)         | in-progress | voice                              | UI live 00058, Erik granted; #38 first call  |
| E2  | Sandbox host: private VM, gVisor containers, egress proxy | parked  | the fence for E3 and E4            | Erik deferred 2026-09-26; reopens it         |
| E3  | Terminal via Open Terminal in the sandbox, admin-only   | planned | terminal, files                    | E1, E2, E5                                   |
| E4  | Browser automation via Playwright MCP in the sandbox    | planned | browser                            | A5, E2, E5                                   |
| E5  | Approval step for risky tool calls (ADR-0013)           | live    | long autonomous runs               | —                                            |
| E6  | Skill proposals: agent drafts, admin approves, sync     | planned | self-improving skills              | E1                                           |
| E7  | Messaging gateway (Telegram first, then WhatsApp)       | planned | chat channels                      | ADR-0012 amendment, D-decision per channel   |
| I1  | Integrations via MCP (Notion first)                     | planned | integrations                       | A5, E5 live, D-decision each (D20)           |
| X1  | Hermes as an admin-only lab runtime                     | parked  | runtime experiments                | Erik reopens it                              |

## Where the gap is (holaOS `a6b58be` vs Asisten JUP `254da9640`)

| Capability   | holaOS                                                            | Asisten JUP today                        | Closed by  |
| ------------ | ----------------------------------------------------------------- | ---------------------------------------- | ---------- |
| Agent loop   | 3 runtimes: pi (in-process), Claude Code, Codex; all auto-approve | 1: the model's native tool loop          | E1–E6      |
| Tools        | 96 built-in (files, bash, 33 browser, cron, apps, media)          | builtins (KB, memory, chats, notes) + 1  | A2–A5, E3, E4 |
| Integrations | 89 via Composio, proxied through `api.holaboss.ai`                | none                                     | A5, I1     |
| Channels     | 8 (Telegram, Slack, Discord, Feishu, DingTalk, QQ, WeCom, WeChat) | web only                                 | E7         |
| Voice        | **none**                                                          | none (ADR-0005/0006 decided, no code)    | V1–V2      |
| Cron         | 60 s cron worker, workflow graph                                  | automations exist, none configured       | A1         |
| Subagents    | `delegate_task` family                                            | native, off                              | A2         |
| Web search   | Holaboss search + Exa                                             | Brave, per-chat toggle (D19)             | A4         |
| Self-improving skills | the agent writes its own                                 | admin-managed only                       | E6 (reviewed) |
| Governance   | none: bypassed approvals, no sandbox, no audit                    | funnel + contract + audit + deny-default | keep it    |

We do not copy holaOS's governance posture. Every phase keeps ADR-0002: **each model turn passes
`generate_chat_completion`, carries the contract and writes an audit line**, and from E1 on each
tool call writes one too. A capability that can't meet that isn't turned on.

## Track A — Open WebUI capability we already ship (cheap, config-only)

- **A1 Automations.** A weekly portfolio digest to Erik, admin-only. Runs go through the funnel
  with no task name, and each run creates a chat. Verify with the first run's chat and audit line.
  Timing retest passed 2026-09-24: the one-off `fc3e9381` fired at 22:00:22Z (05:00 WIB) on a
  throttled instance (request-based CPU, `minScale=1`) with zero requests from 20:01:42Z to 22:10Z;
  run `success`, `portfolio_status` ok. No `--no-cpu-throttling` needed. Test deleted; digest
  `c516815a-1dfb-4d5a-ad7d-3b8e23618eaf` created, owned by Erik, next runs 09:00:43 WIB on Mondays.
- **A2 Subagents + timers.** Turn on `subagents.enable` with background off first, `max_concurrent`
  2 and `max_iterations` at its default. Traced 2026-09-23: subagents and timers call back into the
  governed `CHAT_COMPLETION_HANDLER`. Verify with one delegated task producing an audit line per
  subagent turn.
- **A3 Code interpreter.** Pyodide runs in the user's browser, so there is no server exec and no
  egress. Grant `features.code_interpreter` to staff. The Jupyter engine stays off.
- **A4 Web search.** Decided 2026-09-26 as D19: Brave Search API, queries only, a per-chat
  toggle off by default for staff. Check Brave's retention terms before creating the key.
  `fetch_url` stays behind `chat.web_upload`, which Phase 0 enforced, until E2's proxy exists.
  **Live 2026-09-26:** chat `2bd91910…` on `ent-os-00042-w6f` logged `tool_call search_web ok`
  between two `admitted` turns (contract attached), and the answer cited 3 web sources.
- **A5 MCP.** Native in Open WebUI (`tool_server.connections`). Tool calls are not model traffic,
  but they are egress. D20 (2026-09-26) is a standing rule: JUP-hosted, read-only servers with no
  outbound calls are pre-approved and the first server must be one; every third-party server needs
  its own D-decision and waits for E5.
  **Grilled 2026-09-26 (Erik accepted all four recommendations):** (1) the first server's purpose
  is the plumbing, proving the MCP path and ADR-0013's classes on the harmless case, not new data;
  (2) it serves the decisions register (the D-rows in `~/jup/DECISIONS.md`); (3) E5 ships in full
  with it, as ordered tickets: classes and refuse-by-default first, then the approval card, proven
  with a test-only `external` tool; (4) it runs inside the ent-os container as a second process on
  localhost, and moves out when a server of a different trust level arrives.
  **Round 2 (accepted):** correction first: `DECISIONS.md` is already in the Strategy KB
  (`sync-kb.ts:70-82`), so the server adds exact, status-true lookup, not new reach; kept anyway
  for the plumbing. (5) admin only: no access grants on the connection, which Open WebUI already
  enforces; (6) it serves the Decisions and the open-items table, reversed or superseded rows as
  written with their status; (7) two tools, `search_decisions(query)` and `get_decision(id)`;
  (8) a permanent admin-only `gate_probe` tool, classed `external`, that only echoes, proves the
  approval card live and stays as a regression check; (10) the decisions register stays the first
  server; (11) it reads `/srv/jup/DECISIONS.md`, added to the read-only GCS mount by
  `sync-records.sh`, with no database access. Engineering defaults, not decisions: streamable HTTP
  bound to 127.0.0.1 and started in `start.sh`; MCP audit lines get `tool_id=mcp:<server_id>`.
  **Round 3 (accepted):** `search_web` is `read` by named exception; every vendor built-in gets an
  explicit class in the spec's table and an unlisted one is `external`; note writes, calendar writes
  and image generation are `external`, automation management is `write_own`. Recorded as the
  2026-09-26 amendment to ADR-0013. Spec: issue #17, tickets #18–#24.
  **Live 2026-09-27 (A5 and E5, #24):** all five of spec #17's live checks passed on
  `ent-os-00050-gqw` (image `a945e5765`), each backed by its `jup.governance` line. `gate_probe`
  paused on a card labelled Panggilan Eksternal with `password=••••••` and `token ••••••`; approve
  → `approved`, approved_by Erik, 16.6 s; reject → `rejected`, 3.0 s; tab closed → `timed_out`,
  approved_by None, 601 s. An inactive automation on a temp model → `rejected_unattended`.
  "apa isi D20?" → `decisions_get_decision`, `tool_id mcp:decisions`, `not_required`. Web search →
  `builtin:search_web ok`, `not_required`, no card; the same turn's `fetch_url` got a card as
  intended. KB search (`query_knowledge_files`, `search_knowledge_files`, `view_knowledge_file`)
  → `not_required`, no card. Test model, automation and chats deleted.

## Track V — voice (ADR-0017, ADR-0006)

**Redesigned 2026-09-27 (V1 grilling, Erik accepted every recommendation):** ADR-0017 supersedes
ADR-0005. GPT-Live paraphrases what we hand it and decides for itself when to delegate, so voice is
a chained pipeline instead: OpenAI `gpt-4o-transcribe` → the normal governed chat turn in a chat
marked `voice` → OpenAI `gpt-4o-mini-tts` reading our stored answer by message id. Everything heard
is the governed answer, word for word. Spec: issue #25.

- **V1 Server boundary.**
  - Flag `JUP_VOICE_ENABLED` and a per-user grant; Erik only at first.
  - A start-call route checks flag, grant (`jup.voice.call`; the vendor `chat.call` is UI-only and
    defaults on) and the disclosure acknowledgement, and alone creates voice chats.
  - Every turn in a voice chat runs on "Asisten JUP — Suara": the named document set (ADR-0006) as
    file-level knowledge, tools limited to scoped KB retrieval and `portfolio_status`,
    `view_knowledge_file` unable to reach files outside the set.
  - OpenAI TTS by message id from the user's own voice chat only; OpenAI STT refused without the
    grant; read-aloud elsewhere falls back to the browser's voice.
  - Audit lines `voice_ack`, `voice_stt`, `voice_tts` (sizes, never content).
- **V2 Call UI.**
  - The disclosure (Indonesian first): OpenAI processes speech in the US and may keep it up to 30
    days; the words also pass through OpenRouter/Xiaomi (D17); voice answers only from the named
    documents; whatever is *said* is sent regardless. Acknowledged once (`voice_ack`), one line on
    every call.
  - The vendor call overlay starts calls through the start-call route and plays TTS by message id.
  - Each call is a normal chat, marked as voice.
- **Named voice document set (dated 2026-09-27, named by Erik):** `kb/strategy`, `kb/gas`,
  `kb/portfolio`, `kb/rued`, `kb/governance`, `kb/faq`, `records/projects/gas-spbg-reactivation`,
  `records/gate-assessments/gas-spbg-reactivation-g1`. Out: `kb/partners`, the SKK Migas/PGN
  engagement record, `DECISIONS.md`, `records/README`.
- **Key in place 2026-09-27:** Secret Manager `openai-live-key` (jup-ops, v1), accepted by OpenAI
  (`/v1/models` 200). Not yet wired into `deploy.sh` or readable by the app; used only for
  transcription and speech (ADR-0017).
- **Decided:** D16 (2026-09-19) accepts US processing; D21 (2026-09-26, Erik's final answer)
  removes ZDR as a precondition, so OpenAI's default retention of up to 30 days applies until ZDR
  is approved on the org. People briefed by voice must be told both facts.
- **Your steps:** pick the TTS voice from 3 Indonesian samples; a US$20 monthly budget limit with a
  50% alert on the key's OpenAI project.

## Track E — enhance the Asisten JUP harness

- **E1 Tool-call audit.** Today the audit trail has a line per model turn, not per tool call.
  Add one `jup.governance` line per tool invocation: user, chat, tool id, outcome, and argument
  size rather than argument content. It comes first because every later tool is only as
  accountable as this line. Verify by running `portfolio_status` and a KB tool and finding one
  line each in Cloud Logging.
- **E2 Sandbox host.** A private VM in `asia-southeast2` on the `default` VPC. ent-os already has
  Direct VPC egress there and can reach it on a private IP. Workloads run in gVisor (`runsc`)
  containers, one per session and deleted after it. All outbound traffic goes through an
  allowlist proxy, and nothing on the box holds secrets or JUP records. Cloud Run cannot host this:
  it has no container runtime for per-session sandboxes.
- **E3 Terminal.** Open WebUI already drives an external **Open Terminal** server: our backend
  proxies `routers/terminals.py`, and the tools come from its OpenAPI spec (traced 2026-09-23).
  Host Open Terminal inside E2 and attach it admin-only (`terminal_server.connections`). Each
  command runs inside the model's governed tool loop and gets an E1 audit line.
- **E4 Browser.** A Playwright MCP server in E2, attached through A5. Browsing reaches only what
  the egress proxy allows.
- **E5 Approvals.** Tools marked risky (terminal writes, browser form submits, anything outbound)
  pause for the user's explicit confirmation before they run. The decision is recorded in the E1
  audit line. Decided 2026-09-24 in ADR-0013: three risk classes (`read`, `write_own`, `external`),
  unclassified means `external`, the asking user approves each call, 10-minute timeout, and every
  unattended path (automations, subagents, channels) fails closed. Shipped with A5: live
  2026-09-27 on `ent-os-00050-gqw` (evidence under A5).
- **E6 Skill proposals.** A `propose_skill` tool lets the agent draft a skill from a repeated
  task into a review queue. An admin approves it into `skills/`, and `sync-skills.ts` publishes it.
  This is the self-improvement Hermes has, with a human gate that Hermes lacks.
- **E7 Messaging gateway.** A thin service for Telegram first, then WhatsApp. It maps a verified
  account to one JUP user and calls our pipeline as that user, so every channel turn is governed
  and audited like typed chat. It needs one machine identity: an ADR-0012 amendment, decided
  before code. Each channel is new egress, so each needs a D-decision.

## Parked — Hermes Agent (X1)

Researched 2026-09-23: NousResearch/hermes-agent, MIT, v0.21.4. It is single-tenant by design,
needs one writer on a persistent disk, and skips its dangerous-command checks inside containers.
Parked by Erik's decision. If reopened, it is an admin-only lab runtime on its own VM, never
touching staff or records, and its model calls go through our funnel with no fallbacks.

## Decisions Erik owns, in the order they unblock work

1. **A5, V1:** decided 2026-09-26 (D20, D21); A4 (D19) is live. What remains is a per-change OK for
   each key, config write and deploy.
2. **V2:** the named voice set was named 2026-09-27 (8 files, Track V); each addition is dated and
   named. Also the TTS voice and the OpenAI budget limit.
3. **E2:** deferred 2026-09-26; a VM budget when Erik reopens it. E3 and E4 wait on it.
4. **E7:** the ADR-0012 amendment for one machine identity.
5. **E7/I1:** one D-decision per new egress (channel, integration); third-party MCP only after E5 (D20).
