# PROGRESS — ent-os-new-jup

## Checkpoint 2026-09-22-live (latest) — #16 enforced in production, the UI carries JUP, OpenRouter half-wired

- **Tracker: #16 open** — implemented and deployed; held open only for audit evidence (see below).
- **Commits:** `50173d4dc` (#16), `0341bced5` (token layer), `c3e8e5fcb` (inset panel), `e95a9dfc7` (divider fix).
- **Revisions:** `ent-os-00006-gl2` (#16) → `ent-os-00007-rr8` (UI through `c3e8e5fcb`) → `e95a9dfc7` deployed at wrap time, authorized per-change by Erik.

### #16 — ADR-0002 fail-closed enforcement is live, and still open on purpose

Policy settled by Erik 2026-09-21: **a governed turn must carry the JUP operating contract in its
system message, or it is refused**; every turn audited (admitted / exempt / refused). Governed =
user-facing chat turns including every tool-loop turn; named internal tasks (title, tags, follow-up,
emoji, query, image-prompt, autocomplete, native function_calling, MoA) exempt by a tested allowlist.
Recorded in ADR-0002 itself.

`kb/serve.ts`'s D11 guard could **not** be ported a third time: it inspects the *answer*, which works
only because it is non-streaming. Every ADR-0002 attachment point is an inlet. The contract instead
carries D11's revenue-not-margin rule into the model's context.

Load-bearing details, all tested (26 cases, verified to fail when a patch is dropped):
- `utils/chat.py` attaches + stamps on **every** turn — `middleware.py:5873` strips the system
  message before the tool loop re-enters at `:5994`/`:6214`, so attach-once would be gone by turn two.
- The funnel **also refuses**: the direct-connection and pipe branches never reach a router guard.
- The stamp lives on `request.state`, never `form_data`; the task exemption is honoured only for a
  stamped turn, or a direct caller exempts itself with `metadata.task`.
- `bypass_filter` is ignored by design (`BYPASS_MODEL_ACCESS_CONTROL` forces it True).
- `backend/jup/` cannot import FastAPI, so guards *return* a refusal and the vendor line raises 403.

**Why still open:** zero `jup.governance` log entries exist, because **zero models are configured**,
so no chat turn has ever run on the governed build. Close it on the first real audit entry.

**Audit durability:** `DATA_DIR` is unset in `deploy.sh` and `/srv/jup` is read-only, so the JSONL
file is ephemeral. Every entry also hits `log.info('jup.governance …')` → Cloud Logging, which is the
durable trail. Query:
`gcloud logging read 'resource.labels.service_name="ent-os" AND textPayload:"jup.governance"' --project=jup-ops`

### The UI now carries the canonical JUP identity

Palette = `~/jup/brand` (ratified 2026-09-18), **not** the GSM 2023 palette the `jup-design` skill
still ships — re-confirmed with Erik before starting. Three files, then a layout pass:
- `src/jup-tokens.css` vendored `--jup-*` layer; dark hangs off `.dark`, not the media query.
- The gray ramp was **re-tinted, not re-pointed**: it is overwhelmingly TEXT (gray-500: 1078 of 1095
  uses), so each step kept its exact OKLCH L and gained only the green cast. Largest WCAG shift 0.17.
- Inset shell/panel (Erik's reference): shell `--jup-paper`, panel `--jup-surface`, 16px, 8px inset.
  `main` was `display: contents` and the sidebar is `fixed`; one `#main-content > *` rule re-points
  every route root (all six route groups declare `h-screen` there) instead of editing vendor routes.
- Resting sidebar dividers removed (`#sidebar-resizer` border-r was the visible line).

**"The UI didn't change" was browser cache, not the deploy.** Served CSS contained the build; the
browser held a stale HTML shell pointing at old asset hashes. No service worker. ⌘⇧R.

### Interceptor reaches the live app through IAP

It drives Erik's Chrome, which carries his Google session. This session wrongly claimed twice that
the app was unverifiable because `alesha-bot` lacks IAP access, and verified against a static mock
instead. Verify against the live deployment first.

### OpenRouter — connection set, key missing

Erik chose OpenRouter. The OpenAI connection was re-pointed to `https://openrouter.ai/api/v1` via the
admin API (`/openai/config/update`) — **stored in the app DB, not in `deploy.sh`**. The key field is
empty by design; Erik enters it in Admin Settings → Connections. `/api/models` still returns 0.

**Governance:** D16 governs voice only and explicitly leaves the typed chat path undecided.
OpenRouter is a broker — processing location is per upstream model. Wants a `DECISIONS.md` row and
OpenRouter's "exclude providers that train on prompts" policy. Not drafted yet.

### Traps that cost time this session

- Local `npm run build` OOMs without `NODE_OPTIONS=--max-old-space-size=8192` (Dockerfile sets it).
- A background command's reported exit code is the LAST command's — `| tail` / `| tee` masked a
  failed build once. Capture `$?` immediately, no pipe.

## Checkpoint 2026-09-21-after — backlog cleared, then four gaps taken off the shelf

- **Tracker: #16 open** (ADR-0002 enforcement), filed deliberately. #1–#15 all closed.
- **Cross-repo:** `~/jup` at `9cd0b90`; new repo `erikgunawans/jup-kb-assistant-worker` at `96b9464`+1.

### The assistant had been lying about its own deployment for two months

`~/jup/kb/CONTEXT.md` told the assistant it "runs locally only (`127.0.0.1`) — never web-published
(Decision D13)". D13's **own status field** has read *"STANDING RULE, superseded 2026-07-14 by a
broader exception"* since that date, and Exception v2 records the full hub plus this assistant
serving from `axiara.ai/JUP` behind a password gate.

Not inert prose: `build-kb-bundle.ts:43` bundles `CONTEXT.md` as the assistant's **operating
context**. Asked whether the material was exposed, that line was the answer. Corrected, rebuilt
(8 sources, 53293 bytes), deployed as Worker version `cafea287` (was `b75e6a15`).

**Post-deploy control check — all 401 unauthenticated:** `/JUP/`, `/JUP/api/chat` (POST too),
`/JUP/DECISIONS.md`, `/JUP/COO/`. The POST matters most: that is the Worker's **own** auth check,
not `.htaccess`, because Workers run at the edge and would otherwise bypass it — the gap D13 records
as caught before first deploy. Content itself is unverified; it sits behind Erik's password.

### `~/jup-kb-assistant-worker` was not under version control at all

Not "no remote" — not a git repo. It held `worker.js` as deployed, `wrangler.toml`, the builder, and
the **only copy** of `kb-bundle.js`. Now `erikgunawans/jup-kb-assistant-worker`, **private**, plus a
local bare mirror — D14 says never let `origin` become the only backup, and that reasoning does not
stop at the repo it was written for. No secrets committed; `wrangler.toml` carries identifiers, not
credentials, which is a reason the repo is private rather than a reason to redact.

### #16 — ADR-0002 is Accepted and entirely unimplemented

Not "one remaining hole", which is how the previous handoff framed it. Verified: `VENDOR-PATCHES.md`
has three entries and none is enforcement, `utils/chat.py:151` is pristine, and no `jup` import
exists in `utils/chat.py`, `routers/openai.py` or `routers/ollama.py`. **Every model call in the
operating layer currently reaches its provider ungoverned.**

### Why the 403 test cannot be done first

`get_verified_user` 401s on any role outside the verified set and `DEFAULT_USER_ROLE=pending`, so a
fresh second identity gets **401, not 403**. Reaching the 403 requires promoting an account to
`user` — which is exactly the condition that makes #16 exploitable. **#16 must land before the 403
path can be proven in production.** Erik's call, taken 2026-09-21.

## Checkpoint 2026-09-21-clear — the board is empty; #13 and #15 both closed

- **Session:** `/next` → all four questions answered → #15 deployed and closed → three red gates fixed → token re-minted → #13 closed.
- **Branch:** main · **Commits:** `728d190d3`, `615a27072`, `ef0256cae`, `13a612db7`, `c918b7d6a`, `d33360fa0`
- **Tracker: ZERO open issues.** First time.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync.

### #13 — both drift gates live and green (`d33360fa0`)

`JUP_REPO_TOKEN` re-minted 2026-09-20T20:50:21Z. All four jobs pass: `preflight` skips nothing,
`credential-scope` confirms the runner holds no write permission on the bucket, `kb-drift` agrees
with the live `records/`, `record-sync` reports `in sync` at `ac9dc29`.

**The first live run failed, and that was the valuable part.** `record-sync` exited 1 on real
drift: `Would remove gs://jup-ops-records/deliverables/.DS_Store`. Not litter — a structural bug.
The write path rsyncs a working **filesystem** from a Mac; the gate compares against a git
**checkout**. `.DS_Store` is gitignored in `~/jup`, so it exists on the filesystem and can never
exist in the checkout: the gate would have reported drift **no commit could ever resolve**.
Deleting the object would not have held either, since the next local sync re-uploads it. Both rsync
calls now `--exclude="$JUNK_RE"`. `JUNK_RE` sits with the other config, above the `--check` path
that uses it first — defined lower it would have been unbound under `set -u` on the path that runs
first.

Verified on both sides: `--check` against the live filesystem exits 0, and CI's checkout also says
`in sync`. Local and CI agreeing is the point; their disagreeing was the bug.

**Gap recorded, not fixed:** `preflight` tests only that a secret is **non-empty**, not valid. The
run two minutes before the new token landed did not skip — it ran with the stale token and failed
at `actions/checkout` with `Bad credentials`. Honest (red, and annotated as a checkout failure, not
as drift), but "present" and "valid" are different and only the first is guarded. It will matter
the day this PAT expires.

## Checkpoint 2026-09-21-deployed — #15 deployed and closed, and three red gates explained

- **Session:** `/next` → all four open questions answered by Erik → #15 deployed and verified → the ruff gate pinned → two further red gates found and fixed.
- **Branch:** main · **Commits:** `728d190d3`, `615a27072`, `ef0256cae`, `13a612db7`
- **Deployment:** revision `ent-os-00005-jhc`, image `ent-os:615a27072`, serving 100%.
- **Tracker: one open.** #15 **closed**. #13 unchanged, still blocked on `JUP_REPO_TOKEN`.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`. Not touched this session.

### #15 — deployed with per-change authorization, criteria 7 and 8 met

Rollback to `ent-os-00004-cr2` was staged and an on-demand Cloud SQL backup taken before the
deploy. Neither was needed.

**Criterion 7.** `POST /api/v1/auths/signin` through IAP, carrying a deliberately wrong email *and*
password in the body, returned `erik@axiara.ai` / `admin` / id `beda5418-…`. Because the body was
wrong, the identity can only have come from the header. Four consecutive `GET /api/v1/auths/`
returned `[200,200,200,200]` — the load-bearing half, since `utils/auth.py:415` compares
`user.email != trusted_email` on **every** request and raises `401 User mismatch` on any
difference. A still-prefixed header could not return 200 once.

**Criterion 8.** Same row, not a recreation: `created_at` 2026-09-19 12:28:56 GMT+7, two days
before the deploy; still `admin`; `user_count` 1 before and after the signin call, so no second
prefixed row. `/api/v1/portfolio/` returns the live records.

Invariants held: `DEFAULT_USER_ROLE=pending`, `ENABLE_SIGNUP=False`, `DATABASE_URL` and
`WEBUI_SECRET_KEY` still secret references, ingress still `internal-and-cloud-load-balancing`.

**Still not covered:** the 403-for-non-admin path has never run against the deployment. One
identity exists and signup is closed, so there is no second account to refuse.

### The image was not buildable at all (`615a27072`)

Three builds were needed and the first two failures were not #15's code. Cloud Build now falls back
to the **legacy docker builder**, which does not define the BuildKit-predefined `$BUILDPLATFORM`, so
`Dockerfile:27` expanded empty and died at step 13/65 with `failed to parse platform` — a message
that accuses the Dockerfile rather than the builder. **It reproduces in both the regional and the
global pool**, so the first fix attempted (moving pools) was wrong and was corrected before pushing.
Fixed with an `ARG BUILDPLATFORM=linux/amd64` default, recorded in `VENDOR-PATCHES.md`.

The build pool is still global, but on its own merits only — `e2-highcpu-32` has no quota in
`asia-southeast2`. `deploy.sh` and the README now say explicitly that the split is **not**
load-bearing, so it is not later mistaken for the fix. Note also that the vite OOM is node's own
heap cap and failed identically on 8 GB and 32 GB: machine size has never been the cure, and
`VENDOR-PATCHES.md:14-18` said so before this session claimed otherwise.

### Frontend Build had been red since 2026-09-19, for two independent reasons

Neither had anything to do with the frontend. `npm run format` runs prettier `--write` over
`**/*.md` and the next step is `git diff --exit-code`.

**Cause one (`ef0256cae`):** 43 fork-owned markdown files were not prettier-clean. Formatting them
once would not have held — `/wrap` rewrites `PROGRESS.md` and `.planning/next-session-prompt.md`
every session and neither comes out clean, so the gate would re-red at the next checkpoint. They are
now in `.prettierignore`, along with `tests/fixtures/`: a fixture's value is its exact bytes, and
prettier inserts a blank line into `malformed-unterminated-frontmatter/projects/runaway.md`. The
suite still passes with every fixture prettified (184 passed, verified in a clean clone), so that
one is latent rather than broken — but a fixture whose job is to be malformed must not be quietly
repaired by a formatter.

**Cause two (`13a612db7`):** 29 JUP strings had been added to the Svelte source without the locales
ever being regenerated — "Current Gate", "Engagement", "Blocked on", "Gate state is restricted to
the operating layer". `i18next-parser` re-added them on every run, so the tree came out dirty.
Regenerated: 1856 lines added, 0 deleted, 64 locale files, nothing outside
`src/lib/i18n/locales/`.

**Method note worth keeping:** cause two was only found because the first fix was pushed on the
strength of verifying *half* the gate locally. Verify the whole step sequence in a clean clone, not
the one command you changed. The final check ran prettier **and** `i18n:parse` and asserted zero
dirty files.

`Format & Build` is now green through step 8, **"Production build", which had never executed on any
previous run** because step 7 always failed first. That gate was not merely red; it was not testing
anything.

### The ruff gate, closed (`728d190d3`)

Erik chose pinning CI to the lock. `format-check` runs `uv run --frozen --only-group dev ruff`, so
CI and the local venv are both 0.15.18 and both check 276 files. The `uvx ruff@latest` pre-push
check is retired. Raising the version is now a deliberate `uv lock --upgrade-package ruff`, which
lands in `uv.lock`, which the workflow's `paths:` filter already watches.

### `Release to PyPI` is permanent noise

It fails on every commit, including ones predating this session. Inapplicable upstream workflow. It
is worth knowing because a permanently red gate is where a real failure hides — which is exactly
what `Frontend Build` turned out to be.

## Checkpoint 2026-09-21-wired — #15 wired and guarded, and CI was red the whole time

- **Session:** `/next` → item 1 was #15's unwired modules → registered, tested, documented → CI went red → the red predated this session by five commits.
- **Branch:** main · **Commits:** `4aa919128`, `9041af1fe`, `faaadae54`
- **Tests:** 201 passed locally; 184 passed / 17 skipped in a fresh clone against a runtime-less venv (the CI dev job).
- **Python CI: green for the first time in at least five pushes.** All four jobs.
- **Tracker: two open, unchanged in count.** #15 is code-complete and blocked on deploy authorization; #13 still blocked on Erik.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync. Not touched this session.

### #15 — the modules were real but inert, and now they are registered (`4aa919128`)

`backend/jup/iap_identity.py` and `backend/jup/admin_allowlist.py` were committed last session
**unwired**: nothing imported them, so they changed no behaviour at all. `main.py` now imports both
and registers them.

The order is load-bearing and counter-intuitive. Starlette runs the **last**-added middleware
outermost, so the allowlist is added *first* and the normalizer *second* — which puts the
normalizer on the outside, where every layer below it (the allowlist included) reads an identity
header that has already had IAP's `accounts.google.com:` prefix removed.

### The guard, and proving it can actually fail

ADR-0012's Consequences section asks for a test by name, and the whole argument for choosing a
middleware over a vendor patch rests on it: *a lost patch is a production login loop, a lost
registration line is a failing test.* `tests/test_jup_iap_registration.py` is the second half of
that sentence.

Three of its checks read `main.py` as **source** and need no runtime, so they run in the
`--only-group dev` job on every push. That matters more than the runtime check: it is the one that
actually fires on a rebase. Verified against the real mutations rather than assumed —

| mutation | runtime-less job |
|---|---|
| both `add_middleware` lines deleted | 3 failed, 3 passed, in 0.06s |
| the two lines swapped | 2 failed |
| unmodified | 6 passed, 1 skipped |

A fourth check asserts the **inverse** — that neither `routers/auths.py` nor `utils/auth.py`
imports the normalizer — because the "just to be safe" patch in #15's Traps is exactly what
re-adds the surface option 3 exists to remove. `git diff` against the upstream merge-base
(`0a7c15832`) confirms both files are byte-identical to upstream.

**Its ordering assertions are relational, not absolute, and that was a correction.** The first
version asserted `stack[0] == NORMALIZER` and failed: the vendor registers its session middleware
at the very bottom of `main.py`, inside a `try/except`, so it lands outside these two and *which*
class it is depends on whether Redis resolved. Pinning an index would fail on that alone, and it is
harmless — the session layers read a cookie, never `x-goog-authenticated-user-email`.

### Two defects found in this session's own work, before they shipped

**`deploy.sh` heredoc.** The env-vars heredoc is unquoted (`<<EOF`) so `$ADMIN_EMAILS` expands —
which leaves command substitution live for **everything** inside it, comments included. Backticks
in the first draft of the new comments were executed: `accounts.google.com:erik@axiara.ai: command
not found`. Caught by rendering the heredoc and checking stderr rather than by reading it. The
block is now backtick-free with a comment saying why, and the rendered file is verified to parse to
ten non-empty string values.

**An unreachable branch in `iap_identity.py`.** `except UnicodeDecodeError` around
`value.decode('latin-1')` could never fire — latin-1 maps all 256 byte values — and its docstring
claimed a safety it did not provide. Removed, with a test that a high-byte address survives the
round trip.

### Python CI had been red since before this session, and nobody noticed (`faaadae54`)

The first push went red, which is what prompted looking — and the `pytest` job had failed on
**every** commit for at least five pushes, including checkpoint 2026-09-20-closes's own wrap
(`2f859eefb`). 23 failures in `test_portfolio.py`, every one of them green locally.

**Git does not track empty directories.** Fifteen fixture record trees under
`tests/fixtures/portfolio/` have a deliberately empty `gate-assessments/`. They existed on this
machine and were simply absent from every fresh clone, so `project_portfolio` refused each whole
tree as unavailable. The failures never name the cause: half read `DID NOT RAISE RecordError`,
because an unavailable tree is *returned* rather than raised over, which reads as a validation bug.

Fixed with a `.gitkeep` per directory, each explaining why it exists (`_load_assessments` globs
`*.md`, so none is read as a record). Verified in an actual fresh clone: 184 passed, 17 skipped,
where it had been 23 failed.

This was outside #15's scope and taken anyway, on the reasoning that **a registration guard landing
in a CI nobody trusts is not a guard.**

### A gate gap left open deliberately, because it is Erik's call

`.github/workflows/backend.yaml` runs `pip install "ruff>=0.15.5"` — **unpinned**, so CI always
takes the newest release. The lock pins the local venv. Today that was 0.16.8 in CI against
0.15.18 locally, and they disagree about scope: local checks 276 files, CI checks 437, because
0.16 formats python code blocks **inside markdown** and 0.15 does not. That is what turned the
first push red, on the VENDOR-PATCHES.md entry.

The local gate is therefore permanently weaker than CI and the gap widens with every ruff release.
Pinning CI to the lock, or raising the dev group's floor, would close it — not taken, because it is
a gate-policy decision rather than a silent fix. Until then: check with
`uvx ruff@latest format --check . --exclude .venv --exclude venv` before pushing markdown.

**Resolved 2026-09-21 — Erik chose to pin CI to the lock.** `format-check` now runs
`uv run --frozen --only-group dev ruff …` instead of `pip install "ruff>=0.15.5"`, so CI and the
local venv are the same 0.15.18 and both check 276 files. The `uvx ruff@latest` pre-push check is
**retired** — it now reports failures CI will not have. Raising the version is henceforth a
deliberate `uv lock --upgrade-package ruff`, which lands in the lock, which the workflow's own
`paths:` filter already watches.

### What #15 still needs

Criteria 7 and 8 — sign-in produces no prefix, and the existing account survives — need a
**deployment**, which was explicitly out of scope. Both are marked blocked on the issue rather than
left ambiguous. Only `user:erik@axiara.ai` holds `iap.httpsResourceAccessor`, so a wrong middleware
locks out the one identity that could repair it. Deploy authorization is per-change and was not
assumed.


## Checkpoint 2026-09-20-closes — the blocked board cleared, and the ADR became a ticket

- **Session:** `/next` → every open item was blocked on Erik, so the first act was to ask → he authorized all four → KB bundle deployed → #11 rotated and closed → ADR-0012 decided and implemented-as-#15 → #12 closed won't-fix → started #15's code.
- **Branch:** main · **Commits:** `675cbb59d`, `9d9cdd52c`, + this wrap
- **Tracker: four open → two.** #11, #12, #14 closed. #13 still blocked on Erik. **#15 is new** — the ADR-0012 implementation.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync.

### The handoff's first instruction was "ask", and it was right

Every one of #11–#14 was blocked on a decision or an action only Erik could take, so the session
opened with a question rather than work. He authorized all four at once, which is what made the rest
of the session possible. Worth keeping as a pattern: a board where every item is human-blocked is
not a board an agent should start guessing at.

### #11 — rotated, and the deploy script would have quietly undone it (`675cbb59d`)

The credential is now the `database-url` secret, referenced the way `WEBUI_SECRET_KEY` always was.
Revision `ent-os-00004-cr2` serves 100%, and `GET /api/v1/portfolio/` returns 200 with real records
through IAP. The password was **rotated, not relocated** — `db-password` versions 1 and 2 are
disabled, version 3 carries the new value so the two secrets cannot disagree.

**The part that mattered was not the rotation.** `deploy.sh` rebuilt `DATABASE_URL` from
`db-password` on every run, so the next deploy would have put the plaintext form straight back and
the issue would have reopened itself without anyone touching it. That lookup is deleted, and
`provision.sh` now creates `database-url` instead. A fix that a routine deploy reverts is not a fix.

Two gcloud traps, both recorded in `deploy/gcp/README.md`:

1. **`--update-secrets` alone cannot convert an existing plain env var.** It fails with *"already
   been set with a different type"*, which reads like a permissions or format problem. It needs
   `--remove-env-vars=X` in the **same** command, so no revision exists half-converted.
2. **`--set-secrets` replaces the entire secret block, silently.** Naming one secret drops every
   other reference — `WEBUI_SECRET_KEY` would have vanished.

### ADR-0012 is Accepted, and the decision produced a ticket (`9d9cdd52c`, #14 → #15)

Option 3, the fork-owned middleware. I verified the load-bearing finding before recommending, since
it is the whole reason option 2 is a trap: `utils/auth.py:415` really does re-check the header
against `user.email` on **every request**. Patching only `auths.py:736` therefore creates a
*correct* account and then 401s everything after it — presenting as a session bug, with nothing
pointing at a prefix.

**The deciding argument turned out not to be cost.** It is the shape of the failure: a lost vendor
patch is a production login loop, and a lost middleware registration is a failing test. An outage
you can misdiagnose is worse than one you cannot.

Four sub-questions settled: `admin` comes from an explicit allowlist rather than insertion order;
`DEFAULT_USER_ROLE=pending` stays, keeping IAP access and operating-layer access separable; the
existing account is migrated with its password **dormant, not cleared**; ADR-0001's ceiling does not
move, though the seat list becomes the IAP binding set, which over-counts — the safe direction.

The dormant password rests on `--ingress=internal-and-cloud-load-balancing`. That dependency is
recorded in the ADR because it is invisible from the user table: **loosen ingress and the password
must be cleared.**

### #12 closed as won't-fix, with the condition to reopen

~$7–9/month against a ~$35–60/month deployment, to fix a failure Chrome already routes around by
auto-upgrading to HTTPS. Erik's call. **The reopen condition is a second IAP binding** — a second
person is the first one to type the hostname by hand and read the failure as "the system is down".
Recorded rather than deferred, so it stops consuming a decision slot every session.

### The KB bundle is deployed, and the caveat outlives the deploy

Version `b75e6a15` is live at 100%, replacing a 2026-09-18T21:32 deployment — which confirms the
stale-bundle diagnosis, since #9 landed at 10:43 on the 19th. `--check` proves the bundle current
against `records/`, and it carries the corrected text.

**What is NOT proven is that the page reaches the Worker.** `axiara.ai/JUP/` is 401 behind Hostinger
`.htaccess`, so the end-to-end question could not be asked. The worker README (July) says the
deployed page is a lobby-only teaser whose assistant code calls `http://127.0.0.1:4173/api/chat`. If
that is still true, **this deploy closed nothing** and the commissioner gap is exactly where it was.
Erik took the check.

### #15 started — the modules exist, nothing is wired

Two fork-owned modules written, formatted, linted and smoke-tested, but **imported by nothing**, so
they change no behaviour and are safe on main:

- `backend/jup/iap_identity.py` — `normalize_iap_value` plus a pure ASGI middleware. `rsplit` on the
  **last** colon, because a provider can carry a path (`securetoken.google.com/proj:user`) while
  neither an address nor a numeric subject can contain a colon. A malformed value
  (`accounts.google.com:`) is passed through **unchanged** rather than normalized to `''` — handing
  `auths.py` an empty string is how a malformed header becomes a malformed user instead of a
  rejected request.
- `backend/jup/admin_allowlist.py` — `JUP_ADMIN_EMAILS`, and a middleware that settles the role
  **after** the inner app, once per address per process. After, because a first-ever signin has not
  created the account yet when the request arrives; a startup-only pass would miss precisely the
  person the list was just edited for. It never demotes: "the list shrank" and "this instance
  started before the list grew" are indistinguishable from there.

**Still to do:** the `main.py` registration, the tests, the `VENDOR-PATCHES.md` entry, the env vars
in `deploy.sh`. No deploy — Erik scoped this to code and tests.

## Checkpoint 2026-09-19-gates — the tracker has content again, and the drift gate is half-credentialed

- **Session:** `/next` → opened the four findings as #11–#14 → built #13's skip-path CI → drafted ADR-0012 → Erik authorized the GCP half → provisioned WIF → his PAT turned out broken → wrote the wizard that verifies before storing.
- **Branch:** main · **Commits:** `5afcbc7f2`, `b6fef468d`, `0c6c80ed2`, `6effe355a`, `a0c9fdf09`, `3d8116b2c`, + this wrap
- **Tracker: four open** — #11, #12, #13, #14. It was empty at the last checkpoint; these are that checkpoint's prose findings, finally tracked.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync.

### The findings stopped being prose (#11–#14)

The IAP checkpoint recorded four things in narrative and tracked none of them. Each now has a ticket
carrying evidence rather than a summary of it, re-verified against the live deployment rather than
quoted: `gcloud run services describe` shows exactly one secret reference (`WEBUI_SECRET_KEY`) and a
64-character plaintext `DATABASE_URL` beside it; `curl http://ops.axiara.ai` returns curl 52, an
empty reply on a resolving hostname, which reads as an outage rather than "use HTTPS".

#11 asks for **rotation, not relocation** — that credential has been readable to every `run.viewer`
for the life of the deployment, and a deleted probe job carried it too. Moving it without rotating
would file the finding without closing it.

### The drift gates exist and run nightly (#13, `b6fef468d` → `a0c9fdf09`)

One workflow, because it is one problem: both gates must reach state outside this repository.
**A gate that cannot see what it guards must not report green** — green and "I could not look"
would be the same colour — so preflight probes for each credential and the gate jobs *skip* grey,
with a notice naming what is missing and the drift it is therefore not catching. That is what let
the workflow land before any credential existed.

**Three traps found while building it, each of which would have produced a gate that looked like it
worked:**

1. **`PYTHONPATH=backend` is load-bearing, and its absence is not a no-op.** `pythonpath =
   ["backend"]` is a *pytest* setting; it does nothing for `python -m`. It imports locally only
   because a full `uv sync` leaves an editable-install `.pth`, and `--only-group dev` does not
   install the project. Without it the job dies with `ModuleNotFoundError` and **exit 1** — which is
   `kb_sync`'s code for *drift*. The gate would have cried drift every night about a disagreement
   that did not exist. Proven both ways against a bare venv.
2. **GitHub runs `run:` steps as `bash -e {0}`**, so `cmd; status=$?` aborts before `$?` is read.
   The same trap the `~/jup` pre-commit hook documents, from the other direction.
3. **Under `set -u` an empty bash array is an unbound variable** — the notice loop failed on the one
   path that matters most: both credentials present, nothing skipped.

Exit 1 (drift) and exit 2 (broken tree) stay apart in the annotations. **Exit 2 means the gate
checked nothing** and must not read as a governance alarm.

### WIF provisioned, read-only, and proven (`6effe355a`)

Erik authorized the GCP half only; #11 and #12 were declined and nothing touching the running
service changed. Provisioned as `alesha-bot@axiara.ai`, which holds Owner on `jup-ops`.

```
pool      github-pool
provider  github-provider   condition: assertion.repository == 'erikgunawans/ent-os-new-jup'
identity  records-reader@jup-ops.iam.gserviceaccount.com
grant     roles/storage.objectViewer on gs://jup-ops-records ONLY
```

**Bucket-scoped, not project-scoped:** `objectViewer` at the project would also grant read on
`jup-ops-data`, which holds uploads this gate has no business seeing. **Restricted twice on
purpose** — the provider's `attribute-condition` decides who may mint a token, the
`workloadIdentityUser` principalSet decides who that token may act as. `sts.googleapis.com` had to
be enabled; the handshake fails without it.

**Keyless by choice.** A downloadable service-account key pasted into a repo secret is a long-lived
credential in a second place — #11 arriving by another door.

The assertion was a *step inside* `record-sync`, which also needs the PAT, so it could not run until
both credentials existed. Lifted into its own `credential-scope` job gated on the GCS secrets alone,
it proved itself immediately: **"Runner holds no write permission on jup-ops-records."**
`record-sync` now `needs:` it, so a credential that could publish skips the drift check rather than
running with it.

Not verified locally: the OIDC handshake. **Owner does not include `serviceAccountTokenCreator`**,
so impersonating `records-reader` was denied — and granting that binding just to test would widen
the thing under test. The CI job is the proof, and it passed.

### The PAT was already set, and already broken (`3d8116b2c`)

Erik minted `JUP_REPO_TOKEN` himself at 11:03. Both drift gates still failed:

```
X kb/ agrees with records/ (live tree)   Bad credentials
X The bucket matches the JUP tree        Bad credentials
```

**`Bad credentials` is a 401 — the token string is wrong.** An under-scoped fine-grained PAT returns
**404 `Repository not found`** instead. So this is a truncated paste, a trailing newline, or an
expired token — *not* a permissions mistake, though it reads exactly like one. `erikgunawans` is a
User, not an org, which rules out pending org approval.

It failed that way because **nothing exercised the credential between storing it and a nightly gate
depending on it.** `scripts/wizard-jup-repo-token.sh` is that missing step: mint → **verify** →
store → prove. The verify stage narrows from "is the token real" (`/user`) to "can it see the repo"
(`/repos/jup`) to "can it read Contents" (what `actions/checkout` actually needs), so a failure
names its own cause instead of leaving 401 to be guessed at. Its write probe writes the repository's
**current** description back to itself — a probe that damaged the repo to prove it could would be a
bad trade. Deliberately no `write_env`: CI-only credential, and a second copy on disk is #11.

### ADR-0012 drafted, and the premise it rested on was wrong (`0c6c80ed2`)

#14, the handoff and `iap.md` all described trusted-header auth as a patch to `auths.py:731`. **The
header is read in three places across two vendor files**, and `utils/auth.py:415` re-checks it
against `user.email` on *every* request.

**So patching only the signin path does not create a malformed account — it bricks the deployment.**
The account is created correctly, then every subsequent request compares it against the raw prefixed
header, mismatches, and 401s. The symptom is being signed out immediately after signing in, which
presents as a session bug rather than a prefix bug.

That roughly doubles the vendor-patch surface and moves half of it into `utils/auth.py`, hotter
upstream than `auths.py`. So the ADR carries **four** options, and the new one — a fork-owned ASGI
middleware in `backend/jup/` normalizing the header once, leaving all three sites unpatched — is the
only one that *reduces* the ADR-0007 burden. **LB custom headers cannot do this**: they expand only
load-balancer-provided variables plus `origin_request_header`, with no rewrite facility. A Service
Extension can, and is costed as option 4.

Status **Proposed**. The decision is the Director's and is not recorded.

---

## Checkpoint 2026-09-19-iap — ent-os is reachable; the record sync is observable

- **Session:** `/next` → Erik chose IAP from five untracked candidates → built it → verified in real Chrome → then built the record-sync `--check` and pushed the bucket.
- **Branch:** main · **Commits:** `033479213` (runbook), `61f4d681c` (checkpoint), `5df330e4d` (sync `--check`), + this wrap
- **Tracker: nothing open at the time.** This was untracked work, picked by Erik.
  **Amended 2026-09-19** — the findings recorded below are now tracked as #11 (plaintext
  `DATABASE_URL`), #12 (no port-80 rule), #13 (cross-repo CI for both drift gates) and
  #14 (ADR-0012, trusted-header auth). They were prose-only until then.
- **`https://ops.axiara.ai` is live behind IAP.** Erik is `admin`. The portfolio endpoint returns real records.

### What was standing up, and what it cost

The load balancer is the ADR-0010 shape: Cloud Run stays `--no-allow-unauthenticated` with
`--ingress=internal-and-cloud-load-balancing`, so the `run.app` URL refuses everyone and the only
path in is the LB with IAP on its backend. `ent-os-neg` → `ent-os-backend` (IAP on) → `ent-os-ip`
(**34.111.8.177**) → `ent-os-cert` → `ent-os-lb` / `ent-os-proxy` / `ent-os-fr` on 443.
`erik@axiara.ai` holds `iap.httpsResourceAccessor`; the IAP service agent holds `run.invoker`.

**`deploy/gcp/iap.md` was wrong in three places**, each failing with an error pointing away from its
cause:

1. **The OAuth consent screen step described an API Google shut down on 2026-03-19.**
   `gcloud iap web enable` with no `--oauth2-client-id` now takes a Google-managed client.
   `iap oauth-brands list` returning nothing is expected, not a failure.
2. **`cloudresourcemanager.googleapis.com` must be enabled** or the IAP IAM binding fails with
   `SERVICE_DISABLED` buried under what reads like a permissions error.
3. **The IAP service agent does not exist until asked for.** The `run.invoker` binding fails with
   `Service account service-$PN@gcp-sa-iap... does not exist`, which reads like a typo in the
   address. `gcloud beta services identity create --service=iap.googleapis.com` creates it.

**The cert is ACTIVE ~27 min after DNS, but does not serve immediately.** For about two minutes
after `managed.status` flipped, TCP connected and the TLS handshake died at client hello. Poll the
handshake, not the API status.

### The first account

`ENABLE_SIGNUP=True` for one revision; Erik signed up; the fork promoted him. **The window closes
itself** — `signup_handler` (`routers/auths.py:875`) promotes the only user to `admin` and writes
`ui.enable_signup = False` in the same transaction. `/api/config` confirms `enable_signup: false`
independently of the env var, which was reverted anyway so a future revision cannot reopen it.

A probe job against the private-IP Cloud SQL confirmed `user` and `auth` were both 0 rows first —
had a row existed, the promotion would not fire and Erik would have landed `pending` with no admin
to approve him. The job was deleted after; its config carried the DB password.

### Verified in real Chrome (Interceptor), not asserted

`GET /api/v1/portfolio/` → **200** with real records: `gas-spbg-reactivation`, G1 `fail`, the
evidence chain (`rued-alignment` satisfied with artefact, `gas-allocation-5mmscfd` not),
`awaiting_engagements: ["skk-migas-pgn-allocation"]`, and tier-labelled figures carrying the POTENSI
meaning. GCS records mount, artefact-tree resolution, governance presentation rules and the admin
gate all working together on GCP for the first time. No console errors; 0 of 197 resources failed.

**Not verified:** the 403-for-non-admin path. One user exists and signup is closed, so there is no
second identity to test with. Covered by the 15 local tests; never run against this deployment.

### Two things this session surfaced — now #11 and #12

- **#11 — `DATABASE_URL` carries the Postgres password in plaintext** as a Cloud Run env var, while
  `WEBUI_SECRET_KEY` correctly uses Secret Manager. Readable with a plain `gcloud run services
  describe`. Inconsistent, and a real exposure.
- **#12 — no port-80 forwarding rule**, so `http://ops.axiara.ai` fails rather than redirecting.
  Deliberate — a second rule is a second standing charge — but it is a papercut.

### The better shape, deliberately not taken — now #14

`WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Goog-Authenticated-User-Email` would make IAP *be* the login:
`auths.py:731` creates and authenticates straight from the IAP-verified header, no password and no
signup window ever. That is what ADR-0010 reaches for. It needs a vendor patch first — IAP prefixes
the value (`accounts.google.com:erik@axiara.ai`) and the fork does not strip it — which buys a
permanent ADR-0007 rebase burden. **Decide it as an ADR, not in passing** — #14 carries that
decision, numbered ADR-0012 since 0010 and 0011 are taken.

### The record sync is no longer hand-carried (`5df330e4d`)

`gs://jup-ops-records` is an rsync, not a live mount, so a committed record was not on the dashboard
until someone remembered to run `sync-records.sh`. That was the last hand-carried step between a
record and what a reader sees — the same drift class #9 closed, in a second place, and with **no way
to even observe it**.

**It is not yet in CI — #13.** It runs when a human remembers, which is the failure mode it was
written to end. #13 covers it together with #9's kb-drift gate, because both need the same
credential to reach live state from a runner: one credential problem, two gates.

`sync-records.sh --check` is read-only: `--dry-run` never touches the bucket, verified rather than
assumed — a new file in the forced-failure case never landed there. It exits 1 on drift, so it can
gate a commit or a cron without authorisation to write to deployed infrastructure.

**Two things the first runs taught, both now in the code:**

- **rsync proposes to SET mtime on byte-identical objects**, because an rsync'd object never carries
  the local file's mtime. The first version counted that and reported drift on a tree that was
  genuinely in sync — confirmed false by comparing md5s directly, which matched. A gate that cries
  wolf gets ignored, so only `Would copy|delete|remove` count.
- **`Would remove` is the delete direction and does not match `delete`.** The bucket-has-extra case
  was silent until the filter named it.

The sync path now stamps `.sync-manifest.json` with the commit it published, so `--check` names the
deployed commit rather than only saying it differs. Written **last**: a manifest for a sync that
failed would lie.

**Verified in both directions**, the way #9's gate was: clean mirror of the bucket (24 files) →
`in sync`, exit 0, no false positives. Edited record → `Would copy`. Deleted locally →
`Would remove`. New record → `Would copy`. Uncommitted edit → `DIRTY` warning plus drift. Bad flag →
exit 2. Missing tree → exit 1. Bucket untouched throughout.

**Its first real run found genuine drift:** `records/README.md` in the bucket was missing #9's own
ADR-0011 section — landed locally, never pushed. Erik authorised the sync; the bucket is now at
`ac9dc29` and `--check` reports `in sync`. The live endpoint still returns 200 afterwards, so the
GCS mount picks up a changed bucket without a restart.

---

## Checkpoint 2026-09-19-tracker-empty — #9, #10 and #1 closed; the tracker is empty

- **Session:** `/next` → IAP deferred by Erik → built #9 → built #10 → re-audited and closed #1.
- **Branch:** main · **Commits:** `ca4bed0c9` (#9), `6f8dbc6a4` (#10), + this checkpoint
- **Tracker: nothing open.** #1–#10 all closed. Suite **141 passing**, tree clean after a run.
- **Second repo:** erikgunawans/jup at `ac9dc29`, pushed to origin *and* mirror.

### #9 — `records/` is the single source for partner and gate state (ADR-0011)

`jup.kb_sync` generates the partner state table and the stage-ladder line in `~/jup/kb/partners.md`
from `records/engagements/`, reusing `STAGE_LABELS` rather than copying the vocabulary. Three
mechanisms, because not everything can be generated:

1. **Generate** the structured claims.
2. **Refuse a second home for the vocabulary** — a ladder label used as a *table cell* outside a
   generated region. Prose is exempt: the ladder definition teaches a reader what the table means,
   and "The critical one" argues its case about SKK Migas and PGN/Pertagas by name.
3. **Check** what must stay prose — the "5 mmscfd allocation is not secured" claim in `gas.md` and
   `governance.md`, against the G1 assessments **in both directions**. Deleting the caveat fails as
   loudly as contradicting it, because a governance caveat is a claim and its disappearance is drift.

Two rows became one: the allocation is a single engagement facing SKK Migas *and* PGN/Pertagas
(ADR-0008). A new Evidence column carries each rung's artefact.

**Five counterparties lost their stage.** Danantara/Fadli Rahman, PLN, Pertamina NRE, Pertamina
Patra Niaga and Pelindo had a rung and no record; they now sit in a second table with name and
purpose and **no rung at all**. Three read *Contacted* before. Filing a record moves the row back up,
and the check refuses to let it sit in both.

**The gate is a hook, not CI.** Both repos are private and no cross-repo checkout is wired up, so a
workflow would need a PAT nobody has issued. ent-os CI proves the check catches drift (six
forced-failure cases, all exercised against a copy of the live tree first); `~/jup/.githooks/
pre-commit` stops drift reaching a commit. Its first draft passed silently — `status=$?` after an
`if` block reads the status of the *if construct*, which is 0 when the condition was false.

### #10 — the endpoint is gated on the operating layer, and the seam is tested

**The operating layer is the `admin` role** — Erik's answer, 2026-09-19, held in one named constant.
`get_operating_layer_user` answers **403, not 401**: `get_verified_user`'s 401 means "we do not know
who you are", and telling a signed-in member that bounces them to a sign-in page that cannot help.
The vendor's own `get_admin_user` answers 401 here, which is why the fork has its own dependency.

Configuration moved off module-level `os.environ.get`, which is why this endpoint had **zero** tests
— no `TestClient`, no reference to `/api/v1/portfolio` anywhere in the tree. Now 15, covering signed
out, `pending`, verified-without-permission, permitted, the payload round-trip, ADR-0008 at the wire,
ADR-0009 against the response body, and a `RecordError` as a 500 naming the file and field. Swapping
the handler back to `get_verified_user` fails three of them — run, not assumed.

**The frontend was telling a member without access that the records could not be trusted.** Every
thrown error rendered under *"The portfolio was refused, not emptied"*, the notice for a record the
projection refuses to vouch for. `PortfolioRequestError` now carries the status and 403 gets its own
notice.

**Verified in real Chrome** against uvicorn + vite: `admin` renders the live records (*no gate passed,
blocked on `gas-allocation-5mmscfd`, SKK Migas · PGN/Pertagas at Contacted, G1 refused 2026-09-19*);
`user` gets "Gate state is restricted to the operating layer" on `.jup-notice` without
`jup-notice-refused`; anonymous gets 401.

### The static-wipe landmine fired, and is now disarmed suite-wide

The first unguarded import of the router deleted all 17 tracked vendor assets — exactly what the
previous checkpoint predicted would happen. Restored from git. `tests/conftest.py` now copies the
static tree to a temp dir and sets `STATIC_DIR` at conftest import, before pytest imports any test
module, so a test that imports `open_webui` anywhere is covered without having to know.
`test_boot.py` asserts the guard holds. **Outside pytest it is still live** — an ad-hoc
`python -c 'import open_webui...'` still wipes the tree.

### #1 closed as delivered — 20 met, 1 partial by design, 1 deferred by the spec

Story 17 closed by #9, stories 21 and 19 by #10. Story 13's refused-state hole stays: a `RecordError`
500s, so there is no payload to carry the Named Non-Coverage sentences, and inlining them into the
template reintroduces the staleness #6 removed. Story 22 was never in this slice by its own text.

What remains is not code: a contact record for SKK Migas / PGN, and a `wrangler deploy` Erik has
declined for now — the assistant still answers from the pre-#9 `partners.md`.

### Decisions this session

- **IAP deferred.** Erik declined the ~$18/month forwarding rule for now, so nobody can log in to the
  Cloud Run deployment. `deploy/gcp/iap.md` is ready when he wants it.
- **Operating layer = `admin` role**, not a group or a per-user flag.
- **KB bundle rebuilt, not deployed.** Backed up before the rebuild; `~/jup-kb-assistant-worker` is
  still not under git.


## Checkpoint 2026-09-19-gcp — ent-os runs on GCP; #1 audited, #9 and #10 opened

- **Session:** `/next` → audited #1's 23 stories → opened #9/#10 → exercised the compose overlay →
  deployed ent-os to Google Cloud.
- **Branch:** main · **Commits:** `ae00f74f9` + this checkpoint
- **Tracker: #1, #9, #10 open.** #9 and #10 are this session's findings, not new scope.

### #1 audited, not closed — 18 met, 3 partial, 1 not met, 1 deferred by the spec

Posted as a per-story table on #1. The one that matters is **story 17**: *"the dashboard reads the
same files the board pack is built from, so the two can never disagree."* `records/` is read by
nothing but the dashboard. Gate and partner state also lives in `kb/partners.md`, `kb/gas.md`,
`kb/governance.md` and the board deck. They agree today — `partners.md:10` puts SKK Migas at
Contacted, matching the record — **by hand, not by construction**. → **#9**.

Story 21 is partial: the endpoint carries `get_verified_user` and nothing else, so any `user`-role
account reads every gate refusal and counterparty rung. No endpoint tests exist at all. → **#10**.

Story 13's refused-state hole (a 500 carries no payload, so no Named Non-Coverage) stays as it is —
inlining those sentences into the template reintroduces the staleness #6 removed.

### The compose overlay is exercised — 12/12, and the guard proven

`docker-compose.jup.yaml` had never been run. Client-side: the `:?` guard fires, the bind is
`read_only: true`, and the overlay **adds to** rather than replaces the vendor's data volume.
At runtime: env vars arrive, all three record dirs read, writes and deletes refused, both cited
artefacts resolve. Forced failure with `:rw` flipped exactly the three write checks — and deleted
the live G1 record, which was restored from `jup@fd753ba`. **Run the writable variant against a
copy, never `~/jup`.**

The vendor image was never booted: a full `up` needs several GB and the disk sat at 100%.

### ent-os is deployed to GCP — project `jup-ops`, asia-southeast2

Cloud Run behind a locked ingress, Postgres 16 on a **private IP** with pgvector, records mounted
**read-only** from GCS. Runbook and idempotent scripts in `deploy/gcp/`.

**Verified in the cloud, not asserted:** alembic migrated against Postgres over VPC egress; the
mount probe passes all seven checks in Cloud Run including the write refusal; the auth chain
refuses at both layers (403 unauthenticated at Cloud Run, 401 from `get_verified_user`); and the
deployed app serves `/static/favicon.png`, `loader.js`, `splash.png` and the app shell at 200.

Six gcloud behaviours reported the wrong cause and are all written down in `deploy/gcp/README.md`.
The one worth repeating: **`vite build` OOMs at node's own heap cap, not the machine's** — it failed
identically on 8 GB and 32 GB builders, which is what rules memory out. Fixed by the `NODE_OPTIONS`
line upstream ships commented, logged in `deploy/gcp/VENDOR-PATCHES.md` for the ADR-0007 rebase.

### A landmine removed: the boot test was deleting 17 tracked files

`backend/open_webui/config.py:99` unlinks **every file** in `STATIC_DIR` at import, then repopulates
from `FRONTEND_BUILD_DIR/static`. This tree has no `build/static` unless the frontend was just built,
so the wipe had nothing to put back — and the unlink loop swallows every exception, so it was silent.
Every run of `tests/test_boot.py` deleted the favicons, logo, manifests and `loader.js`. A
`git add -u` after a test run would have committed that.

Fixed in our own test, not vendor code: it now copies the static tree into `tmp_path` and points
`STATIC_DIR` there. **Suite 100 passing and the working tree stays clean after a full run** — which
it did not before.

Harmless in the container: the Cloud Build frontend produces `build/static`, so the delete-then-copy
is a real refresh there. Confirmed by the 200s above.

## Checkpoint 2026-09-19-slice-complete — #4, #8, #5, #6, #7 closed; the slice is delivered

- **Session:** `/next` → #4, then #8, #5, #6, #7 back to back.
- **Branch:** main · **Commits:** `8305ab5d1` · `a0d9bcac2` · `0cbc71200` · `31f0390b5` · `4edec6f2a`
- **Records in the JUP repo:** erikgunawans/jup@`fd753ba`
- **Tracker: 7/8 closed.** Only **#1**, the parent spec, remains open — every child is done.
- **Suite: 37 → 100 passing**, 45 fixture scenarios.

### What the dashboard now does

Reads Gate Assessments, Engagements and projects as markdown from the **live `~/jup` tree**, derives
Current Gate on every read, and renders the gas pillar's binding constraint as a field rather than a
conversation: *no gate passed, blocked on `gas-allocation-5mmscfd`, SKK Migas + PGN/Pertagas at
Contacted, G1 refused 2026-09-19.*

### #4 — evidence detail and fail-closed parse refusals (`8305ab5d1`)

- Each assessment carries its requirements, whether each was met, and its citation.
- `Project.blocking_requirements` counts **refusals only**: a requirement unmet under a *passing*
  verdict is a waiver the board granted, and naming it a blocker would overrule a decision taken.
- Guards beyond the ask: `satisfied` absent is refused (either default invents a claim), `satisfied:
  partially` is refused, bare-path evidence is refused.
- Also closed #3's isort follow-up — `jup`/`open_webui` are now `known-first-party`.

### #8 — boot baseline (`a0d9bcac2`)

- `jup.migrations` reads the alembic graph by **parsing each version file's AST**. Alembic's own
  `ScriptDirectory` can't: `migrations/env.py` imports the whole model tree. A parse also works on a
  tree that is already broken, which is when it is asked.
- Four assertions — one head, one base, no duplicate ids, no dangling parents — each naming every
  file involved. Plus a subprocess boot test, `skipif`-guarded on a **dependency** probe.
- **Premise measured, not assumed:** with two heads injected, importing the app dies with
  `alembic.util.exc.CommandError: Multiple head revisions are present`, exit 1.
- New `boot` CI job, scoped to migration changes + `workflow_dispatch`. **Verified by dispatch:**
  all five ran, 5m27s end to end.

### #5 — engagements, citations, the stage ladder (`0cbc71200`)

- Engagements are their own records; gates **cite** by id and never copy (ADR-0008). One record
  serves two projects — proven across `engagements-shared/`.
- ADR-0009's forecast ban is enforced at `_frontmatter`, the **one door every record type passes
  through**, walking nested mappings and lists. Refused, never dropped.
- **`certainty` is deliberately NOT banned** — Certainty Tier (D11) is the legitimate concept, and
  catching it would refuse the field that keeps FAKTA and POTENSI apart. Pinned by a test.

### #6 — certainty tiers, named non-coverage, legible empty states (`31f0390b5`)

- `figures_by_tier` is the **only** shape served: no flat list, no total, no sum. Composing two bases
  into one statement is something a client would have to go out of its way to do.
- POTENSI labelled margin/profit/NPV is refused, in **both languages**. Whole-word matching, so
  "Marginal volume" passes; POTENSI-only, so NPV on FAKTA passes.
- Named Non-Coverage ships with the payload and renders **outside the branch chain**, so it survives
  the empty and unavailable states.
- The **unreadable directory had no coverage at all**; absent and unreadable now read differently.

### #7 — Gate #1 against the live tree (`4edec6f2a` + jup@`fd753ba`)

- Three records in `~/jup/records/`. **No NPV invented** — `kb/portfolio.md` carries none for SPBG
  reactivation, so the record carries none.
- `artefact_root` turns on artefact resolution. **Proven on the live tree:** renaming the real
  RUED brief produced a refusal naming the file, field and path; restoring it returned to available.
- `docker-compose.jup.yaml` mounts `/srv/jup:ro` as an **overlay**, not a vendor patch (ADR-0007).
- `.env.example` was **wrong** — it pointed at the repo root, not `records/` inside it.

### Verified, not asserted

- **100 passing.** Clean `--only-group dev` env (CI-equivalent): 99 passed, 1 skipped, 0.45s.
- **Every guard in all five tickets was neutered and watched failing**, then restored.
- **Real Chrome against the live `~/jup` tree** and against malformed fixtures: refusals render with
  zero cards, never a partial page. Contrast measured in both themes, worst **4.90:1**, all opacity 1.
- Nothing deployed changed: `build-kb-bundle.ts` reads 8 fixed files, `records/` is not among them.
  `bun build-kb-bundle.ts --check` → *"kb-bundle.js is current."*

### Costs and traps worth not rediscovering

- **YAML eats ` #`.** `purpose: ... — Gate #1 of the gas pillar` parses as `... — Gate`. Nothing
  raises. No parser guard can catch it. The spec's own worked example is unquoted. Quote it.
- **`--only-group dev` silently reuses a full local `.venv`.** A skip-guarded test passes here and
  fails in CI. Verify with `UV_PROJECT_ENVIRONMENT=/tmp/civenv`.
- **Nominal contrast lies when opacity is involved** — an `opacity: 0.82` softening composited to
  3.75:1 from a 4.90:1 token. Fold opacity in before believing a ratio.
- **`read -t N </dev/null` does not sleep** — it returns instantly on EOF. Polling loops built that
  way spin. Use `Monitor` instead.

### Next

**#1 is the only open issue** — the parent spec, with 23 user stories, some explicitly deferred
(story 22's unauthenticated board view says "this slice does not build" it). Decide whether to close
it or audit its stories one by one.

---

## Checkpoint 2026-09-19 — #3 closed: the portfolio tracer bullet, end to end

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
