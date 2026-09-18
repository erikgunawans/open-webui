# Portfolio fixtures

One subdirectory per scenario, each a records root holding `projects/` and
`gate-assessments/` exactly as `~/jup` does (ADR-0004). `portfolio-basic/`, `gate-ladder/`
and `ordering/` are the readable corpora — three project states side by side, gate
derivation and durability, and filenames that deliberately fight the sort keys. The
`missing-*` and `no-assessments/` directories cover the empty-with-reason states, and each
`malformed-*` directory holds exactly one untrustworthy record so the `RecordError` a test
observes is the one it named.

`evidence/` is the corpus for evidence detail and the blocking derivation: a pillar refused
twice on one requirement, a gate *passed* with a requirement outstanding (a waiver, which
is deliberately not a blocker), and an assessment carrying no `evidence:` key at all.
