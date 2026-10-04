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
| V1  | Voice boundary on the server (ADR-0017)                 | live    | voice (holaOS has none)            | closed by Erik 2026-10-01 (#31 call waived)  |
| V2  | Voice call UI, disclosure and voice chats               | live    | voice                              | closed by Erik 2026-10-01 (#31 call waived)  |
| V3  | Voice speaks with Google Chirp3-HD Kore (D23)           | live    | voice                              | live 00057; #32 closed 2026-10-01            |
| V4  | GPT-Live as an opt-in call mode (ADR-0018, D24)         | live        | voice                              | #38 closed 10-03: call 2, content fix 00073    |
| E2  | Sandbox host: private VM, gVisor containers, egress proxy | parked  | the fence for E3 and E4            | Erik deferred 2026-09-26; reopens it         |
| E3  | Terminal via Open Terminal in the sandbox, admin-only   | planned | terminal, files                    | E1, E2, E5                                   |
| E4  | Browser automation via Playwright MCP in the sandbox    | planned | browser                            | A5, E2, E5                                   |
| E5  | Approval step for risky tool calls (ADR-0013)           | live    | long autonomous runs               | —                                            |
| E6  | Skill proposals: agent drafts, admin approves, sync     | planned | self-improving skills              | E1                                           |
| E7  | Channel gateway core: one machine identity, channel user → JUP user | planned | chat channels           | ADR-0012 amendment accepted 10-04; order set 10-03: Teams, then WhatsApp |
| E8  | Microsoft Teams channel: Asisten JUP bot in JUP's tenant | planned | chat channels                      | E7; JUP IT registers the bot; D-decision     |
| E9  | WhatsApp channel: Business Cloud API, verified numbers   | planned | chat channels                      | E7, E8 proven; JUP business number; D-decision |
| I1  | Integrations via MCP (Notion first)                     | in-progress | integrations                   | live 00060, admin-only, off until #41 token |
| O1  | Office output: Word documents (.docx) in the JUP template | in-progress | docs (holaOS: `doc-coauthoring` skill + bash) | live 00060, all staff; staff-account check open |
| O2  | Office output: spreadsheets (.xlsx)                      | live    | sheets (holaOS: `xlsx` skill + bash) | live 00083 10-03; accepted: card 0003 → TERBATAS .xlsx; tool attached to Asisten JUP |
| O3  | Office output: slide decks (.pptx) in the JUP template   | live 10-03 (00086), awaiting Erik's acceptance | slides (holaOS: `pptx` skill + bash) | O2 (shared tool shape); copy Presentasi v1.5-r2 into the repo |
| O4  | Office preview panel: files open in the chat column, view-only | live    | in-app preview (holaOS: desktop preview) | live 00084 10-03; click + auto-open confirmed by Erik |
| X1  | Hermes as an admin-only lab runtime                     | parked  | runtime experiments                | Erik reopens it                              |

## Where the gap is (holaOS `a6b58be` vs Asisten JUP `254da9640`)

| Capability   | holaOS                                                            | Asisten JUP today                        | Closed by  |
| ------------ | ----------------------------------------------------------------- | ---------------------------------------- | ---------- |
| Agent loop   | 3 runtimes: pi (in-process), Claude Code, Codex; all auto-approve | 1: the model's native tool loop          | E1–E6      |
| Tools        | 96 built-in (files, bash, 33 browser, cron, apps, media)          | builtins (KB, memory, chats, notes) + 1  | A2–A5, E3, E4 |
| Integrations | 89 via Composio, proxied through `api.holaboss.ai`                | none                                     | A5, I1     |
| Channels     | 8 (Telegram, Slack, Discord, Feishu, DingTalk, QQ, WeCom, WeChat) | web only                                 | E7–E9      |
| Voice        | **none**                                                          | none (ADR-0005/0006 decided, no code)    | V1–V2      |
| Cron         | 60 s cron worker, workflow graph                                  | automations exist, none configured       | A1         |
| Subagents    | `delegate_task` family                                            | native, off                              | A2         |
| Web search   | Holaboss search + Exa                                             | Brave, per-chat toggle (D19)             | A4         |
| Self-improving skills | the agent writes its own                                 | admin-managed only                       | E6 (reviewed) |
| Office files | docx/pptx/xlsx via installable skills run in its shell; outputs/ + in-app preview | reads attachments only; A3 (Pyodide) has openpyxl in the browser | O1–O3 |
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
- **E7–E9 Channels (re-planned 2026-10-03 from the holaboss-ai comparison).** Directors will not
  open a web app for one question; they are in Teams and WhatsApp all day. holaboss-ai has eight
  channels, none of them JUP's, and maps no channel user to a company identity. That mapping is the
  hard part and the part we must get right. **Order decided by Erik 2026-10-03: Teams first, then
  WhatsApp; Telegram dropped** (JUP staff do not use it).
  - **E7 Gateway core.** A separate Cloud Run service, `jup-gateway`, in `asia-southeast2`. It is
    the only public, non-IAP endpoint, so it verifies every inbound request cryptographically (Bot
    Framework JWT for Teams, Meta's `X-Hub-Signature-256` for WhatsApp) and rejects anything else.
    It holds one machine identity that may call ent-os **on behalf of a mapped user only**: the
    ADR-0012 amendment. That identity may not act as itself, may not act as an unmapped user,
    and every turn it carries writes `channel=<teams|whatsapp>` and the channel user id hash in the
    audit line. Inside ent-os the turn takes the normal governed path: the funnel, the contract,
    tool-call audit, the caller's RBAC. Rules that apply to every channel:
    - **No mapping, no answer.** An unknown sender gets one fixed reply ("akun ini belum terhubung
      ke Asisten JUP") and is never forwarded to the model.
    - **Unattended means fail-closed (ADR-0013).** A tool of class `external` is refused in a
      channel turn with a pointer to the web app. A Teams Adaptive Card approval is a later step,
      not v1.
    - **One chat per channel conversation**, marked `channel` in the chat meta, visible in the web
      app's history, kept like any chat. A new chat after 8 hours of silence or on `baru` (#87).
    - **One turn in flight per conversation; later ones wait, in order** (#87). The lock is
      in-process, so it assumes one ent-os instance serves the conversation. Cloud Run keeps one
      warm but may scale to four (checked 2026-10-04); if turns split across instances start to
      matter, the lock moves to the database.
    - **Files and long answers link back** to `non-jupe.jup.co.id` (behind IAP). Nothing from a
      contract card or Daftar Perkara is pasted into a channel above what the caller may see, and
      TERBATAS content is replaced by a link, never sent as text (confirmed by Erik 2026-10-04).
    - **Answers are text only** in v1: no voice notes in, no audio out.
    - Kill switch `JUP_CHANNELS_ENABLED` plus a per-user grant `jup.channel.use`. Erik only at
      first, as with voice.
  - **E8 Teams.** Identity comes free: staff already sign in with their JUP Entra account
    (ADR-0016), and a Teams message carries the sender's Entra object id and tenant. The gateway
    accepts only JUP's tenant id, resolves the object id to the email through the same single-tenant
    app (Graph `User.ReadBasic.All`, JUP IT consent), and maps that email to the JUP user. There is
    no linking step for staff. Work: JUP IT registers an Azure Bot (single-tenant) and publishes the
    Teams app to JUP's org catalogue (see `deploy/gcp/entra-request-jup-it.md` for the pattern);
    1:1 chat only in v1, with no channel or group mentions. Bot Framework wants a quick 200, so the
    gateway acknowledges at once, shows typing, and posts the answer through the connector API. D-decision: Microsoft Bot
    Service relays message text (it is Microsoft-hosted, inside JUP's existing M365 contract).
    Verify: Erik asks "status proyek SPBG" in Teams → answer in Teams, one chat in his web history
    marked `channel`, audit lines `channel_turn`, `admitted`, the tool calls; a non-JUP-tenant
    message is rejected; a `gate_probe` call is refused with the web-app pointer.
  - **E9 WhatsApp.** WhatsApp Business Cloud API (Meta-hosted) on a JUP business number. There is
    no company identity in WhatsApp, so linking is explicit: in the web app, Settings → Akun → "Hubungkan
    WhatsApp", the user enters their number, the gateway sends a one-time code over WhatsApp, and
    the user types it back in the web app. Only then does the number map to that user; unlinking is
    one click and is audited. Meta's 24-hour service window means the assistant only replies, never
    starts a conversation (no template messages in v1). D-decision: message text passes through
    Meta (US processing), the same kind of disclosure as voice, acknowledged once at linking.
    Ships only after E8 has been proven in daily use, because it is the riskier egress.

## Track O — office output: documents, spreadsheets, slides (added 2026-09-29, Erik)

holaOS (`a6b58be`) has no generator of its own: its Doc/Sheet/Slides chips insert Anthropic's
`doc-coauthoring`, `xlsx` and `pptx` skills, whose Python/Node scripts run through its shell
tool, write to `outputs/` and preview in the desktop app. That needs a sandbox, which is E2
(parked). We do not need one: `python-docx`, `python-pptx` and `openpyxl` are already in our
backend image, so each format is a **native tool with a fixed renderer**. The model sends
structured content (headings, paragraphs, tables; sheets and rows; slides with title, bullets,
table), the renderer builds the file on the server in Jakarta, and it is saved as an app File
owned by the asking user and linked in the chat for download. No model-written code runs, so
there is no code sandbox to build and no new egress, hence no D-decision under D20.

- **O1 Documents.** `create_document` → .docx in the JUP template (GSM 2023 tokens, measured,
  memory `jup-two-canonical-token-layers`). Risk class `write_own` (it only creates a file in the
  caller's own space), E1 audit line with sizes, not content. Establishes the shared path: file
  record, owner, download link, size caps, filename rules. Verify: a generated memo opens in Word
  with the template's styles, its file belongs to the caller, and another user gets 404.
- **O2 Spreadsheets (plan 2026-10-03, ready).** Use cases: "export the contract list I can
  see to Excel", "RKA targets per unit as a sheet", the portfolio status table. Three tickets, the O1 shape:
  1. **Renderer `jup.office_sheet`** (pure, no I/O, like `office_doc.py`): input is
     `{title, classification, sheets: [{name, columns: [{header, type}], rows}]}`; types `text`,
     `number`, `idr`, `percent`, `date`. Numbers stay numbers (an IDR cell is a number formatted
     `"Rp" #,##0`, never a string), dates are real dates, header row bold and frozen, autofilter on,
     column widths from content. A cover sheet "Info" carries title, generator, Draf status,
     classification and the date (Asia/Jakarta). Space Grotesk and the brand tokens, since there is no
     Excel template. **No formulas in v1**: totals are computed by the renderer and written as
     values, so nothing the model writes is ever executed by Excel. Caps: 10 sheets, 5,000 rows,
     50 columns, 32 kB per cell; a cell starting with `=`, `+`, `-` or `@` is written as text
     (CSV/formula injection).
  2. **Tool `create_spreadsheet`** in `office_tool.py`, reusing O1's `_store`, file record, owner,
     download link and filename rules. Class `write_own`, E1 audit line with sizes. Classification
     follows O1's rule: never below the sources (contract money terms or Daftar Perkara → at least
     TERBATAS), enforced in code. Add it to Asisten JUP's tools; **not** to `VOICE_TOOL_IDS` (voice
     does not make files).
  3. **Deploy + grant all staff + live acceptance with Erik**: a contract-list export opens in
     Excel with number-typed amounts, it belongs to the caller, another user gets 404, and a staff
     account cannot export amounts its grant hides.
  Ad-hoc analysis stays in A3 (Pyodide, browser-side, already has openpyxl).
  **Built 2026-10-03:** `jup.office_sheet` + `create_spreadsheet` in the existing "JUP documents"
  tool (already on Asisten JUP and granted to all staff, so no new grant). **Also fixed O1:** the
  classification floor existed but nothing set it. Now `jup.office_floor` keeps a sticky
  `chat.meta.jup_restricted_source`: `get_contract` (when the reader holds `money`) and
  `read_contract_pages` raise it to TERBATAS, both file tools read it, and if either write or read
  fails the tool refuses. After deploy, `sync-tools.ts` must push `jup_documents` 1.1.0 and
  `jup_contracts` 1.1.0 (a DB write, Erik's OK).
- **O3 Slides (plan 2026-10-03).** Use cases: "make this RKA summary into 5 slides", a
  board-pack draft from Ruang Pimpinan, a project profile. Three tickets:
  1. **Template in the repo + renderer `jup.office_slides`.** Copy Presentasi v1.5-r2 (.pptx,
     2.4 MB) into `backend/jup/office_templates/pptx/` with a manifest of layouts 01–20 and their
     placeholder idx (read once with python-pptx and checked in, as for docx). The renderer fills
     placeholders by idx and never draws free-floating shapes, so every slide stays on the master. Input:
     `{title, classification, slides: [{layout, fields}]}`, with `layout` restricted to the 20
     working layouts. Charts (comparison, trend) use python-pptx's native chart data, so they stay
     editable in PowerPoint. Tables come from the same column/row shape as O2. Speaker notes are allowed. Caps: 30
     slides, text per placeholder trimmed to what the layout holds (overflow = a renderer error the
     model must fix, not a shrunken font). Classification and Draf status go in the master's
     footer fields.
  2. **Tool `create_presentation`**, same storage, class, audit and classification rule as O1/O2.
     It must also obey the leadership grants: a deck built from Ruang Pimpinan data only contains
     what `jup_leadership` returned to this caller.
  3. **Deploy + grant all staff + live acceptance with Erik**: the RKA summary deck opens in
     PowerPoint and Keynote on the JUP master, the charts can be edited, and the classification footer is right.
  **Known trap:** the RKA deck's own numbers disagree (GPM 11,3% vs 12,6%, CFO Rp7,81 M vs Rp9,73 M);
  a generated deck repeats whatever the source says, so the deck owner's fix should land first.
  **Built 2026-10-03 (tickets 1-2):** `jup.office_slides.render_slides` + `presentation_layouts` /
  `create_presentation` in the existing `jup_documents` tool (1.2.0; already granted to all staff, so
  no new grant). The model picks layouts by meaning (`agenda`, `kpi`, `bar_chart`, `decision`, …, 18
  plus two cover styles = layouts 01-20) and fills named fields; `manifest.json` maps them to
  placeholder idx. Found while building: the template writes `type="subtitle"` (OOXML says `subTitle`),
  corrected in memory so the checked-in file stays byte-identical; its sizes live on the prompt runs,
  not the list style, so they are copied; tables and charts are cloned from the template's own
  example slides (which are then dropped) but the example chart's fixed axis (0-150) is removed;
  each table layout draws a rule under each example row, so a table keeps that row height and is
  capped at the example's row count (4, or 3 for risks/actions). Text is measured against each box
  and refused when it would overflow (calibrated on LibreOffice renders). Not in `VOICE_TOOL_IDS`.
  Ticket 3 (deploy, `sync-tools` 1.2.0, live acceptance) needs Erik's OKs.
- **Erik's decisions (2026-09-29):** office output is for **all staff**; the templates are
  **JUP Template Dokumen 2.0** (17 Word templates, 17 Sept 2026) and **Presentasi v1.5-r2**, from
  `~/NEW-JUP/deliverables/JUP-Enterprise-Document-Templates-2026-09-17/` (zip of the whole set beside it).
  Copies go into the repo (DOCX ~1.8 MB + PPTX 2.4 MB; the DOTX/POTX duplicates and the PDF are not needed).
- **What the templates impose** (read 2026-09-29):
  - Word: A4, Space Grotesk 12 pt (Space Mono for code, OFL), standard style ids (`Heading1-9`,
    `ListBullet`, `ListNumber`, `TableGrid`, `Quote`, `Caption`), metadata and footer in 32
    content controls per template plus `[bracketed]` fields. O1 fills the metadata controls and
    replaces the body with the model's sections in those styles; header/footer stay the template's.
    The model picks one of the 17 types (memo keputusan, notulen, SOP, …); the catalogue
    `Daftar-Induk-Template.csv` gives each type's code, group and owner.
  - **Classification and status** (`Panduan-Klasifikasi-Dokumen-JUP.md`): PUBLIK / INTERNAL /
    TERBATAS / RAHASIA in the footer, default INTERNAL (both rules below confirmed by Erik
    2026-09-29). A generated file is always status **Draf**
    (the template says status follows proof of approval, which a model does not have); its
    classification is never below what its sources require: anything from contract cards with
    money terms or full text, or from Daftar Perkara, is at least TERBATAS. Enforced in code.
  - Slides: 30 layouts on 2 masters, every field a numbered placeholder with a custom prompt (chart
    placeholders included), so O3 fills by placeholder idx. O3 offers the working layouts 01–20
    (covers, agenda, executive summary, section, text, two columns, four KPI, comparison and trend
    charts, financial table, portfolio, project profile, schedule, process, risks, options,
    decision, follow-up, closing); 21–24 are brand-guide pages and 25–30 speaker/team pages, left out.
  - Spreadsheets: the set has no Excel template, so O2 uses the same fonts and the brand tokens.
- **Access:** all staff via a grant on the tools at go-live (a DB write, its own OK); the content
  still comes only from what the caller may see (contract/perkara access matrix).
- **O4 Preview panel (Erik 2026-10-03).** Clicking a .docx/.xlsx/.pptx in a chat opens it in the
  right-hand column (phone: the drawer) instead of a modal, with the file's Draf status and
  classification badges, sheet tabs and Download. A file the assistant just made opens by itself
  on a large screen. View-only (editing stays under "Later"). Reuses the vendor's renderers; loads
  through the owner-only content route, so access is unchanged. **Not done here:** the installed
  `xlsx` 0.18.5 has published advisories (prototype pollution, ReDoS) for hostile files; upgrading
  to SheetJS 0.20.x means regenerating `package-lock.json` with npm, which needs Erik's OK.
- **Later, not in O1–O3:** editing an uploaded file in place (read → new version), Google
  Docs/Sheets/Slides output (that is I1-style egress and needs its own D-decision).
- **Governance kept:** each call goes through the gate and the E1 audit; content comes only from
  the governed turn, so a contract/perkara answer that the access matrix hides cannot be written
  into a file either (the file is built from the answer the caller was allowed to see).

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
4. **E7–E9:** channel order decided 2026-10-03 (Teams, then WhatsApp; Telegram dropped). Decided
   2026-10-04: the ADR-0012 amendment (the gateway acts only on behalf of a mapped user) and
   TERBATAS-in-a-channel becomes a link. Still open: the JUP IT requests (Azure Bot + Teams app,
   Graph consent); a JUP WhatsApp business number.
5. **E7/I1:** one D-decision per new egress (channel, integration); third-party MCP only after E5 (D20).
6. **O1–O3:** decided 2026-09-29: all staff; JUP Template Dokumen 2.0 + Presentasi v1.5-r2.
   O2: go-ahead 2026-10-03, with no formulas in v1.
