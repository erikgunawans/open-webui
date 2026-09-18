# PROGRESS — ent-os-new-jup

## Checkpoint 2026-09-19 (latest) — #3 closed: the portfolio tracer bullet, end to end

- **Session:** `/next` → #3, then the two deploy items the previous handoff left with Erik.
- **Branch:** main · **Commit:** `3795e1318`
- **Tracker: 2/8 closed.** #1 (spec) and #4–#8 remain open, all `ready-for-agent`.

### Done — #3, a project and its Current Gate from file to page

- **`backend/jup/portfolio.py`** — the projection. A pure function over a directory: no server, no
  database, no network, no global state. Current Gate is derived on every read as the highest gate
  holding a passing assessment (ADR-0003); it is stored nowhere and no setter exists. A later
  refusal does not revoke an earlier pass.
- **Placed OUTSIDE `open_webui/` deliberately.** `open_webui/__init__.py` imports typer and uvicorn,
  so under `--only-group dev` *nothing* in that package is importable. A sibling top-level package
  plus `pythonpath = ["backend"]` makes `jup` importable with no runtime tree, and
  `sources = ["backend"]` already ships it in the wheel. ADR-0007's rebase never has to merge it.
- **Vendor edit is two lines** — an import and an `include_router` in `main.py`. Nothing else.
- **`backend/open_webui/routers/jup_portfolio.py`** — one read-only `GET /api/v1/portfolio/` behind
  `get_verified_user`, reading `JUP_RECORDS_DIR` from the environment (documented in `.env.example`).
  A `RecordError` becomes a loud 500 naming the file rather than a confident blank.
- **`src/routes/(app)/portfolio/+page.svelte`** + `src/lib/apis/portfolio/` + a ported token layer at
  `src/lib/styles/jup-brand.css`. Three states render distinctly: a Current Gate badge, "No gate
  passed" (assessed and refused), "No assessment" (never assessed). A G1–G4 ladder makes the
  derivation visible rather than asserted.
- **Tokens ported, not imported** — the canonical `~/jup/brand` file keys dark off
  `prefers-color-scheme`, but this app switches on a `.dark` class (`darkMode: 'class'`), so
  following the OS would hand a light-OS/dark-workspace user the wrong palette.

### Verified, not asserted

- **37 passing in 0.09s** — 33 new tests over 19 fixture scenarios, external behaviour only. Still
  sub-second, so nothing imports the runtime tree.
- **Mutation-checked**: making a later refusal revoke an earlier pass fails 3 tests; dropping
  refusals at load fails 8. Both rules are genuinely pinned.
- **Real Chrome against running vite + uvicorn** (not a static serve): all three states rendered from
  markdown on disk, `200` on the projection call, zero uncaught errors. Unauthenticated the endpoint
  returns `401`, and the **live OpenAPI schema exposes `GET` and nothing else** — no write surface.
- **All eight rendered text-on-fill pairs pass WCAG AA, worst 4.90:1**, measured from
  `getComputedStyle` in both themes. The canonical accents would have failed as words at 3.05:1 and
  4.02:1, which is why the `-text` variants exist.

### Cost and friction worth not rediscovering

- **The disk hit 100% (1.0 GB free of 460 GB)** and killed `uv sync` mid-extract. Cleared the npm and
  bun download caches (~15.6 GB) with Erik's approval. `~/.cache/uv` is still 21 GB and is locked by
  his running MCP servers; `~/Library/Caches` is 11 GB. Both prunable later.
- **First backend boot downloads `all-MiniLM-L6-v2`** — ~1.1 GB, minutes, before uvicorn binds.
  Unrelated to this work but it gates every Chrome verification.
- **Forge ran as Claude-family, not cross-vendor.** `codex exec` rejected every model: `gpt-5.4` is
  unsupported on a ChatGPT account and `gpt-6-astra` (what `~/.codex/config.toml` pins) needs Codex
  ≥0.155.1 against an installed 0.139.0. The blind-spot diversity that justifies calling Forge did
  not happen, so its output was reviewed by the same family that wrote it.
