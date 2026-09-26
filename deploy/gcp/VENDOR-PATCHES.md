# Patches against vendor code

ADR-0007 rebases onto upstream Open WebUI quarterly, and every patch here must survive that. Each
one is listed with what breaks if it is dropped, so a rebase can verify rather than guess.

Re-check this file after every rebase, alongside
`uv run --only-group dev pytest tests/test_boot.py` (the alembic two-heads check, ADR-0007).

## `Dockerfile` — `ENV NODE_OPTIONS="--max-old-space-size=8192"`

**What:** uncomments a line upstream already ships, commented, directly under a comment naming the
error it fixes. Raised from upstream's suggested 4096.

**Why:** `npm run build` (`pyodide:fetch && vite build`) dies with *"Ineffective mark-compacts near
heap limit — JavaScript heap out of memory"* on Cloud Build. This is node's own heap cap, not the
machine: it failed identically on an 8 GB `E2_HIGHCPU_8` and a 32 GB `E2_HIGHCPU_32`. Raising the
machine type is not a fix, and `E2_HIGHCPU_32` is quota-restricted in `asia-southeast2` on a new
project anyway.

**If dropped:** the image cannot be built at all — the failure is loud and immediate, at the
frontend build step. No silent degradation.

**Conflict risk:** low. One line, in a block upstream maintains for this purpose. If upstream
uncomments it themselves, take theirs and re-check the value is at least 8192.

## `Dockerfile` — `ARG BUILDPLATFORM=linux/amd64` above the frontend stage

**What:** declares `BUILDPLATFORM` with a default immediately before
`FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build`.

