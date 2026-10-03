#!/usr/bin/env bash
# Build ent-os on Cloud Build and deploy it to Cloud Run.
set -euo pipefail

PROJECT="${PROJECT:-jup-ops}"
REGION="${REGION:-asia-southeast2}"
# The BUILD pool is deliberately NOT $REGION: E2_HIGHCPU_32 is quota-blocked in
# asia-southeast2 on this project but available globally, and the global pool is where the
# only build that has ever succeeded here (2026-09-19) actually ran. The deploy below still
# targets $REGION; only the build is global.
#
# This is a quota and speed choice, NOT a fix for the "failed to parse platform" failure --
# that one reproduces identically in both pools and is fixed in the Dockerfile. Do not read
# the split as making the build work. See VENDOR-PATCHES.md.
#
# Machine size is likewise not a memory fix: the vite OOM is node's own heap cap and failed
# identically on 8 GB and 32 GB. NODE_OPTIONS in the Dockerfile is what fixes that.
BUILD_REGION="${BUILD_REGION:-global}"
BUILD_MACHINE="${BUILD_MACHINE:-e2-highcpu-32}"
SERVICE="${SERVICE:-ent-os}"
INSTANCE="${INSTANCE:-jup-ops-db}"
# Who holds `admin`, per ADR-0012. Overridable here rather than hardcoded below because the admin
# set is the one value on this service that changes for reasons unrelated to a code change.
# Erik signs in through Entra as erik@jakarta-utilitas.com since 2026-09-26 (ADR-0016 3c). erik@axiara.ai
# came off the same day: ops.axiara.ai now redirects to non-jupe, and leaving the old address here
# would promote any account the old Google path ever recreated into an empty admin.
ADMIN_EMAILS="${JUP_ADMIN_EMAILS:-erik@jakarta-utilitas.com}"
REPO="asia-southeast2-docker.pkg.dev/$PROJECT/ent-os/ent-os"
SHA="$(git rev-parse --short HEAD)"

[ -z "$(git status --porcelain)" ] || { echo "refusing to deploy a dirty tree" >&2; git status --short >&2; exit 1; }

# SKIP_BUILD=1 deploys the image already built for this commit instead of building it again: the
# recovery when a run died after Cloud Build finished but before the Cloud Run step (closing the
# terminal or a session restart kills this script; Cloud Build carries on without it). The image
# must exist for this exact commit, or nothing is deployed.
if [ "${SKIP_BUILD:-}" = "1" ]; then
  echo "==> SKIP_BUILD=1: deploying the existing $REPO:$SHA"
  gcloud artifacts docker images describe "$REPO:$SHA" --project="$PROJECT" --format='value(image_summary.digest)' >/dev/null \
    || { echo "no image $REPO:$SHA in the registry; run without SKIP_BUILD" >&2; exit 1; }
else
  echo "==> building $REPO:$SHA"
  gcloud builds submit --project="$PROJECT" --region="$BUILD_REGION" \
    --tag="$REPO:$SHA" --timeout=3600s --machine-type="$BUILD_MACHINE"
