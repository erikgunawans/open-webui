---
description: Show the agent-depth phases (holaOS gap, ChatGPT Live voice, Hermes runtime) and what each waits on
argument-hint: '[A|V|H|I|P] — optional track filter'
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
- if the plan's Status line still says DRAFT, say that nothing may be executed until Erik approves.

Do not start work on a phase from this command. When a phase's status changes, edit the ledger row
in the plan (keep the table's five columns and the status vocabulary: live, in-progress, ready,
blocked, planned) — never a copy elsewhere.
