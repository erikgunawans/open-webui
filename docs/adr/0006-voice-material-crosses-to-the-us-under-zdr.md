# Voice material crosses to the United States under ZDR, bounded by a named document set

Voice sessions send audio and text to OpenAI, which offers regional *processing* only in the United
States, Europe and the UAE — Singapore is storage-only and Indonesia is not offered. JUP material
spoken to this system is therefore processed in the US. We accept that with zero data retention
enabled (`/v1/live/sessions` is ZDR-eligible) and bound it **by construction**: a voice session may
retrieve only from an explicitly named set of Strategy KB documents, and anything outside that set
is unreachable, not merely deprioritised.

Classifying documents by sensitivity at ingest was rejected because it fails open on anything not
yet labelled — and every new document is unlabelled until someone acts.

**Scope:** the Strategy KB and gate status. Unreleased commercial terms and partner positions are
outside the voice scope.

## Named non-coverage

This records where voice material is processed and what it may reach. It does **not** claim
OpenAI's infrastructure is audited to any standard. It does **not** cover the typed chat path, which
may use different providers under different terms. And the boundary rests on the contents of one
named document set: once a document is added to that set it is in scope for US processing from that
moment, with no further review.

## Status

This ADR records the engineering constraint only. The corresponding **JUP governance decision**
belongs in `~/jup/DECISIONS.md`, in the class of D13 and D15, and is not made here.