fi

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
# The contract KB bucket (Jakarta), mounted read-only: drafted cards, OCR text and PDFs (D5).
JUP_CONTRACTS_DIR: "/srv/legal-kb"
ENABLE_SIGNUP: "False"
DEFAULT_USER_ROLE: "pending"
ENV: "prod"
# Indonesian first: a browser with no saved language opens in Bahasa Indonesia. One already
# holding a locale in localStorage keeps it; Settings > General switches it.
DEFAULT_LOCALE: "id-ID"
# The product name, shown as-is: the " (Open WebUI)" suffix is patched out of env.py. Replacing
# the branding at all rests on LICENSE clause 4 and the fifty-user ceiling (ADR-0001).
WEBUI_NAME: "None-JUPe"
# Agentic-capabilities plan, Phase 0 (2026-09-23).
# There is no Ollama backend. This value only SEEDS the DB key ollama.enable on a fresh database;
# on the live DB the key already exists and was switched off through the admin API. The
# passthrough routes refuse regardless (jup.governance.refuse_passthrough).
ENABLE_OLLAMA_API: "False"
# The two below are read from the environment on every boot and are not DB-seeded.
# Tools run as Python in the backend. Saving one must not also pip-install into the image.
ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS: "False"
# The embedding models are baked into the image; the auto-update reached HuggingFace on every boot.
RAG_EMBEDDING_MODEL_AUTO_UPDATE: "False"
# multilingual-e5 is trained with these prefixes and loses recall without them. Read from the
# environment on every boot (not DB-seeded). Only correct while the DB embedding model is an e5 model.
RAG_EMBEDDING_QUERY_PREFIX: "query: "
RAG_EMBEDDING_CONTENT_PREFIX: "passage: "
# Erik's call 2026-09-25. The admin-only "new version available" toast pointed at upstream Open
# WebUI releases, which nobody here acts on (upstream moves by quarterly rebase, ADR-0007), and each
# check called api.github.com from the server. Off, /api/version/updates answers current=latest.
ENABLE_VERSION_UPDATE_CHECK: "False"
# ADR-0012, the IAP login. This header is set by IAP itself and cannot be spoofed from outside,
# because --ingress=internal-and-cloud-load-balancing above means there is no path to the service
# that does not pass through the load balancer. LOOSENING THAT INGRESS MAKES THIS HEADER A LOGIN
# BYPASS, and also obliges clearing the dormant password on the existing account — a dependency
# that is invisible from the user table, which is why it is written down in both places.
#
# The value arrives prefixed (accounts.google.com:erik@axiara.ai). IapIdentityHeaderMiddleware
# strips that in the ASGI scope before any vendor code reads it; see VENDOR-PATCHES.md.
#
# No backticks anywhere in this heredoc: the delimiter is unquoted so that $ADMIN_EMAILS expands,
# which leaves command substitution live for everything else, comments included.
WEBUI_AUTH_TRUSTED_EMAIL_HEADER: "X-Goog-Authenticated-User-Email"
# DEFAULT_USER_ROLE stays "pending" above: being admitted by IAP and holding the admin role the
# operating layer requires stay separable, which is what keeps the 403 path meaningful.
JUP_ADMIN_EMAILS: "$ADMIN_EMAILS"
# Admins cannot open other people's chats (Erik's call, 2026-09-26). The chat home tells every
# user their conversations are saved in their own history and says nothing about admins reading
# them; turning this back on makes that copy (Placeholder.svelte) incomplete, so change both.
ENABLE_ADMIN_CHAT_ACCESS: "false"
# Ruang Pimpinan, enabled 2026-09-24 with Erik's OK. The file is the ILLUSTRATIVE P1 sample
# (tests/fixtures/leadership/illustrative-seed.json), outside the records/ tree that
# sync-records.sh mirrors with delete, so a record sync never removes it. Access still needs a
# group grant: the admin role grants nothing. Remove both lines to switch the section off.
JUP_LEADERSHIP_ENABLED: "true"
JUP_LEADERSHIP_SAMPLE_FILE: "/srv/jup/leadership/illustrative-seed.json"
# P2, Erik's call 2026-09-25: the action register is the records store (empty until actions are
# recorded, and it says so), not the deck sample. JUP_LEADERSHIP_BOD_POLICY and
# JUP_LEADERSHIP_PUBLICATION_POLICY are deliberately absent: BOD closure and publication stay off
# (503, every snapshot a draft) until the company decides individual/collective closure and
# publication authority. Evidence files go to jup-ops-data under a temporary hold (proven 09-25).
JUP_LEADERSHIP_ACTIONS_SOURCE: "records"
# Voice (ADR-0017, D16/D21/D22), switched on 2026-09-28 with Erik's OK (#30). The switch alone
# gives no one a call: it also needs the jup.voice.call group grant (Erik only at launch, D22).
# Remove this line to switch voice off (the D22 decommission list has the rest).
JUP_VOICE_ENABLED: "true"
# Transcribe as Bahasa Indonesia (2026-09-28, Erik): with no language, gpt-4o-transcribe guessed
# Japanese on a 2-3 s utterance and the answer followed it. Applies to every STT engine despite
# the name; the vendor retries once without it if a transcription fails. English terms still pass.
WHISPER_LANGUAGE: "id"
EOF

# The legal-kb volume mounts with the runtime service account. Without its read grant (D5) the new
# revision cannot mount the bucket, so stop here rather than ship a revision that may not start.
RUNTIME_SA="$(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --format='value(spec.template.spec.serviceAccountName)')"
if [[ -z "$RUNTIME_SA" ]]; then
  echo "!! could not read the runtime service account of $SERVICE; not deploying." >&2
  exit 1
fi
if ! gcloud storage buckets get-iam-policy gs://jup-ops-legal-kb --project="$PROJECT" --format=json \
  | grep -q "serviceAccount:${RUNTIME_SA}"; then
  echo "!! ${RUNTIME_SA:-the runtime service account} has no grant on gs://jup-ops-legal-kb (contract KB D5)." >&2
  echo "!! Grant roles/storage.objectViewer first; not deploying." >&2
  exit 1
fi

echo "==> deploying to Cloud Run"
# --timeout=3600: a GPT-Live call is one request held open for the whole call, so Cloud Run keeps CPU
# allocated for its sideband without always-on CPU billing (ADR-0018, Option A, Erik 2026-09-28).
# A call is therefore capped at an hour. It was 600.
gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --image="$REPO:$SHA" \
  --port=8080 --cpu=2 --memory=4Gi --timeout=3600 \
  --min-instances=1 --max-instances=4 \
  --no-allow-unauthenticated \
  --ingress=internal-and-cloud-load-balancing \
  --network=default --subnet=default --vpc-egress=private-ranges-only \
  --add-volume="name=jup,type=cloud-storage,bucket=jup-ops-records,readonly=true" \
  --add-volume-mount="volume=jup,mount-path=/srv/jup" \
  --add-volume="name=legal-kb,type=cloud-storage,bucket=jup-ops-legal-kb,readonly=true" \
  --add-volume-mount="volume=legal-kb,mount-path=/srv/legal-kb" \
  --set-secrets="WEBUI_SECRET_KEY=webui-secret-key:latest,DATABASE_URL=database-url:latest,JUP_VOICE_OPENAI_API_KEY=openai-live-key:latest" \
  --env-vars-file="$ENVFILE"

rm -f "$ENVFILE"

echo "==> deployed. URL is reachable only through the load balancer / IAP:"
gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --format='value(status.url)'
