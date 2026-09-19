# The Strategy KB's state claims are generated from `records/`, never typed twice

`records/` (ADR-0004) is the single source for partner and gate state. The partner state table in
`~/jup/kb/partners.md` and the ladder line above it are **generated** from `records/engagements/`
by `jup.kb_sync`; a `--check` mode fails when they disagree.

Before this, `records/` was read by the portfolio projection and by nothing else, while the same
state also lived in `kb/partners.md`, `kb/gas.md`, `kb/governance.md` and the board deck. They
agreed — because someone typed the same thing twice. `kb/partners.md` is loaded **whole** by the
deployed strategy assistant, so a drift there is not a stale document: it is what a commissioner is
told when they ask where PGN stands.

Three mechanisms, in descending order of strength, because not everything can be generated:

1. **Generate** what is structured — the state table, the ladder line.
2. **Refuse a second home for the vocabulary.** A stage-ladder label used as a table cell outside a
   generated region is drift by construction, whether or not it is right today. Prose is exempt: the
   ladder's *definition* teaches a reader what the table means, and "The critical one" argues its
   case about SKK Migas and PGN/Pertagas by name.
3. **Check** what must stay prose. `kb/gas.md` and `kb/governance.md` argue that the 5 mmscfd
   allocation is unsecured. That claim is tested against the G1 assessments **in both directions** —
   deleting the caveat fails as loudly as contradicting it, because a governance caveat is a claim
   and its disappearance is drift too.

A counterparty with no engagement record sits on **no rung at all**, not the bottom one. Rows for
those counterparties keep their name and purpose and lose their stage, because a rung requires a
document (ADR-0008) and none is filed. Filing a record moves the row into the generated table, and
the check refuses to let it sit in both.

## Consequences

**The gate is a hook, not CI.** Both repositories are private and no cross-repo checkout is wired
up, so a GitHub Actions job in either one cannot see the other without a PAT nobody has issued.
What runs where:

| Gate | Where | Proves |
|---|---|---|
| Forced-failure tests | ent-os-new-jup CI | the check catches drift, in five distinct ways |
| `test_the_real_jup_tree_has_no_drift` | every local `pytest` | the live tree is clean; skipped in CI |
| `~/jup/.githooks/pre-commit` | every commit touching `records/` or `kb/` | drift never reaches a commit |

Enable the hook once per clone with `git config core.hooksPath .githooks`. It checks the working
tree rather than the staged content, so a partial stage can still commit drift; wiring cross-repo CI
with a token would close that, and is the open follow-up.

**A record edit now has a second step.** `gs://jup-ops-records` is an rsync and the Worker reads a
built bundle, so a committed record reaches the dashboard only after `sync-records.sh`, and reaches
the assistant only after `bun build-kb-bundle.ts` and a `wrangler deploy`. The deploy is separately
authorised every time. This ADR removes one hand-copy and leaves two builds; the builds at least
fail loudly, which the hand-copy never did.
