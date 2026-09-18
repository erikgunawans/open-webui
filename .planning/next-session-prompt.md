# Next session — ent-os-new-jup (checkpoint 2026-09-18)

> Prepended by /wrap 2026-09-18. First checkpoint — supersedes nothing.

Resume ent-os-new-jup — read PROGRESS.md first (top checkpoint 2026-09-18).

**Anchor:** `origin/main` at `9adb133` **as this was written**, or one commit ahead at this
checkpoint's own wrap commit (subject: `chore(session): checkpoint — repo setup, codebase read,
design-system spec`). Verify with `git log --oneline -1 origin/main`; a single commit of drift whose
subject names this checkpoint is EXPECTED, not drift to investigate. More than that, or a different
subject, is real drift — investigate before writing.

**Current state:** A pristine fork of Open WebUI v0.11.3 at `0a7c158` with **zero product code
written** — the only non-vendor commits are documentation. `docs/architecture/` holds 17 briefs
covering all 348,002 lines of the vendor tree, read in full. No test baseline exists for this fork.

**Do next, in order:**
1. **Get Erik's answers to the four open design-system decisions** in `docs/design-system/PLAN.md`:
   package name/scope (`@axiara/ui`? `@jup/ui`?), keep Open WebUI's `blue-500` accent or move to a
   JUP/Axiara brand color, repo location, and whether composites ship in v1. These block phase 1.
2. **Build the React + Tailwind design system** in a NEW repo per that plan, using
   `docs/design-system/TOKENS.md` verbatim for phase 2. Do NOT attempt this inside ent-os-new-jup.
3. **Establish a test baseline** for this repo before any product code lands.

**Constraints to honor:**
- `/design-sync` cannot target this repo — the converter is React-only, this tree is 662 Svelte files
  with no React. Read `.design-sync/NOTES.md` before re-testing that; the check is already done.
- `gh` targets **upstream** unless `gh repo set-default` is pinned to `erikgunawans/ent-os-new-jup`.
  Pass `--repo` explicitly in any scripted command.
- Never push to `upstream`. `origin` is the private working repo; `fork` is the legacy open-webui fork.
- A fork alembic revision that collides with an upstream one gives **two heads and the app will not
  boot** — migrations run at `config.py` import time. Trust `down_revision`, never the docstring.
- Open WebUI's LICENSE constrains rebranding of marked identifiers (logo, name, notification strings).
- Commits go directly to `main` — this is a private single-maintainer repo and PRs are explicitly not
  a triage surface (`docs/agents/issue-tracker.md`).

**Open items waiting on Erik:** the four design-system decisions in item 1 above — nothing else is
blocked on him.

---

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
