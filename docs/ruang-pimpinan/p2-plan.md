# Ruang Pimpinan P2 — durable board workflows: task plan

**Status: plan only, not authorised to build.** Written 2026-09-24 against `main` at `d59a145dd`
(P1 live on `ent-os-00027-lrc`, Erik-only grant, illustrative sample).

Source of intent: the approved design and the P2 brief in the read-only handoff package
(`~/Documents/ChatGPT/KPI-Dashboard-JUP/docs/handovers/2026-09-24-ruang-pimpinan-claude-code/`,
`IMPLEMENTATION-ROADMAP.md` § P2, `CONTRACTS.md` § Later durable records, `ACCEPTANCE.md`). The
settled decisions are not reopened here: one sidebar entry and two views in layout A; the PIC
submits and only the BOD closes, and admin is not BOD; current data and meeting records stay
separate, and baselines are never overwritten; agents prepare changes and execution waits for an
authorised confirmation.

**Exit evidence (from the roadmap):** ACT-01, ACT-02, ACT-03, SNAP-01, DATA-01 and DATA-02 (P2
parts), plus rollback/restart and conflict tests. P2 is built and verified **locally with synthetic
identities and test policy**. Production use of any P2 operation needs the company decisions listed
at the end, and a separate OK for each one.

## What the current code gives P2

- **The domain is pure and file-backed:** `backend/jup/leadership/`, with `records.py` (validation,
  variance), `policy.py` (default-deny read predicate), `reader.py` (one dataset, two views) and the
  router at `/api/v1/leadership`. Every write path in P2 is new.
- **The fork has no tables of its own.** Portfolio reads markdown from the bucket, and ADR-0004 keeps
  gate assessments in `~/jup` as git-tracked files because "a row cannot say who changed it". P2 is
  the fork's first persisted state.
- **Vendor alembic runs `upgrade head` when the config is imported** (`open_webui/config.py:74`). A
  second head stops the app from booting. `jup/migrations.py` plus `tests/test_boot.py` guard the
  vendor graph at exactly one head.
- **Audit:** `jup.governance.audit(event, **fields)` writes JSONL when `DATA_DIR` is set, and always
  writes to the logger. Production has no `DATA_DIR`, so its trail is Cloud Logging. E1 covers tool
  calls only.
- **Group permissions store unknown keys intact.** The admin editor also keeps them now
  (`e3126777a`). New `jup.ruang_pimpinan.*` capabilities can use the same mechanism as the read
  grant.

## Three engineering decisions to take before T1 (my recommendation first)

**E-1. Where the workflow records live → the app database, with an append-only event log, recorded
as ADR-0014.** ADR-0004 rejected a table because a row has no provenance. P2's shape is different:
every change is an appended event (author, time, reason, prior version), and the aggregate row is
a projection of those events, so the history ADR-0004 wanted from git lives in the log. The design
also needs things git can't give a web request: per-request transactions, optimistic-version
conflicts (a stale update returns 409), idempotent double submission, and per-record access checks
on every read. The ADR must say that the metrics dataset keeps its current authority until an import
replaces it. It must also say that Portfolio's gate assessments stay in `~/jup`, since ADR-0004 is
unchanged for them.
_Alternative:_ markdown records in `~/jup` written by commits. That works for PMO-rate edits, but it
gives up atomic conflicts and makes every PIC submission a git commit from the web tier.

**E-2. How fork tables are migrated → a separate alembic environment for `jup` tables, with its own
version table (`jup_alembic_version`), run right after the vendor upgrade.** Putting fork revisions
in the vendor chain means re-pointing `down_revision` on every quarterly rebase, and re-stamping the
deployed database each time (ADR-0007, architecture doc 08). A separate environment never shares a
head with upstream.

- **Cost:** one call site. It sits beside the router registration that is already a patched spot in
  `main.py`, with a `VENDOR-PATCHES.md` entry and a source-read test.
- **Guard:** extend `jup/migrations.py`'s one-head check to cover both graphs.
  _Alternative:_ fork revisions in the vendor chain, guarded by the existing test. That is cheaper now
  and costs something at every rebase.

**E-3. Where evidence files are stored → the host storage provider (production `jup-ops-data` bucket),
under a `leadership/evidence/` key, and never through the vendor Files table.** The vendor Files table
carries its own sharing, knowledge-base and chat attachment paths. A leadership record must not be
reachable through those (HOST-04, ACCESS-01). Evidence is served only by a leadership endpoint that
rechecks the action's permissions on each request.

## Capabilities added to the policy (default-deny, admin grants nothing)

| Capability key under `jup.ruang_pimpinan` | Allows                                                                        | Also required                                                         |
| ----------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `actions.submit`                          | Progress updates and evidence on actions where the caller is the recorded PIC | Read grant for the view and scope                                     |
| `bod.review`                              | Taking part in closure, return, cancellation and reopening decisions          | A configured BOD policy; unset means closure is disabled for everyone |
| `snapshots.publish`                       | Publishing a draft meeting snapshot                                           | A configured publication policy; unset means everything stays draft   |
| `imports.review`                          | Uploading candidate records and approving or rejecting them                   | Read grant                                                            |

