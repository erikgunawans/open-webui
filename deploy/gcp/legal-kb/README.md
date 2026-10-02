# Contract KB pilot scripts

Operator scripts for the contract knowledge base (proposal "Usulan Basis Pengetahuan Kontrak &
Perkara JUP", decisions in memory `legal-kb-data-location-rule`). They run from a laptop with
`gcloud` signed in to `jup-ops`; nothing here is part of the app image.

Data location: storage in Jakarta (`gs://jup-ops-legal-kb`, asia-southeast2, private), OCR and card
drafting in Singapore (`asia-southeast1`). PDFs and OCR text are streamed through memory and never
written to local disk or to this repo.

| Step | Script | Writes |
|---|---|---|
| 1. Fetch PDFs from OneDrive (Graph, item grant on `SCAN PERJANJIAN`) | `bun fetch.ts <run> <picks.json>` | `<run>/src/NN.pdf`, `<run>/manifest.json` |
| 2. OCR, synchronous, ≤15-page chunks (processor `legal-kb-ocr`, v2.1.1) | `bun ocr.ts [NN ...]` | `<run>/ocr-text/NN.json` (text + confidence per page) |
| 3. Draft cards with `gemini-2.5-flash` (FAQ Kontrak topics, page cited per field) | `bun draft-cards.ts [NN ...]` | `<run>/cards/NN.json` |
| 4. Side-by-side review page (card + OCR pages) | `bun preview.ts` | `<run>/preview/kartu-kontrak-pilot.html` |

**Full run** (all of SCAN PERJANJIAN): `bun inventory.ts full` walks the tree into `full/inventory.json`, then
`bun run.ts full [--concurrency 10] [--limit N] [NNNN ...]` takes every PDF through fetch → OCR → card with a
worker pool. It is resumable: any stage whose output already exists is skipped, so re-running after a crash or a
Mac restart only redoes the documents in flight. Failures land in `full/errors/NNNN.json` and are retried on the next
run; scans with under 200 OCR characters get a card with `skipped: "no-ocr-text"` instead of a guessed one. Logs
carry numbers only. `bun summary.ts full` totals the cards into `full/summary.json`. `bun dates.ts full` adds structured start/end/auto-renewal dates per card (`full/dates/NN.json`, same model and region as drafting), which the app's contract import (`POST /api/v1/contracts/import`) reads with the cards. Prompt, schema and model live in `lib.ts`, Graph access in `graph.ts`, shared by both paths.

`ocr.ts`, `draft-cards.ts` and `preview.ts` read the `pilot` run (`BUCKET` constant at the
top). Install once with `bun install` in this directory.

Why synchronous OCR: the Document AI batch queue sat RUNNING for 1.5 h with no output on 2026-10-01;
synchronous calls did the 10 pilot PDFs (161 pages) in ~2.5 min. Polling an operation needs the
`x-goog-user-project: jup-ops` header.

Pilot (2026-10-01/02): 10 contracts picked from the inventory, approved unchanged by Rully (Business
Legal). Card 01 once listed a notary and witnesses as "perorangan" parties; the instruction now excludes
notaries, witnesses and officials acting for an entity (re-drafted 2026-10-02, v1 kept in `cards-v1/`).

Full run (2026-10-02): 1,035 PDFs, 1,033 cards, 11,553 pages, 0 scans without text. The two misses are one
file stored in two folders that is truncated in OneDrive itself (no trailer, catalog or page tree); its error
records say so and it needs a re-scan or re-upload. 43 cards list "perorangan" parties and are the first to
spot-check before masking.
