# Gate assessments live in the JUP repo as markdown, not in this database

Gate assessments are markdown files in `~/jup`, alongside `DECISIONS.md`. This system reads them and
renders the dashboard as a projection; PMO entry through the UI works by writing a file and
committing it.

A table in our own Postgres was rejected: it creates a second source of truth beside the board pack
with no provenance. A row cannot say who changed it or what it said last month — which is exactly
what an audited governance artefact must be able to say. Git supplies tamper-evident, diffable,
reviewable history for free, and at roughly a dozen projects there is no scale argument for a
database.

## Considered options

- **Postgres table with a markdown export.** Survives the coupling objection below, but reintroduces
  the provenance gap it was meant to close: the export is derived, the row is authoritative.

## Consequences

This repository is coupled to `~/jup` and must handle concurrent edits and commit authorship. In
exchange, the dashboard cannot disagree with the board pack — by construction, not by discipline.
