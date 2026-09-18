# Next session — ent-os-new-jup (checkpoint 2026-09-19-final)

> Prepended by /wrap 2026-09-19 (checkpoint 2026-09-19-final). Supersedes checkpoint
> 2026-09-19-late's anchor.

Resume ent-os-new-jup — read PROGRESS.md first (top checkpoint 2026-09-19 latest).

**Anchor:** `origin/main` at `3795e1318` **as this was written**, or one commit ahead at this
checkpoint's own wrap commit (subject begins `chore(session):`). Verify with
`git log --oneline 3795e1318..origin/main`. A single `chore(session):` commit is EXPECTED — that is
this wrap writing itself down. Any commit in that range whose subject does NOT start
`chore(session):` means a parallel session pushed: real drift, investigate before writing.

**Current state:** **#3 is closed and the tracer bullet runs end to end** — markdown Gate Assessments
on disk → a pure projection → one authenticated read-only endpoint → a Svelte page showing each
project's derived Current Gate. Backend suite **37 passing in 0.09s**. Tracker: **2/8 closed**; #1
(spec) and **#4–#8** remain open, all `ready-for-agent`. The design work stays done: 15 decisions,
`CONTEXT.md`, 10 ADRs.

**Both of the previous handoff's open items are now CLOSED** — Hostinger SSH is restored and D16 is
deployed and verified; the Cloudflare Worker is redeployed with a current KB. Do not carry them
forward.

**What this system is (settled — do not re-litigate):** ent-os is **PT JUP's internal operating
layer**, not a product with JUP as customer zero. Erik is the **appointed Director of Operation and
Business Development** with full decision authority (no longer "nominee").

**Do next, in order:**
1. **#4 — evidence detail and fail-closed parse refusals.** The frontier, and it builds directly on
   #3's parser. It also owns the two follow-ups #3 deliberately left: ruff's isort groups `jup` as
   third-party (no `known-first-party`), and a YAML *timestamp* in `assessed_on` is currently
   **refused** rather than truncated to a date — reversible if you disagree with that call.
2. **#8 — boot baseline.** Small, unblocked, guards the alembic two-heads failure that stops the app
   booting entirely. Take it first if you want the cheaper win.
3. Then **#5** and **#6** in parallel, then **#7**. `/clear` between every ticket — each is
   self-contained by construction.
4. **#7 needs nothing from Erik** — SKK Migas is already at `contacted`, and it is now live in the
   Worker's KB. Do not re-derive a rung from `partners.md` prose.

**Constraints to honor:**
- **Fork-owned Python that must be fast-testable goes in `backend/jup/`, never `backend/open_webui/`.**
  `open_webui/__init__.py` imports typer and uvicorn, so under `--only-group dev` nothing in that
  package is importable at all. `pythonpath = ["backend"]` is what makes `jup` reachable. A test
  dependency must also go in the **dev group** — it will not be inherited from the project.
- **Tests in `tests/` (plural) at the repo root**, never `backend/`, never `test/` (the vendor tree's
  own). Fixtures via `fixtures_dir` / `fixture_path`. Command: `uv run --only-group dev pytest`.
- **`asyncio_mode = auto` is deliberate** — under strict an unmarked `async def` fails outright.
- **CI gates:** `ruff format --check .` with **`quote-style = "single"`** and line-length 120, plus
  `ruff check --select=F --ignore=F401,F403,F405,F541,F811,F841`. The bare `--select=F .` reports 348
  pre-existing vendor errors — the ignore list is what makes it pass; do not "fix" the config.
- **Budget the Chrome verification at the START of a ticket, not the end.** It needs a multi-GB
  `uv sync` AND a ~1.1 GB `all-MiniLM-L6-v2` download on first boot before uvicorn binds. Two
  servers: uvicorn on 8080 **run from `backend/`**, vite on 5173 proxying `/api`.
- **Disk is tight.** It hit 100% (1.0 GB of 460 GB) this session; npm+bun caches were cleared for
  ~15.6 GB. Check `df -h` before any large install. `~/.cache/uv` (21 GB) is prunable only when the
  MCP servers holding its lock are not running.
- **Interceptor cannot screenshot here** — DOM render times out at 15s, OS capture grabs the wrong
  Chrome window. Use `interceptor eval --main` + `getComputedStyle` probes and state the
  missing-pixel gap explicitly. `interceptor state` lists refs when `tree` and `find` return empty.
- **Canonical `~/jup/brand` accents are FILLS and fail AA as text** (3.05:1, 4.02:1). Use the
  `-text` variants in `src/lib/styles/jup-brand.css`, which are measured.
