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

`engagements-shared/` is the ADR-0008 corpus: **one** Engagement cited by gates on **two
different projects**, so a projection that copied its state instead of citing it would have
the same counterparty current in one place and stale in the other. `certainty-tier/` exists
to prove the ADR-0009 ban does **not** catch `certainty` — Certainty Tier (D11) is the
legitimate concept, and banning it would refuse the field that keeps FAKTA and POTENSI
apart.

**A record's `purpose` containing ` #` must be quoted.** In YAML a bare hash starts a
comment, so `purpose: ... — Gate #1 of the gas pillar` silently parses as `... — Gate`.
Nothing raises: the parser receives a shorter, perfectly valid string, so no guard can catch
it. `test_a_purpose_containing_a_hash_survives_when_quoted` pins the quoted form, because
"Gate #1" is the exact phrase the first real records use.

`figures/` is the D11 corpus — one project carrying figures on **three** tiers, which must
project as three groups and never as one list, beside one carrying none (the correct
default). `figures-potensi-legitimate/` guards the other direction: *"Marginal volume"* is
not a margin, and the ban matches whole words, because a false refusal blocks a PMO analyst
from recording a true figure. The `malformed-figure-*` directories cover a POTENSI figure
labelled as margin, as NPV and as `laba`, plus a tier outside the three and a figure missing
its tier, basis or value.

The **unreadable**-directory case has no fixture: it needs a live `chmod 000`, so those two
tests build it under `tmp_path` and skip when the chmod does not bite (as it would not for
root).
