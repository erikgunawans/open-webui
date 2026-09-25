# Putting IAP in front of ent-os

Cloud Run is deployed with `--no-allow-unauthenticated` and
`--ingress=internal-and-cloud-load-balancing`, so the `run.app` URL refuses everyone. The only
path in is a global external load balancer with IAP on its backend service.

This is the ADR-0010 shape: there is no unauthenticated surface at all, and access is a named
grant per person rather than a link that works for whoever holds it.

## What you need first

- **A domain you control.** `ops.axiara.ai` is the obvious choice. IAP needs a real hostname —
  a managed certificate cannot be issued for `run.app`.
- **DNS you can edit.** axiara.ai is on Cloudflare, so the A record goes there. It must be
  **DNS-only (grey cloud)** — if Cloudflare proxies it, Google cannot validate the certificate
  and the managed cert stays stuck in PROVISIONING forever.

## Steps

```sh
PROJECT=jup-ops; REGION=asia-southeast2; DOMAIN=ops.axiara.ai

# 1. Serverless NEG pointing at the Cloud Run service
gcloud compute network-endpoint-groups create ent-os-neg \
  --region=$REGION --network-endpoint-type=serverless \
  --cloud-run-service=ent-os --project=$PROJECT

# 2. Backend service
gcloud compute backend-services create ent-os-backend \
  --global --load-balancing-scheme=EXTERNAL_MANAGED --project=$PROJECT
gcloud compute backend-services add-backend ent-os-backend \
  --global --network-endpoint-group=ent-os-neg \
  --network-endpoint-group-region=$REGION --project=$PROJECT

# 3. Static IP, certificate, and the front end
gcloud compute addresses create ent-os-ip --global --project=$PROJECT
gcloud compute ssl-certificates create ent-os-cert \
  --domains=$DOMAIN --global --project=$PROJECT
gcloud compute url-maps create ent-os-lb --default-service=ent-os-backend --project=$PROJECT
gcloud compute target-https-proxies create ent-os-proxy \
  --url-map=ent-os-lb --ssl-certificates=ent-os-cert --project=$PROJECT
gcloud compute forwarding-rules create ent-os-fr \
  --global --target-https-proxy=ent-os-proxy --ports=443 \
  --address=ent-os-ip --load-balancing-scheme=EXTERNAL_MANAGED --project=$PROJECT

# 4. Point DNS at it (grey cloud), then wait for the cert
gcloud compute addresses describe ent-os-ip --global --project=$PROJECT --format='value(address)'
gcloud compute ssl-certificates describe ent-os-cert --global --project=$PROJECT \
  --format='value(managed.status)'   # wait for ACTIVE — can take 15-60 min after DNS resolves

# 5. Turn IAP on and grant people access, one at a time
gcloud iap web enable --resource-type=backend-services \
  --service=ent-os-backend --project=$PROJECT
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services --service=ent-os-backend \
  --member='user:erik@axiara.ai' --role='roles/iap.httpsResourceAccessor' --project=$PROJECT

# 6. Let IAP's service account actually invoke Cloud Run
PN=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
gcloud run services add-iam-policy-binding ent-os \
  --region=$REGION --project=$PROJECT \
  --member="serviceAccount:service-$PN@gcp-sa-iap.iam.gserviceaccount.com" \
  --role=roles/run.invoker
```

## Three things that bite (all hit on 2026-09-19)

**There is no OAuth brand to configure.** Earlier versions of this runbook said to set up a consent
screen first. The IAP OAuth Admin APIs were shut down on 2026-03-19, and `gcloud iap web enable`
with no `--oauth2-client-id` now uses a Google-managed OAuth client. `gcloud iap oauth-brands list`
returns nothing and prints a deprecation warning — that is expected, not a failure. Just run
step 5 as written.

**`cloudresourcemanager.googleapis.com` must be enabled**, or step 5's
`add-iam-policy-binding` fails with `SERVICE_DISABLED` buried at the bottom of a long error block
that otherwise looks like a permissions problem:

```sh
gcloud services enable cloudresourcemanager.googleapis.com --project=$PROJECT
```

**The IAP service agent does not exist until you ask for it.** Step 6 fails with
`Service account service-$PN@gcp-sa-iap.iam.gserviceaccount.com does not exist`, which reads like a
typo in the address but is not — the agent is created lazily. Create it first:

