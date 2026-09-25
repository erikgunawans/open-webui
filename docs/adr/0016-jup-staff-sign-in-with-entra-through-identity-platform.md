# JUP staff sign in with Entra through Identity Platform

**Status: Accepted 2026-09-26 — Erik Gunawan Supriatna, Director, Operation & Business
Development.** He chose the route (Entra via Identity Platform), approved the two-backend shape,
and decided that he also signs in through Entra.

ADR-0012 made IAP the login. IAP authenticates Google identities only, and JUP staff sign in to
Microsoft 365 (`jakarta-utilitas.com`, MX `mail.protection.outlook.com`). Serving the app at
`non-jupe.jup.co.id` (the ADR-0012 amendment) did not change that. Erik chose the route that keeps
staff on the Microsoft account they already have: **Microsoft Entra ID as an OIDC provider in Google
Cloud Identity Platform, with IAP switched to external identities.**

## What the platform imposes

These come from Google's documentation and shape everything after them:

- External identities are set **per IAP resource**, which is the backend service `ent-os-backend`.
  Both hostnames share it today, so switching it switches them both.
- **"You cannot use IAM for authorization when using external identities."** The current gate,
  `roles/iap.httpsResourceAccessor` for `user:erik@axiara.ai`, stops applying. Whoever can
  complete a sign-in with an enabled provider gets past IAP.
- The identity header becomes `securetoken.google.com/<project>[/<tenant>]:<email>`.
  `backend/jup/iap_identity.py` already strips everything up to the last colon, which was written
  with this prefix in mind, so the three vendor read sites still see a bare address.
- Switching back to Google identities is supported, but it clears the sign-in URL and the
  provider/tenant selection.

## Decision (proposed)

1. **Two IAP resources, one app.** Add a second serverless NEG and backend service,
   `ent-os-backend-jup`, pointing at the same Cloud Run service, and give the URL map a host rule:
   `non-jupe.jup.co.id` → `ent-os-backend-jup` (external identities, Entra only), everything else →
   `ent-os-backend` (unchanged: Google identities, IAM). Erik's `ops.axiara.ai` access and the
   in-tab admin tooling keep working throughout, and the Entra path can be proven on the JUP
   hostname without touching the path that works today. The cost is one more backend service,
   which has no standing charge beyond the forwarding rule that already exists.
2. **Only the JUP tenant signs in.** The Entra app registration is single-tenant (JUP's tenant),
   and it is the only provider enabled for `ent-os-backend-jup`. No Google provider is added: it
   would admit every Google account in the world to the app's front door.
3. **The app is still the gate that matters.** Losing IAM at the edge means "is a JUP employee"
   replaces "is on the list". A first sign-in creates the account as `pending`, as it does now,
   and only an admin approval turns it into a working account. Grants such as `jup.kb.submit`
   follow approval, as before.
4. **IAP hosts the sign-in page.** No extra service to deploy or maintain. A custom page is an
   option later if JUP wants its own branding.
5. **The address comes from the Entra `email` claim.** It must equal the staff member's
   `@jakarta-utilitas.com` mail address. This is confirmed with the first real sign-in, before
   anyone is approved.

## Order of work

Each production step is its own OK, with before-values recorded.

1. JUP IT registers the app in Entra (see `deploy/gcp/entra-request-jup-it.md`), then sends the
   tenant ID, client ID and client secret through a secure channel.
2. Enable Identity Platform on `jup-ops` and add the OIDC provider (issuer
   `https://login.microsoftonline.com/<tenant-id>/v2.0`, code flow).
3. Create the NEG, `ent-os-backend-jup` and the host rule. Enable IAP on the new backend with
   external identities and the IAP-hosted page.
4. One JUP person signs in. Check the header value that reaches the app, the account that was
   created, and its `pending` state. Approve that account.
5. Then the five contributors: approval, then the "Kontributor Pengetahuan" group.

Rollback at any point: remove the host rule, and `non-jupe.jup.co.id` falls back to the Google
path on `ent-os-backend`.

## Erik signs in through Entra too (decided 2026-09-26)

He needs an account in JUP's tenant. His app account is `erik@axiara.ai`, and a first Entra sign-in
under a JUP address would create a **second**, `pending` account with none of his chats, grants or
admin role. So before his first Entra sign-in, the address on his existing account is changed to
the JUP one, and the JUP address is added to `JUP_ADMIN_EMAILS`. Each of those is a production
write, with its own OK and before-values. `ops.axiara.ai` can be retired only after his Entra
sign-in works.

## Progress

- 2026-09-26: Identity Platform enabled and initialized on `jup-ops` (`identitytoolkit.googleapis.com`).
  No providers are enabled. The auth domain is `jup-ops.firebaseapp.com`, which confirms the
  redirect URI in the JUP IT request.
