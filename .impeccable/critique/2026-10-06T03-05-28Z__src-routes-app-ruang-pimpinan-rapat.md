---
target: Rapat Direksi (Notulen + Layar) after live-flow slices
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-10-06T03-05-28Z
slug: src-routes-app-ruang-pimpinan-rapat
---
# Critique — Rapat Direksi (Notulen, Layar) — 2026-10-06 (after the live-flow slices #142–#144)

Method: dual-agent (A: design review · B: detector + live overlay). Live revision ent-os-00113-fn5 (e832b27a9).

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Saved time, ● Di layar, timer, gap counts; the Layar "Isi dulu" hint is clipped off-screen |
| 2 | Match System / Real World | 3 | CONTEXT vocabulary followed; Agenda select still English ("1. Strategic Update"), "Kesimpulan / arahan", "Catatan panjang" |
| 3 | User Control and Freedom | 3 | Urungkan on every Layar decision, Reset undo, reopen with reason; Tutup tetap is the default |
| 4 | Consistency and Standards | 2 | Three names per agenda (nav / Layar / select); "Butir" lands as "isu"; Rail counts Ditunda as decided AND as needing a decision |
| 5 | Error Prevention | 2 | Keputusan gaps enforced; but Tutup tetap is primary + autofocused when gaps exist; Reset next to Tutup rapat |
| 6 | Recognition Rather Than Recall | 3 | Strip says where items go; "dari Agenda 02" on cards |
| 7 | Flexibility and Efficiency | 3 | Enter-to-capture, Layar keys, Ikuti layar; no key to focus Catat cepat |
| 8 | Aesthetic and Minimalist Design | 2 | 703 px of a 778 px laptop viewport before the first card |
| 9 | Error Recovery | 3 | Refused-save alert with a recovery action; unreadable data kept |
| 10 | Help and Documentation | 3 | Panduan written for this screen; still says "Kesimpulan / arahan" |
| **Total** | | **27/40** | **Acceptable** |

## Design Specificity Verdict

**LLM assessment:** authored for this product. One meeting on two screens joined by ● Di layar / Ikuti layar; Keputusan cannot exist without its Rumusan (+ Syarat / date), enforced in `keputusan.ts`, not just copy; decisions typed in place on the projector, never in a modal; kolom inti in working order; Tutup rapat states the gaps; Buka kembali leaves a reason in the Risalah. Generic only in the Notulen card-stack chrome.

**Deterministic scan:** CLI `detect.mjs` exit 0, 0 findings over `src/lib/notulen` and the route (.tsx/.ts/.svelte/.css), sanity-checked against a seeded file. Live overlay: 38 findings over 3 views; ~9 real in this feature: `.nt-focus` ~92 chars/line (`notulen.css:226`, 72ch under-measures), kicker above h2 (deliberate), Layar `.lr-top` 6px brand top border (full-width brand bar, not a card side-tab), all-caps `.lr-eyebrow` / `.lr-k` labels (`layar.css:91-110`), cramped vendored `@jup/ui` Tag sm. False positives: nested-cards (app-shell `<main>` frame and the 16:9 stage), tight-leading at exactly 1.30, text-occlusion on the detector's own labels. Space Grotesk "overused-font" is the JUP brand font. App-shell findings (10px tagline, sidebar `transition: width`) are outside this feature.

## Overall Impression

The live-flow slices moved the tool from "a form that projects" to a meeting instrument: capture by meaning, decisions with words, a close that checks. The single biggest opportunity is the decision moment itself on the Layar, which now overflows its frame.

## What's Working

- **A Keputusan cannot exist without its words.** `decide()` refuses while gaps remain; Layar and Notulen share the rule. Exactly what a Risalah needs.
- **No modals over the projector.** Tolak, the decision form, Tutup and Buka kembali all ask in place.
- **Catat cepat routes by meaning.** One line + Enter; Usulan to 07 tagged with its agenda, Tindakan to 08 with PIC and tenggat.

## Priority Issues

- **[P0] Layar decision form overflows the clipped `.lr-main`.** D-03 bersyarat: "Catat keputusan" 37 px and the "Isi dulu" hint 77 px below the clip (Tunda: 12 / 75 px); autoResize textareas push it further while typing. The Rumusan textarea is 14 px on the 1920 stage vs 22 px lead text. Why: the commit button is half hidden and the reason it is disabled invisible at the highest-stakes moment. Fix: while asking, collapse Rekomendasi / Kewenangan / PIC (or scroll the detail with actions pinned); hint beside the button; textareas at `.lr-lead` size (22–24 px). Command: $impeccable layout
- **[P1] Closing with gaps defaults to the destructive path.** `Footer.tsx:96` autofocuses primary "Tutup tetap"; the Notulen dialog also makes it primary. Fix: when gaps exist, "Kembali ke 07" is primary + focused, "Tutup tetap" outline/danger. Command: $impeccable harden
- **[P1] Three agenda names and Avoid-list terms.** Agenda select shows the stored English options (`schema.ts:769`); "Kesimpulan / arahan" and "Catatan panjang" are CONTEXT Avoid terms; the strip's "Butir" becomes "isu"/"risiko" on the card. Fix: display-map stored Agenda options to `AGENDAS[].nav` (keys unchanged); label "Kesimpulan / arahan" as "Arahan"; rename "Catatan panjang"; strip label per `ITEM_NOUN`. Command: $impeccable clarify
- **[P2] Notulen chrome eats the laptop viewport.** Header 237 px, storage note on every agenda, first card at y=703 of 778. Fix: storage note into the saved badge tooltip, compact sticky header, Reset into an overflow away from Tutup rapat. Command: $impeccable distill
- **[P2] Ikuti layar is on but not obeyed on load.** A remembered view (Panduan) wins over the Layar's agenda. Fix: with follow on and the meeting open, open on `currentAgenda`. Command: $impeccable polish

## Persona Red Flags

- **Corsec typing live:** first card below the fold; date kolom carries time-zone controls mid-meeting; no key to focus Catat cepat; deciding on the Layar shows the Board the cursor hunting; bare 0–8 keys move the projected agenda if focus leaves a field.
- **Direktur across the room:** Rumusan typed at 14 px stage — the words they are meant to watch are the smallest in the card; windowed Layar footer below a 778 px viewport (full screen is mandatory; the hint says so).
- **First-time board member:** "Selesai dibahas →" turns into "Lanjut →" unexplained; one click on an 08 card writes a status in front of everyone.
- **Keyboard / screen reader:** focus moves to the new view's h2 (good); Notulen Tutup dialog opened with no focused element; agenda overrun silent (timer `aria-live="off"`); Usulan list uses `aria-current` inside `role=group`.

## Minor Observations

- Demo data violates its own rule: 3 decided Usulan without a Rumusan, so the demo's Tutup check opens with a scolding.
- Rail counts Ditunda as "Keputusan" decided and under "Perlu keputusan".
- `.nt-focus` runs ~92 characters per line.
- All-caps `.lr-k` labels on long labels ("Kewenangan / persetujuan lanjutan").
- 11 px Space Mono for eyebrows, counts and "● Di layar".

## Questions to Consider

- Should the Layar show controls at all, or only mirror the Rumusan as the Corsec types it in Notulen?
- Should closing with undecided Usulan need the Direktur Utama's explicit "ya" on screen?
- If Catatan pembahasan stays out of the Risalah by default, why does it sit above the Butir that go into it?