The BOD policy is deployment configuration, not a database row: `JUP_LEADERSHIP_BOD_POLICY`, with
`{"mode": "individual" | "collective", "quorum": N}`, lives in `deploy.sh` so every change to it is a
reviewed commit. Unset or invalid means no closure path exists. The same pattern applies to
`JUP_LEADERSHIP_PUBLICATION_POLICY`.

## Tasks

Each task is TDD. Domain tests run under `--only-group dev`; HTTP tests run with the runtime and
real policy boundaries (only identity and data acquisition are faked). No skipped test counts as a
pass.

**T0 — ADR-0014 and the migration seam** (E-1, E-2, E-3 once approved).

- Write the ADR.
- Add `backend/jup/leadership/migrations/` (env, `script.py.mako`, first empty revision) and the
  startup call in `main.py`, with its ledger entry and source-read test.
- Extend the head guard to both graphs.
- _Verify:_ the app boots on SQLite, and on a disposable Postgres of the production major version
  (`docker run postgres:<ver>`). Production is Cloud SQL, so SQLite alone proves nothing about the
  types.

**T1 — Repository and persistence adapter** (`repository.py`, `models.py`).

- Tables: `leadership_action`, `leadership_action_event` (append-only; no UPDATE or DELETE path in
  code, enforced by test), `leadership_evidence`, `leadership_closure_request`,
  `leadership_closure_decision`, `leadership_snapshot`, `leadership_snapshot_version`,
  `leadership_rka_baseline`, `leadership_import_batch`, `leadership_import_candidate`,
  `leadership_external_ref`.
- Use SQLAlchemy Core types that behave the same on SQLite and Postgres. Money is stored as a
  decimal string or `NUMERIC`, never float.
- One `unit_of_work()`: an event append, the aggregate version bump and any idempotency key commit
  together or not at all.
- _Tests:_ a rollback leaves no partial event; state survives a restart (reopen the database); event
  rows cannot be updated.

**T2 — Action aggregate and events** (`actions.py`).

- Stable id, and PIC as a user id plus its display label.
- States: Not started → In progress → Awaiting BOD closure → Closed, plus Blocked. Closure kinds are
  completed, cancelled (reason required) and superseded (links the replacement).
- Original and current due date, each with its precision (`month`/`year`/`year_range`/`day`), and a
  reasoned revision event on every change.
- `expected_version` on every command. A stale version returns a conflict and appends nothing. An
  idempotency key makes a double submission return the first result.
- Overdue/stale is derived separately from the lifecycle and only at `day` precision; nothing
  invents dates or percentages.
- _Acceptance:_ ACT-03.
- _Tests:_
  - An older progress update can't replace a newer one; events are ordered by version, not by
    client time.
  - A date revision keeps the original due date.
  - Precision below a day yields no overdue value.

**T3 — Progress and evidence submission** (`evidence.py`, router commands, storage adapter).

- A PIC with `actions.submit` posts a progress narrative (labelled as an owner update), milestones,
  blockers and evidence revisions (file or link).
- Evidence is versioned. Submitting completion evidence moves the action to Awaiting BOD closure
  and never closes it.
- Files go through E-3 with a size cap, a content-type allowlist and a server-generated key; the
  client filename is metadata only.
- _Acceptance:_ ACT-02 (PIC half).
- _Tests:_
  - A non-PIC is refused; a PIC of another action is refused.
  - Admin, BOC observer and a read-only reader are all refused.
  - Evidence download rechecks access after revocation.

**T4 — BOD closure review** (`closure.py`).

- A closure request binds the exact evidence revision. Review decisions are close, return (back to
  In progress or Blocked, with a reason) and reopen (a new event; the prior closure is kept).
- Collective mode counts distinct `bod.review` identities up to the quorum. An evidence revision
  that changes while a decision is pending makes that decision stale, and the reviewer must look
  again.
- An unconfigured policy means the review endpoints answer 503 "closure is not configured", never a
  silent success.
- _Acceptance:_ ACT-02 (BOD half), ACT-03.
- _Tests:_ the design's list verbatim: PIC; BOC observer; admin without BOD; an authorised BOD
  reviewer in individual and in collective mode; returned evidence; stale evidence; reopened action;
  and a direct API closure attempt by each unauthorised identity.

**T5 — Meeting snapshots and RKA baselines** (`snapshots.py`).

- A draft snapshot freezes one view's content (metrics, actions at their current event versions,
  assumptions, sources) as canonical JSON with a content hash.
- Versions are immutable. A correction creates a linked replacement.
- Publishing needs `snapshots.publish` and a configured publication policy. A draft can never be
  served as an approved meeting record.
