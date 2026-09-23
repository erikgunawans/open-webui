# Ruang Pimpinan — delivery status

Source of intent: the approved design handed over on 2026-09-24
(`~/Documents/ChatGPT/KPI-Dashboard-JUP/docs/handovers/2026-09-24-ruang-pimpinan-claude-code/`,
read-only). That package's approved design, roadmap, contracts and acceptance matrix govern; this
file records what exists in this repository and what the evidence for it is.

**P1 (native read foundation) is implemented and verified locally. It is not deployed, not enabled
anywhere, and holds no real grant.** The whole product is P1–P5; P1 is not completion.

| Item     | State                                                                                                                                                                   |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Commits  | `34dbd9421` (records, policy, API), `ad63a9133` (views, sidebar, preview), plus this file and two id-ID fixes                                                           |
| Pushed   | No. Push is a separate authorisation.                                                                                                                                   |
| Deployed | No. `JUP_LEADERSHIP_ENABLED` is unset in production, so the API answers 503 and the sidebar entry never shows.                                                          |
| Data     | Illustrative only: `tests/fixtures/leadership/illustrative-seed.json`, figures from the 18 Sep 2026 BOD deck and the RKA 2027 Draft 1, labelled unverified and partial. |
| Grants   | None in production. Local verification used synthetic users and groups in a scratch database.                                                                           |

## Where it lives

| Concern                                              | Path                                                                         |
| ---------------------------------------------------- | ---------------------------------------------------------------------------- |
| Dataset validation, variance                         | `backend/jup/leadership/records.py`                                          |
| Read policy (default deny, admins included)          | `backend/jup/leadership/policy.py`                                           |
| Shared reader (human API now, assistant tools in P3) | `backend/jup/leadership/reader.py`                                           |
| HTTP surface                                         | `backend/open_webui/routers/jup_leadership.py` at `/api/v1/leadership`       |
| Frontend API, context, formatting                    | `src/lib/apis/leadership/`, `src/lib/leadership/`                            |
| Views                                                | `src/lib/components/leadership/`, `src/routes/(app)/ruang-pimpinan/`         |
| Sidebar entry                                        | `src/lib/components/layout/Sidebar.svelte` (after Portofolio, both variants) |

Configuration: `JUP_LEADERSHIP_ENABLED` (`true`/`1`) and `JUP_LEADERSHIP_SAMPLE_FILE` (server path).
A grant is a group permission, exact boolean, view **and** scope:
`{"jup": {"ruang_pimpinan": {"board": {"view": true}, "rka": {"view": true}, "scopes": {"jup_consolidated": true}}}}`.

## Evidence, 2026-09-24

Automated:

| Command                                                                                                                                                                              | Result                                                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| `uv run --no-sync --only-group dev pytest tests/test_leadership_records.py tests/test_leadership_policy.py tests/test_leadership_reader.py tests/test_jup_router_registration.py -q` | 112 passed                                                                              |
| `uv run --no-sync pytest tests/test_jup_leadership_endpoint.py tests/test_jup_portfolio_endpoint.py -q` (runtime installed)                                                          | 41 passed (26 leadership, 15 Portfolio unchanged), 0 skipped                            |
| `bunx vitest --run src/lib/leadership`                                                                                                                                               | 18 passed                                                                               |
| `svelte-check` after `svelte-kit sync`                                                                                                                                               | 7794 errors / 202 warnings, identical to the pre-change baseline: this change adds none |
| `ruff check` / `ruff format --check`, `prettier --check`, `i18n:parse`                                                                                                               | clean; every new string has an id-ID translation                                        |

Under CI's `--only-group dev` the endpoint file skips (no runtime). A skip there is not a pass;
the 26 HTTP tests above ran with the runtime.

Local rendered walkthrough (option (a): backend on 8080 and Vite on 5050, scratch `DATA_DIR` and
`STATIC_DIR`, driven in real Chrome through Interceptor, synthetic users `reader` (Board and RKA),
`boardonly`, `member`, and the first-signup `admin` with no grant):

- Live API matrix against the real app and database: signed out 401; admin without grant 403 on
  overview and source; member 403; board-only Board 200 and RKA 403; RKA source through the RKA view
  403, through the Board view 404; bad scope 422; revoking the group membership turned the next
  request into 403 and re-granting restored 200. Every response carried `private, no-store`.
- The vendor group API stored the `jup.ruang_pimpinan` permissions intact.
- Reader: `/ruang-pimpinan` opened Board; tabs, 3 cards, sidebar entry active. id-ID rendering
  checked: labels, `Rp144,47 miliar`, `−Rp14,00 miliar`, `−0,9 poin persentase`, "3 contoh dari
  presentasi · bukan total", five module states with reasons.
