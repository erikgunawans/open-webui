# Knowledge Base document template

The shape a document should have before it enters a knowledge base Asisten JUP reads: the
**JUP Strategy KB** (Route A, from `~/jup`) or **JUP Staff Contributions** (Route B, `/kb-review`).
See [kb-update-process.md](kb-update-process.md) for how each route gets it into the app.

This file lives in `docs/`, not in `~/jup/kb/`, on purpose: the Strategy KB sync loads every
`kb/*.md`, so a template there would become something the assistant answers from.

Two tools produce it:

- **In the app:** the skill **Dokumen KB JUP** (`skills/jup/jup-kb-document.md`). A staff member
  attaches a file and asks for a KB version; the assistant drafts it in this shape for a human to
  check before submitting.
- **On Erik's Mac:** the Claude Code skill `KbDocument` (`~/.claude/skills/KbDocument/`), which
  first extracts any format to raw Markdown (`bun Tools/ToMarkdown.ts <file>`), then rewrites it into
  this shape.

## Why Markdown, and why this shape

The app accepts `md`, `txt`, `pdf`, `docx`, `pptx`, `xlsx` and `csv` (`backend/jup/kb_review.py`), but
it answers best from Markdown:

- **Retrieval cuts documents into chunks, at headings.** A section with one topic is one clean chunk
  that can be found on its own. A PDF is cut wherever the extractor lands, often through a table.
- **A label must sit next to its number.** A search can return one table without the page above
  it, so a certainty tier stated only at the top is lost. This is how the "5 mmscfd is not secured"
  and "revenue, not profit" rules survive in `kb/gas.md`.
- **Tables, lists and headings survive as written.** Slides and scanned PDFs lose their structure
  in extraction.
- **A reviewer can read it** in the `/kb-review` preview in a minute, which is what the approval rests on.

## The template

```markdown
# <Judul dokumen — satu topik per file>

> **Sumber:** <nama dokumen asli, nomor, tanggal terbit>
> **Pemilik:** <unit / nama jabatan> · **Tanggal isi:** <YYYY-MM-DD>
> **Klasifikasi:** INTERNAL | TERBATAS · **Status:** Final | Draf
> **Tingkat kepastian:** TIER 1 · FAKTA | TIER 2 · POTENSI | TIER 3 · ILUSTRATIF
> <Satu kalimat peringatan bila perlu, mis. "Angka rupiah adalah potensi pendapatan, bukan laba.">

## Ringkasan

<3–5 kalimat: apa isi dokumen ini dan pertanyaan apa yang bisa dijawabnya.>

## <Topik 1>

<Paragraf pendek. Satu gagasan per bagian. Sebut nama lengkap, bukan "proyek tersebut".>

## <Topik 2 — angka>

| Butir                       | Nilai        | Tingkat          | Dasar             |
| --------------------------- | ------------ | ---------------- | ----------------- |
| <mis. Investasi reaktivasi> | Rp 10 miliar | TIER 2 · POTENSI | <sumber, halaman> |

## Istilah

- **<Singkatan>**: <kepanjangan dan artinya>

## Yang tidak dicakup dokumen ini

- <Apa yang TIDAK boleh disimpulkan dari file ini, mis. "Belum ada persetujuan Direksi.">
```

Headings may be English for Strategy KB files, which are written in English (the records stay
English); staff documents are usually Indonesian. Keep one language per file.

## Rules

1. **One topic per file.** Split a long report into several files. A file that answers five
   different questions retrieves badly for all five.
2. **A tier next to every figure**, in the table row or the sentence, never only in the header.
   Never add, compare or rank figures from different tiers.
3. **Full names in every section.** "SPBG Kampung Rambutan", not "fasilitas tersebut": each chunk is
   read without the one before it.
4. **Keep "Yang tidak dicakup".** It stops the assistant reading more into a document than it says,
   the same job the non-coverage lines do on the Portfolio page. It names what the **source** leaves
   out or leaves open; it never imports a fact from elsewhere (another KB file, a decision, memory).
5. **Nothing invented.** A field the source does not give stays `<tidak tersedia di sumber>`; a
   conversion that guesses a date, an owner or a tier is worse than one that leaves a gap.
6. **Not for this route:** contracts, Daftar Perkara, and personal data of individuals. They follow
   the contract-KB rules (storage in Jakarta, masking before any model).
7. **Classification:** INTERNAL or TERBATAS. RAHASIA does not go into a shared knowledge base, and
   PUBLIK material does not need one.

## Tiers

| Tier                    | Use for                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------- |
| **TIER 1 · FAKTA**      | Verified, from a signed or official source (a gate assessment, an audited report, a decree).                  |
| **TIER 2 · POTENSI**    | A projection or potential (revenue potential, a plan's estimate). Gas rupiah figures are revenue, not margin. |
| **TIER 3 · ILUSTRATIF** | Illustration or market sizing; never a basis for a decision.                                                  |