- An approved RKA baseline is its own immutable record with an effective period. A forecast or a
  later revision is a new record and never an update.
- Reading any snapshot rechecks current access; revocation denies history too.
- _Acceptance:_ SNAP-01.
- _Tests:_
  - Closing a current action leaves the old snapshot's hash unchanged.
  - An unpublished draft can't pass as published.
  - A forecast write can't touch a baseline.
  - A revoked reader is denied a snapshot they could read before.

**T6 — Reviewed imports** (`imports.py`).

- Input is a structured candidate file in the dataset schema. **P2 doesn't parse PPTX**: extraction
  stays outside the app, and P3's assistant can prepare candidates later.
- Each candidate is matched to an existing action only through a reviewed `leadership_external_ref`
  (source deck plus slide plus owner-confirmed id). Otherwise it is a new-action candidate, which a
  reviewer must accept or link.
- An action absent from a later deck stays open. Recurrence never duplicates.
- Conflicts (different values, dates or states for the same record) are stored and shown and never
  auto-resolved. Draft, hidden or old-slide metadata survives ingestion.
- Nothing is labelled `verified` until an owner with `imports.review` approves that record or
  formula.
- _Acceptance:_ ACT-01, DATA-01 (P2 part), DATA-02.
- _Tests:_
  - Re-importing the same deck is a no-op.
  - A later deck that omits an action leaves it open.
  - A conflicting value creates a conflict record, not an overwrite.
  - A missing value stays null with its reason.

**T7 — Reader and API integration.**

- `reader.py` serves from the repository when records exist, and from the sample file only in
  sample mode (which is visibly labelled, as now). There is never a silent fallback.
- New routes, all `private, no-store`, all rechecking access per request:
  - `GET /actions/{id}` and its history
  - `POST` for progress, evidence, closure request and review decision
  - `GET /evidence/{id}`
  - `GET`/`POST /snapshots`, publish
  - `GET /baselines`
  - `POST /imports`, candidate review
- `capabilities.operations` now lists what the caller may do.
- Every read and state change writes a `governance.audit` line: user, operation, record ids, result,
  and never values or evidence content. For state changes the event row is the record of authority,
  and the audit line is the operational trail.
- _Acceptance:_ ACCESS-01 (P2 surfaces), HOST-03 (expanded).

**T8 — Frontend** (`src/lib/components/leadership/`).

- Components:
  - Action detail with event history
  - PIC progress and evidence form
  - BOD review queue and decision dialog
  - Meeting history with a snapshot viewer (showing draft/published state and correction links)
  - RKA baseline versus draft comparison
  - Import review screen (candidates, matches, conflicts)
- The "changes since last meeting" and "decisions required" modules move from the unavailable state
  to real data once two comparable snapshots exist.
- Every string gets id-ID translation through literal `$i18n.t('...')` calls. Keyboard, contrast,
  text-scale and 390 px checks as in the P1 gap walk. Named dialogs use `ariaLabelledby`.
- _Acceptance:_ UX-02 (expanded).

**T9 — End-to-end walk and evidence.**

- Run locally in real Chrome with synthetic PIC, BOC, BOD (individual and collective), publisher,
  import reviewer and admin identities. Use the design's foundation walkthrough:
  1. Open a revenue exception, then its definition and source.
  2. Follow the linked RKA assumption to its action.
  3. Submit evidence as the PIC.
  4. Try an unauthorised closure.
  5. Close as the configured BOD.
  6. Check that the current view changed and the previous snapshot's hash didn't.
  7. Revoke access and check that history is denied.
- Record each acceptance ID in `status.md` with its commit, environment, data mode and command.

## Order, size and review points

T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9. T7's routes and T8's screens land with each
domain task rather than all at the end, so each task ends with a working HTTP slice.

Rough size: T0 half a day; T1–T2 one day; T3–T4 one and a half days; T5 one day; T6 one day;
T7 and T8 spread across all of them (about two days); T9 half a day. That is about seven
working days of agent time.

At E3 or above, Forge takes the domain modules (it needs the Codex CLI upgrade to run its pinned
model). Cato audits the ADR and the closure policy before T4 merges.

Review points where I stop for Erik:

- after T0 (ADR-0014 and the migration seam)
- after T4 (the closure policy, before anything BOD-shaped goes further)
- before any deploy

## Stays blocked on company decisions (build proceeds with test config)

These block production use of the matching operation, not the build:

- BOD identities, and whether BOD closes individually or collectively, which set
  `JUP_LEADERSHIP_BOD_POLICY`.
- PIC identity mapping.
- Publication authority.
- KPI and formula owners and definitions, needed before anything is labelled verified.
- Retention, backup and data location for leadership records in Cloud SQL and `jup-ops-data`. This
  is the design's "host deployment suitability" item and must be answered before live company data
  goes in.

The illustrative sample stays the production data source until an owner-reviewed import replaces
it.