**Why:** `BUILDPLATFORM` is a BuildKit-*predefined* arg. Cloud Build's builder switched to the
legacy docker builder (it now prints *"the legacy builder is deprecated ... install the buildx
component"*), and the legacy builder does not define it — so `--platform=` expands to the empty
string and the build dies at step 13/65 with *"failed to parse platform: "" is an invalid
component"*. That message accuses the Dockerfile, which is why the first two attempts at this were
spent looking at the wrong file. It reproduces identically in the regional and the global build
pool, so it is not a pool or quota problem.

**Why a default is safe:** BuildKit predefines `BUILDPLATFORM` and its value takes precedence over
an `ARG` default, so a BuildKit build is unaffected and still cross-compiles correctly. Only the
legacy path changes, and only from "empty" to "linux/amd64" — which is what Cloud Build builds on
anyway.

**If dropped:** the image cannot be built at all while Cloud Build runs the legacy builder. Loud
and immediate, at the same step. No silent degradation.

**Conflict risk:** low, but it sits one line above a vendor `FROM`, so a rebase that rewrites the
frontend stage will surface it. Do **not** delete it merely because it looks redundant — it looks
redundant precisely when BuildKit is in use, which is not guaranteed.

## `backend/open_webui/main.py` — two `app.add_middleware` lines and their import

**What:** registers the fork's two ASGI middlewares, defined in `backend/jup/`:

```python
from jup.admin_allowlist import AdminAllowlistMiddleware
from jup.iap_identity import IapIdentityHeaderMiddleware

...
app.add_middleware(AdminAllowlistMiddleware)
app.add_middleware(IapIdentityHeaderMiddleware)
```

Registered in that order because Starlette runs the **last** added outermost, which puts the
normalizer outside the allowlist and outside every vendor layer that reads the identity header.

**Why:** ADR-0012. IAP sends the identity as `accounts.google.com:erik@axiara.ai`, and Open WebUI
reads that header raw in three places — `routers/auths.py:393`, `routers/auths.py:736` and
`utils/auth.py:415`. The middleware strips the provider prefix in the ASGI scope before routing, so
all three read a clean value and **none of them is patched**. `AdminAllowlistMiddleware` settles the
`admin` role from `JUP_ADMIN_EMAILS` instead of from whichever row was inserted first.

**If dropped:** silent, and the worst shape on this list. The app boots, the page loads, and every
local test that does not use a real IAP header still passes. In production, signin succeeds and the
**next request 401s**, because `utils/auth.py` is comparing `erik@axiara.ai` against the still-
prefixed header on every request. That reads as a session bug and nothing points at a prefix. ADR-
0012 chose this shape over patching the auth files precisely because a dropped registration line is
catchable and a dropped auth patch is not.

**The test that catches it:** `tests/test_jup_iap_registration.py`. Two source-level checks run
with no runtime — so they run in CI's `--only-group dev` job, on every push — and assert the
import, the two registrations and their order. A third imports the real app in a subprocess and
asserts the built stack. A fourth asserts the reverse: that **no** vendor auth read site imports
the normalizer, because a belt-and-braces patch re-adds the surface this decision exists to remove.

**Conflict risk:** moderate, and this is the one to check by hand. `main.py`'s middleware block is
upstream's and changes between releases, so a rebase can resolve a conflict there by taking
upstream's side and drop all three lines without any marker surviving. Do not resolve it by patching
`auths.py` or `utils/auth.py` instead — run the test.

## Three fail-closed governance guards — `utils/chat.py`, `routers/openai.py`, `routers/ollama.py`

**What:** one call per file, plus `from jup import governance as jup_governance`. All logic lives in
`backend/jup/governance.py`; the vendor files carry nothing but the call.

```python
# backend/open_webui/utils/chat.py — in generate_chat_completion, after the metadata merge
if refusal := jup_governance.admit(form_data, state=request.state, user_id=getattr(user, 'id', None)):
    raise HTTPException(status_code=refusal.status_code, detail=refusal.detail)

# backend/open_webui/routers/{openai,ollama}.py — at the head of generate_chat_completion
if refusal := jup_governance.refuse_if_ungoverned(form_data, state=request.state, user_id=user.id, route='openai'):
    raise HTTPException(status_code=refusal.status_code, detail=refusal.detail)
```

Two lines each, and the shape is identical in all three: the guard decides, the vendor file raises
its own framework's exception. `backend/jup/` is not allowed to import FastAPI, and a governance
refusal surfacing as a 500 would read as a server fault rather than the deliberate 403 it is.

**Why:** ADR-0002, and issue #16. `utils/chat.py`'s `generate_chat_completion` is the only in-process
funnel to every provider, so that is where the JUP operating contract is attached and the turn is
stamped governed. The two router functions are mounted directly behind only `get_verified_user`, so a
normal user's API key reaches a provider there without passing the funnel at all — they refuse any
turn that is neither stamped nor genuinely carrying the contract.

**The funnel guard refuses too, and that is not ceremonial.** `generate_direct_chat_completion` (a
direct connection) and `generate_function_chat_completion` (a pipe model) are dispatched from the
funnel and never reach a router guard, so for those two branches it is the only control in the path.
It attaches the contract and then *verifies* it attached; a payload it cannot govern — `messages`
present but not a list — is refused rather than forwarded, and is left unmodified rather than
repaired, because silently rewriting a caller's payload discards what they sent.

**Why the funnel call is not the first statement:** it sits after the `request.state` and metadata
assignments because the task exemption cannot be read before `form_data['metadata']` is merged. Those
preceding statements are pure bookkeeping — no `await`, no `return`, no `raise` — and a test asserts
exactly that rather than asserting a line number.

**Why it re-attaches on every turn:** the tool loop strips the system message before re-entering
(`utils/middleware.py:5873` calls `replace_system_message_content('', ...)`, then `:5994` and `:6214`
call back into the funnel). A contract attached once at turn one is gone by turn two. Attaching on
every pass is self-healing.

**Do not hand the guard `bypass_filter`.** It is an access-control flag that
`generate_chat_completion` sets to `True` unconditionally under `BYPASS_MODEL_ACCESS_CONTROL`, so a
guard honouring it would be off in exactly the deployments that need it. A test asserts no line
calling the guard mentions `bypass`.

**If dropped:** silent, and the same shape as the ADR-0012 registrations. The app boots, chat works,
and model calls are simply ungoverned again — which looks identical to a healthy deployment. The
audit trail stops recording, which is the only externally visible symptom.

**The test that catches it:** `tests/test_jup_governance.py`. Source-level checks run with no runtime
— so they run in CI's `--only-group dev` job, on every push — and assert, per file, that the import
and the call are present, that nothing before the call can `await`/`return`/`raise`, and that no
guard line was handed a bypass flag. The behavioural half proves the refusal path, the turn-two
tool-loop case, that a forged `metadata.task` buys nothing on a direct route, and that the trail
records admitted, exempt and refused alike.

**Conflict risk:** `utils/chat.py` is stable (nine touches in twelve months) and cheap to carry.
`routers/openai.py` is not — 59 commits in six months — which is why its guard is a head insert that
can be re-checked at a glance. Re-check all three by running the test, not by reading the diff.

## Passthrough refusals and the URL-fetch gate — `routers/openai.py`, `routers/ollama.py`, `routers/retrieval.py` (2026-09-23)

**What:** six handlers open with a refusal that always fires, and two retrieval handlers open with a
permission check.

```python
# routers/openai.py responses; routers/ollama.py generate_completion, generate_openai_completion,
# generate_openai_chat_completion, generate_anthropic_messages, generate_responses
refusal = jup_governance.refuse_passthrough(user_id=user.id, route='openai', model=form_data.model)
raise HTTPException(status_code=refusal.status_code, detail=refusal.detail)

# routers/retrieval.py process_url, process_web — helper defined above process_url
await _jup_require_web_upload(user)
```

**Why:** ADR-0002's 2026-09-23 amendment. These passthroughs reach a provider without the funnel,
nothing in the app calls them, and their payloads keep instructions outside `messages`, so the
contract check cannot be applied to them soundly. The two retrieval routes fetched any URL for any
verified user; they now enforce `chat.web_upload`, which the vendor defined and checked only in the UI.

**If dropped:** silent. The routes work again, and nothing but the audit trail's missing `refused`
lines would show it.

**The test that catches it:** `tests/test_jup_governance.py` asserts the refusal is the first
statement after the docstring in each of the six handlers, that it is raised, and that
`_jup_require_web_upload(user)` opens both retrieval handlers.

**Conflict risk:** the handler bodies below the insert are upstream's and move often; the insert is
at the head, so re-apply it there and run the test.

## Default tools settle before a `?q=` auto-submit — `src/lib/components/chat/Chat.svelte` (2026-09-23)

**What:** `setDefaults()` no longer returns early when a run is already in flight. A second caller
waits for that run through `defaultsSettled()` and then runs again. The body moved, unchanged, into
`applyDefaults()`. The `?q=` branch of `initNewChat` awaits `defaultsSettled()` before
`submitHandler(q)`.

**Why:** on a fresh load `setDefaults()` first awaits the tool, function and skill lists. The
reactive model-change handler starts that run without awaiting it, and `initNewChat`'s own call hit
the vendor's `if (settingDefaults) return;` and came straight back. The `?q=` auto-submit then sent
the turn with no `tool_ids`, so Asisten JUP was never offered `portfolio_status` and answered from
the KB instead. This was reproduced live: a fresh `/?q=` chat called only the KB tools, while a typed
chat sent `tool_ids: ["portfolio_status"]` and called it.

**If dropped:** silent. Chats still answer, but links and bookmarks that auto-submit lose the
model's default tools.

**The test that catches it:** `tests/test_chat_default_tools_patch.py`.

**Conflict risk:** moderate. `setDefaults` changes upstream now and then. Keep the waiting wrapper
and re-apply the upstream body inside `applyDefaults`.

## The fork's routers are mounted — `backend/open_webui/main.py` (2026-09-24)

**What:** three names in the `from open_webui.routers import (...)` block, `jup_kb_review`,
`jup_leadership` and `jup_portfolio`, and their three `app.include_router(...)` lines, at
`/api/v1/kb-review`, `/api/v1/leadership` and `/api/v1/portfolio`. The router modules themselves are
fork-owned files. `jup_kb_review` was added 2026-09-25 (ADR-0015).

**Why:** Portfolio (ADR-0004) and Ruang Pimpinan (P1, read-only) are served from their own routers
so their rules stay out of vendor code; mounting them is the only edit to `main.py` they need.

**If dropped:** silent. The app boots and the pages load, and the section's API answers 404, which
the Portfolio page renders as a refused load and Ruang Pimpinan as unavailable.

**The test that catches it:** `tests/test_jup_router_registration.py` (source read, runs under
`--only-group dev`).

**Conflict risk:** low to moderate. Upstream adds routers to the same import block and the same
run of `include_router` lines, so a merge can drop a neighbour. Keep all three lines.

## The name carries no " (Open WebUI)" suffix — `backend/open_webui/env.py` (2026-09-23)

**What:** the two lines that append `' (Open WebUI)'` to any custom `WEBUI_NAME` are replaced by a
comment. With `WEBUI_NAME: "None-JUPe"` in deploy.sh, the app reads exactly "None-JUPe".

**Why:** Erik renamed the app to Asisten JUP on 2026-09-23, and to None-JUPe on 2026-09-26.
LICENSE clause 4 permits removing the Open WebUI branding while end users stay at fifty or fewer
in any rolling 30 days. That is the same ground the logo replacement already rests on (ADR-0001).

**If dropped:** silent. The name reads "None-JUPe (Open WebUI)" again.

**The test that catches it:** `tests/test_brand_none_jupe.py`.

**Conflict risk:** low. Upstream rarely touches these lines, but they carry a LICENSE comment that
merges will keep reasserting.

## One audit line per tool call — `backend/open_webui/utils/middleware.py` (2026-09-23)

**What:** one import (`from jup import governance as jup_governance`) and three calls to
`jup_governance.audit_tool_call(...)`. There is one call at each place the vendor runs a tool:

- the native tool loop in `streaming_chat_response_handler`, straight after each result is unpacked (`mode='native'`);
- `drain_approved_tool_calls`, after the status is decided (`mode='approved'`);
- the legacy prompt-based `chat_completion_tools_handler`, after the call returns (`mode='default'`).

Each writes a `tool_call` line with the user, chat, tool name, `tool_id`, outcome
(`ok`/`error`/`not_found`/`unparsed`) and argument size in bytes. It never writes argument
content. All the logic is in `jup/governance.py`, and the call never raises.

**Why:** agent-depth plan E1. `admit()` writes one line per model turn, but a turn can run several
tools, and the tool is where the agent touches data. Every later tool (subagents, code
interpreter, MCP) is only as accountable as this line.

A fourth call (added 2026-09-23 for A3) sits after `ci_item['status'] = 'completed'` in the
**legacy** code-interpreter block (`mode='code_interpreter'`, `tool_id` `builtin:code_interpreter`).
With native function calling, which Asisten JUP uses, the code interpreter runs as the builtin tool
`execute_code` and gets the native loop's line (live check 2026-09-23 on `00022-bs8`:
`execute_code · builtin:execute_code · ok`). The legacy path handles code parsed out of the model's
text in non-native mode. It is covered so that switching the mode cannot open a gap. The line
records the size of the code, never the code itself, and counts an exception or any stderr as
`error`.

