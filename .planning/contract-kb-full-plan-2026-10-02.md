# Contract KB — full version plan (2026-10-02)

Status: **approved by Erik 2026-10-02 with the decisions at the end (D1 changes the proposal; D3 redesigned).** Builds on the approved proposal "Usulan Basis Pengetahuan Kontrak &
Perkara JUP" (decisions 2026-09-29) and the full run (1,033 drafted cards in `gs://jup-ops-legal-kb/full/`).
Daftar Perkara is out of scope here (its xlsx is not granted yet); the same access and masking module serves it later.

## What exists today
- Cards (15 page-cited fields), OCR text per page and source PDFs, all in the Jakarta bucket. Nothing in the app reads them.
- Tool pattern: thin `tools/*.py` wrapper → tested `backend/jup/*` module; `risk_class: read`; synced by
  `deploy/gcp/sync-tools.ts`; every call already audited (`audit_tool_call`).
- Access pattern: boolean group permissions under the `jup` key (as Ruang Pimpinan and KB review do), resolved in
  code with `get_permissions`. Tools only receive the user's role, so the contract module looks permissions up itself.
- **Gaps:** no unit / jabatan / manager data anywhere in the app; no masking code; /kb-review only reviews uploaded
  files and only admins review; the Cloud Run service account cannot read the legal-kb bucket.

## Design

**Data (Jakarta).** A fork table set on its own alembic graph (the leadership pattern: a failure only disables this
section):
- `jup_contract`: one row per PDF — draft card, current card (after Legal's edits), state
  (`draft` / `approved` / `returned`), structured dates (start, end, auto-renewal), unit codes, source pointers
  (bucket object, OneDrive link), draft hash.
- `jup_contract_event`: append-only history (imported, field edited, approved, returned with reason, unit set).
- `jup_contract_party`: stable masking codes ("Perorangan A") per individual party, which Legal can review.

An admin import pulls the run's cards into the table as drafts; a light second pass extracts structured dates so
"which contracts end in the next 6 months" is a query, not a guess.

**Access, enforced in code** (one tested module; grants are group permissions):

| Grant | Gives | Group |
|---|---|---|
| `jup.contracts.cards` | cards without money fields | all staff |
| `jup.contracts.money` | value and payment, penalties, damages caps | managers and up |
| `jup.contracts.fulltext` | every contract's OCR pages and PDF | Legal, Direksi |
| `jup.contracts.unit.<code>` | full text for that unit's contracts | managers of the unit |
| `jup.contracts.review` | the review queue | Legal |

The tool strips what the caller may not see **before** anything reaches the model; a refusal names what is withheld.

**Masking.** Individual parties are replaced by their code in everything the tool returns. After the answer, the
codes are swapped back to names only for users entitled to them (see D2). Company signatories are not masked.

**Tool `jup_contracts`** (`read`), three functions:
- `search_contracts`: partner, number, title, keywords, ends-within-N-days, state.
- `get_contract`: one card, field-filtered.
- `read_contract_pages`: quoted OCR pages, full-text grants only.

Answers cite the contract and page and link the PDF through an access-checked endpoint.

**Review screen** — a "Kartu Kontrak" tab in Tinjauan Pengetahuan:
- A queue with filters (individual parties first, "perlu diperiksa manual", low-confidence OCR).
- The card and its source pages side by side, as in the pilot preview.
- Per-field edits, approve, or return with a reason; set the unit; link addenda.
- Approve is guarded by the draft hash, and every action is written to the event table.

## Phases
1. **Foundation and asking (≈2 days):** table and migration, import, access + masking module, tool, PDF endpoint,
   tests. Then deploy, sync, grants, and a live check. **After this, Erik can ask** (under D1).
2. **Review screen (≈2 days):** the Kartu Kontrak tab, edits/approve/return, unit and addendum links, events.
3. **Staff rollout (when Legal is ready):** groups filled, unit mapping, cards answered for all staff from approved
   cards only.
4. Later: new PDFs in SCAN PERJANJIAN flow in automatically (scheduled run); Daftar Perkara on the same module.

## Decisions (Erik, 2026-10-02)
- **D1 — Any card answers; approval is shown.** Asisten JUP and Asisten JUP - Suara answer from every card,
  approved or not. Each answer carries the card's state: "disetujui Tim Legal" or "draf, belum ditinjau". Legal
  still reviews every card, and approving it sets the indicator. This replaces the proposal's "approved cards only"
  rule. The access matrix still applies in full: drafts are filtered and masked exactly like approved cards.
- **D2 — Unmasked individual names: Legal and Direksi only.** Everyone else sees "Perorangan A".
- **D3 — A title-group column in Admin → Pengguna:** one choice per user (Direksi, Legal, Manager, Staff). It is
  the single place contract access comes from. Each title is a managed group carrying its `jup.contracts.*`
  grants; choosing a title moves the user between the four groups, exactly one at a time.
  - Staff: cards.
  - Manager: cards and money.
  - Legal: cards, money, full text, names and review.
  - Direksi: cards, money, full text and names.

  Admin stays separate from the title (ADR-0012: admin is not Direksi). The Pengguna list is a vendor screen: one
  column is added, recorded in VENDOR-PATCHES.md and guarded by a source test.
- **D4 — Unit scope deferred** until Legal assigns units in the review screen; managers get cards and money meanwhile.
- **D5 — IAM:** the Cloud Run service account gets objectViewer (read-only) on `gs://jup-ops-legal-kb`.

## Phase 1 scope after the decisions
1. The title-group column and its four managed groups.
2. Contract tables, and an import of the full run.
3. The access and masking module.
4. The `jup_contracts` tool, attached to both Asisten JUP models.
5. An access-checked PDF endpoint.
6. Tests, then deploy, sync and a live check.
