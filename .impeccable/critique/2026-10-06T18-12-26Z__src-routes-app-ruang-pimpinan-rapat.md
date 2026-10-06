---
target: Rapat Direksi (Notulen + Layar) after critique-3 fixes (00114)
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
timestamp: 2026-10-06T18-12-26Z
slug: src-routes-app-ruang-pimpinan-rapat
---
# Critique — Rapat Direksi (Notulen, Layar) — 2026-10-07 (after critique-3 fixes, live 00114)

Method: dual-agent (A: design review · B: detector + live overlay), live on non-jupe.jup.co.id.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Tersimpan, "● Di layar", timer good; "● Di layar" is 11px; a status without Rumusan shows no warning on the card |
| 2 | Match System / Real World | 3 | Governance vocabulary strong; leftovers "Review keputusan", "Follow-up Board", "Tindakan / deliverable", "Risk owner / PIC", "Draft / Dalam review" |
| 3 | User Control and Freedom | 3 | Urungkan, Reset undo, Batalkan pilihan; changing Status keputusan in Notulen has no undo |
| 4 | Consistency and Standards | 2 | Deciding differs per surface (6-option select vs in-place form); "— Pilih —" / "Belum diputuskan" / "Belum diisi" all mean undecided; close-check button order differs Notulen vs Layar |
| 5 | Error Prevention | 3 | Decision gate + safe Tutup default excellent; Rumusan can be cleared after a decision and the status stays |
| 6 | Recognition Rather Than Recall | 3 | Kolom inti + Panduan; Layar keys (←/→, 0–8, F) shown nowhere |
| 7 | Flexibility and Efficiency | 2 | Catat cepat + Enter; no Notulen shortcuts, Notulen cannot drive the Layar |
| 8 | Aesthetic and Minimalist Design | 2 | First open card 1032px tall; chrome takes 221px top / 297px left; Notulen column 2163px in a 720px window |
| 9 | Error Recovery | 3 | Save-failure alert with download, quarantine of unreadable data |
| 10 | Help and Documentation | 3 | Panduan written for this screen in CONTEXT words |
| **Total** | | **27/40** | **Acceptable (top of band)** |

## Design Specificity Verdict

**LLM assessment:** mostly authored. Usulan → Keputusan with Rumusan/Syarat/tanggal, Tutup rapat with a reopen reason in the Risalah, Catat cepat routing Usulan to 07 and Tindakan to 08, the 16:9 Layar with agenda timeline and rail — none of this is category-generic. The Notulen card is the generic part: a field form with Notion-era controls (Target waktu "Mulai / Selesai (opsional) / Sertakan waktu · Asia/Jakarta").

**Deterministic scan:** `detect.mjs` on `src/lib/notulen/react` and the rapat route: 0 findings (also with `--no-config`). Live overlay: Notulen 13, Layar 29 — almost all app shell (vendor sidebar occlusion ×20, layout-transition, brand font "overused") or deliberate projector sizing (`.lr-eyebrow` caps, 6px brand top border). Island true positives: `nested-cards` ×6 on `.nt-check` (`PropField.tsx:32`, `notulen.css:434`); first-viewport overflow of `.nt-shell` (2163px / 720px); ~93-char line on `p.nt-hint`. Probes: 0 contrast failures (84 Notulen, 142 Layar text nodes), 0 unnamed buttons, 12 Notulen nodes at 11px (`nt-side__n` ×10, `nt-side__live`, `nt-eyebrow`), 0 Layar nodes under 15px. Outside full screen `.lr-viewport` runs 201px below a 720px window.

## Overall Impression

The rules are now right; the surfaces are not yet calm. Domain logic (`keputusan.ts`) is the strongest part of the product. The biggest opportunity is the Notulen in live use: it opens heavy, starts low, and the Corsec's live controls (advance, decide, close) sit on the projected window.

## What's Working

- Domain rules in code: a Keputusan is not recorded until its Rumusan / Syarat / tanggal exist, on both surfaces.
- Catat cepat routes each capture where it belongs, confirms, and keeps focus in the input.
- Honest failure states: refused-write alert with download, quarantine of unreadable data, Tersimpan tooltip naming where data lives.

## Priority Issues

- **[P1] A status can exist without its Rumusan, silently.** Clearing Rumusan in Notulen (or a meeting stored before the rule) leaves Disetujui with no Rumusan; the card shows nothing and the rail counts it decided. Fix: render `decisionGaps(r)` inline on the 07 card ("Rumusan belum diisi") and exclude such Usulan from the decided count (`selectors.ts` `isDecided`). Files: `RecordCard.tsx`, `selectors.ts`. → `$impeccable harden`
- **[P1] The Notulen in live use opens heavy and starts low.** At 1280×720 Catat cepat starts at y=581 and the first card at y=902; a card opens at 1032px. Fix: sticky capture strip, cards open on Kolom inti collapsed, Catatan pembahasan below the cards. Files: `AgendaView.tsx`, `notulen.css`. → `$impeccable layout`
- **[P2] One undecided state, three names; two decision UIs.** "— Pilih —", "Belum diputuskan", "Belum diisi"; Notulen select vs Layar form; button order differs between the close checks. Fix: one empty label, same option order and button order on both surfaces. → `$impeccable polish`
- **[P2] Small text in the Notulen sidebar.** 11px agenda numbers and "● Di layar" (12 nodes). Fix: 12–13px floor; announce "Di layar" without the bullet glyph. Files: `notulen.css`, `Nav.tsx`. → `$impeccable typeset`
- **[P3] Copy leftovers.** Tinjauan keputusan, Tindak lanjut Direksi, Keluaran, Pemilik risiko (display labels only; storage keys unchanged), Konsep / Ditinjau; drop "Kalender bukan acara kalender pribadi"; hide the empty "Belum diisi 0" group. Files: `DerivedViews.tsx`, `types.ts` labels. → `$impeccable clarify`

## Persona Red Flags

**Alex (power user):** no Notulen shortcuts (agenda jump, focus capture); Layar keys undiscoverable.

**Sam (screen reader / keyboard):** "● Di layar" at 11px read with a bullet glyph; Layar timeline `aria-hidden`, so progress is invisible; a 9-option Agenda select repeats on every 07/08 card.

**The Corsec under live pressure:** must switch to the projected window to advance, decide or close; opening an agenda by hand silently turns Ikuti layar off; a digit typed while the Layar has focus jumps the projector.

## Minor Observations

- Header date repeats the day: "5 Okt 2026 09:00 – 5 Okt 2026 12:00".
- Two h1s ("Ruang Pimpinan" + meeting name).
- "Contoh D-01." helper shows on filled ID fields.
- Vendor sidebar keeps 10 focusable links under the Layar (not inert).

## Contested (settled decisions — for Erik, not fixes)

- Assessment A proposed a 22–24px floor for Layar text; the 15px floor (`.lr-nav__t .lr-sub`) was measured live on all 9 agendas and settled.
- Assessment A proposed composing Keputusan in Notulen with the Layar as a read-only mirror; the 2026-10-06 grill put Syarat typing on the Layar so the room reads it.

## Questions to Consider

- Should the board ever see the Corsec's cursor? If not, the Layar needs a remote control from Notulen.
- Is "Belum diputuskan" a status or the absence of one?
- Does the Notulen need eight agenda forms during the meeting, or only capture plus 07/08, with the forms afterwards?
