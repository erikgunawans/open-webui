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
