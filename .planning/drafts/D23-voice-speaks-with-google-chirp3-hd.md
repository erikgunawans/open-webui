# DRAFT — D23 (for `~/jup/DECISIONS.md`, after Erik signs)

> Status of this draft: **SIGNED by Erik 2026-09-28 (D23/D24 in ~/jup 3d09c24).** Nothing below is in force until it is committed
> to `~/jup/DECISIONS.md`. Chosen by ear 2026-09-28 from an 8-voice comparison (`google-chirp3hd-Kore`).

| # | Decision | Status | Why | Date |
|---|----------|--------|-----|------|
| **D23** | **The voice call speaks with Google Cloud Text-to-Speech (Chirp3-HD, `id-ID-Chirp3-HD-Kore`), not OpenAI. Google receives the governed answer text; OpenAI keeps transcribing speech.** | DRAFT — amends D22 step (3) | OpenAI's `gpt-4o-mini-tts` sounded robotic on real answers, and Erik chose Kore by ear over OpenAI (`nova`, `marin`, `coral`) and ElevenLabs. **What changes:** step (3) of D22 moves from OpenAI to Google: the stored, sealed answer (tool and reasoning blocks removed) is sent to Google Cloud Text-to-Speech, and the audio comes back. Nothing else in D22 moves: the answer is still the governed pipeline's, read by message id, never free text, and OpenAI still receives the user's speech for transcription (D16, D21). **Why Google is the narrower choice:** JUP's app already runs on Google Cloud (`jup-ops`), so this adds no new company to the path. The service calls Text-to-Speech with its own service identity, so there is no API key to store or leak. **Named non-coverage:** (a) no Indonesian data-residency claim: Text-to-Speech is called on Google's global endpoint, and where Google processes the request is Google's choice; (b) no claim that Google does not log requests beyond its Cloud terms; (c) the answer text leaves JUP's project boundary for Google's speech service, a second processor alongside OpenAI; (d) like D16(e), this bounds what the system says, not what a person says into the microphone. **Scope:** unchanged from D22: the eight named documents and gate status. **Decommission:** switch the speech engine back to OpenAI (D22) or off, disable the Text-to-Speech API on `jup-ops`. **Cross-reference:** ADR-0017 (amendment), ent-os issue to be opened. | 2026-09-28 |

## What building it takes (after sign-off, each step its own OK)

1. Enable the Cloud Text-to-Speech API on `jup-ops` (infra change).
2. A server adapter: the vendor has no Google engine, so the sealed-answer speech path
   (`jup_voice.speech_body` → `routers/audio.py:speech`) gains a Google branch. Tests, presence test,
   `VENDOR-PATCHES.md` entry. Same boundary rules: message id only, sealed answers only, `voice_tts` audit.
3. Deploy.
4. Audio config: speech engine → the Google branch, voice `id-ID-Chirp3-HD-Kore` (DB write).
5. A live call to hear it.
