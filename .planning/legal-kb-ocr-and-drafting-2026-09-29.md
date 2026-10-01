# Contract & lawsuit KB — OCR region and card drafting (2026-09-29)

## Decisions (Erik, 2026-09-29)
- Card drafting runs on an **in-region** model (not a model outside SEA), because raw OCR text carries
  individual names before masking.
- OK to enable Document AI on jup-ops.

## Done
- `documentai.googleapis.com` enabled on jup-ops (before: not in the 86 enabled services).
- Live `fetchProcessorTypes` for jup-ops:
  - `asia-southeast1`: `OCR_PROCESSOR` GA, `FORM_PARSER_PROCESSOR` GA, `CUSTOM_EXTRACTION_PROCESSOR` GA.
  - `asia-southeast2` (Jakarta): no Document AI endpoint (404).
- No processor created yet.

## Drafting model (live probe, 2026-09-29)
- Vertex AI (`aiplatform.googleapis.com`) enabled on jup-ops with Erik's OK (before: not enabled).
- One-word probe (no JUP data) to each regional endpoint:
  - `asia-southeast1`: **`gemini-2.5-flash` 200** (only one that answers); `gemini-3-pro-preview`, `gemini-3-flash-preview`,
    `gemini-2.5-pro`, `gemini-2.5-flash-lite`, `gemini-2.0-flash-001` 404 (not served there).
  - `asia-southeast2` (Jakarta): every model 400 "Precondition check failed" — no Gemini in Jakarta.
- So the in-region drafting model is **`gemini-2.5-flash` in `asia-southeast1`**, unless its card quality on the pilot
  is not good enough (then the choice goes back to Erik).

## Open
- ~~OCR and drafting in Singapore are both transfers under UU 27/2022 Pasal 56; Legal to confirm the
  equal-protection basis (Singapore PDPA).~~ Settled 2026-09-29: Erik OK'd the Pasal 56 basis.
- Card reviewers: the **Legal team** reviews the contract cards (Erik, 2026-09-29); the legal officer is
  **Rully** (Erik, 2026-10-01). Weekly capacity still to be named.
- OneDrive access: Erik says granted (2026-10-01), but `none-jupe-graph-secret` is not in jup-ops Secret
  Manager yet (checked 2026-10-01). Verify a read-only listing through the app before building.
