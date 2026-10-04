#!/usr/bin/env bash
# Build jup-gateway on Cloud Build and deploy it to Cloud Run (E7.6, #90).
#
# The approved shape (Erik, 2026-10-04): asia-southeast2, CPU always allocated, min 0, max 2.
# It runs AS jup-gateway, which signs its own Identity Platform token for IAP (#86); IAM on
# ent-os does nothing for it. Ingress is public with the invoker check off, because the org
# policy blocks an allUsers binding: the gateway verifies every Teams request itself.
#
# Secrets come from Secret Manager, never this file or the env: the HMAC key and the Identity
# Platform browser key. Teams stays closed (every request 401) until BOT_APP_ID, the
# bot-app-secret secret and JUP_TENANT_ID exist (E8, #82): set BOT_APP_ID and JUP_TENANT_ID here
# when JUP IT sends them.
#
# SELFCHECK=1 makes the new revision prove its identity through IAP once at start (on behalf of
# SELFCHECK_ON_BEHALF_OF): 422 at the Channel endpoint, 403 elsewhere; read the `selfcheck` log
# line. The next plain deploy drops it.
set -euo pipefail

PROJECT="${PROJECT:-jup-ops}"
REGION="${REGION:-asia-southeast2}"
SERVICE="${SERVICE:-jup-gateway}"
SA="jup-gateway@$PROJECT.iam.gserviceaccount.com"
REPO="asia-southeast2-docker.pkg.dev/$PROJECT/ent-os/jup-gateway"
ENTOS_URL="${ENTOS_URL:-https://non-jupe.jup.co.id}"
BOT_APP_ID="${BOT_APP_ID:-}"
JUP_TENANT_ID="${JUP_TENANT_ID:-}"
SHA="$(git rev-parse --short HEAD)"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

[ -z "$(git status --porcelain -- "$ROOT/gateway" "$0")" ] || { echo "refusing to deploy a dirty gateway/" >&2; exit 1; }

echo "==> building $REPO:$SHA"
gcloud builds submit "$ROOT/gateway" --project="$PROJECT" --region=global --tag="$REPO:$SHA" --timeout=900s

ENV="ENTOS_URL=$ENTOS_URL,GATEWAY_SERVICE_ACCOUNT=$SA"
SECRETS="GATEWAY_HMAC_KEY=gateway-hmac-key:latest,IDENTITY_PLATFORM_API_KEY=identity-platform-browser-key:latest"
if [ -n "$BOT_APP_ID" ] && [ -n "$JUP_TENANT_ID" ]; then
  ENV="$ENV,BOT_APP_ID=$BOT_APP_ID,JUP_TENANT_ID=$JUP_TENANT_ID"
  SECRETS="$SECRETS,BOT_APP_SECRET=bot-app-secret:latest"
fi
if [ "${SELFCHECK:-}" = "1" ]; then
  ENV="$ENV,SELFCHECK_ON_BEHALF_OF=${SELFCHECK_ON_BEHALF_OF:-erik@jakarta-utilitas.com}"
fi

echo "==> deploying $SERVICE"
gcloud run deploy "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --image="$REPO:$SHA" --service-account="$SA" \
  --ingress=all --no-invoker-iam-check \
  --no-cpu-throttling --min-instances=0 --max-instances=2 \
  --cpu=1 --memory=512Mi --timeout=300 --concurrency=20 \
  --set-env-vars="$ENV" --set-secrets="$SECRETS"

echo "==> deployed: $(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" --format='value(status.url)')"
