# Voice is a chained pipeline that speaks our exact answer

**Status: Accepted 2026-09-27, Erik Gunawan Supriatna, Director, Operation & Business
Development.** Settled in the V1 grilling session (Track V in `.planning/agent-depth-plan.md`).
Supersedes ADR-0005. ADR-0006 (the named document set) stands unchanged.

## Why ADR-0005 no longer holds

ADR-0005 chose OpenAI GPT-Live (`gpt-live-1`) in client delegation mode, reasoning that our backend
sees the whole answer before a word is spoken. Reading OpenAI's docs before building (2026-09-27)
showed two things that break that reasoning:

| ADR-0005 assumed | What the docs say |
|---|---|
| Live speaks the answer we return | The answer goes in as `session.commentary.append`, which GPT-Live is "trained to paraphrase". There is no verbatim mode. Figures and caveats can drift between what the pipeline approved and what is heard. |
| Every substantive turn is handed to us | GPT-Live is a full model that decides for itself when to delegate. `session.delegation.created` carries no task text, so the question must be rebuilt from transcript fragments with no end-of-turn event. A turn it answers itself is ungoverned. |

"We see the answer before it is spoken" is only worth something if what is spoken is that answer.

## Decision

Voice is three steps, each on our server:

1. **Transcription:** OpenAI `gpt-4o-transcribe`, language auto-detected so English and Indonesian
   can be mixed.
2. **The governed turn:** the transcript is a normal user message in a chat marked `voice`, run
   through the same pipeline as typed chat (ADR-0002): contract, audit, tool gate.
3. **Speech:** OpenAI `gpt-4o-mini-tts` reads the assistant message we stored, by message id,
   never free text from the browser.

The boundary is enforced on the server:

- A start-call route checks the voice flag, the user's grant and that the voice disclosure was
  acknowledged. Only it creates voice chats. The grant is a `jup.voice.call` group permission, not
  the vendor's `chat.call`, which defaults to on for everyone and was only ever a UI switch; the
  vendor call mode is closed by refusing OpenAI speech without the grant and hiding the button.
  The acknowledgement and the voice-chat mark are signed with a key derived from the server
  secret, because the places they live (`user.info`, `chat.meta`) are client-writable.
- Every turn in a voice chat runs on the model "Asisten JUP — Suara", whatever the browser asks
  for. Its knowledge is the named document set (ADR-0006), listed file by file, and its only tools
  are scoped KB retrieval and `portfolio_status`. `view_knowledge_file`, which lets an admin open
  any file by id, is not offered there or is limited to the model's list.
- OpenAI speech-to-text is refused to anyone without the voice grant. Outside voice chats,
  read-aloud uses the browser's own voice, so a typed answer drawn from the whole KB never reaches
  OpenAI.
- Audit lines `voice_ack`, `voice_call` (started or refused), `voice_stt` and `voice_tts` record
  sizes and outcomes, never content.

## Consequences

- The conversation takes turns rather than being full-duplex, and each turn costs transcription +
  pipeline + speech: a few seconds. We measure it live and accept it; sentence-by-sentence speech
  is the first lever if it is too slow.
- There is no ungoverned speaker. Everything heard was produced by the governed pipeline, word for
  word.
- The OpenAI key lives in Secret Manager as `openai-live-key`. The name dates from ADR-0005 and is
  kept because secrets cannot be renamed; it is used only for transcription and speech.
- D16 (US processing) and D21 (no ZDR gate, up to 30 days' retention) apply unchanged. The
  exposure is narrower than GPT-Live's: OpenAI receives the user's speech and our governed answer,
  not a model session that could reason over either.
- GPT-Live can be reconsidered if OpenAI adds a verbatim mode and forced delegation.

## Named non-coverage

This does not stop a person from saying something out of scope into the microphone. The
transcription carries it to OpenAI regardless (D16(e)); the disclosure says so. It does not claim
OpenAI's transcription or speech endpoints are ZDR-eligible for this organisation.

## Amendment 2026-09-28: transcription language

The first live call showed auto-detection failing on short utterances: a 2-3 second phrase came back
as Japanese, and the answer followed the language it was given. Transcription now requests Bahasa
Indonesia (`WHISPER_LANGUAGE=id` in `deploy/gcp/deploy.sh`, Erik's call). English terms inside
Indonesian speech still transcribe; a whole question spoken in English is the case this trades away.

## Amendments 2026-09-28: the speaking voice and a second mode

- **D23:** speech moves from OpenAI `gpt-4o-mini-tts` to Google Cloud Text-to-Speech
  (`id-ID-Chirp3-HD-Kore`), chosen by ear. Same boundary: only the saved, sealed answer is read, by
  message id. Not yet built.
- **ADR-0018 / D24:** GPT-Live is added as an opt-in second call mode. This ADR stays the default
  call, and "every word heard is the governed answer" holds in it alone.
