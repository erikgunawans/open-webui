# JUP 2.0 — Decision Log (fixture)

> A cut-down copy of `~/jup/DECISIONS.md`'s shape, for `tests/test_jup_decisions.py`. The rows are
> abridged; the table layout, bold markers and the non-coverage convention are the real file's.

| # | Decision | Status | Why | Date |
|---|----------|--------|-----|------|
| **D2** | **Gas is the core.** Sequence: reactivate idle SPBG → CNG Horeca → Jargas. | DECIDED | JUP is already the DKI vehicle-gas operator. | 2026-07-12 |
| **D7** | **Gas allocation (5 mmscfd) = GATE #1.** Nothing in the gas pillar proceeds without it. | **OPEN — the binding constraint** | Not committed. Counterparties: **SKK Migas** and **PGN / Pertagas**. | 2026-07-12 |
| **D13** | **JUP material stays local / offline.** | STANDING RULE, superseded 2026-07-14 by a broader exception (below) | JUP is not Erik's company. Named non-coverage: this record does **not** claim the hosting is audited. | 2026-07-13 |
| **D16** | **JUP material may be spoken to an AI voice interface processed by OpenAI in the United States.** | DECIDED — control (1) amended by **D21** (2026-09-26) | The operating layer needs a director-facing briefing surface. **Named non-coverage:** (a) no audit claim; (b) the named set bounds retrieval, not speech. | 2026-09-19 |
| **D18** | **The JUP brand is the Graphic Standard Manual 2023.** | REVERSED the 2026-09-18 house style | One brand, not two. **Named non-coverage:** (a) the GSM has no dark mode. | 2026-09-22 |
| **D20** | **MCP tool servers: JUP-hosted, read-only servers that make no outbound calls are one pre-approved class.** | DECIDED — standing rule | The line is drawn at egress. **Named non-coverage:** (a) "read-only" is asserted at attach time. | 2026-09-26 |
| **D21** | **Voice (D16) may be built and used without zero data retention confirmed.** | DECIDED — Erik's final answer | Getting ZDR needs OpenAI's approval, with no date. | 2026-09-26 |

---

## Open items — waiting on someone else

| Item | Blocks | Counterparty |
|------|--------|--------------|
| **Gas allocation, 5 mmscfd** — the single hardest dependency | The entire gas pillar (D2, D7) | SKK Migas · PGN / Pertagas |
| **Transjakarta offtake** — assumed captive | SPBG reactivation revenue | Transjakarta |

## Named non-coverage — what this plan does *not* prove

- Gas figures are **potential revenue, not margin**.
