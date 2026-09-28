# DRAFT — ADR-0018: GPT-Live is an opt-in second call mode, beside the governed call

> Status of this draft: **SIGNED by Erik 2026-09-28 (D23/D24 in ~/jup 3d09c24)**, together with D24 below. Until then ADR-0017
> stands unamended and nothing is built.

## Context

ADR-0017 replaced GPT-Live (ADR-0005) with a chained pipeline because GPT-Live **paraphrases** the
answer it is handed (no verbatim mode) and **decides for itself** when to hand a turn to our backend.
The chained call is governed word for word, but it sounded robotic and takes turns slowly. On
2026-09-28 Erik asked for GPT-Live **as one of the options**, after hearing the alternatives.

## Decision

The governed call (ADR-0017) stays the default. GPT-Live is added as a **second call mode the caller
chooses per call**, with its own grant, disclosure and audit:

1. **Its own grant, `jup.voice.live`**, exact boolean, denied by default, Erik only at launch.
   Holding `jup.voice.call` does not imply it.
2. **Its own disclosure, acknowledged separately**, saying plainly that in this mode (a) what is
   heard is the assistant's paraphrase of the governed answer and may differ in wording, figures or
   caveats; (b) the assistant may answer some turns itself, outside the documents and the audit; and
   (c) the whole live session is processed and may be kept by OpenAI in the US for up to 30 days.
3. **The session is minted by our server** (`POST /api/v1/voice/live/sessions`), never by the
   browser with a standing key: an ephemeral credential, our instructions, and exactly one tool,
   `ask_jup`, which runs the question through the governed pipeline in the caller's voice chat on
   "Asisten JUP — Suara" (same eight documents, same contract, same `voice_turn` scope).
4. **Instructions tell GPT-Live to call `ask_jup` for every substantive question and to repeat its
   answer faithfully, including every figure and caveat.** This is an instruction, not a guarantee.
5. **The audit compares what was approved with what was said.** Every `ask_jup` answer is stored and
   sealed as today. The browser posts GPT-Live's own transcript of what it spoke, and each spoken turn
   is recorded against the governed answer it was meant to relay. A spoken turn with no `ask_jup`
   call is flagged `self_answered`.

## Consequences

- The most natural voice available, real interruption, no pause between answer and speech.
- **"Every word heard is the governed answer" no longer holds in this mode.** It holds only in the
  default governed call. That is the trade Erik is making, and the disclosure says so to the caller.
- The browser connects straight to OpenAI for audio. Our server sees the `ask_jup` calls and the
  transcript the browser reports, not the audio stream.
- Before building: re-check OpenAI's current GPT-Live API (session creation, delegation or tool
  events, verbatim options). If a verbatim mode now exists, this ADR gets simpler and safer.

## Named non-coverage

Paraphrase drift, self-answered turns, and OpenAI's session retention are **accepted, not
prevented**. The transcript comparison detects drift after the fact; it does not stop it being heard.

---

# DRAFT — D24 (for `~/jup/DECISIONS.md`, with ADR-0018)

| # | Decision | Status | Why | Date |
|---|----------|--------|-----|------|
| **D24** | **GPT-Live may be offered as an opt-in second voice call mode, beside the governed call, knowing that what is heard in it may differ from the governed answer.** | DRAFT — amends D22 | Erik's call, 2026-09-28, after hearing the governed call's voice and the alternatives: naturalness matters enough to offer it as a choice. **Accepted knowingly:** in this mode (a) GPT-Live paraphrases the governed answer, so wording, figures and caveats can shift between what the pipeline approved and what is heard; (b) GPT-Live may answer some turns itself, outside the eight named documents, the contract and the audit; (c) OpenAI processes the whole live session in the US and may keep it for up to 30 days (D21). **Controls that remain:** its own grant (`jup.voice.live`, Erik only at launch), its own disclosure acknowledged separately, one tool into the governed pipeline, and an audit that records what was spoken against what was approved and flags self-answered turns. **Scope:** unchanged: the eight named documents and gate status. Unreleased commercial terms and partner positions stay outside. **Named non-coverage:** all of D16's, D21's and D22's, plus (a) no guarantee that anything heard in this mode matches the record; (b) drift is detected after the fact, never prevented. **Decommission:** remove the `jup.voice.live` grant and the mode switch; the governed call is unaffected. **Cross-reference:** ADR-0018 in `ent-os-new-jup`. | 2026-09-28 |
