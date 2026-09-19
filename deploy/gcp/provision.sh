#!/usr/bin/env bash
# One-time infrastructure for ent-os on GCP. Idempotent: safe to re-run.
# Read ./README.md first — three gcloud behaviours here are genuinely misleading.
set -euo pipefail

PROJECT="${PROJECT:-jup-ops}"
REGION="${REGION:-asia-southeast2}"
BILLING="${BILLING:-012944-41677E-208592}"
INSTANCE="${INSTANCE:-jup-ops-db}"

have() { "$@" >/dev/null 2>&1; }

echo "==> project"
have gcloud projects describe "$PROJECT" \
  || gcloud projects create "$PROJECT" --name="PT JUP Operating Layer"
gcloud billing projects link "$PROJECT" --billing-account="$BILLING" >/dev/null

echo "==> APIs"
gcloud services enable \
  run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com compute.googleapis.com \
  iap.googleapis.com storage.googleapis.com servicenetworking.googleapis.com \
  --project="$PROJECT"

echo "==> private services access (Cloud SQL has no public IP: org policy forbids it)"
have gcloud compute addresses describe google-managed-services-default --global --project="$PROJECT" \
  || gcloud compute addresses create google-managed-services-default \
       --global --purpose=VPC_PEERING --prefix-length=16 --network=default --project="$PROJECT"
gcloud services vpc-peerings connect --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-default --network=default --project="$PROJECT" || true

echo "==> Cloud SQL"
# --edition=ENTERPRISE is required for db-g1-small; the default ENTERPRISE_PLUS rejects it.
# --network takes a BARE name for a same-project VPC; the full URL form means shared VPC.
have gcloud sql instances describe "$INSTANCE" --project="$PROJECT" \
  || gcloud sql instances create "$INSTANCE" \
       --database-version=POSTGRES_16 --edition=ENTERPRISE --tier=db-g1-small \
       --region="$REGION" --storage-size=10GB --storage-type=SSD --storage-auto-increase \
       --backup --backup-start-time=18:00 --availability-type=zonal \
       --network=default --no-assign-ip --project="$PROJECT"

echo "==> registry and buckets"
have gcloud artifacts repositories describe ent-os --location="$REGION" --project="$PROJECT" \
  || gcloud artifacts repositories create ent-os --repository-format=docker \
       --location="$REGION" --description="ent-os images" --project="$PROJECT"
for b in jup-ops-records jup-ops-data; do
  have gcloud storage buckets describe "gs://$b" --project="$PROJECT" \
    || gcloud storage buckets create "gs://$b" --location="$REGION" \
         --uniform-bucket-level-access --project="$PROJECT"
done

echo "==> secrets"
have gcloud secrets describe webui-secret-key --project="$PROJECT" \
  || printf '%s' "$(openssl rand -hex 32)" \
     | gcloud secrets create webui-secret-key --data-file=- --project="$PROJECT"
have gcloud secrets describe db-password --project="$PROJECT" \
  || printf '%s' "$(openssl rand -base64 24 | tr -d '\n=+/' | cut -c1-24)" \
     | gcloud secrets create db-password --data-file=- --project="$PROJECT"

echo "==> database, user, and the pgvector extension"
DB_PW="$(gcloud secrets versions access latest --secret=db-password --project="$PROJECT")"
have gcloud sql databases describe entos --instance="$INSTANCE" --project="$PROJECT" \
  || gcloud sql databases create entos --instance="$INSTANCE" --project="$PROJECT"
have gcloud sql users describe entos --instance="$INSTANCE" --project="$PROJECT" \
  || gcloud sql users create entos --instance="$INSTANCE" --password="$DB_PW" --project="$PROJECT"
# pgvector is a per-database extension, NOT an instance flag. There is no
# cloudsql.enable_pgvector; passing one fails with a misleading "misspelled flag" error.
echo "    run once against the entos database:  CREATE EXTENSION IF NOT EXISTS vector;"

echo "==> the connection string, as a secret (#11)"
# The WHOLE connection string is the secret, not just the password. Splitting it would mean
# assembling the URL at deploy time, which is exactly the step that used to leave the credential
# in plaintext on the service. `printf '%s'` is load-bearing: a value piped from openssl/cut/echo
# carries a trailing newline, it survives into the secret version, and Cloud Run injects the raw
# bytes — yielding a connection string with an embedded \n whose error names the host, not the
# newline.
DB_IP="$(gcloud sql instances describe "$INSTANCE" --project="$PROJECT" \
  --format='value(ipAddresses[0].ipAddress)')"
have gcloud secrets describe database-url --project="$PROJECT" \
  || printf '%s' "postgresql://entos:${DB_PW}@${DB_IP}:5432/entos" \
     | gcloud secrets create database-url --data-file=- --project="$PROJECT"

echo "==> secret access, scoped to each secret rather than project-wide"
PN_SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
for secret in webui-secret-key database-url; do
  gcloud secrets add-iam-policy-binding "$secret" --project="$PROJECT" \
    --member="serviceAccount:$PN_SA" \
    --role=roles/secretmanager.secretAccessor --quiet >/dev/null
done

echo "==> build service account permissions"
PN="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
for role in roles/artifactregistry.writer roles/logging.logWriter roles/storage.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$PN-compute@developer.gserviceaccount.com" \
    --role="$role" --condition=None --quiet >/dev/null
done

echo "provisioned. next: ./sync-records.sh then ./deploy.sh"