```sh
gcloud beta services identity create --service=iap.googleapis.com --project=$PROJECT
```

## Adding someone later

One command per person — step 5's second call with their address. There is no signup, no invite
link, and no self-service path. That is deliberate.

## Cost

The load balancer forwarding rule is the standing charge, roughly **$18/month**, and it applies
whether or not anyone visits. It buys the property that no unauthenticated request ever reaches
the application.

## What is actually deployed (2026-09-19)

| Resource | Name | Value |
|---|---|---|
| Serverless NEG | `ent-os-neg` | region `asia-southeast2` → Cloud Run `ent-os` |
| Backend service | `ent-os-backend` | global, `EXTERNAL_MANAGED`, **IAP enabled** |
| Static IP | `ent-os-ip` | **34.111.8.177** |
| Managed cert | `ent-os-cert` | `ops.axiara.ai` (fallback since 2026-09-25) |
| Managed cert | `ent-os-cert-jup` | **`non-jupe.jup.co.id`**, added 2026-09-25 |
| URL map / proxy / rule | `ent-os-lb` / `ent-os-proxy` / `ent-os-fr` | port 443 |
| IAP grant | `roles/iap.httpsResourceAccessor` | `user:erik@axiara.ai` |
| Run invoker | `roles/run.invoker` | `service-1001937491646@gcp-sa-iap.iam.gserviceaccount.com` |

**The address is `https://non-jupe.jup.co.id` since 2026-09-25** (Erik's call). `jup.co.id` DNS is
hosted at Indowebsite; JUP IT added `non-jupe A 34.111.8.177`. The URL map has no host rules, so
every hostname on the IP reaches the app, and nothing inside the app is tied to a hostname. The proxy
carries both certs; `ops.axiara.ai` stays as a fallback until Erik retires it (detach `ent-os-cert`,
delete it, remove the `ops` record).

Only port 443 has a forwarding rule. `http://ops.axiara.ai` will not answer at all — there is no
port-80 rule and no redirect, because a second forwarding rule is a second standing charge.

## Getting the first account

`ENABLE_SIGNUP=False` and `DEFAULT_USER_ROLE=pending` on the Cloud Run service, and the database has
no users, so nobody can get in even once the certificate is live. There are two ways to create the
first account, and they differ in kind, not just in effort.

**The signup window.** Set `ENABLE_SIGNUP=True`, sign up, and the fork closes the window itself:
`signup_handler` in `routers/auths.py:875` promotes the only user to `admin` and writes
`ui.enable_signup = False` back to config in the same breath. So the window shuts on its own, and
IAP means only the one granted account could have reached it anyway. Then revert the env var so a
later revision does not reopen it.

**IAP as the login.** Setting `WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Goog-Authenticated-User-Email`
makes `routers/auths.py:731` create and authenticate the user straight from the IAP-verified header
— no password, no signup window, and the account is the Google identity rather than a shared
secret. This is the better shape, and it is what ADR-0010 is reaching for, but it **needs a fork
change first**: IAP prefixes the value (`accounts.google.com:erik@axiara.ai`) and the fork does not
strip it, so the account would be created under a malformed address. Stripping it means editing
vendor `auths.py`, which is an ADR-0007 rebase burden and belongs in `VENDOR-PATCHES.md`.

**That description is incomplete — see ADR-0012 (#14) before acting on it.** The header is read in
three places, not one, and `utils/auth.py:415` re-checks it against `user.email` on *every* request.
Patching only the signin path therefore does not create a malformed account: it creates a correct
account and then 401s every request against it, presenting as a session bug. ADR-0012 costs that
properly and sets out a fork-owned middleware that normalizes the header once, leaving all three
vendor sites unpatched. **Accepted 2026-09-19: option 3, the middleware.** `admin` comes from an
explicit allowlist rather than from being the first row, `DEFAULT_USER_ROLE=pending` stays, and the
existing account is migrated with its password left dormant — dormant *because* ingress is
`internal-and-cloud-load-balancing`, so loosening ingress obliges clearing it. Nothing is
implemented yet; the ticket is the work.

Forging that header is not a risk here as long as Cloud Run keeps
`--no-allow-unauthenticated` with `--ingress=internal-and-cloud-load-balancing` and only the IAP
service agent holds `run.invoker`: the header cannot arrive except from IAP, which strips inbound
copies of its own headers.
