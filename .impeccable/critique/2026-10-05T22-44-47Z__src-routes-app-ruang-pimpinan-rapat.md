---
target: Rapat Direksi (list, Notulen, Layar)
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-10-05T22-44-47Z
slug: src-routes-app-ruang-pimpinan-rapat
---
# Critique — Rapat Direksi (list, Notulen, Layar) — 2026-10-06

Method: dual-agent (A: design review · B: detector + live overlay). Live revision ent-os-00111-vkx (4d663c7b4).

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Agenda timer shows red "71:48 / 20:00" on arrival: agendaEnteredAt persists across sessions |
| 2 | Match System / Real World | 2 | English agenda titles in Indonesian UI; "peramban"; Notulen fields alphabetical; guide speaks Notion |
| 3 | User Control and Freedom | 3 | Urungkan on live writes, Reset undo, Buka kembali, Esc cancels Tolak |
| 4 | Consistency and Standards | 2 | "Sebelumnya" = nav AND origin badge; two filled buttons per list row; mono for body copy |
| 5 | Error Prevention | 3 | Tutup rapat closes with D-03/D-04 undecided, no checkpoint; one click on projected A08 card writes |
| 6 | Recognition Rather Than Recall | 3 | Rail + sidebar counts keep state visible |
| 7 | Flexibility and Efficiency | 2 | Layar has keys; Notulen has no agenda jump, quick capture or search |
| 8 | Aesthetic and Minimalist Design | 3 | Layar calm; Notulen risk card 2,207 px with 11/16 inputs empty |
| 9 | Error Recovery | 3 | Quarantine + download, refused-write alert with Simpan HTML |
| 10 | Help and Documentation | 2 | Panduan & checklist is the Notion guide verbatim |
| **Total** | | **26/40** | **Acceptable — up from 22** |

## Design Specificity Verdict

LLM: Layar is authored for a JUP board meeting (eyebrow, No. 10/RD-JUP/X/2026, Rahasia, kuorum, D-/A- ids, minute-sized timeline, V07 decisions, V09 closing). Notulen is still a ported Notion template in JUP clothing: schema.ts order and GUIDE_HTML drive its IA. The list is competent and generic.

Detector: CLI clean (0 findings over the route + src/lib/notulen/react incl. layar.css, notulen.css; inline style objects are a blind spot). Live overlay ran on all three pages: real — 35–55-char all-caps .lr-eyebrow (layar.css:105), record cards nested in a card (Notulen, list .nt-tablecard), "Agenda 05" kicker repeating the h2 number, .nt-foot ~150 chars/line (notulen.css:504), .nt-focus ~88 chars/line despite 72ch. Shell-wide (not Rapat): 10px .nj-tagline, width transition on sidebar. False positives: lr-top 6px top band (not a side stripe), .lr-rail__t leading at threshold, .lr-viewport nesting (deliberate stage frame), Space Grotesk (brand).

## What's Working
1. Layar composition: fixed 1920×1080 stage, agenda | content | rail, minute-weighted timeline; meeting state legible at a glance.
2. Recovery engineering: undo on every live write, quarantine of unreadable data, refused-write alerts outrank status, draft watermark on the Risalah.
3. Domain fidelity: kewenangan tags (Direksi / Dewan Komisaris / Pemegang Saham), asal tindak lanjut, quorum.

## Priority Issues

- **[P1] Projected type too small where it matters.** Status badges 12 px, dominant data 15–16 px, labels 15 px mono on the 1920 stage; ×0.50 in the RP panel → 6–8 px. Why: the room cannot read decisions, evaluations, presenters. Fix: projection floor 24 px data / 20 px meta / 32 px+ status as filled chips; warn or prefer full screen below 0.75 scale. Command: $impeccable typeset
- **[P1] Notulen field order is alphabetical (Notion export artifact).** schema.ts A→Z, RecordCard.groupsFor keeps it; "Uraian dampak" last. Why: minute-taker hunts for boxes live. Fix: per-agenda working-order groups like INFO_GROUPS; empty optional fields behind "Tampilkan semua kolom". Command: $impeccable layout
- **[P1] The guide teaches Notion.** "Duplikasikan halaman ini", "Gunakan New", "Person — workspace", "Include time"; Fokus lines say "baris". Fix: rewrite for this UI; drop "Panduan asli — ditampilkan lengkap". Command: $impeccable clarify
- **[P2] Tutup rapat has no checkpoint.** Fix: inline summary "2 usulan belum diputuskan · 1 tindakan tanpa PIC — Tutup tetap / Kembali ke 07", same pattern as Tolak. Command: $impeccable harden
- **[P2] Stale agenda timer.** agendaEnteredAt survives sessions → red overrun before anyone speaks. Fix: reset on a new session / first navigation after a gap, or show "—" until entered live. Command: $impeccable harden

## Persona Red Flags
- **Direktur across the room:** cannot read 12 px decision status, evaluation chips, 15 px presenters; red 71:48 reads as "late"; English titles; Rahasia is a tiny outline badge.
- **Corporate Secretary typing live:** alphabetical fields, 2,000+ px cards, 13 px labels / 14 px inputs, no place for the "bersyarat" condition on the Layar, header not sticky so the saved badge scrolls away, Reset next to primary actions.
- **First-time board member:** "Tersimpan di peramban ini" / "Simpan HTML terisi" is developer language; guide refers to Notion buttons; "Sebelumnya" badge reads as navigation; "Tampilan pendukung" says nothing.

## Minor Observations
- List date repeats ("5 Okt 2026 09:00 – 5 Okt 2026 12:00") and uses ":" where the Layar uses ".".
- Real meeting row subtitle shows raw id rd-2026-10-05-0702.
- Theme toggle sits in the meeting meta line beside Rahasia.
- Pencapaian bars amber at 74%/62% with no threshold legend.
- Sasaran strategis header row tall and grey with 15 px mono labels.
- All-caps eyebrows of 35–55 characters (detector).
- Nested cards in Notulen and list (detector).

## Questions to Consider
1. The Layar is the board's shared truth, yet the record lives in one browser — what happens to the Risalah if that laptop dies mid-meeting?
2. Should "Disetujui bersyarat" be impossible without a written condition?
3. Is the Notulen a form to fill or a transcript to capture? A running stream per agenda, structured afterwards, may fit live minuting better.
4. Who closes the meeting — and should the Layar ask the room on screen first?
