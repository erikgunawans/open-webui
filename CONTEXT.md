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

**Channel**:
An outside messaging surface Asisten JUP answers in — Microsoft Teams, later WhatsApp. The web app
is not a Channel.
_Avoid_: integration, connector, platform, the vendor's Channels feature

**Channel Identity**:
Who the sender is inside a Channel — in Teams, the Entra object id and tenant; in WhatsApp, the
phone number. It is never a JUP user by itself.
_Avoid_: channel user, account, handle

**Mapping**:
Turning a Channel Identity into exactly one JUP user. A sender is mapped or unmapped, never partly
mapped; an unmapped sender is never forwarded to the model.
_Avoid_: linking, binding, pairing, account match

**Link Code**:
A six-digit code the web app shows a signed-in user so they can prove a WhatsApp number is theirs by
sending it from that number. Ten minutes, single use; it can only link a number, nothing else.
_Avoid_: OTP, verification code, PIN

**Channel Turn**:
One question and its answer carried through a Channel on behalf of a mapped user. It is one kind of
unattended turn: nobody is present to approve an External Call, so one is refused.
_Avoid_: channel message, bot turn, automation

### Rapat Direksi

**Notulen**:
The minutes of one Rapat Direksi as the Corsec keeps them while the meeting runs: every Butir
pembahasan, Usulan and Tindakan, agenda by agenda.
_Avoid_: notes, workspace, Notion page

**Layar**:
The projected view of the same meeting the Direksi read from across the room. It shows the Notulen;
it is not a second copy of it.
_Avoid_: slides, presentation, deck

**Risalah**:
The formal record printed from a closed Notulen, built only from its Butir pembahasan, Usulan and
Tindakan.
_Avoid_: report, summary, export

**Butir pembahasan**:
One topic discussed under an agenda.
_Avoid_: record, baris, row, item

**Usulan**:
Something put to the Direksi for a decision. It stays Belum diputuskan until it ends in a Keputusan.
_Avoid_: proposal record, decision item

**Keputusan**:
How the Direksi end an Usulan: Disetujui, Disetujui bersyarat, Ditunda or Ditolak. A Ditunda
carries the date the Usulan comes back; without one it is not a Keputusan. Every Keputusan carries
its Rumusan, the decision in words. A Ditunda still waits: the rail and the Tutup rapat check
count it with the Usulan belum diputuskan.
_Avoid_: status, outcome, resolution

**Pertimbangan**:
Why the Direksi decided as they did. Separate from the Syarat: reasoning is not a condition.
_Avoid_: syarat, rationale note

**Syarat**:
The written condition a Disetujui bersyarat carries. A Keputusan bersyarat does not exist without one.
_Avoid_: pertimbangan, note, catatan

**Tindakan**:
A follow-up the Direksi assign, with exactly one PIC and a tenggat.
_Avoid_: action plan row, task, to-do

**Arahan**:
The Direksi's direction on a Butir pembahasan, in words. An Arahan that names who and by when is
also a Tindakan; the Arahan alone is never tracked.
_Avoid_: instruksi, kesimpulan, directive

**Kolom**:
One field of a Butir pembahasan, Usulan or Tindakan.
_Avoid_: properti, property, field

**Kolom inti**:
The few Kolom of a Butir pembahasan, Usulan or Tindakan the Corsec fills while the meeting runs, in
working order. Every other Kolom is filled before or after.
_Avoid_: required fields, mandatory

**Catatan pembahasan**:
The running notes the Corsec types for one agenda as the discussion moves. Not part of the Risalah
unless the Corsec says so.
_Avoid_: transcript, catatan panjang, body

**Tutup rapat**:
The Corsec ending the meeting. It freezes the Notulen; reopening needs a written reason, and that
reason appears in the Risalah.
_Avoid_: finish, end session, close agenda