**If dropped:** silent. Tools still run and answers still arrive, but the trail loses the per-tool
lines.

**The test that catches it:** `tests/test_jup_tool_call_audit.py`. Against the unpatched file,
6 of its tests fail.

**Conflict risk:** moderate. The tool loop changes upstream often. Re-apply each call right after
the site's result is known, and before any `continue` that skips a call.

## Subagent tool calls name their parent chat — `backend/open_webui/utils/subagents.py` + `middleware.py` (2026-09-23)

**What:** `run_reserved` sets `child_request.state.jup_parent_chat_id = parent_chat_id` on the
subagent's synthetic request. It's one line, marked `# JUP:`. All four `audit_tool_call` sites in
`middleware.py` pass `state=request.state`. Together they give a subagent's `tool_call` lines a
`parent_chat` field naming the chat that delegated them.

**Why:** A2 went live with a gap. A subagent runs in its own chat, and its audit lines carried
only that child chat's id, so the trail could link it to the delegating chat only by timing.

The stamp lives on `request.state`, like the ADR-0002 admission stamp, because a direct caller
controls `form_data`, and a forged parent would mislabel the trail.

**If dropped:** silent. Subagent lines lose `parent_chat` again.

**The test that catches it:** `tests/test_jup_tool_call_audit.py`
(`test_the_subagent_request_is_stamped_with_its_parent_chat`,
`test_every_audit_call_site_passes_the_request_state`).

