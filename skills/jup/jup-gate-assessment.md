---
id: jup-gate-assessment
name: JUP stage-gate walkthrough (D10)
description: Walk a JUP project through its fail-closed stage-gate G1–G4 requirements against the evidence on record. Use when asked where a project stands, whether it can proceed, or what is missing.
tags: [jup, governance, d10, gates]
---

# JUP stage-gate walkthrough (D10)

The JUP stage-gates **fail closed**: if something can't be proven from the record, the answer is "no", not "probably yes". No capex moves on faith.

## Steps

1. **Find the project and its assessments** in the knowledge base (`records/projects/`, `records/gate-assessments/`). Use only what is filed.
2. **The current gate is computed, never stored.** It is the highest gate that has a **passing** assessment (ADR-0003). A project with only failed or missing assessments hasn't passed G1, whatever any document says about progress.
3. **For the gate in question, list every requirement** from `kb/governance.md`:
   - **G1 · Feasibility**: stress-tested financials, confirmed offtake, permit pathway, Pertamina LO (energy), RUED alignment test, and gas allocation (gas pillar).
   - **G2 · Capital committed**: KSO/PKS signed, and partner funds in escrow.
   - **G3 · Commissioned**: FAT/SAT, HSE sign-off, and as-built documentation.
   - **G4 · Steady state**: at least target throughput for 3 consecutive months.
4. **Mark each requirement from the record**: satisfied (with its artefact or engagement), not satisfied, or **no evidence on file**. "No evidence on file" counts as not satisfied.
5. **Give the verdict the record gives**, and quote its date and signer. Treat a refusal as the result of an assessment, not as a missing one.
6. **Name what would change the verdict**: the specific missing artefact. For an engagement, say which rung it is on and what a contact record would need to show.

## Never

- **Never estimate the likelihood** that a gate will pass or that a partner will agree. There is no likelihood field on purpose (ADR-0009). Say where things stand, not whether they will close.
- **Never treat a stated intention, meeting or verbal agreement as a satisfied requirement.** Only a filed artefact counts.
- **Never report a gate as passed** because later-stage work is happening. The gate order still holds.

## Answer shape

Start with one line giving the current gate and the verdict. Follow it with a requirement table (requirement | status | evidence), then the missing items. Close with the named non-coverage, meaning what this walkthrough does not prove.
