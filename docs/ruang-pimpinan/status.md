# Ruang Pimpinan — delivery status

Source of intent: the approved design handed over on 2026-09-24
(`~/Documents/ChatGPT/KPI-Dashboard-JUP/docs/handovers/2026-09-24-ruang-pimpinan-claude-code/`,
read-only). That package's approved design, roadmap, contracts and acceptance matrix govern; this
file records what exists in this repository and what the evidence for it is.

**P1 (native read foundation) is implemented and verified locally. It is not deployed, not enabled
anywhere, and holds no real grant.** The whole product is P1–P5; P1 is not completion.

| Item     | State                                                                                                                                                                                                         |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Commits  | `34dbd9421` (records, policy, API), `ad63a9133` (views, sidebar, preview), plus this file and two id-ID fixes                                                                                                 |
| Pushed   | Yes, 2026-09-24 (`34dbd9421`, `ad63a9133`, `57a9b3bd3`). Not deployed.                                                                                                                                        |
| Deployed | Enabled on `ent-os-00027-lrc` (`dd15a3100` + `JUP_LEADERSHIP_ENABLED`, `JUP_LEADERSHIP_SAMPLE_FILE=/srv/jup/leadership/illustrative-seed.json`), 2026-09-24, with Erik's OK. Both values live in `deploy.sh`. |
| Data     | Illustrative only: `tests/fixtures/leadership/illustrative-seed.json`, figures from the 18 Sep 2026 BOD deck and the RKA 2027 Draft 1, labelled unverified and partial.                                       |
| Grants   | One: group `Ruang Pimpinan — uji` (`e5657398…`), Board + RKA on `jup_consolidated`, member Erik only (his OK, 2026-09-24). Board and RKA verified rendering the sample live.                                  |

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

Not verified that night: text scale above 100%, keyboard-only traversal and the mobile drawer. The
Portfolio filter/deep-link behaviour was verified live on production earlier the same night rather
than locally (no local records).

### Gap walk, 2026-09-24 (second session)

Same local setup, real Chrome through Interceptor, reader `reader` unless named.

- **Group editor (defect, fixed).** Opening "Uji Direksi saja" in the admin group editor and pressing
  Save with nothing changed deleted the `jup` grant: `boardonly`'s views went from `["board"]` to
  `[]`. The editor rebuilt `permissions` from the six vendor keys only. Patched (`EditGroupModal.svelte`,
  VENDOR-PATCHES entry, `tests/test_group_editor_keeps_jup_permissions.py`). After the patch, Save
  unchanged and Reset to defaults + Save both keep the grant; the backend log shows each update
  call.
- **Keyboard.** Board has 10 tab stops and RKA 17, all native links and buttons in reading order,
  no positive `tabindex`, and no pointer-only elements. Every stop takes the leadership ring
  (`outline: 2px`, `--jup-brand-text`): 6.57:1 on light, 7.29:1 on dark, against 3:1 required.
  The source dialog traps focus (only "Tutup" is reachable) and Escape closes it.
- **Dialog name (defect, fixed).** The vendor Modal had no accessible name. It now takes
  `ariaLabelledby` (VENDOR-PATCHES entry, `tests/test_modal_accessible_name.py`). Verified live:
  "Rincian sumber" and "Pratinjau konteks untuk Asisten".
- **Text scale.** At a 150% and a 200% root size, Board and RKA have no page overflow and no
  clipped text; figures scale 24 → 48 px. At 200%, RKA's Asumsi table (1152 px) scrolls inside its
  own labelled, focusable region.
- **Mobile drawer (defect, fixed).** At 390 px there was no control to open the sidebar, so a phone
  reader was stranded on the page. Portfolio, which is live, has the same gap. Both now render
  `src/lib/components/jup/MobileSidebarToggle.svelte` (the vendor workspace control and labels).
  Verified in a 390 px same-origin frame: the toggle flips `aria-expanded`, the drawer holds the
  Ruang Pimpinan entry with `aria-current="page"`, and tapping it navigates and closes the drawer.

Still not observed: real Tab key presses. Synthetic keys don't move focus, and OS-level keys would
go to whichever app is in front. The painted ring and the drawer's slide-in weren't seen either,
because the driven tab is hidden (no window focus, and `requestAnimationFrame` paused). The rules,
their colours and the state changes were measured instead.

### T8 walk, 2026-09-24 (local, records mode)

Backend on 8080 and Vite on 5050, scratch `DATA_DIR`/`STATIC_DIR`, `JUP_LEADERSHIP_ACTIONS_SOURCE=records`,
BOD policy individual, publication four-eyes, local evidence store. Synthetic PIC, BOD, two
secretaries, import reviewer, commissioner and assigner; actions seeded with `create_action`.
Driven in real Chrome through Interceptor.