**Conflict risk:** low in `subagents.py`, where `run_reserved`'s request setup is stable. The
`middleware.py` sites move with the tool loop; see the E1 entry above.

## The group editor keeps permission keys it doesn't manage — `src/lib/components/admin/Users/Groups/EditGroupModal.svelte` (2026-09-24)

**What:** `init()` and `resetToDefaultsHandler()` spread the existing permissions object first
(`...loadedPermissions,` and `...permissions,`) before rebuilding the six vendor keys.

**Why:** the editor rebuilt `permissions` from workspace, sharing, access_grants, chat, features and
settings only, and saved that object whole. A Ruang Pimpinan grant lives under `jup`, so opening a
group and pressing Save with nothing changed deleted it. Reproduced in real Chrome on the local dev
server: the board-only reader's capabilities went from `["board"]` to `[]`. Reset to defaults dropped
it the same way. After the patch, both paths keep the grant.

**If dropped:** silent, and it fails closed. Any admin who edits a leadership group revokes its
readers' access without a warning.

**The test that catches it:** `tests/test_group_editor_keeps_jup_permissions.py`.

**Conflict risk:** low to moderate. Upstream adds permission categories to the rebuild now and then.
Keep the spread as the first line of both objects.

## The shared Modal can be named — `src/lib/components/common/Modal.svelte` (2026-09-24)

