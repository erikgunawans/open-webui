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

## Open
- Drafting model: Vertex AI (`aiplatform.googleapis.com`) is NOT enabled on jup-ops; enabling it is its own OK.
  Third-hand: Gemini 2.5 Flash has in-region ML processing in `asia-southeast1`, not Jakarta — confirm with a
  live Vertex call after enablement. "In region" therefore means Singapore, same as OCR.
- OCR and drafting in Singapore are both transfers under UU 27/2022 Pasal 56; Legal to confirm the
  equal-protection basis (Singapore PDPA).
