# Next session — start here

## State as of 2026-09-18

**Repo:** `ent-os-new-jup` = a pristine fork of Open WebUI v0.11.3 at `0a7c158`.
`HEAD` is byte-identical to `upstream/main` — **zero lines of our own code yet.**

**Remotes:** `origin` → `erikgunawans/ent-os-new-jup` (private, created this session, `main` pushed) ·
`fork` → `erikgunawans/open-webui` · `upstream` → `open-webui/open-webui`.
`gh repo set-default` is pinned — without it `gh` targets **upstream**. See `docs/agents/issue-tracker.md`.

## What exists now

- `AGENTS.md` + `docs/agents/{issue-tracker,triage-labels,domain}.md` — engineering-skill config.
  GitHub Issues, five canonical triage labels (all created on the repo), single-context domain docs.
- `docs/architecture/` — **17 files, ~2,400 lines.** All 348,002 lines of the vendor codebase read in
  full by 16 parallel agents. Start at `docs/architecture/README.md`; it has the index and the five
  things that matter most.
- `docs/design-system/{TOKENS.md,PLAN.md}` — design tokens extracted from source, and the plan for a
  React design system.
- `.design-sync/NOTES.md` — why `/design-sync` cannot run against this repo.
- `docs/adr/` — empty, `.gitkeep` only. `CONTEXT.md` does not exist yet; both fill in lazily.

## The agreed next task

**Build a React + Tailwind design system mirroring this product's visual language, so `/design-sync`
can feed Claude Design real on-brand components.** Full plan in `docs/design-system/PLAN.md`.

It is a **new repo** — `/design-sync` is React-only and this tree is 662 Svelte files. Read
`.design-sync/NOTES.md` before revisiting that, so the check isn't redone.

**Open decisions — ask Erik before phase 1:**
1. Package name and scope (`@axiara/ui`? `@jup/ui`?), public or private.
2. Match Open WebUI's `blue-500` accent exactly, or shift to a JUP/Axiara brand color? Changes phase 2.
3. Repo location — sibling directory, or elsewhere.
4. Composites (phase 4) in v1, or primitives only?

## Things that will bite

- **Migrations run at `config.py` import time.** A fork revision colliding with an upstream one gives
  alembic two heads and **the app will not boot**. `d4e5f6a7b8c9`'s docstring already contradicts its
  own `down_revision` from a past hand-fix — trust `down_revision`, never the docstring.
- `workspace.tools` permission = **RCE on the server** by design (`exec()`, no sandbox).
- Every frontend guard is **client-side only**; the backend must re-assert everything.
- Timers, automations, subagents, memory review and context compaction **bypass HTTP middleware** —
  they forge a `Request` and call `CHAT_COMPLETION_HANDLER` directly. Governance must live in the
  pipeline, not in front of it.
- Open WebUI's LICENSE constrains rebranding of marked identifiers. Check before touching logos/names.
