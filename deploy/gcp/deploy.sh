#!/usr/bin/env bash
# Build ent-os on Cloud Build and deploy it to Cloud Run.
set -euo pipefail

PROJECT="${PROJECT:-jup-ops}"
REGION="${REGION:-asia-southeast2}"
SERVICE="${SERVICE:-ent-os}"
INSTANCE="${INSTANCE:-jup-ops-db}"
REPO="asia-southeast2-docker.pkg.dev/$PROJECT/ent-os/ent-os"
SHA="$(git rev-parse --short HEAD)"

[ -z "$(git status --porcelain)" ] || { echo "refusing to deploy a dirty tree" >&2; git status --short >&2; exit 1; }

echo "==> building $REPO:$SHA"
gcloud builds submit --project="$PROJECT" --region="$REGION" \
  --tag="$REPO:$SHA" --timeout=3600s --machine-type=e2-highcpu-8

# DATABASE_URL is NOT assembled here. The whole connection string lives in the `database-url`
# secret and reaches the service as a secret reference (#11). Building it here from `db-password`
# is what put the production credential in plaintext on the service in the first place, readable
# to every `run.viewer` — so the lookup is deliberately gone, not merely unused.
#
# The secret embeds the instance's private IP. If `jup-ops-db` is ever recreated and lands on a
# different address, add a new version of `database-url` — this script will not notice.

# An env-vars FILE, not --set-env-vars: the values below are plain, but the file form is kept so
# adding a value containing '@' or ':' later does not hit "Bad syntax for dict arg".
ENVFILE="$(mktemp)"; trap 'rm -f "$ENVFILE"' EXIT
umask 077
cat > "$ENVFILE" <<EOF
VECTOR_DB: "pgvector"
STORAGE_PROVIDER: "gcs"
GCS_BUCKET_NAME: "jup-ops-data"
JUP_RECORDS_DIR: "/srv/jup/records"
JUP_ARTEFACT_ROOT: "/srv/jup"
ENABLE_SIGNUP: "False"
DEFAULT_USER_ROLE: "pending"
ENV: "prod"
EOF

echo "==> deploying to Cloud Run"
gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --image="$REPO:$SHA" \
  --port=8080 --cpu=2 --memory=4Gi --timeout=600 \
  --min-instances=1 --max-instances=4 \
  --no-allow-unauthenticated \
  --ingress=internal-and-cloud-load-balancing \
  --network=default --subnet=default --vpc-egress=private-ranges-only \
  --add-volume="name=jup,type=cloud-storage,bucket=jup-ops-records,readonly=true" \
  --add-volume-mount="volume=jup,mount-path=/srv/jup" \
  --set-secrets="WEBUI_SECRET_KEY=webui-secret-key:latest,DATABASE_URL=database-url:latest" \
  --env-vars-file="$ENVFILE"

rm -f "$ENVFILE"

echo "==> deployed. URL is reachable only through the load balancer / IAP:"
gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --format='value(status.url)'
