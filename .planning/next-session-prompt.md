# Next session — ent-os-new-jup (checkpoint 2026-09-18b)

> Prepended by /wrap 2026-09-18 (checkpoint 2026-09-18b). Supersedes checkpoint 2026-09-18's anchor.

Resume ent-os-new-jup — read PROGRESS.md first (top checkpoint 2026-09-18 evening).

**Anchor:** `origin/main` at `a901bd4db` **as this was written**, or one commit ahead at this
checkpoint's own wrap commit (subject: `chore(session): checkpoint — @jup/ui rebased on canonical
JUP tokens`). Verify with `git log --oneline -1 origin/main`; a single commit of drift whose subject
names this checkpoint is EXPECTED, not drift to investigate. More than that, or a different subject,
means someone else pushed — investigate before writing.

**Current state:** `ent-os-new-jup` is still a pristine Open WebUI v0.11.3 fork with **zero product
code** — documentation commits only. The design system is DONE and lives in a separate repo,
`~/ent-os-ui` (`@jup/ui`, 3 commits, 20 primitives + provider, 97 stories, all gates green). Brand
is the ratified `~/jup/brand` layer (`#079F4E`, IBM Plex Sans), vendored and drift-gated. No test
baseline exists for either repo.

**Do next, in order:**
1. **⚠️ `~/ent-os-ui` HAS NO GIT REMOTE — three commits exist only on this machine.** Ask Erik to
   authorise a private GitHub repo (the pattern is `erikgunawans/<name>`, matching
   `erikgunawans/ent-os-new-jup`), then `git remote add origin` and push. Until this is done the
   entire design system is unbacked. **Do this first; it is a data-loss risk, not a chore.**
2. **There is still no product spec.** Three sessions have produced a fork, 17 architecture briefs
   and a design system — all scaffolding. Run `/grill-with-docs` here to settle which governance
   capability ships first, for which buyer, and what the smallest paid slice looks like. Keep it in
   ONE unbroken context window through `/to-spec` → `/to-tickets`. Escalate to `/wayfinder` only if
   you cannot name a first shippable slice by the end of the interview.
3. **Minimal boot baseline** for ent-os-new-jup — scope it narrow: does the app boot, and does
   alembic have exactly one head. A comprehensive suite over a pristine fork tests Open WebUI's
   code, not ours; the real suite should land WITH the first product code.
4. `@jup/ui` v2 chat composites (`ChatMessage`, `MessageInput`, `Sidebar`, `ModelSelector`) — they
   carry more brand signal than the primitives, but they are better designed once a spec says what
   screens exist. Do not start these before item 2.

**Constraints to honor:**
- **Three JUP component systems now exist.** Search `~/NEW-JUP/jup-design-system`,
  `~/.claude/skills/synced/*/jup-design` and `~/ent-os-ui` before building any JUP UI. Building a
  fourth is the default mistake — it nearly happened this session.
- **`~/jup/brand/tokens/colors.css` is the ratified canonical palette.** The `jup-design` skill
  still ships the REJECTED GSM 2023 palette (`#00A550`, Space Grotesk) — do not copy tokens out of
  it. In `@jup/ui`, re-vendor on change; never patch `identity.css` by hand.
- **Canonical accents are tuned as fills and fail AA as text.** Use the `-text` variants for words.
  Full numbers in `.design-sync/conventions.md` and the `jup-canonical-palette-contrast-traps`
  memory.
- `/design-sync` cannot target ent-os-new-jup — React-only converter, 662 Svelte files. Read
  `.design-sync/NOTES.md`; the check is already done, do not redo it.
- **Verify web work with Interceptor against `storybook dev`, never `bunx serve`** — serve strips
  `.html` and the query string, so every story reads "No Preview" and looks like a broken config.
- **zsh does not word-split unquoted variables.** `for s in $STORIES` iterates ONCE with the whole
  string. Use an inline list or an array.
- `gh` targets **upstream** unless `gh repo set-default` is pinned. Pass `--repo` explicitly.
- Never push to `upstream`. `origin` is the private working repo; `fork` is the legacy one.
- A fork alembic revision colliding with an upstream one gives **two heads and the app will not
  boot** — migrations run at `config.py` import time. Trust `down_revision`, never the docstring.
- Commits go directly to `main` — private single-maintainer repo, PRs are explicitly not a triage
  surface (`docs/agents/issue-tracker.md`). No PR is expected for a wrap here.

**Open items waiting on me (the user):**
- **Authorise the `~/ent-os-ui` GitHub remote** (item 1). Blocking, and a data-loss risk.
- **Decide the product's first shippable slice** — item 2 needs your answers; the grilling cannot
  invent a buyer.

---

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
