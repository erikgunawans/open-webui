# Drift gates — issuing the two credentials

`.github/workflows/drift-gates.yaml` holds the two checks that compare what is **written**
against what is **served**:

| Gate | Compares | Blocked on |
|---|---|---|
| `credential-scope` | asserts the runner cannot write to the bucket | WIF — **issued** |
| `kb-drift` | `kb/partners.md` against `records/` (#9, ADR-0011) | `JUP_REPO_TOKEN` — **outstanding** |
| `record-sync` | `gs://jup-ops-records` against the JUP tree (#13) | `JUP_REPO_TOKEN` + WIF |

**The GCS half is provisioned (2026-09-19).** `GCP_WIF_PROVIDER` and `GCP_RECORDS_READER_SA` are
set, and the `credential-scope` job proves the handshake and the credential's scope on every run.
**Only `JUP_REPO_TOKEN` remains**, and it gates both drift checks: `kb-drift` needs the JUP checkout,
and `record-sync` needs it too. Until it exists both stay grey — a skipped job is not a passing one,
and the run summary names what is missing and the drift it is therefore not catching.

## Why skip rather than pass

A gate that cannot reach the thing it guards must not report success. If it did, "clean" and "I
could not look" would render identically, and the gate would be worse than absent: absent gates do
not reassure anyone.

## 1. `JUP_REPO_TOKEN` — reading the JUP tree

> **Run `scripts/wizard-jup-repo-token.sh` instead of doing this by hand.** It opens the right page,
> says exactly what to click, and — the part that matters — **verifies the token before storing
> it**. The first attempt at this credential was stored unverified and failed in CI with
> `Bad credentials`, which reads like a permissions problem and is not one. The token also expires,
> so this is a procedure you will run again.

A fine-grained personal access token, scoped to **`erikgunawans/jup` only**, with
**Contents: Read-only**. Nothing else. It is used for one thing: `actions/checkout` fetching the
record tree into the runner so the checkers have something to check.

```
gh secret set JUP_REPO_TOKEN --repo erikgunawans/ent-os-new-jup
```

Set an expiry and diarise the renewal. When it lapses the checkout fails and the job errors — it
does not silently pass, because a failed checkout never reaches the gate's exit-code handling.

## 2. Workload Identity Federation — reading the bucket

Two secrets, `GCP_WIF_PROVIDER` and `GCP_RECORDS_READER_SA`.

**Not a service-account key.** A downloadable JSON key pasted into a repository secret is a
long-lived credential living in a second place — which is the shape of #11 arriving by a different
door. WIF mints a short-lived token per run against GitHub's OIDC identity, so there is nothing to
leak and nothing to rotate.

The service account needs **`roles/storage.objectViewer` on `gs://jup-ops-records` and nothing
more.** The `credential-scope` job asserts this at runtime via `testIamPermissions`, and
`record-sync` `needs:` that job — so a credential that could publish **skips** the drift check
rather than running with it. The assertion writes nothing; it asks IAM what it *would* be allowed
to do.

**What was actually provisioned:**

```
pool      github-pool
provider  github-provider   condition: assertion.repository == 'erikgunawans/ent-os-new-jup'
identity  records-reader@jup-ops.iam.gserviceaccount.com
grant     roles/storage.objectViewer on gs://jup-ops-records ONLY
```

Bucket-scoped, not project-scoped: `objectViewer` at the project would also grant read on
`jup-ops-data`, which holds uploads this gate has no business seeing. Verified at provisioning
time — no project-level binding, nothing on `jup-ops-data`, and `roles/storage.objectViewer`
resolves to `get` and `list` verbs only.

Restricted twice on purpose. The provider's `attribute-condition` decides **who may mint a token**;
the `workloadIdentityUser` principalSet on the service account decides **who that token may act
as**. Either alone would be sufficient; both means widening one does not silently widen access.

The reason is the script's own shape: `sync-records.sh --check` is read-only, but bare
`sync-records.sh` **writes to deployed infrastructure**. The workflow only ever passes `--check`;
the credential is the second line of defence, so that a mistake in the first line cannot publish
anything.

Already set, recorded here so a rebuild can reproduce them:

```
gh secret set GCP_WIF_PROVIDER      --repo erikgunawans/ent-os-new-jup \
  --body "projects/1001937491646/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
gh secret set GCP_RECORDS_READER_SA --repo erikgunawans/ent-os-new-jup \
  --body "records-reader@jup-ops.iam.gserviceaccount.com"
```

`--body`, never a pipe: a piped value carries a trailing newline, and this project has already
been bitten once by a newline surviving into a credential.

## Confirming it works

`gh workflow run "Drift gates" --repo erikgunawans/ent-os-new-jup`, then:

- **Now** — `preflight` and `credential-scope` green, `kb-drift` and `record-sync` grey, summary
  naming `JUP_REPO_TOKEN`.
- **After the PAT** — all four run. Expect green; the live tree and bucket were in sync at
  `ac9dc29`.
- **Forced failure** — change a `stage:` in a record in a scratch clone without regenerating
  `kb/partners.md`, and confirm `kb-drift` fails with **exit 1** and the `KB drift` annotation.

## The one thing to keep straight

Both checkers distinguish **exit 1 (drift)** from **exit 2 (broken tree)**, and the workflow keeps
them apart in its annotations. Drift is a document someone must regenerate. Exit 2 is a checkout
that never arrived, and means the gate **checked nothing** — it is not a governance alarm and must
not be read as one.

This matters more than it looks. `jup.kb_sync` is importable under pytest via
`pythonpath = ["backend"]`, which does nothing for a bare `python -m`. Locally it imports anyway,
but only because a full `uv sync` leaves an editable-install `.pth` pointing at `backend/` — and
CI's `--only-group dev` does not install the project. Without the explicit `PYTHONPATH: backend` in
the workflow, the job dies with `ModuleNotFoundError` and **exit 1** — indistinguishable, to
anything reading the exit code, from real drift.

## Filesystem junk, and why the two halves disagreed

The write path rsyncs a working **filesystem** from a Mac; the CI gate compares against a git
**checkout**. `.DS_Store` is in `~/jup/.gitignore`, so it lives on the filesystem and can never
appear in the checkout. A local sync published one to `deliverables/`, and from then on
`record-sync` reported drift — `Would remove ...deliverables/.DS_Store` — that **no commit could
ever resolve**.

Both rsync invocations now pass `--exclude="$JUNK_RE"` (`.DS_Store`, `Thumbs.db`, AppleDouble
`._*`). Excluding on both paths is the point: deleting the stray object alone would not have held,
because the next local sync would upload it again.

**Every gitignored file rsync can see has this shape.** If a new one appears, widen `JUNK_RE` in
`deploy/gcp/sync-records.sh` rather than deleting from the bucket.
