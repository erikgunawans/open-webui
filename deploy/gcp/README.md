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
| Secrets | `webui-secret-key`, `database-url`, `db-password` in Secret Manager. **Both env vars the service needs are secret references; no credential is a plain value on the service.** |
| Access | IAP in front of a global load balancer. No public path to the app. |

## The database credential is a secret reference, and must stay one

`DATABASE_URL` reaches the service as a reference to the `database-url` secret, the same way
`WEBUI_SECRET_KEY` always did. It did not start that way: the connection string was assembled in
`deploy.sh` and passed as a plain value, which put the production Postgres password in the output of
`gcloud run services describe` — readable with `run.viewer`, the role you hand someone so they can
look at a revision. Rotated and moved on 2026-09-19 (#11); treat every value from before that date
as exposed.

Three things keep it that way:

- **The secret is the whole connection string, not the password.** Splitting it would put the
  assembly step back in `deploy.sh`, and that step is the defect.
- **Write secret versions with `printf '%s'`.** A value piped from `openssl`/`cut`/`echo` carries a
  trailing newline that survives into the version. Cloud Run injects the raw bytes, and the
  resulting error names the host, not the newline. Verify by reading the version back and checking
  its byte length.
- **`--set-secrets` replaces the whole secret block.** Name every secret in one flag, or the one you
  leave out is silently dropped. Converting an existing plain env var needs
  `--remove-env-vars=NAME` in the same command — `--update-secrets` alone fails with *"already been
  set with a different type"*.

`database-url` embeds the instance's private IP. If `jup-ops-db` is recreated on a different
address, add a new secret version; nothing in `deploy.sh` will notice.

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
- **Gate state is admin-only.** The portfolio endpoint and the `portfolio_status` chat tool admit
  only the operating layer, which is the `admin` role (issue #10, the Director's call 2026-09-19).
  A signed-in `user` gets 403, not 401. Promoting someone to `admin` therefore also shows them
  every gate refusal and counterparty rung, so treat that promotion as a grant.

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

**`deploy.sh` builds in the `global` pool, not in `asia-southeast2`** — `e2-highcpu-32` is
quota-blocked in this region on this project, and global is where the only successful build so far
actually ran. Only the *deploy* is regional; copy that split into any trigger you create.

Separately: Cloud Build now runs the **legacy docker builder**, which does not define
`$BUILDPLATFORM`. That kills the build at `Dockerfile:27` with `failed to parse platform`, a message
that accuses the Dockerfile rather than the builder. It reproduces in **both** pools, so changing
region does not help — the fix is the `ARG BUILDPLATFORM` default in the Dockerfile, recorded in
`VENDOR-PATCHES.md`.