- **Interceptor cannot screenshot here.** The DOM render times out at 15s and the OS capture grabs a
  different Chrome window (`macos windows` returns `[]`, so the driven tab cannot be raised).
  Computed-style probes were substituted; the missing-pixel gap is recorded on the ticket.

### Cross-repo — both of the previous handoff's open items are now CLOSED

- **Hostinger SSH restored by Erik**, verified: shell, sftp and the JUP path all resolve. **D16
  deployed** (per-change authorization given): remote backup `~/backups/JUP-2026-09-18-214414.tar.gz`,
  `DECISIONS.md` 11 948 → 14 689 bytes. `/JUP/` and `/JUP/DECISIONS.md` both `401` unauthenticated,
  auth files untouched, **D15 isolation re-proven** (`new-jup:x` → `401` on `/JUP/COO/`).
- **Cloudflare Worker redeployed by Erik.** Two corrections to what the last handoff claimed:
  **`partners.md` was never pending on Hostinger** — there is no `kb/` on the server and never has
  been, so the Strategy KB reaches production *only* through the Worker bundle; and the real problem
  was that **`build_kb_bundle.py` had been lost**, which is why the deployed assistant drifted two
  months while the repo looked correct — retired partner wording plus a decision log missing **half
  its rows** (7 501 of 14 551 chars; D14, D15, D16 all absent). Replaced with
  `~/jup-kb-assistant-worker/build-kb-bundle.ts` (`--check` exits 1 when stale). Recorded in
  `~/jup/CLAUDE.md`, commit `ee9b959`, pushed to `origin` and `mirror`.

### Next

1. **#4** — evidence detail and fail-closed parse refusals. The frontier.
2. **#8** — boot baseline; small, unblocked, guards the alembic two-heads failure.
3. Then #5 and #6 (parallel), then #7.

## Checkpoint 2026-09-19 (late) — first product code: the backend test harness (#2)

- **Session:** `/next` → `/implement` on #2, one ticket, closed and green in CI.
- **Branch:** main · **Commit:** `5cbcea364`
- **Done — #2 closed, the first test suite in this fork:**
  - **`uv run --only-group dev pytest`** — 4 passed. Verified from a deleted `.venv` on **3.11 and
    3.12 locally**, and both again in GitHub Actions.
  - **`--only-group dev` omits the project itself**, so the suite runs in ~13s without installing
    chromadb, transformers or sentence-transformers. A later ticket that must `import open_webui`
    drops the flag and pays for the full tree. Both forms documented in `AGENTS.md`.
  - **Tests live in `tests/` (plural) at the repo root, outside `backend/`** — ADR-0007's quarterly
    rebase must never have to merge them. `test/` (singular) is already the vendor tree's own
    (it holds `sd-empty.pt` for image gen) and was left untouched.
  - Fixture home is `tests/fixtures/`, reached through `fixtures_dir` / `fixture_path` in
    `tests/conftest.py`, which raises `FileNotFoundError` rather than returning a dead path.
  - `pytest>=8.4.0` added to `[dependency-groups] dev`; `uv.lock` updated; `[tool.pytest.ini_options]`
    added to `pyproject.toml`.
- **Decision — `asyncio_mode = "auto"`, not strict.** Under strict an unmarked `async def` is a
  silent hazard, and every later ticket exercises async FastAPI paths. **The guard was proven, not
  assumed:** forcing `-o asyncio_mode=strict` makes `test_async_tests_run_without_a_marker` fail
  outright with "async def functions are not natively supported".
- **Beyond the ACs, deliberately:** a `pytest` job added to the existing
  `.github/workflows/backend.yaml` (path filter extended to `tests/**`), matrix 3.11/3.12, both
  green — a harness nothing runs decays. Also corrected one stale line in `AGENTS.md` that still
  claimed `CONTEXT.md` and `docs/adr/` did not exist yet.
- **Vendor tree untouched:** zero files under `backend/` changed. The `pyproject.toml` edits are
  dependency and test configuration only, which AC 5 permits.
- **Files changed:** 7 (`tests/` ×3 new, `pyproject.toml`, `uv.lock`, `AGENTS.md`, the workflow).
- **Tests:** 4 passing — **the baseline now exists**, where before there were none.
- **Next:** #3 (tracer bullet). #8 is now unblocked — it was waiting on #2 only.
- **Still blocked on Erik:** Hostinger SSH (holding two committed-but-not-live deploys), Cloudflare
  Worker redeploy.


