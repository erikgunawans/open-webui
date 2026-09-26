# JUP Operating Layer

The governed AI workspace PT Jakarta Utilitas Propertindo runs internally. Its job is to deliver the
operating layer JUP's own board materials name as missing — PMO cadence, HSE, KPI visibility and
partner SLAs reconciled to evidence — under the same fail-closed discipline JUP asks its partners to
trust.

## Language

**Operating Layer**:
The management capability JUP must hold in-house for the JUP 2.0 transformation to be deliverable:
PMO cadence, HSE leadership, KPI visibility, and audited partner SLAs.
_Avoid_: platform, tooling, internal tools, enablement

**Gate**:
One of four fail-closed stage gates — G1 feasibility, G2 capital committed, G3 commissioned,
G4 steady state — that a project must pass before capital moves to the next stage.
_Avoid_: stage, milestone, phase, checkpoint

**Fail-closed**:
The property that a control which cannot compute or prove its answer stops, rather than proceeding
on optimism. A gate that cannot verify defaults to no; an assistant that cannot ground an answer
refuses it. The refusal is the guarantee, not the failure.
_Avoid_: strict mode, safe mode, guardrail, blocking

**Certainty Tier**:
The basis a figure rests on — FAKTA (feasibility economics), POTENSI (top-line revenue potential,
never margin), or ILUSTRATIF (order-of-magnitude sizing). Two tiers are never blended in one
statement.
_Avoid_: confidence, accuracy, quality, reliability score

**Named Non-Coverage**:
The explicit statement of what a result does not prove, published alongside the result itself.
_Avoid_: caveat, disclaimer, limitation, known issue

**Strategy KB**:
The curated body of JUP material an assistant is permitted to ground answers in. Material outside it
is not merely unretrieved — it is out of bounds.
_Avoid_: the docs, corpus, context, source material

**Gate Assessment**:
One recorded attempt to pass a gate — the project, the gate, the evidence presented, the verdict,
who signed, and when. A refusal is recorded exactly as a pass is.
_Avoid_: gate status, gate review, approval, sign-off

**Current Gate**:
The highest gate for which a project holds a passing assessment.
_Avoid_: stage, status, progress, maturity

**Voice Scope**:
The explicitly named set of Strategy KB documents a voice session may retrieve from. Material
outside it is unreachable, not merely deprioritised.
_Avoid_: voice permissions, allowlist, filter, restriction

**Engagement**:
A relationship with a named counterparty, pursued for a stated purpose, held at a stage that a
document evidences.
_Avoid_: partnership, relationship, deal, opportunity, lead

**Engagement Stage**:
The rung an engagement occupies — No contact, Contacted, In discussion, Written intent (LOI/MoU), or
Executed (KSO/PKS). Each rung requires an artefact to stand on.
_Avoid_: Initiate, Follow-up, Strengthen, Live, pipeline stage, temperature

**Risk Class**:
What a tool is allowed to touch — `read` (reads only), `write_own` (writes inside the calling user's
own data), or `external` (any effect outside the user's own space). A tool with no declared class is
`external`.
_Avoid_: permission, scope, trust level, safety rating

**External Call**:
One invocation of an `external` tool. It runs only after the user whose turn produced it approves
that exact call; with nobody present to approve, it is refused.
_Avoid_: risky action, write, side effect, dangerous call

**Decision**:
A numbered, dated entry in JUP's decisions register (D20) stating what was decided, its status, the
reasoning, and its named non-coverage. A reversed or superseded Decision stays in the register with
that status.
_Avoid_: D-row, D-decision, ruling, resolution, approval