- Source dialog for revenue: file, 18 September 2026, slide 4, visible, presented, unverified.
- Context preview: zero network requests while opening it, nothing added to the URL.
- Selecting a record put only `?record=<id>` in the URL; Board → RKA → Back restored it.
- RKA: 2027 draft, comparators labelled as 2026 forecasts; the water action is the same record.
- `?context=example-rka-2027-draft-1` on Board: "Pilihan ini tidak tersedia", no metrics.
- Board-only: one tab; `/rka` refused with the server's reason in Indonesian. Member and admin: no
  sidebar entry, both routes refused. Admin still lands on and sees Portfolio.
- Contrast, measured: every checked text 5.66:1 or better in light, 6.02:1 or better in dark.
- 390 px viewport (same-origin iframe, a real media-query viewport): no page overflow, one column.
- Collapsed rail entry has its accessible name and `aria-current`; expanded entry sits before pins.

Not verified: text-scale above 100% and keyboard-only traversal were not walked end to end; the
Portfolio filter/deep-link behaviour was verified live on production earlier the same night rather
than locally (no local records).

## Acceptance matrix

| ID             | Stage     | Status                  | Evidence / gap                                                                                                                         |
| -------------- | --------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| UX-01          | P1        | passed (fixture)        | Layout A in both views; sources and register reachable without chat.                                                                   |
| UX-02          | P1, P2/P4 | partial                 | Scope, period, units, source status visible; id-ID, 390 px and table regions checked. Freshness is P2/P4; keyboard-only walk not done. |
| HOST-01        | P1        | passed (local)          | One entry, expanded and collapsed; active on descendants; Portfolio and chat landing unaffected. Mobile drawer not separately walked.  |
| HOST-02        | P1        | partial                 | Light and dark measured, no double sidebar subtraction, no overflow. Font override and text scale not walked.                          |
| HOST-03        | P1, P2    | passed (P1 scope)       | Back/refresh keep context; board-only denied RKA by URL and API; admin without grant denied.                                           |
| HOST-04        | P3        | context preview only    | Preview sends nothing. The real assistant surface is P3.                                                                               |
| DATA-01        | P1, P2/P4 | P1 part passed          | Actual, budget and forecast kept apart; variance only like-for-like. Reconciliation to sources is P2/P4.                               |
| DATA-02        | P1, P2/P4 | P1 part passed          | Missing is never zero (validator and card); malformed dataset is 503, never an empty report.                                           |
| ACT-01         | P1, P2    | P1 part passed          | One shared action id resolves to one record in both views. Re-import identity is P2.                                                   |
| ACT-02         | P2        | not started             | No write route exists; nothing can close an action.                                                                                    |
| ACT-03         | P1, P2    | P1 part passed          | Month, year and range targets shown with their precision; no overdue computed.                                                         |
| SNAP-01        | P2        | not started             |                                                                                                                                        |
| ACCESS-01      | P1 → P5   | P1 read surfaces passed | Views, API and sources enforce and re-check per request. History, search, export and tools arrive later.                               |
| MX-01          | P1, P3    | P1 part passed          | UI and API read one reader module. Tools are P3.                                                                                       |
| WRITE-01       | P3/P4/P5  | not started             |                                                                                                                                        |
| INTEGRATION-01 | P4/P5     | not started             | Dynamics variant and CRM choice are still open.                                                                                        |

## Next stages (from the approved roadmap)

- **P2: durable workflows.** Action aggregate with append-only events, PIC evidence, BOD closure
  review (policy disabled until configured), meeting snapshots, RKA baselines, reviewed imports.
  Needs: migrations through the JUP alembic head guard (`backend/jup/migrations.py`), audited reads
  and state changes (E1 covers tool calls only), and the company's BOD/PIC identity decisions for
  production use.
- **P3: assistant.** Context panel and `leadership_*` tools over the same reader. Tools declare a
  risk class under ADR-0013; `leadership_prepare_action` is `external`. The one-use, payload-bound
  confirmation by an authorised identity is stricter than ADR-0013's asking-user approval and needs
  its own ADR.
- **P4 Dynamics, P5 CRM.** Blocked on IT's product/environment answer and the CRM choice.

## To switch P1 on for a real reader (each step needs its own OK)

1. Push, then deploy.
2. Set `JUP_LEADERSHIP_ENABLED=true` and `JUP_LEADERSHIP_SAMPLE_FILE` on the service, which puts the
   illustrative deck figures on ops.axiara.ai.
3. Create a group carrying the grant above and add the reader. The admin role grants nothing.

Unverified risk, not tested: the admin group editor may rewrite a group's permissions object without the
`jup` key it does not know. Re-check a leadership grant after editing that group in the UI.