- **`@jup/ui` is REACT and cannot be used in this Svelte tree.** Only the CSS custom properties port.
- **Enforcement is inlet-only.** `EVENT_SINKS` audit but cannot refuse. See ADR-0002.
- **A fifth enterprise hole:** `routers/openai.py:1464` and `routers/ollama.py:1091` sit behind only
  `get_verified_user`, so a user API key bypasses the whole pipeline.
- **The Strategy KB reaches production ONLY via the Cloudflare Worker bundle** — there is no `kb/` on
  the Hostinger server. A `kb/*.md` edit needs `bun build-kb-bundle.ts` then `wrangler deploy`; an
  rsync does nothing. Run `bun build-kb-bundle.ts --check` before believing the assistant matches the
  repo.
- **Deploy authorization for axiara.ai/JUP is per-change, never standing** — ask every time.
- `gh` targets **upstream** unless pinned — pass `--repo erikgunawans/ent-os-new-jup` explicitly.
- Never push to `upstream`. Commits go **directly to `main`** — private single-maintainer repo, PRs
  are explicitly not a triage surface. **No PR is expected for a wrap here.**
- Alembic: a fork revision colliding with upstream gives two heads and the app will not boot. Trust
  `down_revision`, never the docstring. Tracked as #8.
- **zsh does not word-split unquoted variables.** `$SSH` holding a whole command fails.

**Open items waiting on Erik (do not chase these yourself):**
- **One verification only he can run** — the assistant answering `Di rung mana SKK Migas sekarang?`
  should say **Contacted**, not Follow-up. It needs the shared JUP password, which the assistant does
  not hold by design.
- **Two offers he has not answered:** (a) `~/jup/kb/CONTEXT.md` is stale twice over — it calls him
  "nominee Operation Director" and claims the assistant "runs locally only (127.0.0.1) — never
  web-published", which stopped being true under D13 exception v2; fixing it needs a bundle rebuild
  plus another `wrangler deploy`. (b) `~/jup-kb-assistant-worker/` is **not under git** — no origin,
  no mirror, outside D14, and it holds the deployed assistant.
- **Codex CLI is 0.139.0 and needs ≥0.155.1** (`bun add -g @openai/codex@latest`) before Forge can
  give a genuine cross-vendor second opinion. Until then Forge is Claude-family output.
- **An OpenAI key with ZDR enabled**, when voice work starts (ADR-0005/0006, D16). Not needed yet.

---

# Next session — ent-os-new-jup (checkpoint 2026-09-19-late)

> Prepended by /wrap 2026-09-19 (checkpoint 2026-09-19-late). Supersedes checkpoint 2026-09-19's anchor.

Resume ent-os-new-jup — read PROGRESS.md first (top checkpoint 2026-09-19 late).

**Anchor:** `origin/main` at `5cbcea364` **as this was written**, or one commit ahead at this
checkpoint's own wrap commit (subject begins `chore(session):`). Verify with
`git log --oneline 5cbcea364..origin/main`. A single `chore(session):` commit is EXPECTED — that is
this wrap writing itself down. Any commit in that range whose subject does NOT start
`chore(session):` means a parallel session pushed: real drift, investigate before writing.