**What:** one optional prop, `ariaLabelledby`, rendered as `aria-labelledby` on the `role="dialog"`
element. Unset, the attribute is omitted, so every vendor modal renders exactly as before.

**Why:** the dialog had no accessible name, so a screen reader announced Ruang Pimpinan's source
details and context preview as just "dialog". Both now point at their `<h2>`, verified live as
"Rincian sumber" and "Pratinjau konteks untuk Asisten".

**If dropped:** silent. Svelte ignores the unknown prop, and the dialogs are unnamed again.

**The test that catches it:** `tests/test_modal_accessible_name.py`.

**Conflict risk:** low. Keep the prop and the attribute.

## Ruang Pimpinan's own migration graph runs at boot — `backend/open_webui/main.py` (2026-09-24)

**What:** two imports, `run_leadership_migrations` from `jup.leadership.migrate` and
`ENABLE_DB_MIGRATIONS` from `open_webui.env`, plus one guarded call,
`if ENABLE_DB_MIGRATIONS: run_leadership_migrations(engine)`. The call sits just before the fork
routers are mounted.

**Why:** leadership tables migrate on their own alembic graph with their own version table,
`jup_alembic_version` (ADR-0014), so a quarterly rebase can't give the vendor graph a second head.
The call runs on the vendor engine after the vendor upgrade. It never raises: a failure is logged
and leaves only Ruang Pimpinan unavailable.

**If dropped:** silent. The app boots, the leadership tables never get created, and the workflow
routes refuse with 503 because the schema is not ready.

**The test that catches it:** `tests/test_leadership_migration_seam.py` (source read, runs under
`--only-group dev`), and the boot test in `tests/test_boot.py`, which asserts `schema_ready()` after
a real import.

**Conflict risk:** low. Keep the call ahead of the `jup_leadership` mount.

## Everyday control names go through i18n — twelve vendor components (2026-09-25)

**What:** literal English `aria-label`s become `$i18n.t(...)` calls: "New Chat" and "Controls"
(`chat/Navbar.svelte`), "Available Tools", "Voice Input" and "Expand input" (`chat/MessageInput.svelte`),
"Voice Input" (`channel/MessageInput.svelte`), "Fork chat" (`ResponseMessage.svelte`), "Chat Menu"
(`Sidebar/ChatItem.svelte`, `SearchModal.svelte`), "Close" (`InputModal.svelte`,
`CodeEditorModal.svelte`), and the zoom controls in `PDFViewer`, `PptxPreview` and `DocxPreview`
(the first two gain an `i18n` context). The update toast's close button gains `type="button"` and
an `aria-label`.

**Why:** no translation can reach a string literal, so under id-ID a screen reader still said "New
Chat" or "Chat Menu". The toast's close button had no name at all, and it was the third tab stop on
every page (found in the keyboard pass, 2026-09-25). Admin-only screens, parameter names such as
`top_k`, and the `aria-label` on the sidebar's non-interactive "Loading" divs are left as they are.

**If dropped:** silent. The labels read in English again, and the toast button goes back to having
no name.

**The test that catches it:** `tests/test_vendor_aria_labels_translated.py`.

**Conflict risk:** low. These are one-attribute edits. On a conflict, take the vendor's line and
wrap the label again.

## The knowledge-review entry in the sidebar — `src/lib/components/layout/Sidebar.svelte` (2026-09-25)

**What:** two imports (`DocumentArrowUpIcon`, `kbReviewAccess`), two reactive lines (`showKbReview`,
`kbReviewActive`) and two `{#if showKbReview}` blocks linking to `/kb-review`. One is in the collapsed
rail and one in the expanded list, both right after Ruang Pimpinan. Each carries a translated
`aria-label`, `aria-current` and a Tooltip. The Portfolio and Ruang Pimpinan entries beside it are
the same kind of patch; this entry covers only the new one.

