---
target: chat home + sidebar
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-09-25T22-39-50Z
slug: src-routes-app-page-svelte
---
# Critique — chat home + sidebar (None-JUPe), 2026-09-26

Heuristics 23/40 (Acceptable): H1 2, H2 3, H3 3, H4 2, H5 2, H6 2, H7 3, H8 3, H9 2, H10 1.
Specificity: authored copy (contract line, Indonesian greeting, Direksi prompts, kembang goyang mark) on the vendor ChatGPT skeleton; brand is paint and copy, not hierarchy.
Detector: 3 findings — layout-transition Sidebar.svelte:1247 (real, P3); overused-font NoneJupeLockup.svelte:53,81 (false positive: GSM brand face). Overlay blocked by Chrome Local Network Access prompt.

## Priority issues
- [P1] Blue primary spent on voice mode: empty composer's only filled blue control is "Mode suara" (jup-skin.css:95 repaint). Fix: chat.call off for users, or `jup-voice` hook → ghost; blue for Send only.
- [P1] Sidebar has no wayfinding: no active state on Obrolan Baru at "/", active fill bg-black/[0.035] faint on paper, hover bg-gray-100 lighter than paper, no green active marker (tokens promise one), 7 ungrouped items, landmark labelled "Chat history". Fix in jup-skin: #sidebar active = surface + inset 2px brand edge; hover surface-2; divider after actions; aria-current on New Chat.
- [P1] Temporary Chat tooltip empty in id-ID (translation.json:3160) next to "Setiap permintaan dicatat". Audit line is written regardless (utils/chat.py:184), so fill: "Obrolan ini tidak muncul di riwayat Anda; permintaan tetap dicatat untuk audit."
- [P2] UI contrast: Folder "+"/Obrolan collapse text-gray-300 1.39:1; header icons (Obrolan Sementara, Kontrol) 2.76:1; dark section headers ~3.9:1; dark placeholder ~3.2:1. Fix: --jup-ink-faint via jup-skin.
- [P2] Composer/suggestions for first-timers: placeholder truncated ("Lampirkan dokumen atau ajukan"), icon-only +/integrations/"🔧 1", one-model dropdown, suggestions reshuffle each load (Suggestions.svelte:62) and left-offset from input, waterfall anim has no reduced-motion guard, empty Obrolan list has no empty state.

## Personas
Alex: admin "/" lands on /portfolio; suggestions reorder; hotkeys only on hover. Sam: suggestion buttons role=listitem; landmark "Chat history"; sidebar focus ring vendor blue (skin ring scoped to #main-content); icon contrast. Jordan: blue circle = voice call; "🔧 1" and diamond icon unlabeled; nothing near "+" on confidentiality.

## Minor
Greeting h1 weight 400; dark lockup "e" loses green; 9px tagline; Ruang Pimpinan label bypasses i18n (Sidebar.svelte:1084,1390); sidebar width transition.
