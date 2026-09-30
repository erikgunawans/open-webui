# Updating the knowledge base

How new or changed knowledge reaches Asisten JUP, and who has to do what.

Whatever the route, a document should first be in the KB Markdown shape: see
[kb-document-template.md](kb-document-template.md) (the in-app skill **Dokumen KB JUP** drafts it).

There are **two routes in**, and they never mix:

|                       | Route A: the Strategy KB            | Route B: staff contributions                                   |
| --------------------- | ----------------------------------- | -------------------------------------------------------------- |
| Collection in the app | **JUP Strategy KB**                 | **JUP Staff Contributions**                                    |
| Source of truth       | the `~/jup` repository              | a file a staff member uploads                                  |
| Who changes it        | Erik (or whoever edits `~/jup`)     | staff with the `jup.kb.submit` grant, then an admin reviews it |
| How it gets in        | a script syncs `~/jup` into the app | approved in the review queue at `/kb-review`                   |
| Decided in            | ADR-0011                            | ADR-0015                                                       |

> **Never add a file to the JUP Strategy KB by hand in the app.** The sync deletes every file in
> that collection that it did not put there itself, so a hand-added file disappears on the next
> run. Nothing warns you when it does. A staff document goes through Route B instead.

---

## Route A: change the Strategy KB (from `~/jup`)

The Strategy KB is **generated**. You edit the source in `~/jup`, never the copy in the app.

### What is in it

- Every `kb/*.md` **except `kb/CONTEXT.md`**. `CONTEXT.md` is the assistant's operating contract,
  not reference material.
- `DECISIONS.md`.
- Every `records/**/*.md` (engagements, projects, gate assessments and the rest).

### Step 1: edit the source

Edit the Markdown in `~/jup`. Three rules:

- **Partner state lives in `records/engagements/`, not in `kb/partners.md`.** The state table and
  the stage-ladder line in `kb/partners.md` are generated from the records. Change the record, then
  regenerate (step 2).
- **Never edit inside a `<!-- BEGIN generated:... -->` region.** The next regeneration overwrites it.
- **Do not use a stage-ladder label as a table cell outside a generated region.** The check refuses
  it. Prose that names a stage is fine.

`kb/gas.md` and `kb/governance.md` stay hand-written but are **checked**. The "5 mmscfd allocation
is not secured" caveat is tested against the G1 gate assessments in both directions. Contradicting
it fails, and so does deleting it.

### Step 2: regenerate and check

From `~/ent-os-new-jup`:

```sh
uv run --no-sync --only-group dev python -m jup.kb_sync --jup-root ~/jup          # regenerate
uv run --no-sync --only-group dev python -m jup.kb_sync --jup-root ~/jup --check  # verify
```

Exit `0` is clean, exit `1` is drift (the KB disagrees with the records), and exit `2` is a
malformed tree.

### Step 3: commit and push `~/jup`

```sh
cd ~/jup
git add -A && git commit -m "..." && git push
```

The `~/jup` pre-commit hook refuses a commit that touches `records/` or `kb/` while the two
disagree. It is enabled once per clone with `git config core.hooksPath .githooks`. It checks the
working tree, so commit everything you edited, not a partial stage.

### Step 4: sync into the app

From `~/ent-os-new-jup`, with Erik's signed-in tab open in Chrome (the app is behind IAP, so the
script runs its calls inside that tab through Interceptor):

```sh
bun deploy/gcp/sync-kb.ts --check   # what would change; writes nothing, exit 1 if anything would
bun deploy/gcp/sync-kb.ts           # the sync itself
```

The sync compares checksums and uploads only added or changed files. It removes files deleted in
`~/jup`, and the stale copies of changed ones.

**This writes to production: it needs Erik's OK every time.**

### Step 5: if a voice file changed, re-sync the voice model

The voice assistant, "Asisten JUP — Suara", answers from **eight named files** only:

- `kb/strategy.md`, `kb/gas.md`, `kb/portfolio.md`, `kb/rued.md`, `kb/governance.md`, `kb/faq.md`
- `records/projects/gas-spbg-reactivation.md`
- `records/gate-assessments/gas-spbg-reactivation-g1.md`

