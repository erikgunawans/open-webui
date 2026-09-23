# Plan — close the agent-depth gap with holaOS, add ChatGPT Live voice and a Hermes runtime

Status: **DRAFT, awaiting Erik's approval (2026-09-23).** Nothing here is executed until he approves
it. Each deploy and each DB write still needs his per-change OK.

Supersedes nothing. It continues `.planning/agentic-capabilities-plan.md`: Phases 0–4 there are
live, and its Phase 5 is carried into this ledger as A1.

`/agent-depth` prints the ledger below. **Keep the table's shape**, because
`scripts/agent-depth.ts` parses it. Status is one of `live`, `in-progress`, `ready`, `blocked` or
`planned`.

## Phase ledger

| ID  | Phase                                                | Status  | Closes the gap on                        | Waits on                                     |
| --- | ---------------------------------------------------- | ------- | ---------------------------------------- | -------------------------------------------- |
| P0  | Governance holes closed                              | live    | the precondition for everything below    | —                                            |
| P1  | JUP Strategy KB (RAG, pgvector)                      | live    | knowledge / memory recall                | —                                            |
| P2  | Skills: 3 JUP + 16 ported holaOS                     | live    | skills                                   | —                                            |
| P3  | `portfolio_status` tool                              | live    | domain tools                             | —                                            |
| P4  | Memory on for staff, review off                      | live    | memory                                   | —                                            |
| A1  | Automations: weekly portfolio digest                 | ready   | cron                                     | Erik: day/time and per-change OK             |
| A2  | Subagents + timers (Open WebUI native)               | ready   | delegation (`delegate_task`)             | Erik: per-change OK (DB config)              |
| A3  | Code interpreter for staff (Pyodide, in-browser)     | ready   | code execution                           | Erik: per-change OK (DB permission)          |
| A4  | Web search + URL fetch                               | blocked | web search                               | D-decision: search engine and egress         |
| A5  | MCP tool servers                                     | blocked | MCP, integrations                        | D-decision per server: what it reaches       |
| V1  | ChatGPT Live voice — backend delegation endpoint     | blocked | voice (holaOS has none)                  | JUP D-decision on US processing (ADR-0006)   |
| V2  | ChatGPT Live voice — call UI and voice KB scope      | planned | voice                                    | V1                                           |
| H1  | Hermes host: private GCE VM, single writer           | blocked | agent runtime #2                         | Erik: GCE cost OK, D-decision on runtime     |
| H2  | Hermes' LLM calls routed through our funnel          | planned | governance of runtime #2                 | ADR-0012 amendment: a machine identity       |
| H3  | Hermes exposed as an admin-only model in the chat    | planned | agent runtime #2                         | H1, H2                                       |
| H4  | Hermes tools: sandboxed terminal, files, browser     | planned | terminal, browser, files                 | H3, egress allowlist                         |
| H5  | Hermes messaging gateway (Telegram / WhatsApp)       | planned | chat channels                            | H3, D-decision per channel                   |
| H6  | Hermes for staff: one profile per user               | planned | multi-user runtime                       | H4, "JUP Staff" group named                  |
| I1  | Integrations via MCP (Google Workspace first)        | planned | integrations                             | A5, D-decision per integration               |

## Where the gap is (holaOS `a6b58be` vs Asisten JUP `254da9640`)

| Capability     | holaOS                                                     | Asisten JUP today                         | Closed by      |
| -------------- | ---------------------------------------------------------- | ----------------------------------------- | -------------- |
| Runtimes       | 3: pi (in-process), Claude Code, Codex; all auto-approve   | 1: the model's native tool loop           | H1–H4          |
| Tools          | 96 built-in (files, bash, 33 browser, cron, apps, media)   | builtins (KB, memory, chats, notes) + 1   | A2–A5, H4      |
| Integrations   | 89 via Composio, proxied through `api.holaboss.ai`         | none                                      | A5, I1         |
| Channels       | 8 (Telegram, Slack, Discord, Feishu, DingTalk, QQ, WeCom, WeChat) | web only                           | H5             |
| Voice          | **none**                                                   | none (ADR-0005/0006 decided, no code)     | V1–V2          |
| Cron           | 60 s cron worker, workflow graph                           | automations exist, none configured        | A1, Hermes cron |
| Subagents      | `delegate_task` family                                     | native, off                               | A2             |
| Web search     | Holaboss search + Exa                                      | off                                       | A4             |
| Governance     | none: bypassed approvals, no sandbox, no audit             | funnel + contract + audit + deny-default  | keep it        |

