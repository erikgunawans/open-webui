# PROGRESS — ent-os-new-jup

> Newest checkpoint first. Append-only history; never delete entries.

## Current state

| | |
|---|---|
| **What this is** | A fork of [Open WebUI](https://github.com/open-webui/open-webui) v0.11.3, intended as the base for an enterprise AI product (JUP / Axiara) |
| **Our code** | **None yet.** One commit, and it adds only docs — no product code has been written |
| **Branch** | `main` |
| **Vendor baseline** | `0a7c158` (upstream/main at 0.11.3) |
| **Remotes** | `origin` → `erikgunawans/ent-os-new-jup` (private) · `fork` → `erikgunawans/open-webui` · `upstream` → `open-webui/open-webui` |
| **Tests** | Not run this session — no baseline recorded yet |

**Read first:** `docs/architecture/README.md` — the vendor codebase in 17 briefs, and the five things
that matter most before touching anything.

## What to do next

1. **Decide the four open questions in `docs/design-system/PLAN.md`** — package name/scope, whether to
   keep Open WebUI's `blue-500` accent or move to a JUP/Axiara brand color, repo location, and whether
   composites ship in v1. These block phase 1 and are Erik's calls.
2. **Build the React design system** in a new repo, per that plan. It is the agreed next task.
3. **Establish a test baseline** for this repo before any product code lands, so regressions against
   the vendor tree are detectable.

---

## Checkpoint 2026-09-18 (Repo setup, full codebase read, design-system spec)

- **Session:** Three pieces of work: configured the engineering skills for this repo, read the entire
  vendor codebase, and determined that `/design-sync` cannot target it — producing a token spec and
  build plan for the React design system that can.
- **Branch:** `main`
- **Done:**
  - Created the private GitHub repo `erikgunawans/ent-os-new-jup`, rewired remotes (`origin` → new
    repo, old fork → `fork`, `upstream` unchanged), pushed `main`. Pinned `gh repo set-default` —
    without it `gh` silently targets **upstream**, which it did on the first label-create attempt.
  - Wrote `AGENTS.md` and `docs/agents/{issue-tracker,triage-labels,domain}.md`. Created all five
    canonical triage labels on the repo.
  - **Read all 348,002 lines** of the vendor tree (1,017 source files) in full via 16 parallel agents;
    distilled to `docs/architecture/` — 17 briefs plus an index.
  - Established that `HEAD` is **byte-identical to `upstream/main`** — zero divergence from vendor.
  - Determined `/design-sync` is structurally inapplicable: the converter is React-only and this tree
    is 662 Svelte files with no React. Recorded in `.design-sync/NOTES.md`.
  - Extracted the real design language to `docs/design-system/TOKENS.md` and wrote
    `docs/design-system/PLAN.md` for a React DS that the sync *can* consume.
- **Files changed:** 21 added (`AGENTS.md`, 17 × `docs/architecture/`, 2 × `docs/design-system/`,
  3 × `docs/agents/`, `.design-sync/NOTES.md`, `.planning/next-session-prompt.md`) — all documentation,
  no source changes.
- **Tests:** Not run. No baseline exists yet for this fork.
- **Next:** Answer the four open design-system decisions, then build the React DS in a new repo.

### Findings worth carrying forward

- **Migrations run at `config.py` import time.** A fork revision colliding with an upstream one gives
  alembic two heads and **the app will not boot at all**. `d4e5f6a7b8c9`'s docstring already
  contradicts its own `down_revision` from a past hand-fix — trust `down_revision`, never the docstring.
- **`workspace.tools` permission is effectively "grant admin"** — `exec()` of user Python in the server
  process, no sandbox, plus `pip install` from frontmatter. `ENABLE_PLUGINS=false` is the only switch.
- **Every frontend guard is client-side only**; the backend must re-assert everything.
- **Timers, automations, subagents, memory review and context compaction bypass HTTP middleware** —
  they forge a `Request` and call `CHAT_COMPLETION_HANDLER` directly. Governance must live in the
  pipeline, not in front of it.
- **`publish_event` / `EVENT_SINKS` is the cleanest audit/SIEM seam** — already called on nearly every
  mutation, so a sink class needs no router changes.
