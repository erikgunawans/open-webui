# PROGRESS — ent-os-new-jup

## Checkpoint 2026-09-18 (evening) — @jup/ui built in ~/ent-os-ui

**Handoff item 1 (four design-system decisions) — answered.** `@jup/ui` private · GSM 2023 brand ·
`~/ent-os-ui` sibling repo · primitives only in v1.

**Handoff item 2 — reframed before building.** Two JUP React systems already existed and were
already design-synced: `~/NEW-JUP/jup-design-system` (`@jup/design-system`, 13 governance
components, registered `projectId`) and the `jup-design` skill (24 brand primitives + `_ds_bundle.js`
format 4). Building a fresh design system would have duplicated them. Erik chose option B: a new
`@jup/ui` consuming the existing brand identity, holding only what those two lack.

**Built — `~/ent-os-ui`, 2 commits, gates green:**
- Token layer: GSM identity isolated in `src/tokens/identity.css` (the one file with raw hex), a
  semantic layer, and a real dark theme (the GSM has none — only an inverse print scope).
- 20 primitives + `JupUIProvider`: Button, IconButton, Field, Input, Textarea, Select, Checkbox,
  Switch, Badge, Tag, Card, Avatar, Skeleton, Spinner, Alert, Dialog, Tooltip, ToastProvider, Tabs,
  DropdownMenu.
- 20 story files / 97 stories, Storybook 8 with a light/dark toolbar.
- `bun run check` = typecheck (strict) → tsup build → conventions validation.
- `.design-sync/{config.json,conventions.md}`, shape `package`.

**Accessibility defect found and fixed — verified in real Chrome, not assumed.** White on Pigment
Green is **3.23:1**, failing AA for normal text; the source system ships that on its primary button.
Fixed by moving the label to Rich Black (5.67:1) with the identity surface untouched. Needed three
tokens, not one: `--jup-text-on-brand` (Rich Black, green), `--jup-text-on-alt` (white, blue — Rich
Black on Polynesian Blue is 2.11:1), `--jup-text-on-danger` (flips per theme, because `--jup-danger`
lightens in dark and a white label sat at 2.42:1). All 6 button variants × 2 themes and all solid
badges now measure ≥ 4.5:1 against their real painted background.

**Also corrected a claim I had written myself:** `#00A550` on `#011627` is 5.67:1 and *does* clear
AA. The dark-mode brand lift is for small-text headroom, not an AA failure. README and
`semantic.css` fixed.

**Verification notes.** `bunx serve` strips `.html` and the query string (clean-URL rewriting), so
Storybook story ids never arrive and every story reads "No Preview" — use `storybook dev`, not a
static serve, for Interceptor checks. The conventions validator was proven to fail on an injected
bad token and a bad component name before being trusted.

**Open for Erik:** which token layer is canonical — GSM `#00A550`/Space Grotesk (what `@jup/ui`
uses) or `~/jup/brand` `#079F4E`/IBM Plex Sans (what `@jup/design-system` uses). Both self-describe
as canonical. Reversing is a one-file edit in `src/tokens/identity.css`.

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
