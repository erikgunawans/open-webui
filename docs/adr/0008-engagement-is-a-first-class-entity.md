# Engagement is a first-class entity; gates cite engagements

A counterparty **Engagement** — who, what for, which stage, and the artefact evidencing that stage —
is its own record. Gate assessments (ADR-0003) **cite** engagements rather than copying their state,
so one record serves every gate that depends on it.

D7's 5 mmscfd gas allocation is simultaneously an engagement with SKK Migas and PGN/Pertagas *and*
the binding evidence requirement for G1 across the entire gas pillar. Embedded state would go stale
in two places the first time a counterparty replies to anything.

The stage ladder replaces the informal vocabulary in `~/jup/kb/partners.md` — Initiate, Follow-up,
Strengthen, Live, Open·contingent — in which "Follow-up" and "Strengthen" differ in *tone* rather
than in stage, and neither states what would have to be true to advance:

**No contact → Contacted → In discussion → Written intent (LOI/MoU) → Executed (KSO/PKS).**

Each rung requires a document to stand on, exactly as a gate does.

## Consequences

The status column in `~/jup/kb/partners.md` becomes inconsistent with this ladder and needs
migrating. That file is read by the deployed strategy assistant, so the migration is a content change
with an audience, not a refactor.
