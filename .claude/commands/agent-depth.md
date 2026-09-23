---
description: Show the agent-depth phases (holaOS gap, Asisten JUP harness enhancements, ChatGPT Live voice) and what each waits on
argument-hint: '[A|E|V|I|P|X] — optional track filter'
allowed-tools: Bash(bun scripts/agent-depth.ts:*)
---

# /agent-depth — the agent-depth phase ledger

Run the ledger printer and show its output to the user verbatim, in a code block:

```bash
bun scripts/agent-depth.ts $([ -n "$ARGUMENTS" ] && echo "--track $ARGUMENTS")
```

The source of truth is the `## Phase ledger` table in `.planning/agent-depth-plan.md`; the script
only reads it. After the output, add at most three lines:

- the **next** phase and what it waits on;
- any item in "Decisions Erik owns" that is blocking a `ready` or `blocked` phase;
- remind that each deploy and each DB write still needs Erik's per-change OK.

Do not start work on a phase from this command. When a phase's status changes, edit the ledger row
in the plan (keep the table's five columns and the status vocabulary: live, in-progress, ready,
blocked, planned, parked) — never a copy elsewhere.
