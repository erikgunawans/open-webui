---
id: jup-kb-document
name: Dokumen KB JUP
description: Turn an attached or pasted document (PDF, Word, PowerPoint, Excel, CSV, text) into the JUP knowledge-base Markdown format, ready for a human to check and submit at Tinjauan Pengetahuan. Use when asked to "jadikan KB", "ubah ke format basis pengetahuan", "siapkan untuk knowledge base", or to convert a file to Markdown for the KB.
tags: [jup, kb, markdown, bahasa-indonesia]
---

# Dokumen KB JUP

This skill rewrites a source document into the one Markdown shape the JUP knowledge bases use
(docs/kb-document-template.md in the repo). The output is a **draft**: a person checks it, saves it
as a `.md` file and submits it at **Tinjauan Pengetahuan** (`/kb-review`), where an admin approves
it. You never submit anything yourself.

## Before you start

Refuse, and say why, if the source is any of these. They do not go into a shared knowledge base
through this route:

- a contract or agreement (PKS, perjanjian, kontrak), or the Daftar Perkara;
- personal data about individuals (NIK, addresses, salaries, health, performance of named staff);
- anything marked RAHASIA.

If the attached file's text is empty or garbled (a scanned PDF, an image of a slide), say that the
text could not be read and ask for a text-based version. Never reconstruct content from the file name.

## Output format

Answer with the finished document in **one** fenced `markdown` code block, then a short list of
what the person must check. Use exactly this shape:

```markdown
# <Judul — satu topik per file>

> **Sumber:** <nama dokumen asli, nomor, tanggal terbit>
> **Pemilik:** <unit / jabatan>  ·  **Tanggal isi:** <YYYY-MM-DD>
> **Klasifikasi:** INTERNAL | TERBATAS  ·  **Status:** Final | Draf
> **Tingkat kepastian:** TIER 1 · FAKTA | TIER 2 · POTENSI | TIER 3 · ILUSTRATIF
> <Satu kalimat peringatan bila perlu.>

## Ringkasan

<3–5 kalimat: isi dokumen dan pertanyaan yang bisa dijawabnya.>

## <Topik>

<Paragraf pendek, satu gagasan per bagian.>

## <Angka>

| Butir | Nilai | Tingkat | Dasar |
|---|---|---|---|

## Istilah

- **<Singkatan>**: <kepanjangan dan artinya>

## Yang tidak dicakup dokumen ini

- <Apa yang tidak boleh disimpulkan dari dokumen ini.>
```

## Rules

1. **Nothing invented.** Every sentence must come from the source. A header field the source does
   not give is written `<tidak tersedia di sumber>`. Never guess a date, an owner, a number or a tier.
2. **One topic per file.** If the source covers several unrelated topics, produce one code block
   per topic, each a complete document with its own header, and say how you split it.
3. **A tier next to every figure**, in the table row or the same sentence, never only in the header:
   TIER 1 · FAKTA (verified, official or signed source), TIER 2 · POTENSI (projection, potential),
   TIER 3 · ILUSTRATIF (illustration, market sizing). When the source does not make the certainty
   clear, use TIER 3 · ILUSTRATIF and list it under "Periksa". Never add, compare or rank figures
   from different tiers. Every gas rupiah figure says "pendapatan, bukan margin".
4. **Full names in every section**: "SPBG Kampung Rambutan", not "fasilitas tersebut". Each section
   is retrieved without the one before it.
5. **Keep the source's facts, drop its packaging**: no cover pages, tables of contents, slide
   numbers, page headers and footers, or decorative text. Keep tables as Markdown tables.
6. **"Yang tidak dicakup" is required.** Name what the document does not establish, for example
   that a plan is not yet approved, that a figure is an estimate, or that a period is not covered.
   Describe only what the source itself leaves out or leaves open. Never bring in a fact from
   another document or from what you know about JUP.
7. **Classification:** carry the source's own marking. With none, write INTERNAL and list it under
   "Periksa". Never raise a document to PUBLIK.
8. Keep the source's language for its content; headings follow the template (Indonesian). Use
   Indonesian number formatting (Rp 63,3 miliar; 48,6%) and keep business terms in English
   (capex, NPV, offtake, stage-gate).

## After the code block

Write a short **Periksa sebelum mengirim** list: every field left as `<tidak tersedia di sumber>`,
every tier you had to choose, and anything in the source you left out and why. End with one line:
save the block as a `.md` file and submit it at Tinjauan Pengetahuan.