**Current state:** **#2 is closed and the fork has its first test suite** — `uv run --only-group dev
pytest`, 4 passing, green in GitHub Actions on 3.11 and 3.12. The design work stays done: 15
decisions, `CONTEXT.md`, 10 ADRs, spec **#1** and tickets **#3–#8** still open and all
`ready-for-agent`. Tracker: **1/8 closed**. Everything else is still a pristine Open WebUI v0.11.3
fork — no application code yet, only the harness that later tickets write into.

**What this system is (settled — do not re-litigate):** ent-os is **PT JUP's internal operating
layer**, not a product with JUP as customer zero. It delivers what `~/jup/kb/governance.md` names as
missing — PMO cadence, HSE, KPI visibility, audited partner SLAs. Erik is the **appointed Director of
Operation and Business Development** with full decision authority (no longer "nominee").

**Do next, in order:**
1. **`/implement` on #3** (tracer bullet — a project and its Current Gate, from fixture to screen).
   It is the next link in the chain and #2 no longer blocks it.
2. **#8 (boot baseline) is now UNBLOCKED** — it was waiting on #2 only. It is small, it guards the
   alembic two-heads failure that stops the app booting entirely, and it can be taken any time.
   Take it before #3 if you want the cheaper win first.
3. Then the frontier: #3 → {#4 → #5, and #6 in parallel} → #7. `/clear` between every ticket — each
   is self-contained by construction.
4. **#7 needs nothing from Erik** — he has already placed SKK Migas at `contacted`, and the ticket
   says so. Do not re-derive a rung from `partners.md` prose.
5. When SSH is restored (see below), finish the two pending deploys in one pass.

**Constraints to honor:**
- **The test harness is established — use it, do not reinvent it.** Tests go in **`tests/` (plural)
  at the repo root**, never in `backend/` and never in `test/` (singular — that is the vendor tree's
  own, holding `sd-empty.pt`). Fixture data goes in `tests/fixtures/`, reached via `fixtures_dir` /
  `fixture_path` from `tests/conftest.py`. Command is `uv run --only-group dev pytest`; **a ticket
  that must `import open_webui` drops `--only-group` and pays for the full runtime tree** (chromadb,
  transformers, sentence-transformers — minutes, not seconds). All of this is in `AGENTS.md`.
- **`asyncio_mode = auto` is deliberate** — under strict, an unmarked `async def` fails outright.
  Do not "tidy" it to strict.
- **CI gates that will fail you:** `ruff format --check .` with **`quote-style = "single"`** and
  line-length 120, plus `ruff check --select=F`. Run `uv run --only-group dev ruff format .` before
  committing Python.
- **Python is APPROVED for backend work in this fork** (2026-09-19), overriding the global
  TypeScript-only rule. `svelte.config.js` uses `adapter-static` and FastAPI serves the SPA, so there
  are no SvelteKit server routes. Does NOT generalise to other repos.
- **`@jup/ui` is REACT and cannot be used in this Svelte tree.** Same reason `/design-sync` can't
  target this repo. The `~/jup/brand` tokens DO port — they are plain CSS custom properties.
- **Canonical accents are fills and fail AA as text** — use the `-text` variants for words.
- **Enforcement is inlet-only.** No way to block a websocket-streamed response after the first token
  ships. `EVENT_SINKS` audit but cannot refuse — return values discarded, exceptions swallowed, fired
  after the mutation. See ADR-0002 for every rejected extension point.
- **A fifth enterprise hole:** `routers/openai.py:1464` and `routers/ollama.py:1091` sit behind only
  `get_verified_user`, so a user API key bypasses the whole pipeline.
- **zsh does not word-split unquoted variables.** `$SSH` holding a whole command fails.
- **Verify web work with Interceptor against a dev server, never `bunx serve`** (it strips `.html`
  and the query string).
- `gh` targets **upstream** unless pinned — pass `--repo erikgunawans/ent-os-new-jup` explicitly.
- Never push to `upstream`. Commits go **directly to `main`** — private single-maintainer repo, PRs
  are explicitly not a triage surface. **No PR is expected for a wrap here.**
- Alembic: a fork revision colliding with upstream gives two heads and the app will not boot. Trust
  `down_revision`, never the docstring. Tracked as #8.
- **Three JUP component systems exist** — search `~/NEW-JUP/jup-design-system`,
  `~/.claude/skills/synced/*/jup-design` and `~/ent-os-ui` before building any JUP UI.

**Open items waiting on Erik (do not chase these yourself):**
- **Hostinger SSH is DEAD** — the key authenticates but the login shell is `/sbin/nologin` and the
  sftp subsystem is closed, so both the remote `tar` backup and `rsync` fail. Nothing is exposed
  (unauthenticated `curl` still 401s). **Two changes are committed but NOT live: D16 and the
  `partners.md` Stage-ladder migration.** Erik must re-enable SSH in hPanel or publish via File
  Manager. Recorded in `~/jup/CLAUDE.md`.
- **Cloudflare Worker redeploy** — the `kb/partners.md` change reaches the strategy assistant only
  when Erik redeploys the Worker himself via `wrangler` (the harness blocks tool calls carrying live
  credentials).
- **An OpenAI key with ZDR enabled**, when voice work starts (ADR-0005/0006, D16). Not needed yet.

---

# Next session — ent-os-new-jup (checkpoint 2026-09-19)

> Prepended by /wrap 2026-09-19 (checkpoint 2026-09-19). Supersedes checkpoint 2026-09-18b's anchor.

Resume ent-os-new-jup — read PROGRESS.md first (top checkpoint 2026-09-19).

**Anchor:** `origin/main` at `e58be13f7` **as this was written**, or one commit ahead at this
checkpoint's own wrap commit (subject begins `chore(session):`). Verify with
`git log --oneline e58be13f7..origin/main`. A single `chore(session):` commit is EXPECTED — that is
this wrap writing itself down. Any commit in that range whose subject does NOT start
`chore(session):` means a parallel session pushed: real drift, investigate before writing.

**Current state:** The design work is DONE and the build is fully specified. `/grill-with-docs`
settled **15 decisions** across four rounds; `CONTEXT.md` (9 terms) and **10 ADRs** are committed;
spec **#1** and tickets **#2–#8** are on GitHub Issues, all `ready-for-agent`. Still zero product
code — the repo remains a pristine Open WebUI v0.11.3 fork plus documentation. **#2 is grabbable
now and nothing blocks it.**

**What this system is (settled — do not re-litigate):** ent-os is **PT JUP's internal operating
layer**, not a product with JUP as customer zero. It delivers what `~/jup/kb/governance.md` names as
missing — PMO cadence, HSE, KPI visibility, audited partner SLAs. Erik is now the **appointed
Director of Operation and Business Development** with full decision authority (no longer "nominee"),
which added pre-contract business development to the remit.

**Do next, in order:**
1. **`/implement` on #2** (backend test harness), then work the frontier. `/clear` between every
   ticket — each is self-contained by construction. Chain: #2 → #3 → {#4 → #5, and #6 in parallel}
   → #7. #8 (boot baseline) is blocked by #2 only and can be taken any time after it.
2. **#7 needs nothing from Erik** — he has already placed SKK Migas at `contacted`, and the ticket
   says so explicitly. Do not re-derive a rung from `partners.md` prose.
3. When SSH is restored (see below), finish the two pending deploys in one pass.

**Constraints to honor:**
- **Python is APPROVED for backend work in this fork** (2026-09-19), overriding the global
  TypeScript-only rule. `svelte.config.js` uses `adapter-static` and FastAPI serves the SPA, so there
  are no SvelteKit server routes — there is no server-side TypeScript to write here. Does NOT
  generalise to other repos.
- **`@jup/ui` is REACT and cannot be used in this Svelte tree.** Same reason `/design-sync` can't
  target this repo. The `~/jup/brand` tokens DO port — they are plain CSS custom properties. This
  error was in the first draft of spec #1 and was corrected; do not reintroduce it.
- **Canonical accents are fills and fail AA as text** — use the `-text` variants for words.
- **Enforcement is inlet-only.** There is no way to block a websocket-streamed response after the
  first token ships. `EVENT_SINKS` audits but cannot refuse. See ADR-0002 for the evidence on every
  rejected extension point.
- **A fifth enterprise hole, newly found:** `routers/openai.py:1464` and `routers/ollama.py:1091` are
  mounted behind only `get_verified_user`, so a user API key bypasses the whole pipeline.
- **zsh does not word-split unquoted variables.** `$SSH` holding a whole command fails. This bit
  again this session — use inline commands or an array.
- **Verify web work with Interceptor against `storybook dev` / a dev server, never `bunx serve`.**
- `gh` targets **upstream** unless pinned — pass `--repo erikgunawans/ent-os-new-jup` explicitly.
- Never push to `upstream`. Commits go **directly to `main`** — private single-maintainer repo, PRs
  are explicitly not a triage surface. **No PR is expected for a wrap here.**
- Alembic: a fork revision colliding with upstream gives two heads and the app will not boot. Trust
  `down_revision`, never the docstring. Now tracked as #8.
- **Three JUP component systems exist** — search `~/NEW-JUP/jup-design-system`,
  `~/.claude/skills/synced/*/jup-design` and `~/ent-os-ui` before building any JUP UI.

**Open items waiting on Erik (do not chase these yourself):**
- **Hostinger SSH is DEAD** — the key authenticates but the login shell is `/sbin/nologin` and the
  sftp subsystem is closed, so both the remote `tar` backup and `rsync` fail. Nothing is exposed
  (unauthenticated `curl` still 401s). **Two changes are committed but NOT live: D16 and the
  `partners.md` Stage-ladder migration.** Erik must re-enable SSH in hPanel or publish via File
  Manager. Recorded in `~/jup/CLAUDE.md`.
- **Cloudflare Worker redeploy** — the `kb/partners.md` change reaches the strategy assistant only
  when Erik redeploys the Worker himself via `wrangler` (the harness blocks tool calls carrying live
  credentials).
- **An OpenAI key with ZDR enabled**, when voice work starts (ADR-0005/0006, D16). Not needed yet.

---

# Next session — ent-os-new-jup (checkpoint 2026-09-18b)

> Prepended by /wrap 2026-09-18 (checkpoint 2026-09-18b). Supersedes checkpoint 2026-09-18's anchor.

Resume ent-os-new-jup — read PROGRESS.md first (top checkpoint 2026-09-18 evening).

**Anchor:** `origin/main` at `a901bd4db` **as the last non-wrap commit**, followed by this
checkpoint's own wrap commits — every one of which has a subject beginning `chore(session):`.

Verify with `git log --oneline a901bd4db..origin/main`. If every commit in that range is a
`chore(session):` one, there is NO drift — that is this wrap writing itself down, and the count is
deliberately not pinned because each amendment to this file moves the head again. **Any commit in
that range whose subject does NOT start `chore(session):` means a parallel session pushed** — that
is real drift, and item 1 may rest on something that changed underneath it. Investigate before
writing.

**Current state:** `ent-os-new-jup` is still a pristine Open WebUI v0.11.3 fork with **zero product
code** — documentation commits only. The design system is DONE and lives in a separate repo,
`~/ent-os-ui` (`@jup/ui`, 3 commits, 20 primitives + provider, 97 stories, all gates green). Brand
is the ratified `~/jup/brand` layer (`#079F4E`, IBM Plex Sans), vendored and drift-gated. No test
baseline exists for either repo.

