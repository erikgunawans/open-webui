# Drift gates — issuing the two credentials

`.github/workflows/drift-gates.yaml` holds the two checks that compare what is **written**
against what is **served**:

| Gate | Compares | Blocked on |
|---|---|---|
| `kb-drift` | `kb/partners.md` against `records/` (#9, ADR-0011) | `JUP_REPO_TOKEN` |
| `record-sync` | `gs://jup-ops-records` against the JUP tree (#13) | `JUP_REPO_TOKEN` + WIF |

Both are committed and both currently **skip**, because neither credential exists yet. A skipped
job is grey, not green, and the run summary names the missing secret and the drift it is therefore
not catching. Issuing the secrets is the whole of the remaining work — there is no second code
change.

## Why skip rather than pass

A gate that cannot reach the thing it guards must not report success. If it did, "clean" and "I
could not look" would render identically, and the gate would be worse than absent: absent gates do
not reassure anyone.

## 1. `JUP_REPO_TOKEN` — reading the JUP tree

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
more.** The workflow asserts this at runtime: before checking anything it calls `testIamPermissions`
for `storage.objects.create`, `.delete` and `.update`, and **fails the job if the runner holds any
of them.** That assertion writes nothing — it asks the IAM API what it *would* be allowed to do.

The reason is the script's own shape: `sync-records.sh --check` is read-only, but bare
`sync-records.sh` **writes to deployed infrastructure**. The workflow only ever passes `--check`;
the credential is the second line of defence, so that a mistake in the first line cannot publish
anything.

```
gh secret set GCP_WIF_PROVIDER      --repo erikgunawans/ent-os-new-jup   # projects/N/locations/global/workloadIdentityPools/POOL/providers/PROVIDER
gh secret set GCP_RECORDS_READER_SA --repo erikgunawans/ent-os-new-jup   # records-reader@jup-ops.iam.gserviceaccount.com
```

Bind the pool to this repository only, so another repo in the account cannot assume the identity.

## Confirming it works

`gh workflow run "Drift gates" --repo erikgunawans/ent-os-new-jup`, then:

- **Before the secrets** — `preflight` green, both gates grey, summary naming what is missing.
- **After** — both gates run. Expect green; the live tree and bucket were in sync at `ac9dc29`.
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
