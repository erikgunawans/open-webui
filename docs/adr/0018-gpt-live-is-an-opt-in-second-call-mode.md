# GPT-Live is an opt-in second call mode, beside the governed call

**Status: Accepted 2026-09-28 — Erik Gunawan Supriatna, Director, Operation & Business
Development.** The governance decision is D24 in `~/jup/DECISIONS.md`. Amends ADR-0017; nothing is
built yet.

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

## Amendment 2026-09-28 — after the API check

**Accepted 2026-09-28 — Erik Gunawan Supriatna.** The check is in
`.planning/gpt-live-api-check-2026-09-28.md` (#33). GPT-Live is `gpt-live-1` on `POST /v1/live/sessions`.
There is still no verbatim mode: `session.commentary.append` "is trained to paraphrase the text", so
the trade above stands. Three parts of the decision change:

- **Item 3, the session.** Our server mints it by posting the browser's SDP offer with the session
  config to `/v1/live/sessions` and returning the answer. No credential of any kind reaches the
  browser. The config is fixed at start: `gpt-live-1`, `delegation: {type: "client"}`, our
  instructions, and `store: false`.
- **Item 3, the tool.** There is no `ask_jup` tool. With client delegation, GPT-Live raises
  `session.delegation.created`, which carries an id but no question. Our server takes the question
  from the caller's input transcript, runs it through the governed pipeline in the voice chat on
  "Asisten JUP — Suara" (same eight documents, contract and `voice_turn` scope), seals the answer,
  and returns it with `session.commentary.append` under that delegation id. Responses delegation is
  not used: it would put another OpenAI-hosted model between GPT-Live and the pipeline.
- **Item 5, the audit transcript.** It comes from a server sideband WebSocket attached to the session,
  which receives both transcripts and every delegation event, not from the browser. So the browser
  cannot under-report what was said. Each spoken turn is recorded against the sealed answer it
  relayed, or flagged `self_answered`.

Still to prove before launch: Indonesian speech quality (GPT-Live has no Indonesian voice; language is
set by the prompt), whether the org has Zero Data Retention (without it, OpenAI keeps session data 30
days for abuse monitoring, as the disclosure says), and a long-lived sideband socket on Cloud Run.
Checking speech before playback, and playing the governed answer as our own clip, stay possible later
additions, not part of this decision.

## Amendment 2026-10-02 — voice reads every JUP knowledge base

Erik: both call modes must read all of the knowledge base. The voice scope is no longer the eight
named documents of 2026-09-27: `Asisten JUP — Suara` carries the JUP knowledge bases as whole
collections (JUP Strategy KB, JUP Staff Contributions) and the `jup_contracts` tool, which decides per
caller what of a contract they may hear. `jup.voice_turn` still holds every voice turn to that scope
in code: file ids must belong to a scope collection, a search may name only a scope collection, and
no other tool, folder, skill or feature reaches a voice turn. GPT-Live delegates to the same model,
and its instructions now describe the backend as every JUP knowledge base plus the contract cards.

Found while making the change: since the 10-02 latency fix attached the two collections to the voice
model, `voice_turn` treated the scope as misconfigured and offered no retrieval tool, so both modes
answered from `portfolio_status` alone until this amendment shipped.
