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
| A1  | Automations: weekly portfolio digest                    | in-progress | cron                           | Mon 09:00 WIB; quiet-window timing retest    |
| A2  | Subagents + timers (Open WebUI native)                  | live    | delegation                         | —                                            |
| A3  | Code interpreter for staff (Pyodide, in-browser)        | live    | code execution                     | —                                            |
| E1  | Tool-call audit: one audit line per tool invocation     | live    | the audit trail for every tool     | —                                            |
| A4  | Web search + URL fetch                                  | blocked | web search                         | D-decision: search engine and egress         |
| A5  | MCP tool servers                                        | blocked | MCP                                | D-decision per server; E5 gate (ADR-0013)    |
| V1  | ChatGPT Live voice — backend delegation endpoint        | blocked | voice (holaOS has none)            | JUP D-decision on US processing (ADR-0006)   |
| V2  | ChatGPT Live voice — call UI and voice KB scope         | planned | voice                              | V1                                           |
| E2  | Sandbox host: private VM, gVisor containers, egress proxy | planned | the fence for E3 and E4          | Erik: VM budget                              |
| E3  | Terminal via Open Terminal in the sandbox, admin-only   | planned | terminal, files                    | E1, E2, E5                                   |
| E4  | Browser automation via Playwright MCP in the sandbox    | planned | browser                            | A5, E2, E5                                   |
| E5  | Approval step for risky tool calls (ADR-0013)           | ready   | long autonomous runs               | ships with first of E3/E4/A5                 |
| E6  | Skill proposals: agent drafts, admin approves, sync     | planned | self-improving skills              | E1                                           |
| E7  | Messaging gateway (Telegram first, then WhatsApp)       | planned | chat channels                      | ADR-0012 amendment, D-decision per channel   |
| I1  | Integrations via MCP (Google Workspace first)           | planned | integrations                       | A5, D-decision per integration               |
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
| Web search   | Holaboss search + Exa                                             | off                                      | A4         |
| Self-improving skills | the agent writes its own                                 | admin-managed only                       | E6 (reviewed) |
| Governance   | none: bypassed approvals, no sandbox, no audit                    | funnel + contract + audit + deny-default | keep it    |

We do not copy holaOS's governance posture. Every phase keeps ADR-0002: **each model turn passes
`generate_chat_completion`, carries the contract and writes an audit line**, and from E1 on each
tool call writes one too. A capability that can't meet that isn't turned on.

## Track A — Open WebUI capability we already ship (cheap, config-only)

- **A1 Automations.** A weekly portfolio digest to Erik, admin-only. Runs go through the funnel
  with no task name, and each run creates a chat. Verify with the first run's chat and audit line.
- **A2 Subagents + timers.** Turn on `subagents.enable` with background off first, `max_concurrent`
  2 and `max_iterations` at its default. Traced 2026-09-23: subagents and timers call back into the
  governed `CHAT_COMPLETION_HANDLER`. Verify with one delegated task producing an audit line per
  subagent turn.
- **A3 Code interpreter.** Pyodide runs in the user's browser, so there is no server exec and no
  egress. Grant `features.code_interpreter` to staff. The Jupyter engine stays off.
- **A4 Web search.** Needs a D-decision naming the engine and where queries go. `fetch_url` stays
  behind `chat.web_upload`, which Phase 0 enforced.
- **A5 MCP.** Native in Open WebUI (`tool_server.connections`). Tool calls are not model traffic,
  but they are egress, so each server needs a D-decision. The first candidate is internal only.

## Track V — ChatGPT Live as a voice interface (ADR-0005, ADR-0006)

Already decided, never built. GPT-Live runs in **client delegation** mode. The Live session only
hears and speaks. Every substantive turn is handed to our backend, which runs the same governed
pipeline as typed chat, and Live speaks the answer we return. That makes voice the more governable
surface, because we see the whole answer before a word is spoken.

- **V1 Backend.**
  - A server route mints a short-lived Live session. The OpenAI key stays server-side, on a ZDR
    organisation.
  - A delegation route takes the user's utterance and runs `generate_chat_completion` as that
    user. The audit record is built from these pipeline turns, not from Live's transcript.
  - Server-side enforcement of `chat.call`, which is UI-only today.
- **V2 UI and scope.**
  - A call mode in the chat that holds the floor with `session.thinking.append` while the pipeline
    runs.
  - Voice retrieval is limited **by construction** to a named Strategy KB subset (ADR-0006). Nothing
    outside that set can be reached.
- **Blocked on:** the JUP governance decision that voice material may be processed in the US under
  ZDR. It belongs in `~/jup/DECISIONS.md` (class of D13/D15), and ADR-0006 says it is not made there.
  We also need an OpenAI org with ZDR confirmed.
- **Verify at build time, not now:** the exact GPT-Live session and delegation API. The ADRs name
  `gpt-live-1`, `/v1/live/sessions` and `session.thinking.append`. Re-read OpenAI's docs before
  writing code.

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
  unattended path (automations, subagents, channels) fails closed. Ships with the first of E3/E4/A5.
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

1. **A1:** the digest's day and time (WIB).
2. **A2, A3, E1:** a per-change OK for each (a DB config write, a DB permission, a deploy).
3. **V:** the JUP decision on US processing of voice under ZDR, and the named voice KB set.
4. **E2:** a VM budget for the sandbox host.
5. **E7:** the ADR-0012 amendment for one machine identity.
6. **A4/A5/E7/I1:** one D-decision per new egress: search engine, MCP server, channel, integration.
