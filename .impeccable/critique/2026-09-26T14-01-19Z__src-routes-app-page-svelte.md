---
target: chat home
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
timestamp: 2026-09-26T14-01-19Z
slug: src-routes-app-page-svelte
---
Method: dual-agent (A: design review, source-only because production was down during its pass · B: detector + live browser, re-run after recovery)

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | Home shows no knowledge scope, data date or active tools; with one model the model name is hidden |
| 2 | Match System / Real World | 3 | Indonesian greeting and suggestions are native; vendor register leaks ("Obrolan", "Penerjemah Kode") |
| 3 | User Control and Freedom | 3 | Temporary chat, stop, closable sidebar |
| 4 | Consistency and Standards | 3 | Blue reserved for Send holds live; web-search/image toggles (sky-500, unlabelled) exist in code but did not render |
| 5 | Error Prevention | 2 | No guidance on confidential attachments or what "dicatat" covers before typing |
| 6 | Recognition Rather Than Recall | 2 | Tools behind two icon-only 30px buttons; / @ # commands invisible |
| 7 | Flexibility and Efficiency | 3 | Power paths exist, none hinted on the home |
| 8 | Aesthetic and Minimalist Design | 3 | Calm, restrained; contract line (100px block at 390) competes with suggestions |
| 9 | Error Recovery | 2 | Generic upload errors; no branded failure page (today's outages showed raw Google 500) |
| 10 | Help and Documentation | 1 | No "what can I ask", no link to the operating contract, no explanation of logging |
| **Total** | | **24/40** | **Acceptable** |

## Design Specificity Verdict
LLM: a well-made JUP skin on the stock Open WebUI empty state. Culturally exact greeting (Indonesian pagi/siang/sore/malam), the kembang goyang mark that sways once, disciplined tokens, and four genuinely JUP suggestions ("Ringkas dokumen jadi poin keputusan untuk Direksi", "Susun surat resmi untuk mitra atau regulator", "Siapkan bahan rapat", "Uji sebuah klaim"). But the layout is category-interchangeable: nothing says what None-JUPe knows, nothing on the home leads to the surfaces only JUP has (Portofolio, Ruang Pimpinan), and the governance promise is grey small print rather than a stance.
Deterministic: CLI 1 finding (layout-transition, Sidebar.svelte:1252 `transition: width`). Live overlay 5 elements: layout-transition on #sidebar and #chat-container, undersized-ui-text on span.nj-tagline "ASISTEN AI" (9px), nested-cards on #message-input-container; body-level gradient-text/marquee are false positives from the inlined detector source. All measured text passes AA (lowest 5.73:1). Every input-bar and top-bar control is 30x30 or 24x24, under 44x44 at 390px. Suggestions stay above the fold at 390x844.

## Priority Issues
- [P1] The home never says what None-JUPe knows or can do. Why: time-poor leaders will not risk a question they cannot predict; this is the gap between chatbot and operating assistant. Fix: one capability line under the greeting built from the records index ("Mengetahui: rekaman JUP per <tanggal>, portofolio, keputusan BOD · Belum: email, keuangan live"), items clickable as starters. Command: $impeccable onboard
- [P1] The contract line reads as jargon and as surveillance ("tidak pernah menyajikan pendapatan sebagai marjin. Setiap permintaan dicatat."). Why: opaque to non-finance readers; unexplained logging chills candid questions. Fix: plain-Indonesian stance plus an "Apa yang dicatat?" disclosure (what, who sees it, retention). Command: $impeccable clarify
- [P2] Home is role-blind and has no route to Ruang Pimpinan / Portofolio. Why: BOD users' reason to be here is one sidebar hop away and hidden on mobile. Fix: role-aware starters (BOD: decisions this month; staff: task prompts) and a leadership entry on the home for BOD. Command: $impeccable shape
- [P2] Mobile touch targets and micro-text: input bar 30x30, top bar 24x24, "ASISTEN AI" at 9px. Why: misses on a phone, one-handed. Fix: 44px hit areas (padding, not bigger icons), tagline to 11px+. Command: $impeccable adapt
- [P3] Width transitions on #sidebar and #chat-container; nested card around the input. Fix: transform-based slide; flatten the input container. Command: $impeccable optimize

## Persona Red Flags
- Alex (power user): / @ # commands undiscoverable; integrations icon-only; suggestions never change; no New Chat shortcut hint.
- Sam (keyboard/screen reader): conditional web-search/image toggles lack aria-label/aria-pressed; + and Integrations rely on a #main-content focus-ring rule that portals escape; placeholder is CSS ::before (announcement unverified); h1 line-clamp-1 truncates without a tooltip.
- BOD member (Indonesian, non-technical, time-poor): no route to Ruang Pimpinan on the home; "pendapatan sebagai marjin" jargon; "Setiap permintaan dicatat" unexplained; no data-freshness cue; on a phone the sidebar is hidden and the home offers no second path.

## Minor Observations
- Untranslated "By" model-author line in Placeholder (dormant).
- Navbar renders an invisible "Obrolan Baru" title on a new chat: the top bar carries no information.
- Voice-mode button shows on an empty prompt; confirm it is hidden for staff with voice disabled.
- Add a branded Indonesian load-balancer error page ("None-JUPe sedang dipulihkan") for outages. ($impeccable harden)

## Questions to Consider
- If a board member can ask one question this week, why doesn't the home tell them which question None-JUPe answers best?
- Is "Setiap permintaan dicatat" meant to reassure or to warn? Today it does both and commits to neither.
- What if the home opened on JUP's state (open decisions, latest records, what changed since the last visit) instead of an empty prompt?
