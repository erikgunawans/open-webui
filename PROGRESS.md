# PROGRESS — ent-os-new-jup

## Checkpoint 2026-09-25-kbd (latest) — real keyboard pass done; row buttons name their record; live on ent-os-00031-4xd

- **Session:** `/next` (item 1 keyboard pass = Erik's hands) → "can you use interceptor to drive the keyboard pass?" → "retry" → "granted" (Accessibility) → "done" ×2 → "yes go ahead now" → "push and then deploy" → "push" → `/wrap`.
- **Driving real keys works now.** Root cause of every earlier failure: `interceptor-bridge` lacked macOS Accessibility, so its CGEvents were dropped silently. The fix: `tccutil reset Accessibility com.interceptor.bridge`, then `interceptor macos trust --accessibility-prompt`, Erik turns it on, then `pkill` the bridge → `granted`. **Still on** (Erik's call to revoke). **Trap:** HID keys go to Chrome's *active* tab, not the eval tab; once they reached WhatsApp Web (Tab/F6 only, harmless). The walk gates every key on "frontmost = Chrome AND focused window's active tab = ours". Recipe in memory `interceptor-keyboard-focus-limits`.
- **Pass result (live, `ent-os-00030-nq9`):** Board 26 stops incl. sidebar and RKA 15, every one `:focus-visible` with the 2px ring. Register dialog: Close ↔ register region trap, Escape returns focus to the trigger. Source dialog: Close only, Escape returns focus. **Not walked:** action detail and its forms (the records register is empty).
- **Defect fixed (`cf035a3d3`):** "Select", "Source" and "Details" repeated per card/row with no context, and Select never announced its state. Each now has `aria-describedby` → its record title; Select has `aria-pressed` (gets the existing pressed style). Guard: `tests/test_leadership_row_buttons_context.py` (red without the fix). Recorded in `docs/ruang-pimpinan/status.md`. CI: Python CI + Frontend Build green; PyPI red as always.
- **Live:** **`ent-os-00031-4xd`** (image `cf035a3d3`), 100%, env identical. Rollback `ent-os-00030-nq9`. Verified in a fresh tab: 6 row buttons are described by their card titles; Select is false, then true and weight 600 after selecting. No ERROR logs. Before/after: `.planning/deploy-rowbuttons-{before,after}-2026-09-25.json` (`db6056f55`).
- **Seen, not fixed:** the vendor sidebar's 3rd tab stop is a button with no accessible name.
- **Commits (all pushed):** `cf035a3d3`, `db6056f55`.

## Checkpoint 2026-09-25-a1 — register dialog named; live on ent-os-00030-nq9; A1 proven early

- **Session:** `/next` (A1 gated to Mon, keyboard pass needs Erik, register needs a deck, polish optional) → Erik chose "pre-diagnose the Tab trap" → "push 4fb47561b" → "ok to deploy" → "push" → "can we make the Monday morning test done today?" → "push" → `/wrap`.
- **"Tab stuck on Tutup" is not a defect.** It traces to `docs/ruang-pimpinan/status.md`: the source dialog's only control is Close, so the trap holding Tab there is correct. focus-trap 7.8 re-scans tabbables on every Tab, so async dialog content stays reachable. Noted in status.md.
- **Real defect fixed (`4fb47561b`):** the full-register dialog (`LeadershipPage.svelte`) was the one leadership Modal with no `ariaLabelledby`. `tests/test_modal_accessible_name.py` now scans every `<Modal` under `leadership/` instead of a hand list (proven red without the fix). CI: Python CI + Frontend Build green; "Release to PyPI" red as always.
- **Live:** **`ent-os-00030-nq9`** (image `4fb47561b`, build `842e645d`), 100% traffic, env identical. Rollback `ent-os-00029-hz6`. Verified as Erik in a fresh tab: register dialog `aria-labelledby=jlp-register-title`, name "Follow-up register across meetings", focus on Close. Before/after: `.planning/deploy-dialog-{before,after}-2026-09-25.json` (`590acff7e`).
- **A1 proven today (Erik's call), not Monday:** manual `POST /automations/c516815a…/run` → run `0ad9c93b…` `success`, chat `bb19afa1-c43c-468a-b205-7d87f3aab4cc`. `jup.governance` 05:44:44–55Z: 4 `admitted` + 6 `tool_call` lines, **every one carries `chat=bb19afa1…`** — first live proof of `264813589`. A manual run bypasses `claim_due`: schedule untouched, next run Mon 09-28 09:00:43 WIB. Side effect: one extra digest chat in Erik's account. Evidence `.planning/a1-manual-run-2026-09-25.json` (`14010cbd0`).
- **Commits (all pushed):** `4fb47561b`, `590acff7e`, `14010cbd0`.

## Checkpoint 2026-09-25-i18n — chat id on audit lines; sidebar + chat screen in id-ID; live on ent-os-00029-hz6

- **Session:** `/next` (items 1–3 blocked: A1 is Mon 09-28, keyboard pass needs Erik, records register needs a deck) → carried chat-id fix validated, Erik: "OK to push" → "start the critique leftovers" → Erik settled the leftovers → "OK to push" → "ok to deploy" → "OK to push" → `/wrap`.
- **Live:** **`ent-os-00029-hz6`** (image `5b86ea21c`), 100% traffic; env identical to before. Rollback `ent-os-00028-44m`. Before/after: `.planning/deploy-i18n-{before,after}-2026-09-25.json`.
- **Commits (all pushed):** `264813589` (funnel audit lines carry `chat` and, for subagents, `parent_chat`; absent ids omitted), `0019b0adb` (96 empty id-ID sidebar keys filled), `5b86ea21c` (252 empty id-ID chat-path keys filled), `84b694d5a` (deploy records). CI: Python CI green on `264813589`; Frontend Build green on `264813589` and `5b86ea21c`; "Release to PyPI" red as always (vendor).
- **Tests:** full suite 844 passed, 22 skipped; `--only-group dev` 546 passed; ruff clean.
- **Verified live as Erik** (Interceptor, `?lang=id-ID`, then his `locale` restored to `en-US`): sidebar "Tutup Bilah Samping", "Catatan", "Folder", "Menu pengguna"; chat input "Obrolan Sementara", "Model terpilih", "Mode suara", "Integrasi". **Not yet seen live:** the chat id on an audit line (needs a turn; A1's run Monday gives one).

### Decisions (Erik, 2026-09-25)

- **Record content stays English under id-ID (option C).** Only UI chrome is translated; no `_id` fields in `~/jup/records`.
- **Blocker owner / next step / date: owner is Erik, on hold.** No schema change until he lifts it.
- Portfolio sort/filter/deep links were already shipped (`19c590898`, 09-24). The critique leftovers are closed.

### Findings

- id-ID has **2,238 empty vendor keys** left (Settings 269, admin/workspace). `returnEmptyString: false` makes them fall back to English. Only fill empty keys; parse leaves filled ones intact.
- Four chat labels are **hardcoded English `aria-label`s** in vendor code (`Navbar.svelte` "New Chat", "Controls"; `MessageInput.svelte` "Available Tools", "Voice Input") — no translation can reach them.
- Two existing id-ID values read badly: "Delete" → "Menghapus", "Playground" → "Taman bermain".
- Erik's own browser stores `locale: en-US`, so he sees English; `DEFAULT_LOCALE=id-ID` covers users with no stored choice. `?lang=` writes localStorage — restore it after any check.

## Checkpoint 2026-09-25-p2d2 — P2 deployed: live on ent-os-00028-44m; Erik holds actions.assign

- **Session:** after the p2d wrap Erik ran `gcloud auth login`; `deploy.sh` rerun from a clean tree at `c5f47be29`.
- **Live:** **`ent-os-00028-44m`** (image `c5f47be29`), 100% traffic. Rollback `ent-os-00027-lrc`. Only env change `+JUP_LEADERSHIP_ACTIONS_SOURCE=records`; BOD and publication policies unset by design. `jl0001`→`jl0002` ran on Cloud SQL at startup, no errors.
- **Verified live as Erik** (Interceptor, IAP): overview 200 in records mode, 0 actions with its note; `/meeting-changes` `available: false`; snapshots empty; the page shows "0 open of 0 recorded actions" and the unavailable meeting comparison. Erik has no leadership operations yet. After-values: `.planning/deploy-p2-after-2026-09-25.json`.
- **Orphan:** build `299c3299` (image `6f3f0da51`) finished SUCCESS after the first run died on re-auth; never deployed.
- **Grant (Erik OK):** `actions.assign` added to `Ruang Pimpinan — uji` (only change; 1 member, views unchanged); Erik's capabilities now `["actions.assign"]`. Before/after in `.planning/grant-actions-assign-before-2026-09-25.json`.
- **Next:** A1 after Mon 09-28 09:00 WIB; Erik's keyboard pass; the open decisions.

## Checkpoint 2026-09-25-p2d — P2 polish, meeting changes, hold proven; P2 deploy started, stopped at gcloud re-auth

- **Session:** `/next` (item 1 waits for Mon 09-28) → polish → Erik: "push 0d987b3f8 and c086b9088" → Claude desktop closed, Chrome walk → "OK" → "push" → "yes please" (RKA comparison) → blocked, Erik chose "changes since last meeting" → "push dc6b12721" → "the keyboard and focus-ring check then the P2 deploy prep" → hold proof OK, records / BOD unset / publication unset → "push 78c3fd0b4 and 3a1248a3e. then P2 Deploy" → `/wrap`.
- **Live:** **unchanged, `ent-os-00027-lrc`** (`dd15a3100`). The P2 deploy of `6f3f0da51` was started: Cloud Build `299c3299-972b-4de0-b233-d34020cc48cd` (global) was submitted, then `gcloud builds submit` died streaming its log: *"Reauthentication failed. cannot prompt during non-interactive execution"* (alesha-bot's session needs `gcloud auth login`). The build keeps running server-side; **`gcloud run deploy` never ran.** Before-values: `.planning/deploy-p2-before-2026-09-25.json` (env diff vs live: only `+JUP_LEADERSHIP_ACTIONS_SOURCE=records`; both secret refs unchanged).
- **Commits:** pushed and green: `0d987b3f8` (refusals/flag reasons in id-ID), `c086b9088` (author names), `82fe86b6c` (frozen action state), `77a308013` (RKA content labels), `dc6b12721` (changes since last meeting), `78c3fd0b4` (field focus ring), `3a1248a3e` (deploy.sh `ACTIONS_SOURCE=records`, hold proof). Python CI + Frontend Build green on `dc6b12721`; Frontend Build green on `3a1248a3e` (no Python CI: path filter, no backend change). `6f3f0da51` (deploy before-values) was local until this wrap.
- **Tests:** full suite 843 passed, 22 skipped; `--only-group dev` 545 passed; snapshot+endpoint+meeting-changes suites 174 passed on Postgres 16; vitest 71. Mutation-checked: author-name resolution, meeting ordering by date, scope comparability.

### What shipped

- **Server text in the reader's language:** `src/lib/leadership/refusals.ts` recognises every server refusal and flag reason (fixed and value-built) as a code; `ServerText.svelte` holds one literal `$i18n.t` per code; unknown text shows as sent; the `LeadershipRequestError:` prefix no longer leaks. 41 id-ID strings.
- **History names its authors:** `GET /actions/{id}` adds `author_name` per event via `leadership_user_names` (one directory call); null for someone no longer in the directory.
- **`ActionState.svelte`** shared by register and snapshot viewer; frozen actions show their frozen state.
- **`rkaEntry`**: `pendapatan_idr_miliar: 158.47` reads "Pendapatan · Rp158,47 miliar"; raw key on hover.
- **Changes since the last meeting:** `GET /meeting-changes` compares the two latest *published* meeting records of a view by meeting date (a draft never counts; fewer than two is `available: false`). Metric differences are server Decimal, only for the same unit, kind and scope (else a note says which differed); action state/target changes, new and dropped; different actions sources are not compared. `MeetingChanges.svelte` on both views; the Board's `prior-meeting-change` module reads "Tersedia" once real. Walked in Chrome (0 meetings, RKA Sept→Okt, Board two meetings).
- **Focus ring on every leadership field** (`app.css` excludes input/textarea from its global ring). Rule loaded and matches every dialog field; *not seen rendering*.
- **GCS temporary hold proven on `jup-ops-data`:** probe held, `rm` refused with 403 for the project owner, released, removed (soft-delete copy until 2026-10-02). Runtime SA impersonation is denied; its `storage.objectUser` includes `objects.update`. `status.md` records it.
- `deploy.sh` heredoc: `JUP_LEADERSHIP_ACTIONS_SOURCE: "records"`; BOD and publication policies deliberately absent (Erik, 2026-09-25).

### Findings

- **The RKA baseline-vs-draft comparison is blocked:** RKA content is free-form, the draft is dataset metrics, and no key links them (KPI definitions); the table has no reason column; no route records an RKA record. "Decisions required" needs a new record type. Both written into `p2-plan.md`.
- **Real keyboard focus still can't be driven here:** AppleScript activate, tab select, AXRaise and a click all leave `document.hasFocus()` false in the Interceptor tab group's window.
- **Python CI is path-filtered** (`backend/**`, `tests/**`, …): a frontend-only push gets no Python run; that is not a missing result.
- The vendor's `"Actions"` i18n key is empty in id-ID; the meeting module uses "Follow-up actions" instead of filling the vendor key app-wide.
- The walk's `boc@walk.test` has lost its grant in the scratch DB (not investigated).

### Open at checkpoint

- **Finish the P2 deploy** after `gcloud auth login` (see the handoff).
- Keyboard-only Tab walk and focus rings: Erik's hands.
- RKA baseline-vs-draft and "decisions required": blocked on Erik's KPI definitions / decision model.
- A1's first run after Mon 2026-09-28 09:00 WIB.

## Checkpoint 2026-09-25-t9b — CI confirmed green on the T9 wrap

- **Session:** continuation of 2026-09-25-t9 after its wrap: CI watched to the end; `/agent-depth` read (no status change); `/wrap`.
- **CI:** Python CI and Frontend Build green on `4c5e730d0` (the t9 wrap, which carries all of the session's code, including the due-revision screen). The Frontend Build on `a85583fce` was cancelled, superseded by the wrap push, not failed. "Release to PyPI" failed again (vendor workflow).
- **Agent-depth ledger:** 9 live, E5 ready (ships with the first of E3/E4/A5), A4/A5/V1 blocked on Erik's D-decisions, E2 on the VM budget. Unchanged.
- **Next:** as 2026-09-25-t9's list, minus the CI check.

## Checkpoint 2026-09-25-t9 — P2 T9 walked; two missing routes built; T4–T8 now really run on Postgres

- **Session:** `/next` → Erik: `actions.assign` held by "Erik Gunawan", "yes you can push" → Postgres run → Erik: "push 9c00bf349" → polish item after CI → Erik chose BOD-only due revision → Erik: "push fad0afc12 and a85583fce" → `/wrap`.
- **Live:** unchanged, `ent-os-00027-lrc`. No deploy. `origin/main` is ahead of live by T0–T9.
- **Commits (all pushed):** `863ba4a75` (PIC start/block/unblock route), `f438c71b1` (T9 walk record), `f3c65f6c2` (Erik holds `actions.assign`), `9c00bf349` (suites on Postgres), `fad0afc12` (BOD due revision), `a85583fce` (status). CI: Python CI and Frontend Build green on `9c00bf349`; Python CI green on `a85583fce`, Frontend Build still running at wrap.
- **Tests:** full suite 821 passed, 22 skipped (SQLite); on Postgres 16.15 the eight leadership suites 373 passed, 0 skipped; CI's `--only-group dev` 533 passed; vitest 58. New guards mutation-checked (PIC-only state move; owner cannot move own due date).

### What shipped

- **T9, the recorded end-to-end walk** (`docs/ruang-pimpinan/status.md`, "T9 walk"): the design's seven steps in real Chrome, records mode, collective BOD (quorum 2) then individual, nine synthetic identities. ACT-02 and SNAP-01 now "passed (local walk)"; ACCESS-01's P2 history part passed. Text scale 150%/200% and 390 px (same-origin iframe) clean on the new screens.
- **`POST /actions/{id}/state`** (`863ba4a75`): the recorded PIC with `actions.submit` starts, blocks (reason) and unblocks; Start / Resume / Mark blocked in the PIC form.
- **`POST /actions/{id}/due`** (`fad0afc12`): `bod.review` holders who are not the action's PIC move the due date with a reason; one member in either mode; no closure policy needed; `DueRevise` form in the action detail. Walked in Chrome.
- **`leadership_db_url`** (`tests/conftest.py`, `9c00bf349`): closure, snapshots, imports, evidence, actions and endpoint suites take a fresh Postgres database per test when `JUP_TEST_POSTGRES_URL` is set, SQLite otherwise.

### Findings

- **No route moved an action out of `not_started`**, so completion was unreachable for every created or imported action; `revise_due` had no route either. The T8 walk hid the first because its seed called `change_state` directly. Seed only the start state; grep the router for each domain command's caller.
- **Earlier "Postgres runs of T4–T8" ran T4–T8 on SQLite:** only the repository and migration suites read the variable. Proven fixed with the server's DDL log (48 `CREATE DATABASE` for two suites, none left).
- **T7 call (1) is smaller than thought:** the RKA view resolves a recorded action as soon as ids match (seeded under the dataset's ids, the WTP assumption reached `example-action-water`). The empty view is imports minting new ids.
- **Interceptor drift navigated Erik's `localhost:3001` Storymaker tab** away (restored with `back`; in-page state lost). The walk helper now refuses both the write and the navigate on the wrong host.
- **Keyboard/focus rings not verifiable here:** synthetic Tab doesn't move focus, OS Tab went to another window, `:focus-visible` never matches in the unfocused walk window. Leadership text fields have no focus rule of their own.
- Collective mode refuses a second close vote from the same director (422). Four-eyes refusal text is English under id-ID.

### Open at checkpoint

- **Keyboard-only use and focus rings** on the leadership screens: needs Erik's hands or a focused Chrome window.
- Polish: English server refusals and flag reasons under id-ID; author ids instead of names in history; frozen snapshot actions show no state; RKA content shows raw keys; RKA baseline-vs-draft comparison and the two snapshot-comparison modules not built.
- T7 call (1) (imports should carry or link dataset action ids) and call (2).
- Before any P2 deploy: GCS hold on the real bucket; each new env value's OK; the `actions.assign` grant for Erik (its own OK then).
- A1's first run after Mon 2026-09-28 09:00 WIB.

## Checkpoint 2026-09-24-p2t8 — P2 T8 frontend built, walked in Chrome, PIC assignment added

- **Session:** `/next` → T8 slices a–f, each committed → Erik: "ok to push" → Erik: "please start" (local Chrome walk) → walk fixes → Erik: "push 0c92f11f2" → Erik: "yes please build" (PIC assignment) → Erik: "push 9e35391b2" → `/wrap`.
- **Live:** unchanged, `ent-os-00027-lrc`. No deploy. `origin/main` is ahead of live by T0–T8.
- **Commits (all pushed; Python CI and Frontend Build green on `ea6975d04` and `9e35391b2`, Frontend Build green on `0c92f11f2`):** `139ceab99` (T8a API client, register safe for records), `3013eeaba` (T8b action detail; server lists evidence, hides `storage_key`), `87d995736` (T8c PIC form), `fd6060ed2` (T8d BOD queue and decision), `da8c7460a` (T8e meetings, snapshots, RKA records), `ea6975d04` (T8f import review), `0c92f11f2` (walk fixes), `9e35391b2` (PIC assignment).
- **Tests:** full suite 805 passed, 22 skipped; CI's `--only-group dev` 533 passed; vitest 54; svelte-check has no finding in any leadership file (vendor has 7794); the format → i18n → `git diff --exit-code` gate is clean. New guards mutation-checked (evidence list and storage key; PIC capability, reason, unknown person, under review).

### What shipped

- **T8 frontend**, six slices: API client for every P2 route (409 detail kept); records-mode register (null due, no progress, lifecycle states, closure request status); `ActionDetail` (flags, evidence revisions with download or link, history newest first); `ActionSubmit` (progress; evidence file or https link, optional completion / cancellation+reason / supersession+replacement; one idempotency key per form); `ClosureReview` (close, return with reason and state, reopen; vote count vs quorum) and a BOD queue on the page; `MeetingHistory` + `SnapshotViewer` (published by default, draft labelled, versions and correction links, freeze and publish by hash); `RkaRecords`; `ImportReview`. Capabilities store now carries `operations`. Every string id-ID.
- **Server, T8b:** `GET /actions/{id}` lists the evidence revisions; the history's evidence events name `evidence_id` and no longer carry the bucket `storage_key`.
- **PIC assignment:** `actions.assign` capability (default false); `assign_pic` → `pic_assigned` event; `POST /actions/{id}/pic` by sign-in email (stored as the user id); reason required to replace; refused when closed, under BOD review, unchanged or unknown. No schema change.
- **Local Chrome walk** of every T8 screen with seven synthetic roles: recorded in `docs/ruang-pimpinan/status.md` (T8 walk). ACT-02 and SNAP-01 now "built, walked locally".

### Findings

- **An imported action had no PIC user**, so nobody could ever submit evidence on it. Fixed by the PIC assignment; who holds `actions.assign` in production is open.
- **From the UI the version check always fires before the stale-evidence check:** any new evidence revision bumps the version. The stale-evidence 409 is reachable only through the API; the UI's "changed since you opened it" and reload cover it.
- **Vendor i18n keys with empty id-ID values** ("History", "Open", "Note", "Reason", "Open link", "Missing") are not flagged by `i18n:parse`, because the key already exists. Check the id-ID value of every key a new screen uses, not only the new ones.
- **The Interceptor a11y tree came back empty** on the leadership page; the walk drove it with main-world DOM clicks guarded by `location.host`.
- **A truncated read misled me once:** `tail` of a joined eval string cut the part I was reading. Read one value per eval when asserting a message.
- Dev servers were cheap: runtime and MiniLM already cached; a scratch `DATA_DIR`/`STATIC_DIR` and env file in the session scratchpad.

### Open at checkpoint

- **Who holds `actions.assign`** in production (a new capability holder: its own OK).
- **T9**: the recorded end-to-end walk (design's seven steps, acceptance ids in `status.md`), plus keyboard-only, text scale and 390 px on the new screens.
- Before any P2 deploy: the GCS hold on the real bucket; Postgres 16 run of T4–T8; each new env value's OK.
- Two T7 calls; English server refusals and flag reasons under id-ID; author ids instead of names; the RKA baseline-vs-draft comparison and the two snapshot-comparison modules not built.
- A1's first run after Mon 2026-09-28 09:00 WIB.

## Checkpoint 2026-09-24-p2t7 — P2 T4–T7 built and pushed; evidence-wipe fixed

- **Session:** `/next` → disk 1.7 GB, Codex blocked → T4 → Erik: "Merge. Ok to push and Evidence-wipe fix" → push, hold fix, CI fix → T5 → push → T6 → push → Erik confirmed T5 and T6 calls → T7 → push → T8 stopped on disk/swap → `/wrap`.
- **Live:** unchanged, `ent-os-00027-lrc`. No deploy. `origin/main` is ahead of live by T0–T7 (all inert until deployed; the new env values are unset, so every new path answers 503 or keeps P1 behaviour).
- **Commits (all pushed, Python CI green on each after `dc0996fd0`):** `fe91c7d9d` (T4), `7784beaaf` (evidence hold), `dc0996fd0` (CI fix), `02d6325aa` (T5), `3f37f47e7` (T6), `36ec2c253` + `96046c78c` (T6/T5 decisions recorded), `e8e367223` (T7).
- **Tests:** full suite 790 passed, 22 skipped (Postgres-only). CI's `--only-group dev` job reproduced locally: 533 passed. Every task mutation-checked (T4 14, T5 20, T6 17, T7 17 guards; all killed after the survivors got tests). **T4–T7 not yet run on Postgres 16** (disk).

### What shipped

- **T4** `closure.py`: `bod.review` capability; `JUP_LEADERSHIP_BOD_POLICY` `{"mode":"individual"}` or `{"mode":"collective","quorum":N≥2}`, unset/invalid → 503 for a reviewer, 403 for anyone else. PIC never reviews own action. A decision names the evidence revision; a newer one → 409 stale. Collective counts distinct reviewers on the latest revision only. Return (in progress/blocked, reason) and reopen (reason, closure kept) are single-reviewer. `POST /actions/{id}/closure`. Erik merged it **without the Cato audit** the plan called for.
- **Evidence-wipe fix** `7784beaaf`: `GCSEvidenceStore.put` uploads with `if_generation_match=0`, sets a temporary hold, rereads it; `EvidenceNotHeld` fails the put so no row points at an unheld object. The vendor's delete-all raises `Forbidden` at the first held object (it wraps only `NotFound`). Runtime SA has `roles/storage.objectUser` on `jup-ops-data`, enough to set holds. **Not yet proven against the real bucket.**
- **T5** `snapshots.py`: drafts freeze one view as canonical JSON + sha256; immutable versions (draft / publication / correction); publication needs `snapshots.publish` + `JUP_LEADERSHIP_PUBLICATION_POLICY` `{"four_eyes": bool}` and the reviewed hash; every read verifies hash, state and links. RKA records: baseline / revision / forecast, insert-only. Routes `GET/POST /snapshots`, `GET /snapshots/{id}`, `POST /snapshots/{id}/publish`, `GET /baselines`.
- **T6** `imports.py`: structured candidate file (no PPTX), checked whole; nulls need a reason; `source_metadata` kept verbatim; same bytes = no-op; matching only through reviewed `leadership_external_ref`; title/owner/due differences stored as conflicts; review once (accept / link / reject); verified only after accept or link. `imports.review`; `POST/GET /imports`, `GET /imports/{id}`, `POST /imports/candidates/{id}/review`.
- **T7**: `JUP_LEADERSHIP_ACTIONS_SOURCE` `sample` (default) / `records` / else 503; every overview names `actions_source`; records mode: Board = whole register, RKA = recorded actions its section references; empty register served empty with `actions_note`, never the sample. `recorded_actions()` in the dataset's action shape. Evidence carries `closure_kind` (completed / cancelled+reason / superseded+replacement). `/overview` and `/sources` audited.
- Erik confirmed the four T5 and four T6 calls (recorded in `p2-plan.md`).

### Findings

- **CI's Python job runs `--only-group dev`:** a test module that imports sqlalchemy or `google` at top level breaks collection. Domain modules import the DB runtime inside functions (as `actions.py` did); guard `find_spec` of a dotted name against a missing parent.
- **The falling free space is swap, not a leak.** `vm.swapusage` 8.4 of 9.2 GB used; free disk swung 2.0 → 4.9 GB within minutes. Erik deleted the claude-mem backup (`claude-mem.db.bak-cwd-remap-*`) and `~/.claude-mem/logs/*`. `uv cache prune` timed out on the lock held by macos-mcp (Claude desktop), serena ×2 and chroma-mcp.
- ruff's C901 (complexity 10) bit every new module; the domain functions are split into planner helpers.

### Open at checkpoint

- **T8 frontend** not started. The P1 register breaks on records-mode actions (`due: null`, lifecycle states), so `records` must not be switched on before T8.
- Two T7 calls await Erik: RKA view membership in records mode; closure requests riding on evidence.
- Postgres 16 run of T4–T7; the hold on the real bucket; the Cato/Codex question; A1's first run after Mon 2026-09-28 09:00 WIB.

## Checkpoint 2026-09-24-p2t3 — T0 verified on Postgres 16, P2 T1–T3 built and pushed

- **Session:** `/next` → Docker unresponsive, so the carried #10 README fix → Erik restarted Docker → T0 on Postgres 16 → Erik: "OK on T0" → T1 → T2 → T3 → push (Erik's OK) → Codex upgrade attempt, blocked by a full disk → `/wrap`.
- **Live:** unchanged, `ent-os-00027-lrc`. No deploy this session. `origin/main` is ahead of live by T0–T3 (all inert until deployed).
- **Commits (pushed):** `35699ee31` (#10 README), `0df207f5e` (T1), `faf114a8b` (T2), `140979974` (T3).
- **Tests:** full suite 616 passed, 22 skipped (the Postgres-only cases). Leadership schema and repository 48/48 on a disposable Postgres 16.15.

### What shipped

- **T0 verified on Postgres 16.15:** `test_leadership_migrate.py` 4/4, and the database held only `jup_alembic_version` at `jl0001`. Erik approved T0 ("OK on T0").
- **`deploy/gcp/README.md`**: the stale "portfolio has no operating-layer permission" warning replaced. The gate is `OPERATING_LAYER_ROLE = 'admin'` in both the endpoint and `portfolio_status`; a signed-in `user` gets 403.
- **T1** (`0df207f5e`): `jl0002` creates the 11 `leadership_*` tables (written out explicitly; `models.py` mirrors them and a test holds the two equal on both databases). `repository.unit_of_work()`: event append + conditional version bump + aggregate changes + idempotency key in one transaction; stale version → `VersionConflict`; replayed key → first event; reused key with other content → refused; unique constraints back both. No float column; payload floats refused. A source-reading test forbids UPDATE/DELETE on the five append-only tables, with a planted-violation test.
- **T2** (`faf114a8b`): `actions.py`, the design's lifecycle in one `TRANSITIONS` table; the owner walks only not_started/in_progress/blocked. Due dates keep P1's precision names (`date`, `month`, `year`, `year_range`), not the plan's `day`. Overdue only at `date` precision; `stale` is None until the company records a threshold. `GET /api/v1/leadership/actions/{id}` with per-request grant, 503/404, no-store and an audit line of ids only.
- **T3** (`140979974`): `actions.submit` capability (own exact-boolean grant on top of the view grant; `capabilities.operations` lists it). Only the recorded PIC submits. Evidence is versioned; completion moves in_progress → awaiting_bod_closure and opens a closure request bound to that revision, never closing. Own evidence store (`evidence_store.py`) for the host provider under `leadership/evidence/<sha256>`, 20 MiB cap, type judged from the bytes. Routes: `POST /actions/{id}/progress`, `POST /actions/{id}/evidence`, `GET /evidence/{id}`. `jl0002` (never run on a real DB) gained `closure_kind` and `replacement_action_id`.
- Every task was checked by deliberate mutation. T2's first test set let a missing transition check pass; the missing case (the owner cannot pull an action out of BOD review) was added.

### Findings

- **The vendor's admin "delete all files" (`DELETE /api/v1/files/all`) deletes every object in the bucket**, which would wipe evidence in `jup-ops-data`. Recorded in `p2-plan.md`; settle before any deploy (my recommendation: a temporary hold on each evidence object at upload).
- **The vendor storage provider can't hold evidence:** its GCS get/delete keep one key segment and every upload copies into `UPLOAD_DIR`.
- **Forge (and so Cato) can't run.** Codex refuses `gpt-5.4` on a ChatGPT account, whatever the CLI version. The active CLI is bun's 0.139.0 (Homebrew 0.144.4 and nvm 0.131.0 are shadowed; latest 0.156.1), which is also too old for Erik's own default `gpt-6-astra`.
- **The disk filled a third time today.** Today's big writes: the Claude desktop app's VM image (`~/Library/Application Support/Claude/vm_bundles/claudevm.bundle/rootfs.img`, 9.1 GB), claude-mem databases (4.8 GB), a Docker Desktop update download, the Hermes diagnostic log (353 MB). `bun add -g` re-resolves every global package and spent about 4 GB before it was stopped at "Resolving dependencies". Erik cleared the npm cache (+3.7 GB) and bun's cache (+0.3 GB); 1.7 GB free at wrap.
- `uv cache prune` can't take its lock while uv-launched MCP servers run (Claude desktop's macos-mcp, serena, chroma-mcp).

### Open at checkpoint

- **Codex upgrade** (not installed) and Forge's model pin; then how T4 is audited.
- **P2 T4** (BOD closure), then Erik's review point.
- **The evidence-wipe hazard**, before any deploy.
- **A1's first real run** after Mon 2026-09-28 09:00 WIB.

## Checkpoint 2026-09-24-a1 — A1 timing retest passed, weekly digest live

- **Session:** a background watcher collected the 05:00 WIB fire → read and validated it → Erik: "do all three" (clean up, create the digest, mark the plan) → push → `/wrap` (first attempt blocked by a full disk, `ENOSPC`; rerun after Erik freed space, 2.8 GB free).
- **Live:** unchanged, `ent-os-00027-lrc`. No deploy this session.
- **Commit:** `30f7bacee` (plan row), pushed.

### What shipped

- **A1 timing retest: valid, on time.** Automation `fc3e9381` fired at 22:00:22Z (run record `success`, chat `20950b9f…`); audit shows `admitted` 22:00:36Z and `portfolio_status` + `get_current_timestamp` ok at 22:00:44Z. The request log had **zero requests from 20:01:42Z to 22:10Z** (query re-run at 22:12Z against a wider window to prove it returns rows). Throttled CPU (request-based, `minScale=1`) is enough: no `--no-cpu-throttling`.
- **Test automation deleted** (DELETE 200) and **the digest created** with Erik's OK: "Ringkasan mingguan portofolio JUP", id `c516815a-1dfb-4d5a-ad7d-3b8e23618eaf`, model `xiaomi/mimo-v2.6-pro-ultraspeed` (= Asisten JUP, the only model), owner Erik (`beda5418…`), `RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0`. It is the only automation.
  - Next runs: **Mon 2026-09-28 09:00:43 WIB**, Mon 2026-10-05. The `:43` is the creation second (no `BYSECOND`); harmless.
  - The prompt was written by me (no draft existed): Indonesian, calls `portfolio_status`, no invented figures, per-project status line, changes since last week, risks with owner and deadline, decisions needed. Erik may revise it.
- `.planning/agent-depth-plan.md`: A1 → `live`, evidence recorded under Track A.

### Findings

- **The disk filled again** (ENOSPC on every tool call, even `df`). Nothing was lost; Erik freed space. Watch it before any Docker pull.
- Erik's old ops tab `893472588` stayed open through the window but made no request after 20:01:42Z, so an idle open tab does not necessarily void the test; a polling page does.

### Open at checkpoint

- **Verify A1's first real run** after Mon 2026-09-28 09:00 WIB: its chat, run record `success`, and the `admitted` + `portfolio_status` audit lines.
- **T0 on Postgres 16**, then T1 on Erik's review of T0 (carried unchanged).

## Checkpoint 2026-09-24-p2t0 — P1 gaps fixed, Ruang Pimpinan enabled (Erik only), P2 plan approved, T0 built

- **Session:** `/next`. A1 wasn't due (22:00Z) → item 3, the P1 gap walk, found three defects and fixed them → Erik: deploy → push → enable Ruang Pimpinan → Erik-only grant → P2 plan → approved → build T0 → `/wrap`.
- **Live:** `ent-os-00027-lrc` (image `dd15a3100` + `JUP_LEADERSHIP_ENABLED=true`, `JUP_LEADERSHIP_SAMPLE_FILE=/srv/jup/leadership/illustrative-seed.json`). Chain: `00025-s4l` → `00026-mvj` (deploy `dd15a3100`) → `00027-lrc` (env only). Rollback: `00026-mvj` (section dormant) or `00025-s4l`. Before-values: `.planning/deploy-e3126777a-before-2026-09-24.json`, `.planning/leadership-enable-before-2026-09-24.json`.
- **`origin/main` is ahead of live** by docs and T0 (`055470184`: the migration graph, not deployed; it is inert until deployed and creates only `jup_alembic_version`).
- **Tests:** 474 dev-group pass + 1 skip (the Postgres case); 46 leadership/boot tests with the runtime pass + the same skip. svelte-check at baseline 7794 / 202.

### What shipped

- **P1 gap walk** (`e3126777a`, live on `00026-mvj`+). Evidence in `docs/ruang-pimpinan/status.md`.
  - **The admin group editor deleted the `jup` grant on Save.** `EditGroupModal.svelte` rebuilt `permissions` from six vendor keys. Reproduced in real Chrome (board-only reader went `["board"]` → `[]`), patched in `init()` and reset, vendor-patch entry + `tests/test_group_editor_keeps_jup_permissions.py`.
  - **Dialogs had no accessible name.** Vendor `Modal.svelte` takes `ariaLabelledby`; the source and context dialogs are named. Entry + `tests/test_modal_accessible_name.py`.
  - **No mobile sidebar toggle on fork pages**, Portfolio (live) and Ruang Pimpinan: a phone reader was stranded. `src/lib/components/jup/MobileSidebarToggle.svelte` in both headers; verified live at 390 px.
  - Keyboard order and rings (6.57:1 light, 7.29:1 dark), text scale 150/200 % and the dialog trap/Escape all passed.
- **Ruang Pimpinan enabled in production** with Erik's per-step OKs: deploy, flag + sample, grant.
  - The sample is at `gs://jup-ops-records/leadership/`, outside the `records/` tree that `sync-records.sh` mirrors **with delete**.
  - Both env values are in `deploy.sh` (`aeffc1009`), because `--env-vars-file` replaces the whole environment.
  - Group `Ruang Pimpinan — uji` (`e5657398…`): Board + RKA, member Erik only. Both views verified rendering the sample live.
- **P2 plan** (`docs/ruang-pimpinan/p2-plan.md`), approved by Erik with decisions E-1 (app DB, append-only events), E-2 (own alembic graph), E-3 (evidence in the storage bucket, not vendor Files).
- **P2 T0** (`055470184`, not deployed): ADR-0014; `backend/jup/leadership/migrations/` with version table `jup_alembic_version` and empty base `jl0001`; `jup.leadership.migrate` runs on the vendor engine and never raises (`schema_ready()`); a guarded `main.py` call (vendor-patch entry + `tests/test_leadership_migration_seam.py`); `test_boot.py`'s graph checks cover both graphs and the boot asserts `schema_ready()`.

### Findings

- **Docker's pull filled the disk.** 3.2 GB free → 137 MB during `docker pull postgres:16`; Docker Desktop then answered 500s and now reports "unable to start". The disk recovered to 2.3 GB on its own. The Postgres 16 check for T0 is still open.
- **The PAI security hook blocks `rm -r` on scratchpad paths** under `/private/tmp` as "system root". Don't route around it.
- **The local venv has no `psycopg2`,** so the Postgres test needs a driver; the strongest check is the built image booting against Postgres 16.
- `capabilities` answers 200 `enabled:false` when the flag is off (the other routes 503). status.md corrected.
- A hidden driven tab has no window focus and paused `requestAnimationFrame`: `:focus-visible` never matches and rAF animations never finish. Measure rules and state instead.
- Synthetic Tab keys don't move focus in Interceptor; OS-level keys go to the front app, so don't use them.

### Open at checkpoint

- **A1:** the 05:00 WIB (22:00Z) fire of `fc3e9381…`. Erik's ops tab was still open at 20:29Z (now id 893472588).
- **T0 on Postgres 16**, then T1 on Erik's review of T0.
- Push of `055470184` was not yet OK'd when the wrap began; the wrap pushes it.

## Checkpoint 2026-09-24-leadership — E5 decided (ADR-0013), Portfolio sort/filter/deep links live, Ruang Pimpinan P1 built

- **Session:** `/next`. The A1 test hadn't fired yet (05:00 WIB is still ahead), so I moved to E5: a grilling session produced ADR-0013. Erik then approved Portfolio polish with a deploy; I deployed it, found two defects live, fixed them and redeployed. Erik then handed over the approved Ruang Pimpinan design (read-only package), authorised P1 with local verification, and I built and verified it. `/wrap`.
- **Live:** `ent-os-00025-s4l` (`ba81ffa5b`, Portfolio). Rollback: `00024-ddh`, then `00023-pcd`. **`origin/main` is ahead of live:** the three Ruang Pimpinan commits (`34dbd9421`, `ad63a9133`, `57a9b3bd3`) are pushed but not deployed. The next deploy ships them. They stay dormant until `JUP_LEADERSHIP_ENABLED` is set and a group grant exists.
- **Tests:** 112 leadership domain tests plus the registration tests; 26 leadership HTTP tests with the runtime (`uv run --no-sync pytest`, no skips); 18 Vitest; 15 Portfolio API tests unchanged. `svelte-check` is at the pre-change baseline (7794 errors / 202 warnings).

### What shipped

- **ADR-0013: risky tool calls need the asking user to approve them** (E5, `9e2ef8ab5`). Decided, not built.
  - Three risk classes: `read`, `write_own` and `external`; a tool with no class counts as `external`.
  - The gate is enforced on the server; a chat's `ask`/`full` switch can't bypass it.
  - The asking user approves each call; an unanswered approval times out after 10 minutes.
  - Automations, subagents and channels all fail closed.
  - The decision goes into the E1 audit line.
  - The vendor's `ask` mode was ruled insufficient: it pauses every tool, it's user-controlled, automations and channels bypass it, and it records nothing in the audit.
  - The ledger now shows E5 `ready`; E3, E4 and A5 depend on it.
- **Portfolio: sort, filter and deep links** (`19c590898`, `ba81ffa5b`; live on `00025-s4l`).
  - Search, pillar and status filters and sort live in the query string. Cards carry `#project-`/`#engagement-` ids, and the "Blocked on" counterparty links to its engagement card.
  - The title is "Portfolio / Asisten JUP". There's no sort by figure (D11).
  - Two defects were found live and fixed: counterparty search hid the project, and CSS `:target` never matched cards that render after load.
- **Ruang Pimpinan P1** (handoff: `~/Documents/ChatGPT/KPI-Dashboard-JUP/docs/handovers/2026-09-24-ruang-pimpinan-claude-code/`, read-only).
  - **Backend:** `backend/jup/leadership/` (records, policy, reader) and `routers/jup_leadership.py` at `/api/v1/leadership`, serving capabilities, overview and sources.
    - Access is default-deny, admins included: each view needs an exact-boolean group grant for both the view and the scope, checked on every request.
    - Responses are `private, no-store`, errors included.
  - **Frontend:** `src/routes/(app)/ruang-pimpinan/`, `src/lib/components/leadership/`, and a sidebar entry after Portofolio in both variants. id-ID translated.
  - The evidence and the acceptance-ID map are in `docs/ruang-pimpinan/status.md`.
  - The router registration in `main.py` has a `VENDOR-PATCHES.md` entry and a source-read test.
  - Forge wrote `records.py` on GPT-5.5, because the installed Codex CLI can't run the pinned gpt-5.4. It caught and fixed a Unicode-digit bug.

### Findings

- **The handoff mis-stated the timing:** it said A1 "fired", but 05:00 WIB was still in the future. Check the clock before reading logs for a scheduled event.
- **Open WebUI's group API stores unknown permission keys intact:** the `jup.ruang_pimpinan` grant came back through `/groups/id/{id}` unchanged. It is not yet tested whether the admin group editor preserves it on save.
- **The i18n extractor only sees literal calls.** `$i18n.t(MAP[x])` is invisible to it, and `i18n:parse` deletes those translations. Use reactive maps of literal `$i18n.t('...')` calls, as Portfolio does.
- **A 422 is a `RequestValidationError`, not an `HTTPException`,** so a route class that stamps headers must catch both.
- **Interceptor's `back` did not move the driven tab;** `history.back()` in the page did.
- **svelte-check reports route-type comparison errors for new routes** until `svelte-kit sync` runs. `bun run check` syncs first; bare `bunx svelte-check` does not.
- **Local dev verification was cheap this time:** the runtime and the MiniLM model were already cached. Boot with scratch `STATIC_DIR` and `DATA_DIR`. A same-origin iframe gives a real 390 px viewport with no probe file.
- **The disk is at 100% with about 3.5 GB free.**

### Open at checkpoint

- **A1: read the 05:00 WIB (22:00Z, 2026-09-23) fire of `fc3e9381…`.** Erik's ops tab 893472375 was still polling at 17:46Z, so check the request log for 21:30–22:10Z first. Then delete the automation.
- **Ruang Pimpinan P1 gaps:** text scale, keyboard-only use and the mobile drawer were not walked. P2 needs a plan (migrations, audited reads, BOD/PIC identities). P3 needs its own ADR on top of ADR-0013.

## Checkpoint 2026-09-24-audit — E1 tool-call audit, A2 subagents, A3 code interpreter, subagent parent link

- **Session:** `/next` → E1 built, deployed and verified → Erik confirmed E1 then A2 → A2 DB write → A1 day and time set (Mon 09:00 WIB) plus a timing test → A3 DB permission → code-interpreter audit line → subagent parent link via `/tdd` → `/wrap`.
- **Live:** `ent-os-00023-pcd` (`53ae50d34`). Chain: `00020-lwb` → `00021-tbv` (E1, `2a68e6a0b`) → `00022-bs8` (CI audit, `365fdf183`) → `00023-pcd`. Every deploy and DB write had Erik's OK for that change. Rollback: `00022-bs8`.
- **Tests:** 322 pass (`uv run --no-sync --only-group dev pytest`). Both vendor files are at their pre-change lint baselines (middleware 62, subagents 6).

### What shipped

- **E1: one audit line per tool call.** `jup.governance.audit_tool_call` writes `tool_call` entries: user, chat, tool, `tool_id`, outcome (`ok`/`error`/`not_found`/`unparsed`) and `arg_bytes`. It never writes argument content, and it never raises.
  - There are four call sites in `utils/middleware.py`: `native`, `approved`, `default` and the legacy `code_interpreter` block.
  - Verified live: `portfolio_status` → 1 line, and a KB chat → `query_knowledge_files` + `grep_knowledge_files`.
- **A2: subagents on.** The DB write set `ENABLE_SUBAGENTS` true and `max_concurrent` 20→2. Background stays off. Before-values are in `.planning/a2-subagents-before-2026-09-23.json`.
  - A delegated task verified that every subagent turn is `admitted` with the contract and every tool call is audited.
  - Subagents re-enter `CHAT_COMPLETION_HANDLER`, so they are fully governed.
- **A3: code interpreter for staff.** The default permission `features.code_interpreter` went from false to true; that was the only diff. Before-values are in `.planning/a3-permissions-before-2026-09-23.json`.
  - The engine was already Pyodide and Jupyter is empty. It reaches nobody until staff get a model grant.
  - **Correction recorded:** in native mode the code interpreter is the builtin tool `execute_code`, and E1's native line already covered it (verified live). The `365fdf183` insert covers the legacy text-parsed path.
- **Subagent → parent link** (`53ae50d34`, built with TDD).
  - `subagents.py` stamps `child_request.state.jup_parent_chat_id`, on `request.state` so it can't be forged.
  - All four audit sites pass `state=request.state`.
  - Verified live: the subagent's `portfolio_status` line carries `parent_chat` = the delegating chat.
- **A1 timing test** (in progress).
  - A one-off automation ran at 23:00:01 WIB, on time, called `portfolio_status` (outcome ok), and its run record says `success`.
  - **This proves nothing about throttling.** Erik's Portfolio tab was open and polling, and an open tab keeps Cloud Run's CPU awake.
  - A second test, `fc3e9381-f433-4d7b-a11f-25e0cf496c2b`, fires once at **05:00 WIB 2026-09-24 (22:00Z)**. The service has `minScale=1` but request-based CPU (throttled).

### Findings

- `/api/v1/auths/` does **not** return `timezone`. The stored value is set from the browser on every load (`+layout.svelte:1283`), so Erik's is `Asia/Jakarta`, and an automation `BYHOUR=9` means 09:00 WIB.
- `?code-interpreter=true` in the URL turns the code interpreter on for a `?q=` chat.
- `interceptor tabs` works even when `eval` times out. "Tabs cannot be edited right now" came before a full extension disconnect.

### Open at checkpoint

- **Read the 05:00 WIB timing-test result.** Check the audit lines at 22:00Z and the request log from 21:30Z to 22:10Z. A request in that window means the test is invalid. Then delete `fc3e9381…`.
- Admitted (per-turn) lines still carry no chat id. Only `tool_call` lines link chats.

## Checkpoint 2026-09-23-depth — ?q= tools fixed, Asisten JUP rebrand live, agent-depth plan approved in direction

- **Session:** `/next` → item 1 root-caused and fixed (`?q=` tools race) → item 2 staff memory note → rename to Asisten JUP + logo system → deploy `00020-lwb` verified live → holaOS comparison re-shown → agent-depth plan + `/agent-depth` → Erik: enhance Asisten JUP, park Hermes.
- **Live:** `ent-os-00020-lwb` (`254da9640`, contains `d010e877c`). Deployed with Erik's OK; before-value and rollback `00019-snl`.
- **Tests:** 301 pass (`uv run --no-sync --only-group dev pytest`). Local format, i18n parse and production build clean.

### What shipped

- **`?q=` auto-submit now offers the model's default tools** (`d010e877c`).
  - Root cause: the vendor `setDefaults()` returned early while a run was in flight. On a fresh load that run awaits the tool list, so `initNewChat`'s `?q=` submit sent no `tool_ids`.
  - A typed chat was unaffected because a person types slower than three fetches.
  - Fix: waiters await the in-flight run via `defaultsSettled()`, and `?q=` awaits it before submitting. The patch and entry are in `VENDOR-PATCHES.md`, with a test in `tests/test_chat_default_tools_patch.py` that fails against the old file.
  - Verified live on `00020-lwb`: a fresh `/?q=` chat called `portfolio_status` and answered correctly.
  - Earlier note corrected: "the chat recorded no toolIds" proved nothing, because user messages never store toolIds. The evidence is the request body and the assistant `output` function_call names.
- **Staff memory note** at `docs/staff/onboarding-memori.md` (Indonesian). Memory is on and background review off (Phase 4). The assistant itself can add, update or delete memories through the builtin memory tools, since the model's capabilities are null and so default to on. `search_chats` is scoped to the caller.
- **Rebrand to Asisten JUP** (`254da9640`), from Erik's "Logo Asisten JUP" logo system.
  - `WEBUI_NAME: "Asisten JUP"`. The `' (Open WebUI)'` suffix is patched out of `env.py` under LICENSE clause 4 and ADR-0001. Title and manifest follow.
  - The sidebar lockup is panel 1a: logogram + "Asisten **JUP**" (JUP `#004999`, 8.70:1) + "JAKARTA UTILITAS" at 0.2em tracking (the file uses 0.34em, which overshoots at 19px). Dark mode is single-colour white.
  - `deploy/gcp/brand/build-icons.ts` builds all 12 icons from the official rasters in `deploy/gcp/brand/` by trim and scale only. App icons follow panel 1c.
  - The BangJayaOS marks are removed. `tests/test_brand_asisten_jup.py` guards the suffix and the two static dirs.
  - Verified live with getComputedStyle probes in both themes; the name comes from `/api/config`, and the BangJayaOS mark returns 404.
- **Agent-depth plan** at `.planning/agent-depth-plan.md` (`259429034`, `e75bbd507`).
  - `/agent-depth [track]` runs `scripts/agent-depth.ts`, which parses the plan's `## Phase ledger` table.
  - Erik approved the direction: enhance Asisten JUP rather than adopt Hermes, and Hermes is parked as X1.
  - Tracks: A (Open WebUI native: digest, subagents, code interpreter, web search, MCP), V (ChatGPT Live per ADR-0005/0006), E (tool-call audit, sandbox VM with gVisor and an egress proxy, Open Terminal, Playwright MCP, risky-tool approvals, skill proposals, messaging gateway), I (integrations via MCP).

### Research recorded

- **holaOS inventory, read-only.** 3 runtimes (pi in-process, Claude Code with `bypassPermissions`, Codex auto-approving), 96 tools, 89 Composio integrations proxied via `api.holaboss.ai`, and 8 channels. There is no voice and no audit log.
- **Hermes Agent.** NousResearch/hermes-agent, MIT, v0.21.4 (2026-09-21).
  - It is single-tenant by design and needs one writer on a persistent disk.
  - It skips dangerous-command checks inside containers.
  - Its auxiliary LLM calls must be pinned to our endpoint, with no fallbacks.
- **Open WebUI drives an external Open Terminal server** through `routers/terminals.py`, with tools from its OpenAPI spec.

### Open at checkpoint

- **CI:** the "Create and publish Docker images" CUDA and Ollama variants failed on `259429034` at "Build Docker image". Earlier runs were all cancelled when newer pushes superseded them. The cause is not investigated. Our deploy builds on Cloud Build, so it is unaffected.
- The Portfolio page's `<title>` is "Portfolio", with no app name. This is pre-existing.

## Checkpoint 2026-09-23-agentic — Phase 0–3 of the agentic-capabilities plan shipped

- **Session:** `/next` → item 1 plan (3 read-only code traces) → Erik approved it, with records in the KB and memory kept for staff → Phase 0 governance fixes → 0e permissions baseline → KB loader + "JUP Strategy KB" → 3 JUP skills → 16 holaOS skills ported → `portfolio_status` tool.
- **Live:** `ent-os-00019-snl` (`47cf5c86e`). Chain today: `00017-nfp` → `00018-6g2` (Phase 0, `e7856e0ef`) → `00019-snl`. Every deploy and DB write was authorized per change. Rollback: `00018-6g2`.
- **Plan of record:** `.planning/agentic-capabilities-plan.md` (Progress section at the top).

### What shipped (all live-verified via Interceptor and the Cloud Run audit log)

- **Phase 0, governance holes.** These were masked only because non-admins hold no model grant.
  - Six raw passthroughs are now refused outright by `jup.governance.refuse_passthrough`: `openai /responses` and five Ollama routes. Live they return 403 and write `refused` audit lines.
  - MoA is removed from `EXEMPT_TASKS`.
  - `retrieval /process/url` and `/process/web` now enforce `chat.web_upload`.
  - ADR-0002 is amended, and `VENDOR-PATCHES.md` has a new entry.
  - deploy.sh: `ENABLE_OLLAMA_API=False` (seed only), no pip install on tool save, no HuggingFace auto-update at boot.
- **0e DB write:** a deny-by-default `user.permissions`, and `ollama.enable=false`. Before-values are in `.planning/0e-before-values-2026-09-23.json`.
- **Phase 1, knowledge base.**
  - `deploy/gcp/sync-kb.ts` uses the vendor's incremental sync through Erik's tab.
  - "JUP Strategy KB" (`82f7d2f7-…`) holds 12 files from `~/jup` `1e1d4b6`: `kb/*.md` minus CONTEXT.md, plus DECISIONS.md and `records/**`. Grants are empty (admin only).
  - It is attached to Asisten JUP. Native tool calling retrieves with citations, and no exempt query-generation call is made.
- **Phase 2, skills.**
  - `skills/` is the source of truth, and `deploy/gcp/sync-skills.ts` upserts it. It never sends grants on update, so grants set by hand survive.
  - Three JUP skills: tier discipline, gate walkthrough, and the Indonesian briefing. The briefing was made self-contained after a live test showed a referenced skill is not loaded.
  - 16 holaOS skills were ported from `a6b58be`. The copy was read-only; the licence texts and a NOTICE with the skip reasons are in the repo. Prettier ignores `skills/`.
- **Phase 3, tools.**
  - `jup/portfolio_tool.py` renders the `project_portfolio` projection. It refuses non-admins, since the role now lives in `jup.portfolio.OPERATING_LAYER_ROLE`, and fails closed on a bad record.
  - `tools/portfolio_status.py` is a single-call wrapper, and a test enforces that.
  - `sync-tools.ts` created the tool, and it is attached via `meta.toolIds`.
- **Shared runner:** `deploy/gcp/lib/in-tab.ts`. It stages payloads in 2.5 KB chunks, because `interceptor eval` dies at about 8 KB, and it host-guards and polls every call.
- **MiMo does native tool calls** (verified).
- **Tests:** 283 pass.

### Open at checkpoint

- **`portfolio_status` was NOT called in its first live test.** "Proyek mana yang sudah lolos G1?" was answered correctly ("none, SPBG refused on the allocation"), but through the KB tools. The chat recorded no toolIds. It is unknown whether the `?q=` auto-submit sends the model's default toolIds.
- **The record's Rp 10 miliar reactivation capex is labelled Tier 2 · POTENSI.** D11 defines POTENSI as revenue, so this is a data fix for Erik in `~/jup`.
- **D19 is not written:** records are in scope for typed chat, and unreleased terms must never be filed in `records/`.
- **The "JUP Staff" group is unnamed.** The model, KB, skills and tool are all admin-only until then.
- **The KB is a copy.** Re-run `bun deploy/gcp/sync-kb.ts` after any `~/jup` commit to `kb/`, `records/` or `DECISIONS.md`.

## Checkpoint 2026-09-23-brand — handoff items 1–3 shipped, BangJayaOS lockup, Portfolio pass, holaOS compared

- **Session:** `/next` → onboard (Portfolio entry, admin landing, id-ID) → clarify (greeting, JUP
  suggestions, Arena off) → polish (sidebar AA) → re-critique 23/40 → JUP white-label (ADR-0001) →
  BangJayaOS lockup → Portfolio type/a11y/distill pass → read-only holaOS capability comparison.
- **Live:** `ent-os-00017-nfp` (`854ce30f6`). Chain today: `00012-s7l` (41ce4fe3c) → `00013-dq4`
  (a1d5ade1e) → `00014-lwz` (e64f16162) → `00015-xdl` (81c734e53) → `00016-v7v` (aead9b34f) → `00017-nfp`.
  Every deploy was authorized per change. Rollback: `00016-v7v`.
- **Records bucket** synced to `~/jup` `1e1d4b6` (SPBG figures now read "Rp 63,3 miliar").

### What shipped (all live-verified via Interceptor, getComputedStyle probes)

- **Portfolio onboarding:**
  - Sidebar entry "Portofolio" for admins only, with a GateLadder icon, in both the list and the rail.
  - Admins entering at a bare `/` land on `/portfolio`. The first attempt used `afterNavigate`, which was dead code; the fix reads the navigation-timing entry (see memory).
  - `DEFAULT_LOCALE=id-ID`, `<html lang="id">`, and 48 id-ID portfolio strings. `tests/test_portfolio_i18n.py` guards the backend sentences.
- **Chat home:**
  - `<h1>` greeting "Hello/Halo, {first name}".
  - A contract line that describes what the contract instructs.
  - Placeholder "Attach a document or ask a question…".
- **Live DB config, not code** (before-values recorded in the transcript):
  - 4 JUP suggestions in Indonesian (was 6 stock).
  - `ENABLE_EVALUATION_ARENA_MODELS=false`.
  - MiMo overridden as **"Asisten JUP"** with EMPTY access_grants, so it stays admin-only as before.
- **Contrast:** sidebar timestamps, section labels, hints and date headers are 5.07:1 in light (were 1.82 and 2.44) and 6.64:1 in dark; the hint was 3.2:1 in dark. Chat Menu targets are 24px.
- **Brand:**
  - `WEBUI_NAME=JUP`, so the UI reads "JUP (Open WebUI)".
  - Favicon, icons and model avatar use the JUP compass mark, cropped from `~/jup/brand/tokens/logo.b64`. It is 256px native, so the 512px icon is upscaled.
  - **Sidebar = BangJayaOS lockup** (`Sidebar/BangJayaLockup.svelte`). The rail and splash use the BangJayaOS mark: green `#00A550` outer; inner `#004999` in light and `#85AAD2` in dark (Erik's call, because `#004999` is 2.11:1 on Rich Black).
- **Portfolio pass** (`854ce30f6`):
  - Type scale is exactly 12/14/16/20/24px, nothing under 12.
  - 68ch measure.
  - Evidence is folded into "Evidence: n of m satisfied".
  - "Waiting on" is shown only when there is no Blocked on box.
  - Screen-reader state on the gate rungs, and `aria-current=step` on the held stage.
  - Figures in Space Mono at 20px; pills at 4px radius; card shadow gone.
  - The non-coverage statements are untouched (ADR-0009).
- **Frontend Build** had been red on the 09-22 checkpoint because of `.impeccable/` snapshots; that folder is now in `.prettierignore`.

### Re-critique 23/40 (`.impeccable/critique/2026-09-22T18-56-50Z__…md`)

Ran as two isolated agents. They **collided on Erik's Chrome**: one's `?lang=` navigation moved the
other's tab. Run browser agents sequentially next time. Since the critique, its top-severity issue
(Open WebUI identity) and the date-header contrast failure it raised have both been fixed. Open items:
- Blockers have no owner, next step or date (a records schema change in `~/jup`).
- Record data is still English under id-ID.
- The sidebar is half translated.
- No sort, filter or deep links on the Portfolio.

### holaOS (`~/holaboss-ai`, READ-ONLY per Erik) vs ent-os

holaOS is a single-user Electron agent workspace. It has deep agent capability: 3 runtimes, 40+ tools,
MCP, skills, memory, cron, 89 integrations and 8 chat channels. Governance is effectively absent:
Claude Code runs with permission checks bypassed, Codex auto-approves with no sandbox, and there is
no audit log. It is cloud-proxied by default despite its "local-first" claim. Its licence forbids
SaaS use or distribution to third parties without Holaboss permission.

Verdict: do not swap. **ent-os's gap is agent depth, and most of it ships in Open WebUI but is not
configured.** That is next session's plan item.

### Corrections to earlier claims

- The critique's "gray-600 = 5.73:1" is measured on the **white chat surface**. On the sidebar
  (`#F0F1F1`) it is **5.07:1**. `fc6a12b27`'s message repeats the 5.73 figure.
- The critique's "dark already clears AA" was false for the shortcut hint (3.2:1).
- `deploy/gcp/README.md`'s "What this does not do" still says the portfolio has no operating-layer
  permission (#10). That is stale: the 403 is implemented and tested.

## Checkpoint 2026-09-22-gsm — #16 closed, 403 test passed, GSM 2023 brand live, D17/D18 recorded

- **Session:** `/next` → e95a9dfc7 deploy confirmed → OpenRouter key in, MiMo allowlisted, #16 closed on evidence → D17 → 403 test passed → dark seam fixed → GSM 2023 rebrand everywhere (D18) → panel radius 14px → impeccable critique 22/40.
- **Tracker: zero open issues** — #16 closed 2026-09-22 with the audit line quoted.
- **Live:** `ent-os-00011-npn` (`b585967d9`, digest `sha256:b2779a93…df1f`). Chain today: `00008-wnn` (e95a9dfc7) → `00009-ds4` (1ddd29d02) → `00010-mtx` (a66ead2ce, GSM) → `00011-npn` (14px panel).

### #16 closed on evidence

OpenRouter key entered by Erik (app DB). The connection exposed all ~445 OpenRouter models, so D17's
allowlist was set: `OPENAI_API_CONFIGS["0"].model_ids = ["xiaomi/mimo-v2.6-pro-ultraspeed"]`.
One turn via `/api/chat/completions` → 200, provider Xiaomi, and Cloud Logging:
`jup.governance {'event':'admitted','model':'xiaomi/mimo-v2.6-pro-ultraspeed','contract':'attached'}`
at 2026-09-22T12:07:15Z on `ent-os-00008-wnn`.

### D17 — typed chat provider (in `~/jup/DECISIONS.md`, `ea84443`)

OpenRouter → Xiaomi MiMo only. OpenRouter lists **one** endpoint for it: Xiaomi, HQ China, DCs SG/NL.
Erik accepted processing outside Indonesia and Xiaomi's terms knowingly. **Unconfirmed:** OpenRouter
account privacy toggles (D17d). One endpoint, no fallback.

### 403-for-non-admin — PASSED on the deployment

alesha-bot@axiara.ai, time-boxed IAP grant (IAM condition expiry), Incognito, role `user` confirmed via
`/api/v1/auths/` → `/api/v1/portfolio/` **403** at 15:11:05, 15:12:32, 15:15:43 UTC. Gap: the pending→401
rung was not captured (Erik promoted first). A 200 at 15:12:20 was Erik's admin profile — provable
because `utils/auth.py:415` 401s any session whose user ≠ IAP identity. Cleanup: binding removed, account
back to `pending`.

### D18 — the GSM 2023 is the one JUP brand (reverses 2026-09-18)

- ent-os `a66ead2ce`: `src/jup-tokens.css` is the single token layer (portfolio's `jup-brand.css`
  folded in); gray ramp keeps OKLCH L, takes GSM hue 248; GSM green/blue ramps; radius sm2/md4/lg4/xl4/
  2xl6/4xl10; shadows near-absent (none in dark); Space Grotesk + Space Mono self-hosted
  (`static/assets/fonts`). Main panel shadowless, **14px** radius (Erik's one exception, `b585967d9`).
- `~/jup` `72ea747`: D18 + `brand/tokens/colors.css` (same names, GSM values; dark from the inverse
  scope; sun/H2/orange/gold flagged "not GSM", D18c). KB bundle rebuilt `02ca8b1` (needs `wrangler deploy`).
- `@jup/ui` `f8929ce`: identity.css regenerated from canonical; `validate:tokens` 43/36 0 drift; check green.
- **Skill contrast table is wrong**: `#008A43` text = 4.45:1 on white (fails). Words use `#006C34`.
- Live-verified both themes: Space Grotesk loaded, page `#F0F1F1`/`#011627`, panel white/`#0B2135`,
  radius 14px, shadow none, sidebar = shell colour (seam gone).

### Impeccable critique — 22/40 (`.impeccable/critique/2026-09-22T16-41-57Z__…md`)

P0 `/portfolio` has **no entry point** in `src`. P1 chat home is stock Open WebUI (model slug hero,
stock prompts, 👋). P1 sidebar metadata fails AA in light (timestamps 1.8:1 at 10px, labels 2.4:1).
P1 contract invisible in chat. P2 portfolio type (11 sizes, 12 elements <12px, 122ch) + English-only.
Erik chose: **portfolio first, Indonesian-first, top 3** → onboard, clarify, polish.

### Next
1. `$impeccable onboard` — "Portofolio" in the sidebar, admin landing, id-ID default + `lang="id"`, id-ID portfolio copy.
2. `$impeccable clarify` — chat home: Indonesian JUP greeting + 3–4 JUP suggestions, hide Arena Model.
3. `$impeccable polish` — sidebar metadata to gray-600/12px, 24px targets; then re-critique.

## Checkpoint 2026-09-22-live — #16 enforced in production, the UI carries JUP, OpenRouter half-wired

- **Tracker: #16 open** — implemented and deployed; held open only for audit evidence (see below).
- **Commits:** `50173d4dc` (#16), `0341bced5` (token layer), `c3e8e5fcb` (inset panel), `e95a9dfc7` (divider fix).
- **Revisions:** `ent-os-00006-gl2` (#16) → `ent-os-00007-rr8` (UI through `c3e8e5fcb`) → `e95a9dfc7` deployed at wrap time, authorized per-change by Erik.

### #16 — ADR-0002 fail-closed enforcement is live, and still open on purpose

Policy settled by Erik 2026-09-21: **a governed turn must carry the JUP operating contract in its
system message, or it is refused**; every turn audited (admitted / exempt / refused). Governed =
user-facing chat turns including every tool-loop turn; named internal tasks (title, tags, follow-up,
emoji, query, image-prompt, autocomplete, native function_calling, MoA) exempt by a tested allowlist.
Recorded in ADR-0002 itself.

`kb/serve.ts`'s D11 guard could **not** be ported a third time: it inspects the *answer*, which works
only because it is non-streaming. Every ADR-0002 attachment point is an inlet. The contract instead
carries D11's revenue-not-margin rule into the model's context.

Load-bearing details, all tested (26 cases, verified to fail when a patch is dropped):
- `utils/chat.py` attaches + stamps on **every** turn — `middleware.py:5873` strips the system
  message before the tool loop re-enters at `:5994`/`:6214`, so attach-once would be gone by turn two.
- The funnel **also refuses**: the direct-connection and pipe branches never reach a router guard.
- The stamp lives on `request.state`, never `form_data`; the task exemption is honoured only for a
  stamped turn, or a direct caller exempts itself with `metadata.task`.
- `bypass_filter` is ignored by design (`BYPASS_MODEL_ACCESS_CONTROL` forces it True).
- `backend/jup/` cannot import FastAPI, so guards *return* a refusal and the vendor line raises 403.

**Why still open:** zero `jup.governance` log entries exist, because **zero models are configured**,
so no chat turn has ever run on the governed build. Close it on the first real audit entry.

**Audit durability:** `DATA_DIR` is unset in `deploy.sh` and `/srv/jup` is read-only, so the JSONL
file is ephemeral. Every entry also hits `log.info('jup.governance …')` → Cloud Logging, which is the
durable trail. Query:
`gcloud logging read 'resource.labels.service_name="ent-os" AND textPayload:"jup.governance"' --project=jup-ops`

### The UI now carries the canonical JUP identity

Palette = `~/jup/brand` (ratified 2026-09-18), **not** the GSM 2023 palette the `jup-design` skill
still ships — re-confirmed with Erik before starting. Three files, then a layout pass:
- `src/jup-tokens.css` vendored `--jup-*` layer; dark hangs off `.dark`, not the media query.
- The gray ramp was **re-tinted, not re-pointed**: it is overwhelmingly TEXT (gray-500: 1078 of 1095
  uses), so each step kept its exact OKLCH L and gained only the green cast. Largest WCAG shift 0.17.
- Inset shell/panel (Erik's reference): shell `--jup-paper`, panel `--jup-surface`, 16px, 8px inset.
  `main` was `display: contents` and the sidebar is `fixed`; one `#main-content > *` rule re-points
  every route root (all six route groups declare `h-screen` there) instead of editing vendor routes.
- Resting sidebar dividers removed (`#sidebar-resizer` border-r was the visible line).

**"The UI didn't change" was browser cache, not the deploy.** Served CSS contained the build; the
browser held a stale HTML shell pointing at old asset hashes. No service worker. ⌘⇧R.

### Interceptor reaches the live app through IAP

It drives Erik's Chrome, which carries his Google session. This session wrongly claimed twice that
the app was unverifiable because `alesha-bot` lacks IAP access, and verified against a static mock
instead. Verify against the live deployment first.

### OpenRouter — connection set, key missing

Erik chose OpenRouter. The OpenAI connection was re-pointed to `https://openrouter.ai/api/v1` via the
admin API (`/openai/config/update`) — **stored in the app DB, not in `deploy.sh`**. The key field is
empty by design; Erik enters it in Admin Settings → Connections. `/api/models` still returns 0.

**Governance:** D16 governs voice only and explicitly leaves the typed chat path undecided.
OpenRouter is a broker — processing location is per upstream model. Wants a `DECISIONS.md` row and
OpenRouter's "exclude providers that train on prompts" policy. Not drafted yet.

### Traps that cost time this session

- Local `npm run build` OOMs without `NODE_OPTIONS=--max-old-space-size=8192` (Dockerfile sets it).
- A background command's reported exit code is the LAST command's — `| tail` / `| tee` masked a
  failed build once. Capture `$?` immediately, no pipe.

## Checkpoint 2026-09-21-after — backlog cleared, then four gaps taken off the shelf

- **Tracker: #16 open** (ADR-0002 enforcement), filed deliberately. #1–#15 all closed.
- **Cross-repo:** `~/jup` at `9cd0b90`; new repo `erikgunawans/jup-kb-assistant-worker` at `96b9464`+1.

### The assistant had been lying about its own deployment for two months

`~/jup/kb/CONTEXT.md` told the assistant it "runs locally only (`127.0.0.1`) — never web-published
(Decision D13)". D13's **own status field** has read *"STANDING RULE, superseded 2026-07-14 by a
broader exception"* since that date, and Exception v2 records the full hub plus this assistant
serving from `axiara.ai/JUP` behind a password gate.

Not inert prose: `build-kb-bundle.ts:43` bundles `CONTEXT.md` as the assistant's **operating
context**. Asked whether the material was exposed, that line was the answer. Corrected, rebuilt
(8 sources, 53293 bytes), deployed as Worker version `cafea287` (was `b75e6a15`).

**Post-deploy control check — all 401 unauthenticated:** `/JUP/`, `/JUP/api/chat` (POST too),
`/JUP/DECISIONS.md`, `/JUP/COO/`. The POST matters most: that is the Worker's **own** auth check,
not `.htaccess`, because Workers run at the edge and would otherwise bypass it — the gap D13 records
as caught before first deploy. Content itself is unverified; it sits behind Erik's password.

### `~/jup-kb-assistant-worker` was not under version control at all

Not "no remote" — not a git repo. It held `worker.js` as deployed, `wrangler.toml`, the builder, and
the **only copy** of `kb-bundle.js`. Now `erikgunawans/jup-kb-assistant-worker`, **private**, plus a
local bare mirror — D14 says never let `origin` become the only backup, and that reasoning does not
stop at the repo it was written for. No secrets committed; `wrangler.toml` carries identifiers, not
credentials, which is a reason the repo is private rather than a reason to redact.

### #16 — ADR-0002 is Accepted and entirely unimplemented

Not "one remaining hole", which is how the previous handoff framed it. Verified: `VENDOR-PATCHES.md`
has three entries and none is enforcement, `utils/chat.py:151` is pristine, and no `jup` import
exists in `utils/chat.py`, `routers/openai.py` or `routers/ollama.py`. **Every model call in the
operating layer currently reaches its provider ungoverned.**

### Why the 403 test cannot be done first

`get_verified_user` 401s on any role outside the verified set and `DEFAULT_USER_ROLE=pending`, so a
fresh second identity gets **401, not 403**. Reaching the 403 requires promoting an account to
`user` — which is exactly the condition that makes #16 exploitable. **#16 must land before the 403
path can be proven in production.** Erik's call, taken 2026-09-21.

## Checkpoint 2026-09-21-clear — the board is empty; #13 and #15 both closed

- **Session:** `/next` → all four questions answered → #15 deployed and closed → three red gates fixed → token re-minted → #13 closed.
- **Branch:** main · **Commits:** `728d190d3`, `615a27072`, `ef0256cae`, `13a612db7`, `c918b7d6a`, `d33360fa0`
- **Tracker: ZERO open issues.** First time.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync.

### #13 — both drift gates live and green (`d33360fa0`)

`JUP_REPO_TOKEN` re-minted 2026-09-20T20:50:21Z. All four jobs pass: `preflight` skips nothing,
`credential-scope` confirms the runner holds no write permission on the bucket, `kb-drift` agrees
with the live `records/`, `record-sync` reports `in sync` at `ac9dc29`.

**The first live run failed, and that was the valuable part.** `record-sync` exited 1 on real
drift: `Would remove gs://jup-ops-records/deliverables/.DS_Store`. Not litter — a structural bug.
The write path rsyncs a working **filesystem** from a Mac; the gate compares against a git
**checkout**. `.DS_Store` is gitignored in `~/jup`, so it exists on the filesystem and can never
exist in the checkout: the gate would have reported drift **no commit could ever resolve**.
Deleting the object would not have held either, since the next local sync re-uploads it. Both rsync
calls now `--exclude="$JUNK_RE"`. `JUNK_RE` sits with the other config, above the `--check` path
that uses it first — defined lower it would have been unbound under `set -u` on the path that runs
first.

Verified on both sides: `--check` against the live filesystem exits 0, and CI's checkout also says
`in sync`. Local and CI agreeing is the point; their disagreeing was the bug.

**Gap recorded, not fixed:** `preflight` tests only that a secret is **non-empty**, not valid. The
run two minutes before the new token landed did not skip — it ran with the stale token and failed
at `actions/checkout` with `Bad credentials`. Honest (red, and annotated as a checkout failure, not
as drift), but "present" and "valid" are different and only the first is guarded. It will matter
the day this PAT expires.

## Checkpoint 2026-09-21-deployed — #15 deployed and closed, and three red gates explained

- **Session:** `/next` → all four open questions answered by Erik → #15 deployed and verified → the ruff gate pinned → two further red gates found and fixed.
- **Branch:** main · **Commits:** `728d190d3`, `615a27072`, `ef0256cae`, `13a612db7`
- **Deployment:** revision `ent-os-00005-jhc`, image `ent-os:615a27072`, serving 100%.
- **Tracker: one open.** #15 **closed**. #13 unchanged, still blocked on `JUP_REPO_TOKEN`.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`. Not touched this session.

### #15 — deployed with per-change authorization, criteria 7 and 8 met

Rollback to `ent-os-00004-cr2` was staged and an on-demand Cloud SQL backup taken before the
deploy. Neither was needed.

**Criterion 7.** `POST /api/v1/auths/signin` through IAP, carrying a deliberately wrong email *and*
password in the body, returned `erik@axiara.ai` / `admin` / id `beda5418-…`. Because the body was
wrong, the identity can only have come from the header. Four consecutive `GET /api/v1/auths/`
returned `[200,200,200,200]` — the load-bearing half, since `utils/auth.py:415` compares
`user.email != trusted_email` on **every** request and raises `401 User mismatch` on any
difference. A still-prefixed header could not return 200 once.

**Criterion 8.** Same row, not a recreation: `created_at` 2026-09-19 12:28:56 GMT+7, two days
before the deploy; still `admin`; `user_count` 1 before and after the signin call, so no second
prefixed row. `/api/v1/portfolio/` returns the live records.

Invariants held: `DEFAULT_USER_ROLE=pending`, `ENABLE_SIGNUP=False`, `DATABASE_URL` and
`WEBUI_SECRET_KEY` still secret references, ingress still `internal-and-cloud-load-balancing`.

**Still not covered:** the 403-for-non-admin path has never run against the deployment. One
identity exists and signup is closed, so there is no second account to refuse.

### The image was not buildable at all (`615a27072`)

Three builds were needed and the first two failures were not #15's code. Cloud Build now falls back
to the **legacy docker builder**, which does not define the BuildKit-predefined `$BUILDPLATFORM`, so
`Dockerfile:27` expanded empty and died at step 13/65 with `failed to parse platform` — a message
that accuses the Dockerfile rather than the builder. **It reproduces in both the regional and the
global pool**, so the first fix attempted (moving pools) was wrong and was corrected before pushing.
Fixed with an `ARG BUILDPLATFORM=linux/amd64` default, recorded in `VENDOR-PATCHES.md`.

The build pool is still global, but on its own merits only — `e2-highcpu-32` has no quota in
`asia-southeast2`. `deploy.sh` and the README now say explicitly that the split is **not**
load-bearing, so it is not later mistaken for the fix. Note also that the vite OOM is node's own
heap cap and failed identically on 8 GB and 32 GB: machine size has never been the cure, and
`VENDOR-PATCHES.md:14-18` said so before this session claimed otherwise.

### Frontend Build had been red since 2026-09-19, for two independent reasons

Neither had anything to do with the frontend. `npm run format` runs prettier `--write` over
`**/*.md` and the next step is `git diff --exit-code`.

**Cause one (`ef0256cae`):** 43 fork-owned markdown files were not prettier-clean. Formatting them
once would not have held — `/wrap` rewrites `PROGRESS.md` and `.planning/next-session-prompt.md`
every session and neither comes out clean, so the gate would re-red at the next checkpoint. They are
now in `.prettierignore`, along with `tests/fixtures/`: a fixture's value is its exact bytes, and
prettier inserts a blank line into `malformed-unterminated-frontmatter/projects/runaway.md`. The
suite still passes with every fixture prettified (184 passed, verified in a clean clone), so that
one is latent rather than broken — but a fixture whose job is to be malformed must not be quietly
repaired by a formatter.

**Cause two (`13a612db7`):** 29 JUP strings had been added to the Svelte source without the locales
ever being regenerated — "Current Gate", "Engagement", "Blocked on", "Gate state is restricted to
the operating layer". `i18next-parser` re-added them on every run, so the tree came out dirty.
Regenerated: 1856 lines added, 0 deleted, 64 locale files, nothing outside
`src/lib/i18n/locales/`.

**Method note worth keeping:** cause two was only found because the first fix was pushed on the
strength of verifying *half* the gate locally. Verify the whole step sequence in a clean clone, not
the one command you changed. The final check ran prettier **and** `i18n:parse` and asserted zero
dirty files.

`Format & Build` is now green through step 8, **"Production build", which had never executed on any
previous run** because step 7 always failed first. That gate was not merely red; it was not testing
anything.

### The ruff gate, closed (`728d190d3`)

Erik chose pinning CI to the lock. `format-check` runs `uv run --frozen --only-group dev ruff`, so
CI and the local venv are both 0.15.18 and both check 276 files. The `uvx ruff@latest` pre-push
check is retired. Raising the version is now a deliberate `uv lock --upgrade-package ruff`, which
lands in `uv.lock`, which the workflow's `paths:` filter already watches.

### `Release to PyPI` is permanent noise

It fails on every commit, including ones predating this session. Inapplicable upstream workflow. It
is worth knowing because a permanently red gate is where a real failure hides — which is exactly
what `Frontend Build` turned out to be.

## Checkpoint 2026-09-21-wired — #15 wired and guarded, and CI was red the whole time

- **Session:** `/next` → item 1 was #15's unwired modules → registered, tested, documented → CI went red → the red predated this session by five commits.
- **Branch:** main · **Commits:** `4aa919128`, `9041af1fe`, `faaadae54`
- **Tests:** 201 passed locally; 184 passed / 17 skipped in a fresh clone against a runtime-less venv (the CI dev job).
- **Python CI: green for the first time in at least five pushes.** All four jobs.
- **Tracker: two open, unchanged in count.** #15 is code-complete and blocked on deploy authorization; #13 still blocked on Erik.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync. Not touched this session.

### #15 — the modules were real but inert, and now they are registered (`4aa919128`)

`backend/jup/iap_identity.py` and `backend/jup/admin_allowlist.py` were committed last session
**unwired**: nothing imported them, so they changed no behaviour at all. `main.py` now imports both
and registers them.

The order is load-bearing and counter-intuitive. Starlette runs the **last**-added middleware
outermost, so the allowlist is added *first* and the normalizer *second* — which puts the
normalizer on the outside, where every layer below it (the allowlist included) reads an identity
header that has already had IAP's `accounts.google.com:` prefix removed.

### The guard, and proving it can actually fail

ADR-0012's Consequences section asks for a test by name, and the whole argument for choosing a
middleware over a vendor patch rests on it: *a lost patch is a production login loop, a lost
registration line is a failing test.* `tests/test_jup_iap_registration.py` is the second half of
that sentence.

Three of its checks read `main.py` as **source** and need no runtime, so they run in the
`--only-group dev` job on every push. That matters more than the runtime check: it is the one that
actually fires on a rebase. Verified against the real mutations rather than assumed —

| mutation | runtime-less job |
|---|---|
| both `add_middleware` lines deleted | 3 failed, 3 passed, in 0.06s |
| the two lines swapped | 2 failed |
| unmodified | 6 passed, 1 skipped |

A fourth check asserts the **inverse** — that neither `routers/auths.py` nor `utils/auth.py`
imports the normalizer — because the "just to be safe" patch in #15's Traps is exactly what
re-adds the surface option 3 exists to remove. `git diff` against the upstream merge-base
(`0a7c15832`) confirms both files are byte-identical to upstream.

**Its ordering assertions are relational, not absolute, and that was a correction.** The first
version asserted `stack[0] == NORMALIZER` and failed: the vendor registers its session middleware
at the very bottom of `main.py`, inside a `try/except`, so it lands outside these two and *which*
class it is depends on whether Redis resolved. Pinning an index would fail on that alone, and it is
harmless — the session layers read a cookie, never `x-goog-authenticated-user-email`.

### Two defects found in this session's own work, before they shipped

**`deploy.sh` heredoc.** The env-vars heredoc is unquoted (`<<EOF`) so `$ADMIN_EMAILS` expands —
which leaves command substitution live for **everything** inside it, comments included. Backticks
in the first draft of the new comments were executed: `accounts.google.com:erik@axiara.ai: command
not found`. Caught by rendering the heredoc and checking stderr rather than by reading it. The
block is now backtick-free with a comment saying why, and the rendered file is verified to parse to
ten non-empty string values.

**An unreachable branch in `iap_identity.py`.** `except UnicodeDecodeError` around
`value.decode('latin-1')` could never fire — latin-1 maps all 256 byte values — and its docstring
claimed a safety it did not provide. Removed, with a test that a high-byte address survives the
round trip.

### Python CI had been red since before this session, and nobody noticed (`faaadae54`)

The first push went red, which is what prompted looking — and the `pytest` job had failed on
**every** commit for at least five pushes, including checkpoint 2026-09-20-closes's own wrap
(`2f859eefb`). 23 failures in `test_portfolio.py`, every one of them green locally.

**Git does not track empty directories.** Fifteen fixture record trees under
`tests/fixtures/portfolio/` have a deliberately empty `gate-assessments/`. They existed on this
machine and were simply absent from every fresh clone, so `project_portfolio` refused each whole
tree as unavailable. The failures never name the cause: half read `DID NOT RAISE RecordError`,
because an unavailable tree is *returned* rather than raised over, which reads as a validation bug.

Fixed with a `.gitkeep` per directory, each explaining why it exists (`_load_assessments` globs
`*.md`, so none is read as a record). Verified in an actual fresh clone: 184 passed, 17 skipped,
where it had been 23 failed.

This was outside #15's scope and taken anyway, on the reasoning that **a registration guard landing
in a CI nobody trusts is not a guard.**

### A gate gap left open deliberately, because it is Erik's call

`.github/workflows/backend.yaml` runs `pip install "ruff>=0.15.5"` — **unpinned**, so CI always
takes the newest release. The lock pins the local venv. Today that was 0.16.8 in CI against
0.15.18 locally, and they disagree about scope: local checks 276 files, CI checks 437, because
0.16 formats python code blocks **inside markdown** and 0.15 does not. That is what turned the
first push red, on the VENDOR-PATCHES.md entry.

The local gate is therefore permanently weaker than CI and the gap widens with every ruff release.
Pinning CI to the lock, or raising the dev group's floor, would close it — not taken, because it is
a gate-policy decision rather than a silent fix. Until then: check with
`uvx ruff@latest format --check . --exclude .venv --exclude venv` before pushing markdown.

**Resolved 2026-09-21 — Erik chose to pin CI to the lock.** `format-check` now runs
`uv run --frozen --only-group dev ruff …` instead of `pip install "ruff>=0.15.5"`, so CI and the
local venv are the same 0.15.18 and both check 276 files. The `uvx ruff@latest` pre-push check is
**retired** — it now reports failures CI will not have. Raising the version is henceforth a
deliberate `uv lock --upgrade-package ruff`, which lands in the lock, which the workflow's own
`paths:` filter already watches.

### What #15 still needs

Criteria 7 and 8 — sign-in produces no prefix, and the existing account survives — need a
**deployment**, which was explicitly out of scope. Both are marked blocked on the issue rather than
left ambiguous. Only `user:erik@axiara.ai` holds `iap.httpsResourceAccessor`, so a wrong middleware
locks out the one identity that could repair it. Deploy authorization is per-change and was not
assumed.


## Checkpoint 2026-09-20-closes — the blocked board cleared, and the ADR became a ticket

- **Session:** `/next` → every open item was blocked on Erik, so the first act was to ask → he authorized all four → KB bundle deployed → #11 rotated and closed → ADR-0012 decided and implemented-as-#15 → #12 closed won't-fix → started #15's code.
- **Branch:** main · **Commits:** `675cbb59d`, `9d9cdd52c`, + this wrap
- **Tracker: four open → two.** #11, #12, #14 closed. #13 still blocked on Erik. **#15 is new** — the ADR-0012 implementation.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync.

### The handoff's first instruction was "ask", and it was right

Every one of #11–#14 was blocked on a decision or an action only Erik could take, so the session
opened with a question rather than work. He authorized all four at once, which is what made the rest
of the session possible. Worth keeping as a pattern: a board where every item is human-blocked is
not a board an agent should start guessing at.

### #11 — rotated, and the deploy script would have quietly undone it (`675cbb59d`)

The credential is now the `database-url` secret, referenced the way `WEBUI_SECRET_KEY` always was.
Revision `ent-os-00004-cr2` serves 100%, and `GET /api/v1/portfolio/` returns 200 with real records
through IAP. The password was **rotated, not relocated** — `db-password` versions 1 and 2 are
disabled, version 3 carries the new value so the two secrets cannot disagree.

**The part that mattered was not the rotation.** `deploy.sh` rebuilt `DATABASE_URL` from
`db-password` on every run, so the next deploy would have put the plaintext form straight back and
the issue would have reopened itself without anyone touching it. That lookup is deleted, and
`provision.sh` now creates `database-url` instead. A fix that a routine deploy reverts is not a fix.

Two gcloud traps, both recorded in `deploy/gcp/README.md`:

1. **`--update-secrets` alone cannot convert an existing plain env var.** It fails with *"already
   been set with a different type"*, which reads like a permissions or format problem. It needs
   `--remove-env-vars=X` in the **same** command, so no revision exists half-converted.
2. **`--set-secrets` replaces the entire secret block, silently.** Naming one secret drops every
   other reference — `WEBUI_SECRET_KEY` would have vanished.

### ADR-0012 is Accepted, and the decision produced a ticket (`9d9cdd52c`, #14 → #15)

Option 3, the fork-owned middleware. I verified the load-bearing finding before recommending, since
it is the whole reason option 2 is a trap: `utils/auth.py:415` really does re-check the header
against `user.email` on **every request**. Patching only `auths.py:736` therefore creates a
*correct* account and then 401s everything after it — presenting as a session bug, with nothing
pointing at a prefix.

**The deciding argument turned out not to be cost.** It is the shape of the failure: a lost vendor
patch is a production login loop, and a lost middleware registration is a failing test. An outage
you can misdiagnose is worse than one you cannot.

Four sub-questions settled: `admin` comes from an explicit allowlist rather than insertion order;
`DEFAULT_USER_ROLE=pending` stays, keeping IAP access and operating-layer access separable; the
existing account is migrated with its password **dormant, not cleared**; ADR-0001's ceiling does not
move, though the seat list becomes the IAP binding set, which over-counts — the safe direction.

The dormant password rests on `--ingress=internal-and-cloud-load-balancing`. That dependency is
recorded in the ADR because it is invisible from the user table: **loosen ingress and the password
must be cleared.**

### #12 closed as won't-fix, with the condition to reopen

~$7–9/month against a ~$35–60/month deployment, to fix a failure Chrome already routes around by
auto-upgrading to HTTPS. Erik's call. **The reopen condition is a second IAP binding** — a second
person is the first one to type the hostname by hand and read the failure as "the system is down".
Recorded rather than deferred, so it stops consuming a decision slot every session.

### The KB bundle is deployed, and the caveat outlives the deploy

Version `b75e6a15` is live at 100%, replacing a 2026-09-18T21:32 deployment — which confirms the
stale-bundle diagnosis, since #9 landed at 10:43 on the 19th. `--check` proves the bundle current
against `records/`, and it carries the corrected text.

**What is NOT proven is that the page reaches the Worker.** `axiara.ai/JUP/` is 401 behind Hostinger
`.htaccess`, so the end-to-end question could not be asked. The worker README (July) says the
deployed page is a lobby-only teaser whose assistant code calls `http://127.0.0.1:4173/api/chat`. If
that is still true, **this deploy closed nothing** and the commissioner gap is exactly where it was.
Erik took the check.

### #15 started — the modules exist, nothing is wired

Two fork-owned modules written, formatted, linted and smoke-tested, but **imported by nothing**, so
they change no behaviour and are safe on main:

- `backend/jup/iap_identity.py` — `normalize_iap_value` plus a pure ASGI middleware. `rsplit` on the
  **last** colon, because a provider can carry a path (`securetoken.google.com/proj:user`) while
  neither an address nor a numeric subject can contain a colon. A malformed value
  (`accounts.google.com:`) is passed through **unchanged** rather than normalized to `''` — handing
  `auths.py` an empty string is how a malformed header becomes a malformed user instead of a
  rejected request.
- `backend/jup/admin_allowlist.py` — `JUP_ADMIN_EMAILS`, and a middleware that settles the role
  **after** the inner app, once per address per process. After, because a first-ever signin has not
  created the account yet when the request arrives; a startup-only pass would miss precisely the
  person the list was just edited for. It never demotes: "the list shrank" and "this instance
  started before the list grew" are indistinguishable from there.

**Still to do:** the `main.py` registration, the tests, the `VENDOR-PATCHES.md` entry, the env vars
in `deploy.sh`. No deploy — Erik scoped this to code and tests.

## Checkpoint 2026-09-19-gates — the tracker has content again, and the drift gate is half-credentialed

- **Session:** `/next` → opened the four findings as #11–#14 → built #13's skip-path CI → drafted ADR-0012 → Erik authorized the GCP half → provisioned WIF → his PAT turned out broken → wrote the wizard that verifies before storing.
- **Branch:** main · **Commits:** `5afcbc7f2`, `b6fef468d`, `0c6c80ed2`, `6effe355a`, `a0c9fdf09`, `3d8116b2c`, + this wrap
- **Tracker: four open** — #11, #12, #13, #14. It was empty at the last checkpoint; these are that checkpoint's prose findings, finally tracked.
- **Second repo:** erikgunawans/jup unchanged at `ac9dc29`, bucket in sync.

### The findings stopped being prose (#11–#14)

The IAP checkpoint recorded four things in narrative and tracked none of them. Each now has a ticket
carrying evidence rather than a summary of it, re-verified against the live deployment rather than
quoted: `gcloud run services describe` shows exactly one secret reference (`WEBUI_SECRET_KEY`) and a
64-character plaintext `DATABASE_URL` beside it; `curl http://ops.axiara.ai` returns curl 52, an
empty reply on a resolving hostname, which reads as an outage rather than "use HTTPS".

#11 asks for **rotation, not relocation** — that credential has been readable to every `run.viewer`
for the life of the deployment, and a deleted probe job carried it too. Moving it without rotating
would file the finding without closing it.

### The drift gates exist and run nightly (#13, `b6fef468d` → `a0c9fdf09`)

One workflow, because it is one problem: both gates must reach state outside this repository.
**A gate that cannot see what it guards must not report green** — green and "I could not look"
would be the same colour — so preflight probes for each credential and the gate jobs *skip* grey,
with a notice naming what is missing and the drift it is therefore not catching. That is what let
the workflow land before any credential existed.

**Three traps found while building it, each of which would have produced a gate that looked like it
worked:**

1. **`PYTHONPATH=backend` is load-bearing, and its absence is not a no-op.** `pythonpath =
   ["backend"]` is a *pytest* setting; it does nothing for `python -m`. It imports locally only
   because a full `uv sync` leaves an editable-install `.pth`, and `--only-group dev` does not
   install the project. Without it the job dies with `ModuleNotFoundError` and **exit 1** — which is
   `kb_sync`'s code for *drift*. The gate would have cried drift every night about a disagreement
   that did not exist. Proven both ways against a bare venv.
2. **GitHub runs `run:` steps as `bash -e {0}`**, so `cmd; status=$?` aborts before `$?` is read.
   The same trap the `~/jup` pre-commit hook documents, from the other direction.
3. **Under `set -u` an empty bash array is an unbound variable** — the notice loop failed on the one
   path that matters most: both credentials present, nothing skipped.

Exit 1 (drift) and exit 2 (broken tree) stay apart in the annotations. **Exit 2 means the gate
checked nothing** and must not read as a governance alarm.

### WIF provisioned, read-only, and proven (`6effe355a`)

Erik authorized the GCP half only; #11 and #12 were declined and nothing touching the running
service changed. Provisioned as `alesha-bot@axiara.ai`, which holds Owner on `jup-ops`.

```
pool      github-pool
provider  github-provider   condition: assertion.repository == 'erikgunawans/ent-os-new-jup'
identity  records-reader@jup-ops.iam.gserviceaccount.com
grant     roles/storage.objectViewer on gs://jup-ops-records ONLY
```

**Bucket-scoped, not project-scoped:** `objectViewer` at the project would also grant read on
`jup-ops-data`, which holds uploads this gate has no business seeing. **Restricted twice on
purpose** — the provider's `attribute-condition` decides who may mint a token, the
`workloadIdentityUser` principalSet decides who that token may act as. `sts.googleapis.com` had to
be enabled; the handshake fails without it.

**Keyless by choice.** A downloadable service-account key pasted into a repo secret is a long-lived
credential in a second place — #11 arriving by another door.

The assertion was a *step inside* `record-sync`, which also needs the PAT, so it could not run until
both credentials existed. Lifted into its own `credential-scope` job gated on the GCS secrets alone,
it proved itself immediately: **"Runner holds no write permission on jup-ops-records."**
`record-sync` now `needs:` it, so a credential that could publish skips the drift check rather than
running with it.

Not verified locally: the OIDC handshake. **Owner does not include `serviceAccountTokenCreator`**,
so impersonating `records-reader` was denied — and granting that binding just to test would widen
the thing under test. The CI job is the proof, and it passed.

### The PAT was already set, and already broken (`3d8116b2c`)

Erik minted `JUP_REPO_TOKEN` himself at 11:03. Both drift gates still failed:

```
X kb/ agrees with records/ (live tree)   Bad credentials
X The bucket matches the JUP tree        Bad credentials
```

**`Bad credentials` is a 401 — the token string is wrong.** An under-scoped fine-grained PAT returns
**404 `Repository not found`** instead. So this is a truncated paste, a trailing newline, or an
expired token — *not* a permissions mistake, though it reads exactly like one. `erikgunawans` is a
User, not an org, which rules out pending org approval.

It failed that way because **nothing exercised the credential between storing it and a nightly gate
depending on it.** `scripts/wizard-jup-repo-token.sh` is that missing step: mint → **verify** →
store → prove. The verify stage narrows from "is the token real" (`/user`) to "can it see the repo"
(`/repos/jup`) to "can it read Contents" (what `actions/checkout` actually needs), so a failure
names its own cause instead of leaving 401 to be guessed at. Its write probe writes the repository's
**current** description back to itself — a probe that damaged the repo to prove it could would be a
bad trade. Deliberately no `write_env`: CI-only credential, and a second copy on disk is #11.

### ADR-0012 drafted, and the premise it rested on was wrong (`0c6c80ed2`)

#14, the handoff and `iap.md` all described trusted-header auth as a patch to `auths.py:731`. **The
header is read in three places across two vendor files**, and `utils/auth.py:415` re-checks it
against `user.email` on *every* request.

**So patching only the signin path does not create a malformed account — it bricks the deployment.**
The account is created correctly, then every subsequent request compares it against the raw prefixed
header, mismatches, and 401s. The symptom is being signed out immediately after signing in, which
presents as a session bug rather than a prefix bug.

That roughly doubles the vendor-patch surface and moves half of it into `utils/auth.py`, hotter
upstream than `auths.py`. So the ADR carries **four** options, and the new one — a fork-owned ASGI
middleware in `backend/jup/` normalizing the header once, leaving all three sites unpatched — is the
only one that *reduces* the ADR-0007 burden. **LB custom headers cannot do this**: they expand only
load-balancer-provided variables plus `origin_request_header`, with no rewrite facility. A Service
Extension can, and is costed as option 4.

Status **Proposed**. The decision is the Director's and is not recorded.

---

## Checkpoint 2026-09-19-iap — ent-os is reachable; the record sync is observable

- **Session:** `/next` → Erik chose IAP from five untracked candidates → built it → verified in real Chrome → then built the record-sync `--check` and pushed the bucket.
- **Branch:** main · **Commits:** `033479213` (runbook), `61f4d681c` (checkpoint), `5df330e4d` (sync `--check`), + this wrap
- **Tracker: nothing open at the time.** This was untracked work, picked by Erik.
  **Amended 2026-09-19** — the findings recorded below are now tracked as #11 (plaintext
  `DATABASE_URL`), #12 (no port-80 rule), #13 (cross-repo CI for both drift gates) and
  #14 (ADR-0012, trusted-header auth). They were prose-only until then.
- **`https://ops.axiara.ai` is live behind IAP.** Erik is `admin`. The portfolio endpoint returns real records.

### What was standing up, and what it cost

The load balancer is the ADR-0010 shape: Cloud Run stays `--no-allow-unauthenticated` with
`--ingress=internal-and-cloud-load-balancing`, so the `run.app` URL refuses everyone and the only
path in is the LB with IAP on its backend. `ent-os-neg` → `ent-os-backend` (IAP on) → `ent-os-ip`
(**34.111.8.177**) → `ent-os-cert` → `ent-os-lb` / `ent-os-proxy` / `ent-os-fr` on 443.
`erik@axiara.ai` holds `iap.httpsResourceAccessor`; the IAP service agent holds `run.invoker`.

**`deploy/gcp/iap.md` was wrong in three places**, each failing with an error pointing away from its
cause:

1. **The OAuth consent screen step described an API Google shut down on 2026-03-19.**
   `gcloud iap web enable` with no `--oauth2-client-id` now takes a Google-managed client.
   `iap oauth-brands list` returning nothing is expected, not a failure.
2. **`cloudresourcemanager.googleapis.com` must be enabled** or the IAP IAM binding fails with
   `SERVICE_DISABLED` buried under what reads like a permissions error.
3. **The IAP service agent does not exist until asked for.** The `run.invoker` binding fails with
   `Service account service-$PN@gcp-sa-iap... does not exist`, which reads like a typo in the
   address. `gcloud beta services identity create --service=iap.googleapis.com` creates it.

**The cert is ACTIVE ~27 min after DNS, but does not serve immediately.** For about two minutes
after `managed.status` flipped, TCP connected and the TLS handshake died at client hello. Poll the
handshake, not the API status.

### The first account

`ENABLE_SIGNUP=True` for one revision; Erik signed up; the fork promoted him. **The window closes
itself** — `signup_handler` (`routers/auths.py:875`) promotes the only user to `admin` and writes
`ui.enable_signup = False` in the same transaction. `/api/config` confirms `enable_signup: false`
independently of the env var, which was reverted anyway so a future revision cannot reopen it.

A probe job against the private-IP Cloud SQL confirmed `user` and `auth` were both 0 rows first —
had a row existed, the promotion would not fire and Erik would have landed `pending` with no admin
to approve him. The job was deleted after; its config carried the DB password.

### Verified in real Chrome (Interceptor), not asserted

`GET /api/v1/portfolio/` → **200** with real records: `gas-spbg-reactivation`, G1 `fail`, the
evidence chain (`rued-alignment` satisfied with artefact, `gas-allocation-5mmscfd` not),
`awaiting_engagements: ["skk-migas-pgn-allocation"]`, and tier-labelled figures carrying the POTENSI
meaning. GCS records mount, artefact-tree resolution, governance presentation rules and the admin
gate all working together on GCP for the first time. No console errors; 0 of 197 resources failed.

**Not verified:** the 403-for-non-admin path. One user exists and signup is closed, so there is no
second identity to test with. Covered by the 15 local tests; never run against this deployment.

### Two things this session surfaced — now #11 and #12

- **#11 — `DATABASE_URL` carries the Postgres password in plaintext** as a Cloud Run env var, while
  `WEBUI_SECRET_KEY` correctly uses Secret Manager. Readable with a plain `gcloud run services
  describe`. Inconsistent, and a real exposure.
- **#12 — no port-80 forwarding rule**, so `http://ops.axiara.ai` fails rather than redirecting.
  Deliberate — a second rule is a second standing charge — but it is a papercut.

### The better shape, deliberately not taken — now #14

`WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Goog-Authenticated-User-Email` would make IAP *be* the login:
`auths.py:731` creates and authenticates straight from the IAP-verified header, no password and no
signup window ever. That is what ADR-0010 reaches for. It needs a vendor patch first — IAP prefixes
the value (`accounts.google.com:erik@axiara.ai`) and the fork does not strip it — which buys a
permanent ADR-0007 rebase burden. **Decide it as an ADR, not in passing** — #14 carries that
decision, numbered ADR-0012 since 0010 and 0011 are taken.

### The record sync is no longer hand-carried (`5df330e4d`)

`gs://jup-ops-records` is an rsync, not a live mount, so a committed record was not on the dashboard
until someone remembered to run `sync-records.sh`. That was the last hand-carried step between a
record and what a reader sees — the same drift class #9 closed, in a second place, and with **no way
to even observe it**.

**It is not yet in CI — #13.** It runs when a human remembers, which is the failure mode it was
written to end. #13 covers it together with #9's kb-drift gate, because both need the same
credential to reach live state from a runner: one credential problem, two gates.

`sync-records.sh --check` is read-only: `--dry-run` never touches the bucket, verified rather than
assumed — a new file in the forced-failure case never landed there. It exits 1 on drift, so it can
gate a commit or a cron without authorisation to write to deployed infrastructure.

**Two things the first runs taught, both now in the code:**

- **rsync proposes to SET mtime on byte-identical objects**, because an rsync'd object never carries
  the local file's mtime. The first version counted that and reported drift on a tree that was
  genuinely in sync — confirmed false by comparing md5s directly, which matched. A gate that cries
  wolf gets ignored, so only `Would copy|delete|remove` count.
- **`Would remove` is the delete direction and does not match `delete`.** The bucket-has-extra case
  was silent until the filter named it.

The sync path now stamps `.sync-manifest.json` with the commit it published, so `--check` names the
deployed commit rather than only saying it differs. Written **last**: a manifest for a sync that
failed would lie.

**Verified in both directions**, the way #9's gate was: clean mirror of the bucket (24 files) →
`in sync`, exit 0, no false positives. Edited record → `Would copy`. Deleted locally →
`Would remove`. New record → `Would copy`. Uncommitted edit → `DIRTY` warning plus drift. Bad flag →
exit 2. Missing tree → exit 1. Bucket untouched throughout.

**Its first real run found genuine drift:** `records/README.md` in the bucket was missing #9's own
ADR-0011 section — landed locally, never pushed. Erik authorised the sync; the bucket is now at
`ac9dc29` and `--check` reports `in sync`. The live endpoint still returns 200 afterwards, so the
GCS mount picks up a changed bucket without a restart.

---

## Checkpoint 2026-09-19-tracker-empty — #9, #10 and #1 closed; the tracker is empty

- **Session:** `/next` → IAP deferred by Erik → built #9 → built #10 → re-audited and closed #1.
- **Branch:** main · **Commits:** `ca4bed0c9` (#9), `6f8dbc6a4` (#10), + this checkpoint
- **Tracker: nothing open.** #1–#10 all closed. Suite **141 passing**, tree clean after a run.
- **Second repo:** erikgunawans/jup at `ac9dc29`, pushed to origin *and* mirror.

### #9 — `records/` is the single source for partner and gate state (ADR-0011)

`jup.kb_sync` generates the partner state table and the stage-ladder line in `~/jup/kb/partners.md`
from `records/engagements/`, reusing `STAGE_LABELS` rather than copying the vocabulary. Three
mechanisms, because not everything can be generated:

1. **Generate** the structured claims.
2. **Refuse a second home for the vocabulary** — a ladder label used as a *table cell* outside a
   generated region. Prose is exempt: the ladder definition teaches a reader what the table means,
   and "The critical one" argues its case about SKK Migas and PGN/Pertagas by name.
3. **Check** what must stay prose — the "5 mmscfd allocation is not secured" claim in `gas.md` and
   `governance.md`, against the G1 assessments **in both directions**. Deleting the caveat fails as
   loudly as contradicting it, because a governance caveat is a claim and its disappearance is drift.

Two rows became one: the allocation is a single engagement facing SKK Migas *and* PGN/Pertagas
(ADR-0008). A new Evidence column carries each rung's artefact.

**Five counterparties lost their stage.** Danantara/Fadli Rahman, PLN, Pertamina NRE, Pertamina
Patra Niaga and Pelindo had a rung and no record; they now sit in a second table with name and
purpose and **no rung at all**. Three read *Contacted* before. Filing a record moves the row back up,
and the check refuses to let it sit in both.

**The gate is a hook, not CI.** Both repos are private and no cross-repo checkout is wired up, so a
workflow would need a PAT nobody has issued. ent-os CI proves the check catches drift (six
forced-failure cases, all exercised against a copy of the live tree first); `~/jup/.githooks/
pre-commit` stops drift reaching a commit. Its first draft passed silently — `status=$?` after an
`if` block reads the status of the *if construct*, which is 0 when the condition was false.

### #10 — the endpoint is gated on the operating layer, and the seam is tested

**The operating layer is the `admin` role** — Erik's answer, 2026-09-19, held in one named constant.
`get_operating_layer_user` answers **403, not 401**: `get_verified_user`'s 401 means "we do not know
who you are", and telling a signed-in member that bounces them to a sign-in page that cannot help.
The vendor's own `get_admin_user` answers 401 here, which is why the fork has its own dependency.

Configuration moved off module-level `os.environ.get`, which is why this endpoint had **zero** tests
— no `TestClient`, no reference to `/api/v1/portfolio` anywhere in the tree. Now 15, covering signed
out, `pending`, verified-without-permission, permitted, the payload round-trip, ADR-0008 at the wire,
ADR-0009 against the response body, and a `RecordError` as a 500 naming the file and field. Swapping
the handler back to `get_verified_user` fails three of them — run, not assumed.

**The frontend was telling a member without access that the records could not be trusted.** Every
thrown error rendered under *"The portfolio was refused, not emptied"*, the notice for a record the
projection refuses to vouch for. `PortfolioRequestError` now carries the status and 403 gets its own
notice.

**Verified in real Chrome** against uvicorn + vite: `admin` renders the live records (*no gate passed,
blocked on `gas-allocation-5mmscfd`, SKK Migas · PGN/Pertagas at Contacted, G1 refused 2026-09-19*);
`user` gets "Gate state is restricted to the operating layer" on `.jup-notice` without
`jup-notice-refused`; anonymous gets 401.

### The static-wipe landmine fired, and is now disarmed suite-wide

The first unguarded import of the router deleted all 17 tracked vendor assets — exactly what the
previous checkpoint predicted would happen. Restored from git. `tests/conftest.py` now copies the
static tree to a temp dir and sets `STATIC_DIR` at conftest import, before pytest imports any test
module, so a test that imports `open_webui` anywhere is covered without having to know.
`test_boot.py` asserts the guard holds. **Outside pytest it is still live** — an ad-hoc
`python -c 'import open_webui...'` still wipes the tree.

### #1 closed as delivered — 20 met, 1 partial by design, 1 deferred by the spec

Story 17 closed by #9, stories 21 and 19 by #10. Story 13's refused-state hole stays: a `RecordError`
500s, so there is no payload to carry the Named Non-Coverage sentences, and inlining them into the
template reintroduces the staleness #6 removed. Story 22 was never in this slice by its own text.

What remains is not code: a contact record for SKK Migas / PGN, and a `wrangler deploy` Erik has
declined for now — the assistant still answers from the pre-#9 `partners.md`.

### Decisions this session

- **IAP deferred.** Erik declined the ~$18/month forwarding rule for now, so nobody can log in to the
  Cloud Run deployment. `deploy/gcp/iap.md` is ready when he wants it.
- **Operating layer = `admin` role**, not a group or a per-user flag.
- **KB bundle rebuilt, not deployed.** Backed up before the rebuild; `~/jup-kb-assistant-worker` is
  still not under git.


## Checkpoint 2026-09-19-gcp — ent-os runs on GCP; #1 audited, #9 and #10 opened

- **Session:** `/next` → audited #1's 23 stories → opened #9/#10 → exercised the compose overlay →
  deployed ent-os to Google Cloud.
- **Branch:** main · **Commits:** `ae00f74f9` + this checkpoint
- **Tracker: #1, #9, #10 open.** #9 and #10 are this session's findings, not new scope.

### #1 audited, not closed — 18 met, 3 partial, 1 not met, 1 deferred by the spec

Posted as a per-story table on #1. The one that matters is **story 17**: *"the dashboard reads the
same files the board pack is built from, so the two can never disagree."* `records/` is read by
nothing but the dashboard. Gate and partner state also lives in `kb/partners.md`, `kb/gas.md`,
`kb/governance.md` and the board deck. They agree today — `partners.md:10` puts SKK Migas at
Contacted, matching the record — **by hand, not by construction**. → **#9**.

Story 21 is partial: the endpoint carries `get_verified_user` and nothing else, so any `user`-role
account reads every gate refusal and counterparty rung. No endpoint tests exist at all. → **#10**.

Story 13's refused-state hole (a 500 carries no payload, so no Named Non-Coverage) stays as it is —
inlining those sentences into the template reintroduces the staleness #6 removed.

### The compose overlay is exercised — 12/12, and the guard proven

`docker-compose.jup.yaml` had never been run. Client-side: the `:?` guard fires, the bind is
`read_only: true`, and the overlay **adds to** rather than replaces the vendor's data volume.
At runtime: env vars arrive, all three record dirs read, writes and deletes refused, both cited
artefacts resolve. Forced failure with `:rw` flipped exactly the three write checks — and deleted
the live G1 record, which was restored from `jup@fd753ba`. **Run the writable variant against a
copy, never `~/jup`.**

The vendor image was never booted: a full `up` needs several GB and the disk sat at 100%.

### ent-os is deployed to GCP — project `jup-ops`, asia-southeast2

Cloud Run behind a locked ingress, Postgres 16 on a **private IP** with pgvector, records mounted
**read-only** from GCS. Runbook and idempotent scripts in `deploy/gcp/`.

**Verified in the cloud, not asserted:** alembic migrated against Postgres over VPC egress; the
mount probe passes all seven checks in Cloud Run including the write refusal; the auth chain
refuses at both layers (403 unauthenticated at Cloud Run, 401 from `get_verified_user`); and the
deployed app serves `/static/favicon.png`, `loader.js`, `splash.png` and the app shell at 200.

Six gcloud behaviours reported the wrong cause and are all written down in `deploy/gcp/README.md`.
The one worth repeating: **`vite build` OOMs at node's own heap cap, not the machine's** — it failed
identically on 8 GB and 32 GB builders, which is what rules memory out. Fixed by the `NODE_OPTIONS`
line upstream ships commented, logged in `deploy/gcp/VENDOR-PATCHES.md` for the ADR-0007 rebase.

### A landmine removed: the boot test was deleting 17 tracked files

`backend/open_webui/config.py:99` unlinks **every file** in `STATIC_DIR` at import, then repopulates
from `FRONTEND_BUILD_DIR/static`. This tree has no `build/static` unless the frontend was just built,
so the wipe had nothing to put back — and the unlink loop swallows every exception, so it was silent.
Every run of `tests/test_boot.py` deleted the favicons, logo, manifests and `loader.js`. A
`git add -u` after a test run would have committed that.

Fixed in our own test, not vendor code: it now copies the static tree into `tmp_path` and points
`STATIC_DIR` there. **Suite 100 passing and the working tree stays clean after a full run** — which
it did not before.

Harmless in the container: the Cloud Build frontend produces `build/static`, so the delete-then-copy
is a real refresh there. Confirmed by the 200s above.

## Checkpoint 2026-09-19-slice-complete — #4, #8, #5, #6, #7 closed; the slice is delivered

- **Session:** `/next` → #4, then #8, #5, #6, #7 back to back.
- **Branch:** main · **Commits:** `8305ab5d1` · `a0d9bcac2` · `0cbc71200` · `31f0390b5` · `4edec6f2a`
- **Records in the JUP repo:** erikgunawans/jup@`fd753ba`
- **Tracker: 7/8 closed.** Only **#1**, the parent spec, remains open — every child is done.
- **Suite: 37 → 100 passing**, 45 fixture scenarios.

### What the dashboard now does

Reads Gate Assessments, Engagements and projects as markdown from the **live `~/jup` tree**, derives
Current Gate on every read, and renders the gas pillar's binding constraint as a field rather than a
conversation: *no gate passed, blocked on `gas-allocation-5mmscfd`, SKK Migas + PGN/Pertagas at
Contacted, G1 refused 2026-09-19.*

### #4 — evidence detail and fail-closed parse refusals (`8305ab5d1`)

- Each assessment carries its requirements, whether each was met, and its citation.
- `Project.blocking_requirements` counts **refusals only**: a requirement unmet under a *passing*
  verdict is a waiver the board granted, and naming it a blocker would overrule a decision taken.
- Guards beyond the ask: `satisfied` absent is refused (either default invents a claim), `satisfied:
  partially` is refused, bare-path evidence is refused.
- Also closed #3's isort follow-up — `jup`/`open_webui` are now `known-first-party`.

### #8 — boot baseline (`a0d9bcac2`)

- `jup.migrations` reads the alembic graph by **parsing each version file's AST**. Alembic's own
  `ScriptDirectory` can't: `migrations/env.py` imports the whole model tree. A parse also works on a
  tree that is already broken, which is when it is asked.
- Four assertions — one head, one base, no duplicate ids, no dangling parents — each naming every
  file involved. Plus a subprocess boot test, `skipif`-guarded on a **dependency** probe.
- **Premise measured, not assumed:** with two heads injected, importing the app dies with
  `alembic.util.exc.CommandError: Multiple head revisions are present`, exit 1.
- New `boot` CI job, scoped to migration changes + `workflow_dispatch`. **Verified by dispatch:**
  all five ran, 5m27s end to end.

### #5 — engagements, citations, the stage ladder (`0cbc71200`)

- Engagements are their own records; gates **cite** by id and never copy (ADR-0008). One record
  serves two projects — proven across `engagements-shared/`.
- ADR-0009's forecast ban is enforced at `_frontmatter`, the **one door every record type passes
  through**, walking nested mappings and lists. Refused, never dropped.
- **`certainty` is deliberately NOT banned** — Certainty Tier (D11) is the legitimate concept, and
  catching it would refuse the field that keeps FAKTA and POTENSI apart. Pinned by a test.

### #6 — certainty tiers, named non-coverage, legible empty states (`31f0390b5`)

- `figures_by_tier` is the **only** shape served: no flat list, no total, no sum. Composing two bases
  into one statement is something a client would have to go out of its way to do.
- POTENSI labelled margin/profit/NPV is refused, in **both languages**. Whole-word matching, so
  "Marginal volume" passes; POTENSI-only, so NPV on FAKTA passes.
- Named Non-Coverage ships with the payload and renders **outside the branch chain**, so it survives
  the empty and unavailable states.
- The **unreadable directory had no coverage at all**; absent and unreadable now read differently.

### #7 — Gate #1 against the live tree (`4edec6f2a` + jup@`fd753ba`)

- Three records in `~/jup/records/`. **No NPV invented** — `kb/portfolio.md` carries none for SPBG
  reactivation, so the record carries none.
- `artefact_root` turns on artefact resolution. **Proven on the live tree:** renaming the real
  RUED brief produced a refusal naming the file, field and path; restoring it returned to available.
- `docker-compose.jup.yaml` mounts `/srv/jup:ro` as an **overlay**, not a vendor patch (ADR-0007).
- `.env.example` was **wrong** — it pointed at the repo root, not `records/` inside it.

### Verified, not asserted

- **100 passing.** Clean `--only-group dev` env (CI-equivalent): 99 passed, 1 skipped, 0.45s.
- **Every guard in all five tickets was neutered and watched failing**, then restored.
- **Real Chrome against the live `~/jup` tree** and against malformed fixtures: refusals render with
  zero cards, never a partial page. Contrast measured in both themes, worst **4.90:1**, all opacity 1.
- Nothing deployed changed: `build-kb-bundle.ts` reads 8 fixed files, `records/` is not among them.
  `bun build-kb-bundle.ts --check` → *"kb-bundle.js is current."*

### Costs and traps worth not rediscovering

- **YAML eats ` #`.** `purpose: ... — Gate #1 of the gas pillar` parses as `... — Gate`. Nothing
  raises. No parser guard can catch it. The spec's own worked example is unquoted. Quote it.
- **`--only-group dev` silently reuses a full local `.venv`.** A skip-guarded test passes here and
  fails in CI. Verify with `UV_PROJECT_ENVIRONMENT=/tmp/civenv`.
- **Nominal contrast lies when opacity is involved** — an `opacity: 0.82` softening composited to
  3.75:1 from a 4.90:1 token. Fold opacity in before believing a ratio.
- **`read -t N </dev/null` does not sleep** — it returns instantly on EOF. Polling loops built that
  way spin. Use `Monitor` instead.

### Next

**#1 is the only open issue** — the parent spec, with 23 user stories, some explicitly deferred
(story 22's unauthenticated board view says "this slice does not build" it). Decide whether to close
it or audit its stories one by one.

---

## Checkpoint 2026-09-19 — #3 closed: the portfolio tracer bullet, end to end

- **Session:** `/next` → #3, then the two deploy items the previous handoff left with Erik.
- **Branch:** main · **Commit:** `3795e1318`
- **Tracker: 2/8 closed.** #1 (spec) and #4–#8 remain open, all `ready-for-agent`.

### Done — #3, a project and its Current Gate from file to page

- **`backend/jup/portfolio.py`** — the projection. A pure function over a directory: no server, no
  database, no network, no global state. Current Gate is derived on every read as the highest gate
  holding a passing assessment (ADR-0003); it is stored nowhere and no setter exists. A later
  refusal does not revoke an earlier pass.
- **Placed OUTSIDE `open_webui/` deliberately.** `open_webui/__init__.py` imports typer and uvicorn,
  so under `--only-group dev` *nothing* in that package is importable. A sibling top-level package
  plus `pythonpath = ["backend"]` makes `jup` importable with no runtime tree, and
  `sources = ["backend"]` already ships it in the wheel. ADR-0007's rebase never has to merge it.
- **Vendor edit is two lines** — an import and an `include_router` in `main.py`. Nothing else.
- **`backend/open_webui/routers/jup_portfolio.py`** — one read-only `GET /api/v1/portfolio/` behind
  `get_verified_user`, reading `JUP_RECORDS_DIR` from the environment (documented in `.env.example`).
  A `RecordError` becomes a loud 500 naming the file rather than a confident blank.
- **`src/routes/(app)/portfolio/+page.svelte`** + `src/lib/apis/portfolio/` + a ported token layer at
  `src/lib/styles/jup-brand.css`. Three states render distinctly: a Current Gate badge, "No gate
  passed" (assessed and refused), "No assessment" (never assessed). A G1–G4 ladder makes the
  derivation visible rather than asserted.
- **Tokens ported, not imported** — the canonical `~/jup/brand` file keys dark off
  `prefers-color-scheme`, but this app switches on a `.dark` class (`darkMode: 'class'`), so
  following the OS would hand a light-OS/dark-workspace user the wrong palette.

### Verified, not asserted

- **37 passing in 0.09s** — 33 new tests over 19 fixture scenarios, external behaviour only. Still
  sub-second, so nothing imports the runtime tree.
- **Mutation-checked**: making a later refusal revoke an earlier pass fails 3 tests; dropping
  refusals at load fails 8. Both rules are genuinely pinned.
- **Real Chrome against running vite + uvicorn** (not a static serve): all three states rendered from
  markdown on disk, `200` on the projection call, zero uncaught errors. Unauthenticated the endpoint
  returns `401`, and the **live OpenAPI schema exposes `GET` and nothing else** — no write surface.
- **All eight rendered text-on-fill pairs pass WCAG AA, worst 4.90:1**, measured from
  `getComputedStyle` in both themes. The canonical accents would have failed as words at 3.05:1 and
  4.02:1, which is why the `-text` variants exist.

### Cost and friction worth not rediscovering

- **The disk hit 100% (1.0 GB free of 460 GB)** and killed `uv sync` mid-extract. Cleared the npm and
  bun download caches (~15.6 GB) with Erik's approval. `~/.cache/uv` is still 21 GB and is locked by
  his running MCP servers; `~/Library/Caches` is 11 GB. Both prunable later.
- **First backend boot downloads `all-MiniLM-L6-v2`** — ~1.1 GB, minutes, before uvicorn binds.
  Unrelated to this work but it gates every Chrome verification.
- **Forge ran as Claude-family, not cross-vendor.** `codex exec` rejected every model: `gpt-5.4` is
  unsupported on a ChatGPT account and `gpt-6-astra` (what `~/.codex/config.toml` pins) needs Codex
  ≥0.155.1 against an installed 0.139.0. The blind-spot diversity that justifies calling Forge did
  not happen, so its output was reviewed by the same family that wrote it.
- **Interceptor cannot screenshot here.** The DOM render times out at 15s and the OS capture grabs a
  different Chrome window (`macos windows` returns `[]`, so the driven tab cannot be raised).
  Computed-style probes were substituted; the missing-pixel gap is recorded on the ticket.

### Cross-repo — both of the previous handoff's open items are now CLOSED

- **Hostinger SSH restored by Erik**, verified: shell, sftp and the JUP path all resolve. **D16
  deployed** (per-change authorization given): remote backup `~/backups/JUP-2026-09-18-214414.tar.gz`,
  `DECISIONS.md` 11 948 → 14 689 bytes. `/JUP/` and `/JUP/DECISIONS.md` both `401` unauthenticated,
  auth files untouched, **D15 isolation re-proven** (`new-jup:x` → `401` on `/JUP/COO/`).
- **Cloudflare Worker redeployed by Erik.** Two corrections to what the last handoff claimed:
  **`partners.md` was never pending on Hostinger** — there is no `kb/` on the server and never has
  been, so the Strategy KB reaches production *only* through the Worker bundle; and the real problem
  was that **`build_kb_bundle.py` had been lost**, which is why the deployed assistant drifted two
  months while the repo looked correct — retired partner wording plus a decision log missing **half
  its rows** (7 501 of 14 551 chars; D14, D15, D16 all absent). Replaced with
  `~/jup-kb-assistant-worker/build-kb-bundle.ts` (`--check` exits 1 when stale). Recorded in
  `~/jup/CLAUDE.md`, commit `ee9b959`, pushed to `origin` and `mirror`.

### Next

1. **#4** — evidence detail and fail-closed parse refusals. The frontier.
2. **#8** — boot baseline; small, unblocked, guards the alembic two-heads failure.
3. Then #5 and #6 (parallel), then #7.

## Checkpoint 2026-09-19 (late) — first product code: the backend test harness (#2)

- **Session:** `/next` → `/implement` on #2, one ticket, closed and green in CI.
- **Branch:** main · **Commit:** `5cbcea364`
- **Done — #2 closed, the first test suite in this fork:**
  - **`uv run --only-group dev pytest`** — 4 passed. Verified from a deleted `.venv` on **3.11 and
    3.12 locally**, and both again in GitHub Actions.
  - **`--only-group dev` omits the project itself**, so the suite runs in ~13s without installing
    chromadb, transformers or sentence-transformers. A later ticket that must `import open_webui`
    drops the flag and pays for the full tree. Both forms documented in `AGENTS.md`.
  - **Tests live in `tests/` (plural) at the repo root, outside `backend/`** — ADR-0007's quarterly
    rebase must never have to merge them. `test/` (singular) is already the vendor tree's own
    (it holds `sd-empty.pt` for image gen) and was left untouched.
  - Fixture home is `tests/fixtures/`, reached through `fixtures_dir` / `fixture_path` in
    `tests/conftest.py`, which raises `FileNotFoundError` rather than returning a dead path.
  - `pytest>=8.4.0` added to `[dependency-groups] dev`; `uv.lock` updated; `[tool.pytest.ini_options]`
    added to `pyproject.toml`.
- **Decision — `asyncio_mode = "auto"`, not strict.** Under strict an unmarked `async def` is a
  silent hazard, and every later ticket exercises async FastAPI paths. **The guard was proven, not
  assumed:** forcing `-o asyncio_mode=strict` makes `test_async_tests_run_without_a_marker` fail
  outright with "async def functions are not natively supported".
- **Beyond the ACs, deliberately:** a `pytest` job added to the existing
  `.github/workflows/backend.yaml` (path filter extended to `tests/**`), matrix 3.11/3.12, both
  green — a harness nothing runs decays. Also corrected one stale line in `AGENTS.md` that still
  claimed `CONTEXT.md` and `docs/adr/` did not exist yet.
- **Vendor tree untouched:** zero files under `backend/` changed. The `pyproject.toml` edits are
  dependency and test configuration only, which AC 5 permits.
- **Files changed:** 7 (`tests/` ×3 new, `pyproject.toml`, `uv.lock`, `AGENTS.md`, the workflow).
- **Tests:** 4 passing — **the baseline now exists**, where before there were none.
- **Next:** #3 (tracer bullet). #8 is now unblocked — it was waiting on #2 only.
- **Still blocked on Erik:** Hostinger SSH (holding two committed-but-not-live deploys), Cloudflare
  Worker redeploy.


## Checkpoint 2026-09-19 — the build is specified; 15 decisions, 10 ADRs, 7 tickets

- **Session:** `/grill-with-docs` → `/to-spec` → `/to-tickets`, in one unbroken window.
- **Branch:** main
- **Done:**
  - **15 decisions settled** over four grilling rounds. The root one: ent-os is **PT JUP's internal
    operating layer**, not a product with JUP as customer zero — `governance.md` already commissions
    it (PMO, HSE, KPI visibility, audited partner SLAs).
  - `CONTEXT.md` created — 9 terms drawn from JUP's own governance language, glossary only.
  - **10 ADRs.** Seat ceiling as a licence constraint · fail-closed attaches at `utils/chat.py:151`
    with every rejected extension point evidenced · gate assessments not gate status · records
    git-backed in `~/jup` · GPT-Live client delegation · US processing under ZDR · quarterly upstream
    rebase · Engagement as a first-class entity · no likelihood field · no external seats.
  - **Spec #1 + tickets #2–#8** published, all `ready-for-agent`, blocking edges pointing at real
    issue numbers.
  - **Investigation result that changed a plan:** `EVENT_SINKS` are observers, not gates — return
    values discarded, exceptions swallowed, fired after the mutation. The prior standing
    recommendation to build governance on them was right about cost, wrong about capability.
  - **Fifth enterprise hole found:** `routers/openai.py:1464` / `routers/ollama.py:1091` sit behind
    only `get_verified_user`; a user API key bypasses the pipeline entirely.
  - **In `~/jup`:** D16 added (voice / US processing under ZDR, bounded by a named document set),
    `kb/partners.md` migrated to the Engagement Stage ladder, and the dead SSH deploy path recorded.
  - Erik appointed **Director of Operation and Business Development**, full decision authority.
- **Files changed:** 12 in this repo (CONTEXT.md, 10 ADRs, handoff) + 3 in `~/jup`.
- **Tests:** still none — #2 establishes the first backend suite, which is where the baseline belongs.
- **Next:** `/implement` on #2. Blocked on Erik: Hostinger SSH, which is holding two deploys.

## Checkpoint 2026-09-18 (evening) — @jup/ui built in ~/ent-os-ui

**Handoff item 1 (four design-system decisions) — answered.** `@jup/ui` private ·
`~/ent-os-ui` sibling repo · primitives only in v1 · brand initially GSM 2023, then **reversed to
`~/jup/brand` on Erik's ratification later the same session** (see the token section below).

**Handoff item 2 — reframed before building.** Two JUP React systems already existed and were
already design-synced: `~/NEW-JUP/jup-design-system` (`@jup/design-system`, 13 governance
components, registered `projectId`) and the `jup-design` skill (24 brand primitives + `_ds_bundle.js`
format 4). Building a fresh design system would have duplicated them. Erik chose option B: a new
`@jup/ui` consuming the existing brand identity, holding only what those two lack.

**Built — `~/ent-os-ui`, 3 commits, gates green:**
- Token layer: identity isolated in `src/tokens/identity.css`, a semantic layer on top, and a
  dark theme.
- 20 primitives + `JupUIProvider`: Button, IconButton, Field, Input, Textarea, Select, Checkbox,
  Switch, Badge, Tag, Card, Avatar, Skeleton, Spinner, Alert, Dialog, Tooltip, ToastProvider, Tabs,
  DropdownMenu.
- 20 story files / 97 stories, Storybook 8 with a light/dark toolbar.
- `bun run check` = typecheck (strict) → tsup build → conventions validation → **token drift gate**.
- `.design-sync/{config.json,conventions.md}`, shape `package`.

**Accessibility defect found and fixed — verified in real Chrome, not assumed.** White on Pigment
Green is **3.23:1**, failing AA for normal text; the source system ships that on its primary button.
Fixed by moving the label to Rich Black (5.67:1) with the identity surface untouched. Needed three
tokens, not one: `--jup-text-on-brand` (Rich Black, green), `--jup-text-on-alt` (white, blue — Rich
Black on Polynesian Blue is 2.11:1), `--jup-text-on-danger` (flips per theme, because `--jup-danger`
lightens in dark and a white label sat at 2.42:1). All 6 button variants × 2 themes and all solid
badges now measure ≥ 4.5:1 against their real painted background.

**Also corrected a claim I had written myself:** `#00A550` on `#011627` is 5.67:1 and *does* clear
AA. The dark-mode brand lift is for small-text headroom, not an AA failure. README and
`semantic.css` fixed.

**Verification notes.** `bunx serve` strips `.html` and the query string (clean-URL rewriting), so
Storybook story ids never arrive and every story reads "No Preview" — use `storybook dev`, not a
static serve, for Interceptor checks. The conventions validator was proven to fail on an injected
bad token and a bad component name before being trusted.

**Canonical token ratification — the second half of the session.** Erik chose `~/jup/brand`
(`#079F4E`, IBM Plex Sans) over the GSM 2023 palette. `@jup/ui` was re-based onto it:

- `identity.css` is now a **vendored copy** of `~/jup/brand/tokens/colors.css`, gated by a new
  `validate:tokens` script diffing all **42 light / 36 dark** canonical tokens and failing on drift.
  Vendored not imported, because `@jup/design-system` is unpublished and design-sync needs a
  self-contained `dist/`. The gate was proven to fail by reverting `--jup-brand` to `#00A550`.
- **The swap was wider than billed.** My "one-file edit" claim held for hex values and font names
  only — the GSM system is square and flat, JUP 2.0 is rounded (16px panels, 8px controls) and
  elevated, so `radius.css`, `elevation.css`, every component radius and the conventions
  house-style moved too. **Brand character is not just colour.**
- **Three real bugs surfaced:** `--jup-shadow-lg: var(--jup-shadow-lg)` was a circular reference
  (CSS resolves that to guaranteed-invalid — the large shadow silently vanished); the dark
  `--jup-text-inverse` override made the inverse button's label and surface the same colour
  (1.00:1, invisible); the font stack had dropped two canonical fallbacks.
- **Contrast redone, not ported** — the canonical palette behaves oppositely. Fill and text are now
  separate tokens per hue (canonical accents fail as *text* on their own tinted bg at 2.65–4.60:1);
  `--jup-text-brand` resolves to `brand-deep` because `#079F4E` as text on paper is 3.20:1;
  `--jup-text-on-{brand,alt,danger,warning}` are per-hue and per-theme; small helper text moved off
  `--jup-text-muted` (4.15:1, large-text only) to `--jup-text-secondary` (7.48:1).
- Swept **9 stories × 2 themes in real Chrome: zero failures.** The one flagged item is a disabled
  tab at 2.74:1, reported as exempt under WCAG 1.4.3 rather than silently passed.

**RESOLVED same session:** Erik ratified `~/jup/brand` (`#079F4E`, IBM Plex Sans). `@jup/ui` was
re-based onto it — identity vendored + drift-gated, contrast reworked for the new palette, three real
bugs caught in the process (a circular `--jup-shadow-lg` that silently killed the large shadow, a
dark inverse button at 1.00:1 with label and surface the same colour, and a dropped font fallback).
Swept 9 stories × 2 themes in real Chrome: zero failures.

**Framing correction — Erik pushed back, correctly.** I described the project as having "zero
product code" and prior work as "scaffolding," and recommended a from-scratch product grilling.
Erik challenged it: the fork already has Open WebUI's full capability. He was right, and the
architecture briefs are design work, not survey work — they name the governance chokepoints with
file:line.

The accurate statement is much narrower: **nothing yet says who pays, for what, instead of running
stock Open WebUI free.** And the thesis is already in our own notes — stock Open WebUI is
enterprise-*capable* but not enterprise-*deployable*:

- Audit redaction is **one regex** (`audit.py:285`); `REQUEST_RESPONSE` captures response bodies
  **verbatim**. Full audit builds a PII repository, not a compliance control.
- `workspace.tools` = unsandboxed `exec()` + `pip install` from user frontmatter. Only kill switch
  is `ENABLE_PLUGINS=false`.
- Every frontend guard is a client-side `goto('/')`.
- Timers, automations, subagents and context compaction bypass HTTP middleware entirely — governance
  must live in the pipeline. This is a genuine moat: a competitor bolting policy onto middleware
  ships something that silently misses those paths.

Already present and cheap to build on: `publish_event`/`EVENTS` with `EVENT_SINKS` taking a sink
class, and `merge_usage` (`response.py:100`) aggregating per-user/per-group tokens for chargeback.

Erik deferred the grilling to next session. It is scoped to three questions — which hole ships
first, who signs, and what beats "just use Azure AI Foundry / Bedrock" — not a blank page. Carried
into the handoff with an explicit warning not to reopen with the rejected framing.

**`~/ent-os-ui` remote — found missing and fixed during the wrap.** The three commits existed only
on this machine; the session's entire deliverable was unbacked. Erik authorised it and it is now
private at `github.com/erikgunawans/ent-os-ui`, all 3 commits pushed, remote SHA verified against
local HEAD. Worth noting for next time: a repo created with `git init` mid-session has no remote,
and nothing warns you — check for one before ending any session that created a repo.

**Superseded — was open for Erik:** which token layer is canonical — GSM `#00A550`/Space Grotesk (what `@jup/ui`
uses) or `~/jup/brand` `#079F4E`/IBM Plex Sans (what `@jup/design-system` uses). Both self-describe
as canonical. Reversing is a one-file edit in `src/tokens/identity.css`.

> Newest checkpoint first. Append-only history; never delete entries.

## Current state

| | |
|---|---|
| **What this is** | A fork of [Open WebUI](https://github.com/open-webui/open-webui) v0.11.3, intended as the base for an enterprise AI product (JUP / Axiara) |
| **Our code** | **None yet.** One commit, and it adds only docs — no product code has been written |
| **Branch** | `main` |
| **Vendor baseline** | `0a7c158` (upstream/main at 0.11.3) |
| **Remotes** | `origin` → `erikgunawans/ent-os-new-jup` (private) · `fork` → `erikgunawans/open-webui` · `upstream` → `open-webui/open-webui` |
| **Tests** | Not run this session — no baseline recorded yet |

**Read first:** `docs/architecture/README.md` — the vendor codebase in 17 briefs, and the five things
that matter most before touching anything.

## What to do next

1. **Decide the four open questions in `docs/design-system/PLAN.md`** — package name/scope, whether to
   keep Open WebUI's `blue-500` accent or move to a JUP/Axiara brand color, repo location, and whether
   composites ship in v1. These block phase 1 and are Erik's calls.
2. **Build the React design system** in a new repo, per that plan. It is the agreed next task.
3. **Establish a test baseline** for this repo before any product code lands, so regressions against
   the vendor tree are detectable.

---

## Checkpoint 2026-09-18 (Repo setup, full codebase read, design-system spec)

- **Session:** Three pieces of work: configured the engineering skills for this repo, read the entire
  vendor codebase, and determined that `/design-sync` cannot target it — producing a token spec and
  build plan for the React design system that can.
- **Branch:** `main`
- **Done:**
  - Created the private GitHub repo `erikgunawans/ent-os-new-jup`, rewired remotes (`origin` → new
    repo, old fork → `fork`, `upstream` unchanged), pushed `main`. Pinned `gh repo set-default` —
    without it `gh` silently targets **upstream**, which it did on the first label-create attempt.
  - Wrote `AGENTS.md` and `docs/agents/{issue-tracker,triage-labels,domain}.md`. Created all five
    canonical triage labels on the repo.
  - **Read all 348,002 lines** of the vendor tree (1,017 source files) in full via 16 parallel agents;
    distilled to `docs/architecture/` — 17 briefs plus an index.
  - Established that `HEAD` is **byte-identical to `upstream/main`** — zero divergence from vendor.
  - Determined `/design-sync` is structurally inapplicable: the converter is React-only and this tree
    is 662 Svelte files with no React. Recorded in `.design-sync/NOTES.md`.
  - Extracted the real design language to `docs/design-system/TOKENS.md` and wrote
    `docs/design-system/PLAN.md` for a React DS that the sync *can* consume.
- **Files changed:** 21 added (`AGENTS.md`, 17 × `docs/architecture/`, 2 × `docs/design-system/`,
  3 × `docs/agents/`, `.design-sync/NOTES.md`, `.planning/next-session-prompt.md`) — all documentation,
  no source changes.
- **Tests:** Not run. No baseline exists yet for this fork.
- **Next:** Answer the four open design-system decisions, then build the React DS in a new repo.

### Findings worth carrying forward

- **Migrations run at `config.py` import time.** A fork revision colliding with an upstream one gives
  alembic two heads and **the app will not boot at all**. `d4e5f6a7b8c9`'s docstring already
  contradicts its own `down_revision` from a past hand-fix — trust `down_revision`, never the docstring.
- **`workspace.tools` permission is effectively "grant admin"** — `exec()` of user Python in the server
  process, no sandbox, plus `pip install` from frontmatter. `ENABLE_PLUGINS=false` is the only switch.
- **Every frontend guard is client-side only**; the backend must re-assert everything.
- **Timers, automations, subagents, memory review and context compaction bypass HTTP middleware** —
  they forge a `Request` and call `CHAT_COMPLETION_HANDLER` directly. Governance must live in the
  pipeline, not in front of it.
- **`publish_event` / `EVENT_SINKS` is the cleanest audit/SIEM seam** — already called on nearly every
  mutation, so a sink class needs no router changes.
