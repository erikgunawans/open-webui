# Should IAP be the login?

**Status: Accepted 2026-09-19 — Erik Gunawan Supriatna, Director, Operation & Business
Development.** Option 3. The analysis that produced it is kept below unchanged, including the
finding that ruled out option 2. Issue #14.

`https://ops.axiara.ai` authenticates twice. IAP authenticates at the load balancer, and then Open
WebUI authenticates again against its own password record. Erik holds a password for an application
that cannot be reached without having already proved who he is to Google.

`WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Goog-Authenticated-User-Email` collapses the two: the app trusts
the IAP-verified header and creates or authenticates from it, with no password and no signup window
ever. That is the mechanism ADR-0010 implies — if there are no external seats, the seat list and the
IAP access list are the same list, and keeping two of them is a way for them to disagree.

The signup window is the part that argues for changing. Standing IAP up required setting
`ENABLE_SIGNUP=True` for one revision and being first to the door. It worked — the fork promotes the
only user to `admin` and closes the window in the same transaction, and a probe confirmed `user` and
`auth` were both empty first — but it is a manoeuvre, not a mechanism, and it does not survive
needing a second person.

## The prefix problem, and the part that was missed

IAP sends `accounts.google.com:erik@axiara.ai`, not `erik@axiara.ai`. The fork never strips it:

```python
# routers/auths.py:736
email = request.headers[WEBUI_AUTH_TRUSTED_EMAIL_HEADER].lower()
```

**The header is read in three places, not one.** #14 and the session notes that preceded it both
describe this as a patch to `auths.py:731`. It is not:

| Site | What it does |
|---|---|
| `routers/auths.py:393` | refuses password changes in trusted-header mode |
| `routers/auths.py:736` | creates and authenticates from the header |
| `utils/auth.py:415` | **re-checks the header against `user.email` on every request** |

The third is load-bearing and it is the one nobody has costed:

```python
# utils/auth.py:415
if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
    trusted_email = request.headers.get(WEBUI_AUTH_TRUSTED_EMAIL_HEADER, '').lower()
    if trusted_email and user.email != trusted_email:
        raise HTTPException(401, detail='User mismatch. Please sign in again.')
```

**A patch to the signin path alone does not produce a malformed account — it bricks the
deployment.** Strip the prefix at `auths.py:736` and the account is created correctly as
`erik@axiara.ai`; then every subsequent request compares `erik@axiara.ai` against the raw
`accounts.google.com:erik@axiara.ai`, mismatches, and 401s. The symptom is being signed out
immediately after signing in, on every request, presenting as a session bug rather than as a
prefix bug. Whoever implements the ticket as currently written walks into this.

This roughly doubles the vendor-patch surface and moves part of it into `utils/auth.py`, which is
hotter than `auths.py` on upstream. Under ADR-0007 that cost is re-paid every quarter.

## Considered options

**1. Ratify the status quo.** Two auth layers, deliberately. Costs nothing today and keeps the
vendor tree clean. Leaves the signup window as the only way to admit a second person — open it,
race to it, close it — which is the thing that does not scale past one.

**2. Vendor-patch both read sites.** Strip the prefix in `auths.py:736` and `utils/auth.py:416`.
Direct, and wrong in the way that compounds: two files, three sites, one of which silently
invalidates every session if the rebase drops it. `VENDOR-PATCHES.md` carries the `NODE_OPTIONS`
patch today with no test guarding it; a lost `NODE_OPTIONS` patch fails the build loudly, and a lost
auth patch fails as a login loop in production.

**3. A fork-owned ASGI middleware that normalizes the header once.** Fork-owned Python lives in
`backend/jup/`. A middleware that rewrites `X-Goog-Authenticated-User-Email` to its bare address
before routing means **all three sites read a clean value and none of them is patched.** The vendor
surface shrinks to one registration line in `main.py` — a line whose absence is detectable by a test
rather than by a user being logged out. This is the only option that reduces the ADR-0007 burden
instead of adding to it. The normalization belongs to us: the prefix is IAP's convention, and
translating a vendor's convention at our own boundary is fork-owned work by definition.

**4. A Service Extension at the load balancer.** Traffic extensions can mutate request headers
before the backend sees them, so the app would need no change at all. It costs a new GCP component,
a callout service to run, per-request latency and standing spend — against a deployment whose
current monthly cost is roughly $35–60 in total. Disproportionate for stripping a prefix.

**Custom request headers cannot do this.** Worth recording because it is the obvious first idea and
it does not work: LB custom headers expand only load-balancer-provided variables (geography, TLS
parameters) plus `origin_request_header`. There is no variable referencing an arbitrary inbound
header and no substring or rewrite facility. The load balancer can *overwrite* a header with a
static value; it cannot *derive* one from what the client sent.

## What the decision settled

**The mechanism: option 3, a fork-owned ASGI middleware.** It normalizes
`X-Goog-Authenticated-User-Email` to its bare address before routing, so all three read sites see a
clean value and none of them is patched. The deciding argument is not cost, it is the shape of the
failure: option 2's lost patch is a production login loop that reads as a session bug, and option
3's is a missing registration line that a test catches. An outage you can misdiagnose is worse than
one you cannot.

**`admin` is assigned from an explicit allowlist**, read by fork-owned code in `backend/jup/`
alongside the middleware. The admin set stops being a side effect of which row was inserted first.
"Be the only row in the table" was a manoeuvre, and the same objection the ADR raises against the
signup window applies to it.

**`DEFAULT_USER_ROLE=pending` stays.** IAP access and operating-layer access remain separable: a
person can be admitted to the app without being handed the admin role the operating layer requires.
That keeps the 403 path meaningful (ADR-0010's reading of the operating layer as an admin-role
surface), and it costs nothing while exactly one user exists.

**The existing `erik@axiara.ai` account is migrated and its password record left dormant.** The row
holds `admin` and all existing data, so it is kept rather than recreated. The password is not
cleared: `auths.py:393` already refuses password changes in trusted-header mode, and
`--ingress=internal-and-cloud-load-balancing` means there is no path to the app that bypasses IAP.
Clearing it would be a data change to the vendor's user table, needing its own migration and test,
to close a hole that the ingress setting already closes. **If ingress is ever loosened, that
reasoning expires and the password must be cleared** — recorded here because the dependency is not
visible from the user table.

**ADR-0001's fifty-seat ceiling does not move.** It is a licensing limit, not a capacity one, so
nothing here touches the number. What changes is that it becomes countable at a better place: the
seat list is now the set of `iap.httpsResourceAccessor` principals, which sits upstream of the app
rather than inside its user table. Bindings are standing while the ceiling counts end users over a
rolling thirty days, so counting bindings over-counts — the conservative direction for a license
ceiling, and the right one to err in.

## Consequences

Whichever is chosen, if a vendor patch survives into it, `VENDOR-PATCHES.md` gains an entry **and a
test that fails when the patch is lost.** The `NODE_OPTIONS` precedent is not the model to copy
here: a build that fails is an inconvenience, and an auth path that fails is an outage that looks
like a session bug.

Nothing here is implemented. This ADR produces a decision; a separate ticket implements it.