## Checkpoint 2026-09-19 — the build is specified; 15 decisions, 10 ADRs, 7 tickets

- **Session:** `/grill-with-docs` → `/to-spec` → `/to-tickets`, in one unbroken window.
- **Branch:** main
- **Done:**
  - **15 decisions settled** over four grilling rounds. The root one: ent-os is **PT JUP's internal
    operating layer**, not a product with JUP as customer zero — `governance.md` already commissions
    it (PMO, HSE, KPI visibility, audited partner SLAs).
  - `CONTEXT.md` created — 9 terms drawn from JUP's own governance language, glossary only.
  - **10 ADRs.** Seat ceiling as a licence constraint · fail-closed attaches at `utils/chat.py:151`
    with every rejected extension point evidenced · gate assessments not gate status · records
    git-backed in `~/jup` · GPT-Live client delegation · US processing under ZDR · quarterly upstream
    rebase · Engagement as a first-class entity · no likelihood field · no external seats.
  - **Spec #1 + tickets #2–#8** published, all `ready-for-agent`, blocking edges pointing at real
    issue numbers.
  - **Investigation result that changed a plan:** `EVENT_SINKS` are observers, not gates — return
    values discarded, exceptions swallowed, fired after the mutation. The prior standing
    recommendation to build governance on them was right about cost, wrong about capability.
  - **Fifth enterprise hole found:** `routers/openai.py:1464` / `routers/ollama.py:1091` sit behind
    only `get_verified_user`; a user API key bypasses the pipeline entirely.
  - **In `~/jup`:** D16 added (voice / US processing under ZDR, bounded by a named document set),
    `kb/partners.md` migrated to the Engagement Stage ladder, and the dead SSH deploy path recorded.
  - Erik appointed **Director of Operation and Business Development**, full decision authority.
- **Files changed:** 12 in this repo (CONTEXT.md, 10 ADRs, handoff) + 3 in `~/jup`.
- **Tests:** still none — #2 establishes the first backend suite, which is where the baseline belongs.
- **Next:** `/implement` on #2. Blocked on Erik: Hostinger SSH, which is holding two deploys.

## Checkpoint 2026-09-18 (evening) — @jup/ui built in ~/ent-os-ui

**Handoff item 1 (four design-system decisions) — answered.** `@jup/ui` private ·
`~/ent-os-ui` sibling repo · primitives only in v1 · brand initially GSM 2023, then **reversed to
`~/jup/brand` on Erik's ratification later the same session** (see the token section below).

**Handoff item 2 — reframed before building.** Two JUP React systems already existed and were
already design-synced: `~/NEW-JUP/jup-design-system` (`@jup/design-system`, 13 governance
components, registered `projectId`) and the `jup-design` skill (24 brand primitives + `_ds_bundle.js`
format 4). Building a fresh design system would have duplicated them. Erik chose option B: a new
`@jup/ui` consuming the existing brand identity, holding only what those two lack.

**Built — `~/ent-os-ui`, 3 commits, gates green:**
- Token layer: identity isolated in `src/tokens/identity.css`, a semantic layer on top, and a
  dark theme.
- 20 primitives + `JupUIProvider`: Button, IconButton, Field, Input, Textarea, Select, Checkbox,
  Switch, Badge, Tag, Card, Avatar, Skeleton, Spinner, Alert, Dialog, Tooltip, ToastProvider, Tabs,
  DropdownMenu.
- 20 story files / 97 stories, Storybook 8 with a light/dark toolbar.
- `bun run check` = typecheck (strict) → tsup build → conventions validation → **token drift gate**.
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

**Canonical token ratification — the second half of the session.** Erik chose `~/jup/brand`
(`#079F4E`, IBM Plex Sans) over the GSM 2023 palette. `@jup/ui` was re-based onto it:

- `identity.css` is now a **vendored copy** of `~/jup/brand/tokens/colors.css`, gated by a new
  `validate:tokens` script diffing all **42 light / 36 dark** canonical tokens and failing on drift.
  Vendored not imported, because `@jup/design-system` is unpublished and design-sync needs a
  self-contained `dist/`. The gate was proven to fail by reverting `--jup-brand` to `#00A550`.