The voice model points at those files by their file id. A changed file is uploaded again under a
**new id**, so after step 4 the voice model can still point at the removed copy. Re-point it:

```sh
bun deploy/gcp/sync-voice-model.ts --dry-run   # resolve and print; writes nothing
bun deploy/gcp/sync-voice-model.ts             # update the model (a DB write: Erik's OK)
```

Adding a ninth file to the voice set is a governance change. It needs a date and Erik's name
(ADR-0006).

### Step 6: sync the records bucket (for the dashboard)

The Portfolio dashboard reads `records/` from the bucket `gs://jup-ops-records`, which is a copy of
`~/jup`, not a live view of it. From `~/ent-os-new-jup/deploy/gcp`:

```sh
./sync-records.sh --check   # has the bucket fallen behind? writes nothing
./sync-records.sh           # push ~/jup records and cited artefacts (Erik's OK)
```

### Step 7: the separate Worker assistant (only if it must change too)

The public-facing strategy Worker keeps its own bundle. In `~/jup-kb-assistant-worker`:

```sh
bun build-kb-bundle.ts
wrangler deploy             # authorised per change
```

### Step 8: verify

- `bun deploy/gcp/sync-kb.ts --check` reports no drift.
- Ask Asisten JUP a question only the new content answers, and check that it cites the file.
- If a voice file changed, ask the same question in a voice call.

---

## Route B: a staff member contributes a document

### Who can do what

- **Submitting** needs the group grant `jup.kb.submit`. Nobody has it by default, the admin role
  does not include it, and it must be granted exactly as `true`.
- **Reviewing** needs the `admin` role.

### The flow

1. **Submit.** The staff member opens **`/kb-review`** and uploads the document with a note. It is
   stored as an ordinary file marked `pending`, with a SHA-256 digest of its text.
2. **Review.** An admin opens the same page, sees the queue, and opens the preview.
3. **Approve or reject.**
   - **Approve** adds the file to **JUP Staff Contributions**, the first approval creates that
     collection. The file is marked `approved` only after the add succeeds, so a failed embedding
     leaves it `pending` with the error shown. Approval is refused (409) if the text changed after
     the reviewer opened the preview.
   - **Reject** needs a reason. A rejected file cannot be resubmitted; the staff member uploads a
     corrected copy as a new file.
4. **Attach (one-time).** Approved contributions reach answers only once **JUP Staff
   Contributions** is attached to Asisten JUP's knowledge next to the Strategy KB. That production
   edit is Erik's to authorise, and it is still pending (ADR-0016 step 5).

Every submit, approve and reject writes one `jup.governance` audit line. The line carries ids and
the result, never the document, the note or the reason.

**Known gap.** The owner of an approved file can still edit its text, and the app re-processes it.
The queue then shows "changed since submitted": it detects the edit but cannot stop it.

---

## Quick reference

| I want to...                          | Do this                                                                 |
| ------------------------------------- | ----------------------------------------------------------------------- |
| Change partner or gate state          | edit the record in `~/jup/records/`, regenerate, commit, `sync-kb.ts`   |
| Change strategy prose                 | edit `~/jup/kb/*.md`, check, commit, `sync-kb.ts`                       |
| Record a decision                     | edit `~/jup/DECISIONS.md`, commit, `sync-kb.ts` (and `sync-records.sh`) |
| Change one of the eight voice files   | as above, then `sync-voice-model.ts`                                    |
| Add a staff document                  | Route B at `/kb-review`                                                 |
| See whether the app has fallen behind | `sync-kb.ts --check` and `sync-records.sh --check`                      |

## Production steps that need Erik's OK every time

- `sync-kb.ts` (without `--check`)
- `sync-voice-model.ts` (without `--dry-run`)
- `sync-records.sh` (without `--check`)
- `wrangler deploy` of the Worker
- Attaching JUP Staff Contributions to Asisten JUP
- Granting `jup.kb.submit` to a group