**Why:** the queue (ADR-0015) needs an entry point for staff with the `jup.kb.submit` grant and for
admins, who review. The entry is presentation only. The server re-checks the grant and the role on
every request.

**If dropped:** silent. `/kb-review` still works for anyone who types it, and nobody else finds it.

**The test that catches it:** `tests/test_sidebar_kb_review_entry.py` (source read, runs under
`--only-group dev`).

**Conflict risk:** moderate. Upstream edits `Sidebar.svelte` often, in both of these regions. Keep
both blocks and their imports.

## The approval gate decides before any tool runs — `backend/open_webui/utils/middleware.py` + `utils/tools.py` (2026-09-26)

`jup_tool_policy.decide(name, tool)` is called at each of the three places the vendor runs a
tool, before the tool's code or the browser's `execute:tool` event:

- the native tool loop's `execute_tool_call`, after the tool entry is resolved. A refusal returns
  the refusal text as the tool's result, and the gate's answer is kept in `jup_gate_approvals` for
  that call's audit line;
- `execute_tool_call_for_output`, which runs the calls a user approved in `ask` mode. The gate
  still decides after the user has: a user's approval is not a Risk Class. The answer travels to
  the drain's audit line as `jup_approval` in the returned dict;
- the legacy prompt-based `tool_call_handler`, where the existing `if tool.get('direct')` becomes
  an `elif` under `if not jup_gate.runs:`.

Each `audit_tool_call` now passes `approval=` (required, no default) and the line gains `approval`
and `approval_wait_ms`. A refused call audits as `outcome: refused`, `approval: rejected`. The
legacy code-interpreter block passes `approval='not_required'`: it is `execute_code`'s capability,
classed `read`, and is not a tool dispatch.

In `utils/tools.py:get_tools`, the DB tool's entry gains `'risk_class'`, read from
`tool.meta.manifest`. The vendor already copies a tool's frontmatter into `meta.manifest` on
create and update, so a native tool declares its class in its own source (`risk_class: read`) and
`deploy/gcp/sync-tools.ts` carries it by pushing the content. All policy is in `jup/tool_policy.py`.

**Why:** A5 + E5 ticket 1/7 (#18), ADR-0013. Every tool gets a Risk Class and, until the approval
card exists, every `external` call is refused, in `ask` and `full` mode alike.

**Deploy order:** the live `portfolio_status` row predates `risk_class`, so until
`sync-tools.ts` re-pushes it the gate reads it as `external` and refuses it. Run the sync straight
after the deploy that carries this patch.

**If dropped:** silent. Every tool runs ungated, `gate_probe` included, and nothing looks wrong.

**The test that catches it:** `tests/test_jup_tool_gate_presence.py` (each gate sits before the
code that runs the tool, and there are exactly three), plus
`test_each_audit_call_site_records_the_gates_answer` in `tests/test_jup_tool_call_audit.py`.
Removing any one gate fails at least two tests.

**Conflict risk:** moderate, for the same reason as the audit line: the tool loop changes upstream
often. Re-apply the gate after the tool entry and its params are resolved and before the
`direct_tool` branch.

## The decisions-register MCP server starts with the app — `backend/start.sh` (2026-09-26)

One line after `PYTHON_CMD` is set, before the final `exec`: `"$PYTHON_CMD" -m jup_mcp.decisions &`,
under a `JUP` comment. It starts the read-only decisions-register MCP server
(`backend/jup_mcp/decisions.py`) in the background. The server binds to 127.0.0.1 in code, with no
host setting, and reads `/srv/jup/DECISIONS.md` from the read-only records mount on every call
(`JUP_DECISIONS_FILE` and `JUP_DECISIONS_MCP_PORT`, default 8765, override that for tests).

**Why:** A5 + E5 ticket 5/7 (#19), D20's pre-approved class: JUP-hosted, read-only, no outbound
calls. It is not attached to the app until ticket 6/7 registers the tool-server connection.

**If dropped:** the app still boots, and the decisions tools fail once the connection is registered.
Nothing restarts the server if it dies, either; the same symptom, and the container restart fixes it.

**The test that catches it:** `tests/test_jup_decisions_mcp.py`
(`test_start_sh_starts_it_in_the_background_before_the_app`).

**Conflict risk:** low. `start.sh` changes rarely; keep the line above the final `exec`.
