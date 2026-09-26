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

His JUP tenant account already exists: `erik@jakarta-utilitas.com`. His app account is `erik@axiara.ai`, and a first Entra sign-in
under a JUP address would create a **second**, `pending` account with none of his chats, grants or
admin role. So before his first Entra sign-in, the address on his existing account is changed to
`erik@jakarta-utilitas.com`, and that address is added to `JUP_ADMIN_EMAILS`.

**The rename is a cutover, not a preparation step.** An account holds one address. After the
rename, a visit to `ops.axiara.ai` still presents `erik@axiara.ai`, which no longer matches any
account, so the app creates a fresh one. Because `erik@axiara.ai` is on `JUP_ADMIN_EMAILS`, that
fresh account is an empty admin. So the rename happens only once the Entra path is proven on
`non-jupe.jup.co.id`, immediately before his first Entra sign-in. After that, he stops using
`ops.axiara.ai` and `erik@axiara.ai` comes off `JUP_ADMIN_EMAILS`. Each of those is a production
write, with its own OK and before-values. `ops.axiara.ai` can be retired only after his Entra
sign-in works.

## Progress

- 2026-09-26: Identity Platform enabled and initialized on `jup-ops` (`identitytoolkit.googleapis.com`).
  No providers are enabled. The auth domain is `jup-ops.firebaseapp.com`, which confirms the
  redirect URI in the JUP IT request.
- 2026-09-26: JUP IT sent tenant ID `fc521bfb-40c2-4b87-95a7-65e0e888fdf8` (verified as
  `jakarta-utilitas.com` by public discovery) and client ID `095f7f79-2430-4cff-8363-560bb063b3e1`.
  The first secret arrived in a plain-text file and passed through a Claude session, so Erik chose to
  rotate it before cutover. `deploy/gcp/entra-provider.sh` creates provider `oidc.entra-jup` from a
  secret pasted into a real terminal (and replaces only the secret on later rotations). Before-values:
  `.planning/entra-before-2026-09-26.json` (no providers).
- 2026-09-26: **Step 3b done, with a deviation.** The org policy `iam.allowedPolicyMemberDomains`
  blocks `allUsers`, so the Console's "create a sign-in page for me" cannot grant public access and
  rolls itself back. The sign-in page is instead self-deployed as
  `iap-gcip-hosted-ui-ent-os-backend-jup` (Google's `gcr.io/gcip-iap/authui`, `--no-invoker-iam-check`,
  own service account with only `roles/identitytoolkit.viewer`, config in `UI_CONFIG`, admin panel
  off) and attached with "Use an existing hosted sign-in page". The planned `allUsers` IAP accessor
  grant was dropped: the same policy blocks it, and IAP enforces no IAM under external identities.
  JUP IT's app registration is named **None-Jupe**; the hosted page's `/__/auth/handler` is a
  registered redirect URI; admin consent is granted; the client secret was replaced.
- 2026-09-26: **Step 3c done.** `non-jupe.jup.co.id` routes to `ent-os-backend-jup`. Erik's account
  was renamed to `erik@jakarta-utilitas.com` immediately before his first Entra sign-in, which matched
  it (no signup). `ops.axiara.ai` now 302-redirects to `non-jupe.jup.co.id`, and `erik@axiara.ai` is
  off `JUP_ADMIN_EMAILS`. Step 4's header check is satisfied by Erik's sign-in; the five contributors
  already hold `user` accounts that Erik created, so for them `pending` is not a gate.