**Do next, in order:**
1. **Run `/grill-with-docs` — Erik deferred it from last session specifically to start here.**

   ⚠️ **Do NOT open by saying there is no product, no spec, or that prior work was "scaffolding."**
   That framing was used last session and Erik correctly pushed back on it. What exists: a full
   Open WebUI platform (chat, RAG over 13 vector stores and 22 search providers, models, tools,
   pipelines, `access_grants` RBAC, admin surface) AND a governance blueprint in
   `docs/architecture/` naming the exact chokepoints with file:line. The gap is narrow and
   COMMERCIAL, not technical: **nothing yet says who pays, for what, instead of running stock
   Open WebUI free.**

   The thesis is already in our own notes — stock Open WebUI is enterprise-*capable* but not
   enterprise-*deployable*, and we know the four holes and where they attach:
   - Audit redaction is **one regex** (`audit.py:285`) and `REQUEST_RESPONSE` captures response
     bodies **verbatim** — full audit builds a PII repository, not a compliance control.
   - `workspace.tools` = unsandboxed `exec()` + `pip install` from user frontmatter; the only kill
     switch is `ENABLE_PLUGINS=false`. No enterprise security review passes that.
   - Every frontend guard is a client-side `goto('/')`. Cosmetic.
   - Timers, automations, subagents and context compaction forge a synthetic `Request` straight to
     `CHAT_COMPLETION_HANDLER` — **policy in HTTP middleware silently will not cover them.**

   Already present and cheap to build on: `publish_event`/`EVENTS` on nearly every mutation with
   `EVENT_SINKS` accepting a sink class (no router changes), and `merge_usage` (`response.py:100`)
   already aggregating per-model/per-user/per-group tokens for chargeback.

   **Grill these three, not a blank page:**
   1. **Which hole ships first?** Standing recommendation: audit/DLP — most legible to a buyer, and
      `EVENT_SINKS` means building it without forking the request path. The RCE sandbox is more
      urgent technically but sells as "you fixed a bug," not as a product.
   2. **Who signs?** CISO vs Head of AI Governance vs the platform team that must get Open WebUI
      past security review. Different buyers want different first features.
   3. **Does it survive the alternative?** The real competitor is "just use Azure AI Foundry /
      Bedrock, governance included" — not another fork. Erik's Google years are the best source.

   Keep it in ONE unbroken context window through `/to-spec` → `/to-tickets`. Escalate to
   `/wayfinder` only if no first shippable slice can be named by the end of the interview.
2. **Minimal boot baseline** for ent-os-new-jup — scope it narrow: does the app boot, and does
   alembic have exactly one head. A comprehensive suite over a pristine fork tests Open WebUI's
   code, not ours; the real suite should land WITH the first product code.
3. `@jup/ui` v2 chat composites (`ChatMessage`, `MessageInput`, `Sidebar`, `ModelSelector`) — they
   carry more brand signal than the primitives, but they are better designed once a spec says what
   screens exist. Do not start these before item 1.

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
- **The three grill questions in item 1** — which hole first, who signs, and what beats the
  hyperscaler alternative. The grilling cannot invent a buyer; these are Erik's to answer.

*(Resolved during this wrap: `~/ent-os-ui` now has a private remote at
`github.com/erikgunawans/ent-os-ui`, all 3 commits pushed. No longer a risk.)*

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
