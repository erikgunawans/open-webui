---
target: app shell (chat home + portfolio)
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
timestamp: 2026-09-22T16-41-57Z
slug: src-routes-app-layout-svelte
---
## Design Health Score: 22/40 (Acceptable)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | Portfolio shows gate state well; chat gives no sign the fail-closed contract is active |
| 2 | Match system / real world | 2 | lang="en" and English copy for an Indonesian-first BUMD; id-ID strings empty; "Rp 63,3 M" |
| 3 | User control and freedom | 3 | Stock regenerate/edit/fork; nothing to fault |
| 4 | Consistency and standards | 2 | Pills (999px) and bg-black send button break square-cut GSM; stock Tailwind gray in prose; paper panel on portfolio vs white on chat |
| 5 | Error prevention | 3 | Portfolio separates access-denied from load error; copy prevents misreading |
| 6 | Recognition rather than recall | 1 | /portfolio reachable only by typing the URL; "Arena Model" noise |
| 7 | Flexibility and efficiency | 3 | Shortcuts exist, hints at 1.82:1 |
| 8 | Aesthetic and minimalist design | 2 | Empty state full of irrelevant stock prompts; 48 buttons per chat turn |
| 9 | Error recovery | 2 | Refusals say what is missing, not what to do or who owns it |
| 10 | Help and documentation | 2 | Excellent non-coverage asides, but English-only with unfollowable ADR/D refs |

## Design specificity
Category-interchangeable where users live (chat home: Open WebUI name/logo, model slug as hero, stock prompts, pill controls, no brand colour), specific only on /portfolio, which has no entry point. Detector: CLI 2 findings (side-tab at portfolio :604, real but quiet; layout-transition in Sidebar :1137, upstream false positive). Live: 18 light / 21 dark — sidebar metadata low-contrast (1.8–2.4:1, real regression), 10px timestamps, 12 elements under 12px, 11 distinct font sizes, portfolio lines ~122ch; overused-font (Space Grotesk is mandated) and dark gray-on-color (9.7:1, passes) are false positives.

## Priority issues
- [P0] Portfolio has no entry point — no link/route/redirect in src. Fix: "Portofolio" item under New Chat; consider it the admin landing. (onboard)
- [P1] Chat home is stock Open WebUI — model slug hero, Roman-Empire suggestions, emoji replies. Fix: 3–4 JUP suggestions in Bahasa Indonesia; sentence-case JUP greeting stating the contract is active. (clarify)
- [P1] Sidebar metadata fails AA in light — timestamps #acb6bf on #f0f1f1 1.8:1 at 10px; section labels 2.4:1; shortcut hints 1.82:1. Fix: raise to gray-600 (5.73:1), 12px floor. (polish)
- [P1] Governance contract invisible in chat. Fix: quiet persistent contract indicator by the input; distinct refusal message style. (harden)
- [P2] Portfolio type and language — 11 font sizes, text at 11.2–12.8px, 122ch lines, figures in Grotesk not Mono, English only, "Rp 63,3 M". Fix: 14px floor, 68ch measure, Space Mono tabular figures, id-ID copy, "Rp 63,3 miliar". (typeset)
- [P2] GSM geometry broken in chrome — rounded-full controls, bg-black send/voice, 20×20 Chat Menu targets. Fix: 4px controls (avatars exempt), Pigment Green or Rich Black send fill, 24px targets. (polish)

## Persona red flags
- Alex: no shortcut to Portfolio; invisible shortcut hints; Arena Model noise; 48 buttons per turn.
- Sam: lang="en" over Indonesian text; 20×20 targets; 10px timestamps; sidebar metadata below AA in light.
- The Director: portfolio entirely English; half-translated "Tier 2 · POTENSI"; ADR/D jargon; refused G1 has no next action or owner; first screen reads as a generic AI toy.

## Minor observations
- The 14px panel exception disappears on /portfolio (paper panel inside the panel).
- Portfolio cards carry a redundant 1px shadow beside the hairline.
- Eyebrow casing differs between chat ("Suggested", sentence case) and portfolio (uppercase tracked).
- Dark mode clears AA on sidebar metadata that light mode fails.

## Questions
- If the portfolio is what makes this JUP's, why is chat the home route?
- Should "What this view does not prove" open the page as the reading contract instead of closing it?
- What does a fail-closed refusal look like in chat, if it looks like any other reply today?
