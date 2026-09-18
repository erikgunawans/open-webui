# Gate state is a set of assessments, not a status field

A **Gate Assessment** records one attempt to pass a gate: the project, the gate, the evidence
presented, the verdict, who signed, and when. A project's **current gate** is derived as the highest
gate holding a passing assessment — it is never stored as a field, and a failed assessment is
recorded exactly as a passing one is.

Fail-closed governance is about recording refusals. `~/jup/kb/CONTEXT.md` already holds the strategy
assistant to logging every turn, answered *and* refused; a gate applies the same discipline to
capital. A mutable status field is precisely the artefact that lets a board forget it stopped a
project in August, and why.

## Consequences

"The gas pillar failed G1 three times on the same missing 5 mmscfd allocation" becomes a query
rather than an anecdote.
