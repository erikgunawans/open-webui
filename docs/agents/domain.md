# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

**Layout: single-context.** One `CONTEXT.md` at the repo root and one `docs/adr/`
covering the whole system — the SvelteKit frontend in `src/` and the Python/FastAPI
backend in `backend/` share a domain vocabulary, so they share a glossary.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

`CONTEXT.md` does not exist yet, and `docs/adr/` is empty. That is the expected
starting state — both fill in lazily.

## File structure

Single-context repo (most repos — **this repo**):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context repo (presence of `CONTEXT-MAP.md` at the root):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

If this repo ever splits frontend and backend into genuinely separate domain
languages, add `CONTEXT-MAP.md` at the root pointing to `src/CONTEXT.md` and
`backend/CONTEXT.md`, and the skills will switch modes automatically.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_

## Vendor code vs. our code

Most of this tree is inherited from `open-webui/open-webui`. ADRs and `CONTEXT.md`
describe **our** decisions and **our** domain language, not upstream's. When an
architectural choice was simply inherited rather than decided here, it does not need
an ADR — record an ADR when we deviate from upstream, or decide something upstream
left open.