We do not copy holaOS's governance posture. Every phase below keeps ADR-0002: **each model turn
passes `generate_chat_completion`, carries the contract and writes an audit line.** A capability
that can't meet that isn't turned on.

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

## Track H — Hermes Agent as a second runtime

**What Hermes is (researched 2026-09-23).**
- NousResearch/hermes-agent, MIT, Python. v0.21.4 released 2026-09-21, with weekly releases and
  heavy churn.
- It has an optional OpenAI-compatible API server: `/v1/chat/completions`, `/v1/runs` with an
  approval endpoint, and `/api/jobs` for cron. The docs include an Open WebUI integration guide.
- Toolsets: terminal (local, docker, ssh, modal …), files, browser, cron, `delegate_task`, memory,
  self-written skills, an MCP client, and 30+ messaging adapters.
- **It is single-tenant by design.** Multi-user means one profile per user.
- It needs a persistent disk with exactly one writer (SQLite WAL). The docs say never to run two
  gateways on one data dir.

**Architecture.**

```
browser ──IAP──▶ ent-os (Cloud Run) ──funnel+contract+audit──▶ Hermes API (private GCE VM)
                     ▲                                               │
                     └──── every Hermes LLM call (custom provider) ◀─┘
                                 funnel+contract+audit ──▶ OpenRouter/MiMo
```

- **H1 Host.**
  - An `e2-standard-2`-class VM in `asia-southeast2`, private IP only, on the `default` VPC. ent-os
    already has Direct VPC egress there, so it can reach the VM.
  - A persistent disk for `/opt/data`, using the official `nousresearch/hermes-agent` image,
    version-pinned.
  - Cloud Run is **not** the host: it scales out, has no Docker daemon for sandboxed terminals, and
    cron needs an always-on process.
- **H2 Governed model routing.** This is the load-bearing part.
  - Hermes' `model.provider: custom` points at **our** OpenAI-compatible endpoint, never at OpenRouter.
  - Every auxiliary task is pinned to the same endpoint: compression, titles, vision, web
    summarisation, MoA and the approval classifier. There are no `fallback_providers` or
    `fallback_chain`s, so no call can leave by another road.
  - Our endpoint sits behind IAP, and ADR-0012 rejects any session whose user isn't the IAP
    identity. So Hermes needs **one scoped machine identity**: an internal-ingress path, a
    service-account-bound key, and nothing but `/api/chat/completions`. That's an ADR-0012
    amendment, decided before any code.
- **H3 Exposure.**
  - Hermes becomes an OpenAI-compatible connection in Open WebUI, shown as a model such as
    "Asisten JUP · Agen", with empty grants (admin-only).
  - The outer turn is governed at the funnel, and Hermes' inner turns are governed again by H2.
    Both write audit lines.
- **H4 Tools.**
  - The terminal uses the docker backend, one container per session, not persistent, with egress
    limited to an allowlist. Hermes skips its dangerous-command checks inside containers, so the
    container **is** the boundary.
  - `approvals.unattended_mode: deny` stays on. Off: `computer_use`, `homeassistant`, `image_gen`,
    `tts`, and the `model_catalog` fetch. Telemetry stays off (its default).
- **H5 Channels.** Telegram or WhatsApp through Hermes' gateway. This closes holaOS's channel gap.
  Each channel is new egress plus an identity-mapping problem, so it needs a D-decision per channel.
- **H6 Staff.** One Hermes profile per staff member (own key, own memory). This waits on the "JUP
  Staff" group and the 50-seat ceiling (ADR-0001).

**Open risks.**
- Heavy upstream churn: pin the version and upgrade deliberately.
- An open issue (#31346) where an SSE MCP server fails on Cloud Run. It doesn't bite on GCE.
- The client system message is layered on Hermes' own core prompt, not substituted for it. Our
  contract still arrives on every inner turn through H2, which is the guarantee that matters.

## Decisions Erik owns, in the order they unblock work

1. Approve this plan and its order (A → V → H).
2. **A1:** the digest's day and time (WIB).
3. **V:** the JUP decision on US processing of voice under ZDR, and the named voice KB set.
4. **H1:** a GCE VM budget for the Hermes host.
5. **H2:** the ADR-0012 amendment for one machine identity.
6. **A4/A5/H5/I1:** one D-decision per new egress: search engine, MCP server, channel, integration.