- **The swap was wider than billed.** My "one-file edit" claim held for hex values and font names
  only — the GSM system is square and flat, JUP 2.0 is rounded (16px panels, 8px controls) and
  elevated, so `radius.css`, `elevation.css`, every component radius and the conventions
  house-style moved too. **Brand character is not just colour.**
- **Three real bugs surfaced:** `--jup-shadow-lg: var(--jup-shadow-lg)` was a circular reference
  (CSS resolves that to guaranteed-invalid — the large shadow silently vanished); the dark
  `--jup-text-inverse` override made the inverse button's label and surface the same colour
  (1.00:1, invisible); the font stack had dropped two canonical fallbacks.
- **Contrast redone, not ported** — the canonical palette behaves oppositely. Fill and text are now
  separate tokens per hue (canonical accents fail as *text* on their own tinted bg at 2.65–4.60:1);
  `--jup-text-brand` resolves to `brand-deep` because `#079F4E` as text on paper is 3.20:1;
  `--jup-text-on-{brand,alt,danger,warning}` are per-hue and per-theme; small helper text moved off
  `--jup-text-muted` (4.15:1, large-text only) to `--jup-text-secondary` (7.48:1).
- Swept **9 stories × 2 themes in real Chrome: zero failures.** The one flagged item is a disabled
  tab at 2.74:1, reported as exempt under WCAG 1.4.3 rather than silently passed.

**RESOLVED same session:** Erik ratified `~/jup/brand` (`#079F4E`, IBM Plex Sans). `@jup/ui` was
re-based onto it — identity vendored + drift-gated, contrast reworked for the new palette, three real
bugs caught in the process (a circular `--jup-shadow-lg` that silently killed the large shadow, a
dark inverse button at 1.00:1 with label and surface the same colour, and a dropped font fallback).
Swept 9 stories × 2 themes in real Chrome: zero failures.

**Framing correction — Erik pushed back, correctly.** I described the project as having "zero
product code" and prior work as "scaffolding," and recommended a from-scratch product grilling.
Erik challenged it: the fork already has Open WebUI's full capability. He was right, and the
architecture briefs are design work, not survey work — they name the governance chokepoints with
file:line.

The accurate statement is much narrower: **nothing yet says who pays, for what, instead of running
stock Open WebUI free.** And the thesis is already in our own notes — stock Open WebUI is
enterprise-*capable* but not enterprise-*deployable*:

- Audit redaction is **one regex** (`audit.py:285`); `REQUEST_RESPONSE` captures response bodies
  **verbatim**. Full audit builds a PII repository, not a compliance control.
- `workspace.tools` = unsandboxed `exec()` + `pip install` from user frontmatter. Only kill switch
  is `ENABLE_PLUGINS=false`.
- Every frontend guard is a client-side `goto('/')`.
- Timers, automations, subagents and context compaction bypass HTTP middleware entirely — governance
  must live in the pipeline. This is a genuine moat: a competitor bolting policy onto middleware
  ships something that silently misses those paths.

Already present and cheap to build on: `publish_event`/`EVENTS` with `EVENT_SINKS` taking a sink
class, and `merge_usage` (`response.py:100`) aggregating per-user/per-group tokens for chargeback.

Erik deferred the grilling to next session. It is scoped to three questions — which hole ships
first, who signs, and what beats "just use Azure AI Foundry / Bedrock" — not a blank page. Carried
into the handoff with an explicit warning not to reopen with the rejected framing.

**`~/ent-os-ui` remote — found missing and fixed during the wrap.** The three commits existed only
on this machine; the session's entire deliverable was unbacked. Erik authorised it and it is now
private at `github.com/erikgunawans/ent-os-ui`, all 3 commits pushed, remote SHA verified against
local HEAD. Worth noting for next time: a repo created with `git init` mid-session has no remote,
and nothing warns you — check for one before ending any session that created a repo.

**Superseded — was open for Erik:** which token layer is canonical — GSM `#00A550`/Space Grotesk (what `@jup/ui`
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
