---
target: Rapat Direksi
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-10-05T16-42-32Z
slug: src-routes-app-ruang-pimpinan-rapat
---
# Rapat Direksi critique — 2026-10-05

Score 22/40 (Acceptable). H1 2, H2 2, H3 2, H4 3, H5 2, H6 3, H7 2, H8 2, H9 1, H10 3.
Specificity: Layar specific (quorum, WIB clock, Rahasia, timeline by minutes); Notulen reads as a Notion-database port; list generic.
Detector: 0 findings on 11 markup files + notulen.css (planted-sample check confirmed it scans .tsx/.svelte). Browser overlay not run (Interceptor: no extensions connected).
Cognitive load: 4/8 fail (single focus, chunking, >4 options, working memory).

## Priority issues
1. [P1] Autosave fails silently — repo.ts:81-86 swallows quota/blocked errors while UI says "tersimpan otomatis". harden.
2. [P1] Notulen ignores session.currentAgenda — secretary must track the projector by hand; no quick decision capture. shape.
3. [P1] Notion leftovers — showTypes on (NotulenApp.tsx:107), origin labels, "n/m terisi", "properti · record", Notion footer (schema.ts:977), 2 Informasi records seeded. clarify, distill.
4. [P2] Layar fullscreen: toasts portal to body, invisible in fullscreen (mount.tsx); ←/→ hijack role=listbox decisions (V07Keputusan.tsx:48); .lr-bar class collision; no reduced-motion. harden.
5. [P2] No closing state on last agenda (Footer.tsx:35 "Lanjut" to nowhere); Cetak prints a form dump, not a Risalah with signature block. typeset, delight.

## Persona red flags
Alex: no Notulen shortcuts; list unsorted; no delete/duplicate; no carry-forward of prior actions; untitled meetings indistinguishable.
Sam: listbox/arrow conflict; view switch doesn't move focus; done-agenda icon replaces its number label; 11px hint; scaled stage text ~7px in panel.
Corporate Secretary: two windows, same-browser sync only; public one-click "Tolak"; action tiles cycle forward with no undo; no save proof.

## Minor
Quorum counts all Peserta but says "Direksi hadir"; Reset same weight as Cetak; Notulen same-tab vs Layar new-tab; theme toggle among badges on projector; 13px rail labels on projected stage; "Data dummy" badge only on Layar; English agenda names mixed in.
