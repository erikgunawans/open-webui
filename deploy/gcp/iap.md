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

The OAuth consent screen must exist before step 5; if `iap web enable` complains about a missing
brand, configure it once in the console under **APIs & Services → OAuth consent screen** (Internal,
if axiara.ai is a Workspace domain).

## Adding someone later

One command per person — step 5's second call with their address. There is no signup, no invite
link, and no self-service path. That is deliberate.

## Cost

The load balancer forwarding rule is the standing charge, roughly **$18/month**, and it applies
whether or not anyone visits. It buys the property that no unauthenticated request ever reaches
the application.
