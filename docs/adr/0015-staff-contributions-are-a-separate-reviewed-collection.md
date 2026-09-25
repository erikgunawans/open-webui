# Staff contributions are a separate, reviewed collection

**Status: Accepted 2026-09-25 — Erik Gunawan Supriatna, Director, Operation & Business
Development.**

Staff need a way to put documents in front of the assistant. The only knowledge base today, "JUP
Strategy KB", is generated from `~/jup` by `deploy/gcp/sync-kb.ts` (ADR-0011). That sync ends with a
cleanup step that deletes every file in the collection it did not put there itself. Anything added to
the Strategy KB by hand is gone on the next sync, and nothing warns anyone.

## Decision

1. **An approved contribution goes into its own collection, "JUP Staff Contributions".** The
   Strategy KB is untouched and stays generated from records, so ADR-0011 holds. The review queue
   creates the collection on the first approval, owned by the approving admin, with **no access
   grants**, the same as the Strategy KB today. The assistant reads it only once it is attached to
   the model, which is a separate production step.
2. **Submitting is a group grant, `jup.kb.submit`, denied by default.** It must be an exact boolean
   `true`, merged from the caller's Open WebUI groups. Nobody holds it until an admin grants it, and
   the admin role does not imply it. A malformed grant is a denial, the same rule as the Ruang
   Pimpinan grants (`jup.leadership.policy`).
3. **Reviewing is the `admin` role only**, the same line the Portfolio operating layer draws. A
   signed-in account without it gets **403, not 401**: 401 would send a member who is already signed
   in to a sign-in page that cannot help.
4. **No table and no migration.** A submission is an ordinary vendor file, uploaded through
   `POST /api/v1/files/`. Its review state is one key in that file's `meta`, `jup_kb_review`
   (`pending` → `approved` or `rejected`). Migrations are this fork's documented hazard, and the
   file row already carries the owner, the extracted text and the timestamps. The queue finds
   submissions with a SQL filter on that JSON key, which the vendor itself uses on both SQLite and
   Postgres.

Approval reuses the vendor's own add-file handler, called as a function; vendor code is not
patched. The file is marked approved only after the add has succeeded, so a failed embedding leaves
it pending with the error shown. Every submit, approve and reject writes one `jup.governance`
audit line. The line carries ids and the result, never the document, the note or the reason.

## Consequences

**The owner can still edit an approved file.** The vendor lets a file's owner rewrite its extracted
text (`POST /api/v1/files/{id}/data/content/update`). The vendor then re-processes that text into
every collection holding the file, this one included. The queue cannot prevent that without
patching vendor code. It narrows the gap in two ways:

- A submission records the SHA-256 of its text.
- Approval must carry the digest of the preview the reviewer opened. It is refused (409) if the text
  has changed since.

After approval the queue shows "changed since submitted" when the digest no longer matches. It
detects the edit; it does not stop it. Closing the gap means either a vendor patch or copying the
text into an admin-owned file on approval. That is a decision for later, not made here.

**Two collections, one assistant.** The model's `meta.knowledge` must list both collections before
approved contributions reach answers. That production edit is Erik's to authorise.

**A rejected file cannot be resubmitted.** The submitter uploads the corrected document again as a
new file. The old decision and its reason stay on the old file.