- Register and short list render records-mode actions, including one with no due date.
- PIC: progress recorded without a state change; an `http` link refused; completion with an https
  link moved the action to awaiting BOD closure; the history names the evidence id, no storage key.
- BOD: the queue listed both requests; a close after the PIC added revision 2 was refused (the
  version check fires before the stale-evidence check, since new evidence bumps the version) and the
  record reloaded to revision 2; the close then landed; a return without a reason was refused, with
  a reason and `blocked` it landed; a closed action offers reopening.
- Snapshots: a draft froze with its hash and a "not an approved meeting record" label; four-eyes
  refused the author's publish; the second secretary published the same hash.
- Commissioner: no forms, queue or import panel. RKA view: the approved baseline listed; its action
  list empty in records mode (the open T7 call).
- Imports: candidates unverified until reviewed; no Accept without an owner; accept and link made
  both verified and the batch "All reviewed".
- PIC assignment: an unknown email refused; a mixed-case email matched; the assigned PIC then got
  the update form.
- id-ID labels checked; the action detail stacks over the register dialog.

Fixed from the walk (`0c92f11f2`): a BOD decision's confirmation vanished with the review section;
a missing import value's reason sat in the value's place; six vendor keys had empty id-ID values.
Seen once, not reproduced: the detail dialog closed after the first progress submit. Not walked:
keyboard-only use, text scale and 390 px for the new screens.

### T9 walk, 2026-09-24 (local, records mode, both BOD policies)

Commit `b4f7cc84f` plus the fix it found (`863ba4a75`). Backend on 8080 and Vite on 5050, scratch
`DATA_DIR`/`STATIC_DIR`, `JUP_LEADERSHIP_ACTIONS_SOURCE=records`, publication four-eyes, local
evidence store; BOD policy `{"mode": "collective", "quorum": 2}` for the design walk, then a restart
with `{"mode": "individual"}`. Synthetic PIC, two BOD members, BOC, two secretaries (publisher),
import reviewer, assigner and admin; grants through `/groups/create`. The three recorded actions
were created under the **illustrative dataset's own action ids**, so the RKA assumption's link
resolves to a recorded action. Driven in real Chrome through Interceptor, one value per eval,
guarded by `location.host`; refusals also checked against the API.

1. **Revenue exception, definition, source** (BOC): Pendapatan usaha Rp144,47 miliar against
   Rp158,47 miliar, −Rp14,00 miliar; the source dialog names the deck, slide 4, "presented",
   "not verified". The definition shown is its status only (candidate, period, scope, unit,
   comparison basis): no definition text exists until KPI definitions are decided.
2. **RKA assumption to its action** (BOC): the WTP KBB assumption's related follow-up resolves to
   the recorded `example-action-water`; its detail shows version 1, no forms.
3. **PIC evidence**: the PIC started the action (new route, below), then submitted completion with
   an https link; the action moved to awaiting BOD closure (version 3). A block without a reason
   was refused in the form.
4. **Unauthorised closure**: no decision form for the PIC, BOC or admin (admin is denied the view
   outright); `POST /closure` as PIC, BOC, admin and assigner all 403, action unchanged.
5. **Closure by the configured BOD**, collective: the first director's vote recorded "1 of 2"
   without closing; a second vote from the same director refused (422); the second director's vote
   closed it (version 5). Individual (after restart): the assigner named the PIC of
   `example-action-gas` by mixed-case email, the PIC started it and uploaded a PDF as completion
   (content-addressed, no storage key in the response), one director closed it; reopening offered.
6. **Current view changed, snapshot didn't**: a draft frozen by one secretary, refused to its author
   (four-eyes), published by the second under the same hash `f45d05a6…fb495` before the closure.
   After it the RKA view reads "0 open of 1"; the snapshot response is byte-identical before and
   after, the action inside still `awaiting_bod_closure`.
7. **Revocation**: the BOC removed from the readers group; the same session token then gets 403 on
   the snapshot, the snapshot list, the action history and the overview, and the page shows no
   access and no meeting history.

Also: text scale 150% and 200% on the PIC dialog, no overflow. 390 px through a same-origin iframe:
the PIC dialog and the snapshot viewer fit (390/390); the register table scrolls inside its
keyboard-reachable region.

