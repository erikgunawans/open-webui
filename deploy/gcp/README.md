# Deploying ent-os to Google Cloud

The operating layer runs on Cloud Run, behind IAP, against Cloud SQL Postgres. The JUP
record tree is a **read-only GCS mount**, which is the cloud equivalent of the read-only bind
in `docker-compose.jup.yaml` — this container must never be able to write a governance record.

| Piece | What it is |
|---|---|
| Project | `jup-ops` — PT JUP's own project, not an Axiara one. JUP is a separate legal entity. |
| Region | `asia-southeast2` (Jakarta) — latency, and the records stay in-country. |
| Compute | Cloud Run service `ent-os`, CPU-only. |
| Database | Cloud SQL `jup-ops-db`, Postgres 16, **private IP only**. Serves both the app DB and pgvector. |
| Records | `gs://jup-ops-records`, mounted read-only at `/srv/jup`. |
| Uploads | `gs://jup-ops-data` via `STORAGE_PROVIDER=gcs`. |
| Secrets | `webui-secret-key`, `db-password` in Secret Manager. |
| Access | IAP in front of a global load balancer. No public path to the app. |

## Three things that will bite you

1. **`--edition=ENTERPRISE` is required for shared-core tiers.** The Cloud SQL default is
   ENTERPRISE_PLUS, which rejects `db-g1-small` with a message that does not mention editions.

2. **Public IP on Cloud SQL is blocked by org policy** (`constraints/sql.restrictPublicIp`).
   The instance is private-IP only, which means VPC private services access must exist *first*:
   allocate a `VPC_PEERING` range, then `gcloud services vpc-peerings connect`. Cloud Run reaches
   it through direct VPC egress, not a connector.

3. **`--network` takes a bare name for a same-project VPC.** Passing the full
   `projects/X/global/networks/Y` URL makes gcloud treat it as a shared-VPC reference and fail with
   *"Projects instance [jup-ops] not found: The requested flag is either misspelled or unsupported"*,
   which names the wrong cause entirely.

4. **The frontend build needs a big machine.** `npm run build` (vite) dies with
   *"Ineffective mark-compacts near heap limit — JavaScript heap out of memory"* on
   `E2_HIGHCPU_8`, because BuildKit runs the node stage in parallel with the python stage that is
   installing torch, and they compete for the same 8 GB. `E2_HIGHCPU_32` gives node enough headroom.
   The Dockerfile ships a commented-out `ENV NODE_OPTIONS="--max-old-space-size=4096"` naming this
   exact error — uncommenting it is the fallback, at the cost of a vendor edit to carry across every
   ADR-0007 rebase.

Also: **there is no `cloudsql.enable_pgvector` database flag.** pgvector is enabled per database
with `CREATE EXTENSION vector;`. Passing it as a `--database-flags` value produces the same
misleading "misspelled flag" error as (3).

## Records are a copy, and that has a consequence

`gs://jup-ops-records` is an **rsync of `~/jup`**, not a live view of it. A record edited and
committed in the JUP repo does not reach the dashboard until `sync-records.sh` runs. That is a
real difference from the local compose overlay, where the working tree is mounted directly.

Until that sync is automated, **a record change is a two-step act**: commit it in `erikgunawans/jup`,
then sync. Anyone who forgets the second step is looking at a dashboard that disagrees with the
repo — which is the failure mode issue #9 exists to close.

`./sync-records.sh --check` is read-only and answers "has it fallen behind?" without writing
anything. `.github/workflows/drift-gates.yaml` runs that daily so nobody has to remember to ask —
but it is credential-gated and currently skips; see `drift-gates.md` for what to issue (#13).

## Order of operations

```sh
./provision.sh     # project, APIs, VPC peering, Cloud SQL, buckets, secrets, registry
./sync-records.sh  # push ~/jup records + cited artefacts to the bucket
./deploy.sh        # build on Cloud Build, deploy to Cloud Run
```

IAP and the load balancer are the last step and need a domain — see `iap.md`.
The drift gates that watch this deployment are in `drift-gates.md`.

## What this does not do

- **No unauthenticated view.** ADR-0010 answers partner disclosure with a generated export, not a
  hosted surface. IAP is in front of everything.
- **Signup is off** (`ENABLE_SIGNUP=False`). Accounts are created deliberately.
- **The portfolio endpoint still has no operating-layer permission** (issue #10). Every account
  promoted to `user` for chat can also read every gate refusal and counterparty rung. Know this
  before promoting anyone.

## A note on build speed

`deploy.sh` uploads the whole 159 MB build context from this machine on every run, which dominates
the wall-clock time. Once the deployment is settled, replace it with a Cloud Build trigger on
`erikgunawans/ent-os-new-jup` so GCP fetches the source itself:

```sh
gcloud builds triggers create github \
  --repo-name=ent-os-new-jup --repo-owner=erikgunawans --branch-pattern='^main$' \
  --build-config=deploy/gcp/cloudbuild.yaml --region=asia-southeast2 --project=jup-ops
```

That needs the Cloud Build GitHub app connected to the repo first, which is a console step.
