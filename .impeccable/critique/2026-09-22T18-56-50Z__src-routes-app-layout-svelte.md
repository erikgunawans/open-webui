---
target: app shell (chat home + portfolio)
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
timestamp: 2026-09-22T18-56-50Z
slug: src-routes-app-layout-svelte
---
## Design Health Score: 23/40 (Acceptable), up from 22

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Gate state and blockers read at a glance; no "as of" time on the portfolio; active nav is a 3.5% tint |
| 2 | Match system / real world | 2 | Blockers shown as slugs; ADR-0009 / D11 in user copy; record data English under id-ID; "anak tangga", "keterlibatan" read as translation |
| 3 | User control and freedom | 2 | Admin entering at / always lands on /portfolio with no setting; chat reached via New Chat |
| 4 | Consistency and standards | 2 | Pills 999px on a square-cut brand; OI logo, "Open WebUI" title, pure-black voice button |
| 5 | Error prevention | 3 | Denied / refused / unavailable / empty kept distinct |
| 6 | Recognition rather than recall | 2 | Ladders are colour-only; engagement slugs resolved by memory against cards further down |
| 7 | Flexibility and efficiency | 2 | No sort, filter, deep link or collapse on the portfolio |
| 8 | Aesthetic and minimalist design | 2 | One blocker stated three times; six non-coverage statements outweigh the one project card |
| 9 | Error recovery | 3 | "Refused, not emptied" copy; access-denied separated from bad records |
| 10 | Help and documentation | 2 | Tier meanings inline; nothing says what G1–G4 each certify |

## Design specificity
Portfolio: authored for JUP (refused vs never-assessed, waived vs blocking, tiers kept apart, mono requirement ids inside the refusal fill). Chat home and sidebar: still category-interchangeable. The model avatar resolves to the Open WebUI favicon, the sidebar wordmark and the / tab title read "Open WebUI", the model slug sits in the input bar, the voice button is rgb(0,0,0) not Rich Black, placeholder is stock "How can I help you today?". Detector: CLI exit 2, two findings, side-tab portfolio:668 (neutral --jup-line tier divider, deliberate, false positive in spirit) and layout-transition Sidebar:1172 (upstream vendor, true positive). Live overlay: 12 anti-patterns: low-contrast x1 (sidebar "Yesterday" 2.44:1), layout-transition x3 (vendor), line-length x7 (~122–125ch on portfolio), tiny-text x1, cramped-padding x1, overused-font (Space Grotesk is mandated, false positive). Probes: 0 targets under 24px; portfolio 12 distinct font sizes, 9 elements under 12px (blocking label, rungs, tier label and meaning, evidence state, non-coverage label).

## Priority issues
- [P0] Open WebUI identity on the chat home and the sidebar: OI avatar beside the greeting, "Open WebUI" wordmark and tab title, model slug in the input bar. Fix: JUP mark as the model profile image, display name "Asisten JUP", WEBUI_NAME (licence renders "JUP (Open WebUI)"), Indonesian placeholder. Blocked on Erik's licence decision. (polish)
- [P1] Sidebar date headers fail AA in light: "Yesterday"/"Kemarin", Sidebar.svelte:1681, text-gray-500 = oklch(0.69 0.023 248) on #f0f1f1, 2.44:1 at 12px. Missed by the 2026-09-23 contrast pass, which fixed timestamps, section labels and hints. Fix: gray-600 (5.07:1 measured on the same surface). (polish)
- [P1] Blockers have no owner, next action or date, and are shown as slugs. Fix: owner and next step on the record; render one plain-language line, slug as secondary mono. (clarify, layout)
- [P1] Same fact three times, and the page ends on disclaimers: Blocked on + evidence list + Waiting on; two non-coverage boxes, six statements. Fix: keep Blocked on; evidence behind details; one collapsed non-coverage footnote. (distill)
- [P2] Ladders give a screen reader no state; Placeholder.svelte:137 sets aria-hidden on a focusable button; chat home has no heading. Fix: visually hidden rung state, aria-current="step", heading on the greeting. (harden)
- [P2] Portfolio type: 12 sizes, 5 between 11.2 and 12.8px, lines to 97ch; pills 999px. Fix: 14px floor for body, 12px for labels, 68ch measure, --jup-radius-sm on pills. (typeset, polish)

## Persona red flags
- Alex: / always bounces an admin to the Portfolio; no project anchors or filters; suggestion order reshuffles each load.
- Sam: "Yesterday" header 2.44:1; no heading on chat home; aria-labels stay English under id-ID; ladders colour-only.
- The Director: OI logo and slug on the first chat screen; record data English under id-ID; sidebar half translated ("Notes", "Folders"); no owners or dates; ADR/D references in copy.

## Minor observations
- Greeting uses the full legal name; first name would be warmer.
- Chat input text is Tailwind gray-700, not a JUP ink token.
- Portfolio active nav item is a faint 3.5% tint with no accent.
- Five-rung engagement ladder at 11.5px likely squashes under ~400px (from code, not verified).
- The contract line reads more as a warning to the user than as reassurance.

## Questions
- If the Director lands on the Portfolio, should chat be a tool inside it ("ask about this blocker") rather than a separate home?
- Who is the non-coverage copy for, the Director or a later auditor, and does it need to be on every read?
- Would the product read as more governed if the assistant had no visible model identity at all, only the contract?