Found and fixed (`863ba4a75`): **no route moved an action out of `not_started`.** `change_state`
and `OWNER_TRANSITIONS` existed, but nothing exposed them, so completion (in progress only) was
unreachable for every created or imported action. The T8 walk seeded `change_state` directly and
missed it. Now `POST /actions/{id}/state` (the recorded PIC with `actions.submit`; start, block
with a reason, unblock) and Start / Resume / Mark blocked in the PIC's form.

Also found: `revise_due` had no route either. Built in `fad0afc12` after Erik decided a due date is the
BOD's to move: `POST /actions/{id}/due` for `bod.review` holders who are not the action's PIC,
and a form in the action detail; walked in Chrome (a misshapen value refused, 2026 → 2027 with the
original kept, the PIC offered no form).

Not verified: keyboard-only operation and focus rings. Synthetic Tab doesn't move focus, OS-level
Tab reached another window, and `:focus-visible` doesn't match in the unfocused walk window, so no
ring could be measured. Structurally the new buttons are native and carry `.jlp-button`, which has
the ring rule; the leadership text fields have no focus rule of their own. Seen again (carried
polish): refusals and flag reasons in English under id-ID, author ids in history, no state on
frozen snapshot actions. Imports were not re-walked (T8 covered them).

### Postgres 16, 2026-09-24

Until now only the repository and migration suites read `JUP_TEST_POSTGRES_URL`; the closure,
snapshot, import, evidence, action and endpoint suites built SQLite whatever was set, so earlier
"Postgres runs of T4–T8" tested T4–T8 on SQLite. They now take their store from the shared
`leadership_db_url` fixture (`tests/conftest.py`): a fresh database per test on the given server,
dropped after; SQLite when unset, so CI is unchanged. On Postgres 16.15 (`postgres:16`, local
container): 373 passed, 0 skipped, across repository, migrate, closure, snapshots, imports,
evidence, actions and the endpoint (the new state route included). The server's DDL log showed 48
`CREATE DATABASE` for the actions and closure suites alone, none left behind. SQLite: 351 passed,
22 skipped.

## Acceptance matrix

| ID             | Stage     | Status                    | Evidence / gap                                                                                                                              |
| -------------- | --------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| UX-01          | P1        | passed (fixture)          | Layout A in both views; sources and register reachable without chat.                                                                        |
| UX-02          | P1, P2/P4 | P1 part passed            | Scope, period, units, source status visible; id-ID, 390 px, table regions and keyboard order/rings checked. Freshness is P2/P4.             |
| HOST-01        | P1        | passed (local)            | One entry, expanded and collapsed; active on descendants; Portfolio and chat landing unaffected. Mobile drawer reachable (toggle added).    |
| HOST-02        | P1        | passed (local)            | Light and dark measured, no double sidebar subtraction, no overflow; text scale 150% and 200% clean.                                        |
| HOST-03        | P1, P2    | passed (P1 scope)         | Back/refresh keep context; board-only denied RKA by URL and API; admin without grant denied.                                                |
| HOST-04        | P3        | context preview only      | Preview sends nothing. The real assistant surface is P3.                                                                                    |
| DATA-01        | P1, P2/P4 | P1 part passed            | Actual, budget and forecast kept apart; variance only like-for-like. Reconciliation to sources is P2/P4.                                    |
| DATA-02        | P1, P2/P4 | P1 part passed            | Missing is never zero (validator and card); malformed dataset is 503, never an empty report.                                                |
| ACT-01         | P1, P2    | P1 part passed            | One shared action id resolves to one record in both views. Re-import identity is P2.                                                        |
| ACT-02         | P2        | passed (local walk)       | T9: PIC start, completion evidence, unauthorised closure refused, BOD closure in collective (quorum 2) and individual modes (`863ba4a75`).  |
| ACT-03         | P1, P2    | P1 part passed            | Month, year and range targets shown with their precision; no overdue computed.                                                              |
| SNAP-01        | P2        | passed (local walk)       | T9: four-eyes refusal, publication by hash; the published snapshot byte-identical after a later closure.                                    |
| ACCESS-01      | P1 → P5   | P2 history passed (local) | T9: a revoked reader is denied a snapshot, the snapshot list and action history on the same session. Search, export and tools arrive later. |
| MX-01          | P1, P3    | P1 part passed            | UI and API read one reader module. Tools are P3.                                                                                            |
| WRITE-01       | P3/P4/P5  | not started               |                                                                                                                                             |
| INTEGRATION-01 | P4/P5     | not started               | Dynamics variant and CRM choice are still open.                                                                                             |

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

The admin group editor used to drop the `jup` key on save; that is patched (see the gap walk
above). Re-check the grant after the first real edit in production anyway.
