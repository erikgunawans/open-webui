# `evidence/`

The evidence-detail scenario for ticket #4. It holds the three cases the blocking
derivation has to tell apart:

- **`gas-spbg-reactivation`** is refused twice at G1 on the *same* missing allocation and
  once on a second requirement. Its blockers must name the allocation once, not twice.
- **`air-marunda-perpipaan`** *passed* G1 with an unsatisfied requirement recorded — a
  waiver the board granted on the record. A waiver is not a blocker.
- **`properti-kalibaru-rusun`** has one assessment carrying no `evidence:` key at all,
  which is permitted and means the record states no requirements.
