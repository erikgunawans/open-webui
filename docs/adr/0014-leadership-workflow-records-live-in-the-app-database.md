# Leadership workflow records live in the app database, as an append-only event log

**Status: Accepted 2026-09-24 — Erik Gunawan Supriatna, Director, Operation & Business
Development.** Approved with the Ruang Pimpinan P2 plan (`docs/ruang-pimpinan/p2-plan.md`,
decisions E-1, E-2 and E-3).

Ruang Pimpinan P2 adds records that change through the day: a PIC submitting progress and
evidence, a BOD reviewer closing or returning an action, a meeting snapshot being published, an
import being reviewed. These are the fork's first persisted state. Until now every JUP record has
been either a file in `~/jup` (ADR-0004) or read-only data in the records bucket.

## Decision

1. **Actions, their events, evidence, closure requests and decisions, snapshots, RKA baselines and
   import candidates live in the app's database** (Cloud SQL Postgres 16 in production), in
   fork-owned `leadership_*` tables.
2. **Every change is an appended event row.** An event records its author, time, reason and the
   version it replaced. The aggregate row (an action's current state) is a projection of its events,
   and code has no path that updates or deletes an event. A state change, its event and the version
   bump commit in one transaction. A stale `expected_version` returns a conflict and writes nothing.
3. **These tables migrate on their own alembic graph,** at `backend/jup/leadership/migrations/`,
   recorded in its own version table, `jup_alembic_version`, not in the vendor's `alembic_version`.
   - `main.py` runs it after the vendor upgrade, under the same `ENABLE_DB_MIGRATIONS` switch.
   - A failure is logged and leaves only Ruang Pimpinan unavailable (`schema_ready()` is False);
     chat keeps running.
   - `tests/test_boot.py` holds both graphs to one head and one base.
4. **Evidence files are stored with the host storage provider under `leadership/evidence/`**
   (production bucket `jup-ops-data`). They are served only by a leadership endpoint that rechecks the
   action's permissions on every request, and never through the vendor Files table.

## Why this departs from ADR-0004, and where it doesn't

ADR-0004 kept gate assessments in `~/jup` because "a row cannot say who changed it or what it said
last month". Its argument was about provenance, and an append-only event log answers it. Who
changed an action, when, why and from what is in the events, and the same query answers what an
action said last month.

What git can't give P2 is the web-request shape of the work:
- a PIC and a BOD reviewer acting on the same action within seconds, which needs per-request
  transactions and an optimistic-version conflict
- a double-clicked submission that must be idempotent
- per-record access checks on every read, including history

A commit per PIC submission from the web tier would also turn a governance log into a
merge-conflict queue.

**ADR-0004 is unchanged for what it governs.** Gate assessments stay markdown in `~/jup`, and the
Strategy KB stays generated from records (ADR-0011). The metrics dataset keeps its current authority
(the configured sample, or later a reviewed import) until an owner-reviewed import replaces a record.

## Why a separate migration graph

A fork revision inside the vendor graph must be re-pointed at the new upstream head at every
quarterly rebase (ADR-0007). The deployed database must then be re-stamped, and getting either wrong
stops the app booting, because the vendor runs `upgrade head` at config import. A separate graph
never shares a head with upstream, so a rebase can't collide with it. It costs one call site in
`main.py`, recorded in `deploy/gcp/VENDOR-PATCHES.md` and guarded by a source-read test.

## Why evidence stays out of the vendor Files table

Vendor files carry their own sharing, knowledge-collection and chat-attachment paths. A leadership
record reachable through any of those would bypass the section's access checks (HOST-04,
ACCESS-01). Keeping evidence behind its own endpoint means one access rule and one audit trail.

## Consequences

- **Leadership records inherit the database's retention and backup.** Whether Cloud SQL's current
  settings are suitable for board records is an open company decision ("host deployment suitability"
  in the approved design). It must be answered before live company data goes in; test data may go in
  before then.
- There is no git history for these records. The event log is the history, and a future export
  (for archiving or disclosure) reads from it.
- Two alembic graphs share one database. A table name collision is prevented by the `leadership_`
  prefix; the head checks run over both graphs.

## Considered options

- **Markdown in `~/jup`, written by commits.** Rejected for the concurrency, idempotency and
  per-record access reasons above.
- **Fork revisions in the vendor chain.** Cheaper today, with a recurring cost and a boot-stopping
  failure mode at every rebase. Rejected.
- **Evidence in the vendor Files table.** Rejected: its sharing paths are wider than the section's
  access rules.
