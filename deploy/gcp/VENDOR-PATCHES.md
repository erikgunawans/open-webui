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
