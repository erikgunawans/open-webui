# GPT-Live API check (#33, ADR-0018) — 2026-09-28

Source: OpenAI developer docs, read as Markdown on 2026-09-28: `guides/live`, `live-delegation`,
`live-conversations`, `live-prompting`, `voice-webrtc`, `voice-server-controls`, `your-data`,
`models/gpt-live-1`.

## What exists

- **Model `gpt-live-1`**, launched in the API on 2026-09-10. It is full duplex: it listens while it
  speaks. It costs US$0.05 a minute, billed per second, and backend model and tool use is billed
  separately. A WebRTC session bills 15 s at start-up, credited once the session runs. Rate limits
  count concurrent sessions (25 at Tier 1).
- **Endpoint `POST /v1/live/sessions`.** It is not `/v1/realtime`. Transport is WebRTC for a
  browser, WebSocket for a server, or SIP.

## Findings that change ADR-0018

1. **There is no verbatim mode.** `session.commentary.append` "is trained to paraphrase the
   text". A "say exactly" request through `session.instructions.append` is only a request. For
   exact wording, OpenAI's own advice is to "play a verified recording or rendered clip through
   your application and control GPT-Live playback while it plays". So ADR-0018's premise
   (paraphrase) holds.
2. **Delegation is the model's choice and cannot be forced every turn.** A prompt policy ("Delegate
   to the backend when…") is the only lever. So ADR-0018's `self_answered` flag is still needed.
3. **Client delegation fits the governed pipeline, but not as an `ask_jup` tool.**
   - In client mode, `session.delegation.created` carries only `delegation.id` and `offset_ms`, **no
     task text**. Our server must rebuild the question from `session.input_transcript.delta`
     fragments, then return the answer with `session.commentary.append` (at most 500 tokens,
     keyed by `delegation_id`).
   - A tool with a `question` argument exists only in Responses delegation. There, an
     OpenAI-hosted Responses model sits between GPT-Live and our tool: one more model, and more
     data at OpenAI.
   - → Recommend **client delegation**, with the question taken from the caller's transcript.
4. **The server mints the session and no key ever reaches the browser.**
   - Our server posts `{session, transport: {type: "webrtc", sdp}}` to `/v1/live/sessions` and
     returns the SDP answer. That is stronger than the ephemeral credential ADR-0018 assumed.
   - Config fixed at start: `model`, `instructions` (≤16,384 tokens), `input`, `audio.output.voice`,
     `delegation.type`, `store`.
5. **A server "sideband" WebSocket can watch the session.**
   - It can attach to the session and receive both transcripts and the delegation events, and it
     can send commands.
   - → The audit transcript can come from **our server**, not from the browser as ADR-0018 says.
     That is stronger, because the browser can't under-report.
   - Cost: a long-lived WebSocket from Cloud Run, which runs into the CPU-throttling concern (the
     request-based CPU billing).
6. **Checking speech before playback is possible, but heavy.** The app would buffer the output
   audio, run its own output VAD (OpenAI provides none), check each segment's transcript, and only
   then play it. That adds latency, and withheld speech stays in the model's context. It would let
   us refuse a spoken figure that is not in the governed answer.

## Language, voice, data

- **No Indonesian voice.** GPT-Live's extra voices are English and Portuguese, and the default is
  `marin`. Language is set by prompt ("write the prompt in the language you want spoken").
  Indonesian quality must be heard before launch. Custom voices exist, behind a separate approval.
- **Greeting:** `session.instructions.append` after `session.started`. The Betawi pantun would be
  a paraphrase risk; exact playback means playing our own clip.
- **Data:**
  - `store` defaults to `false`. Abuse-monitoring retention is 30 days, the recording is kept 30
    days only when `store: true`, and GPT-Live is ZDR-eligible.
  - Data residency is the US or the EU only. Delegated backends have their own controls.
  - → The ADR-0018 disclosure "(c) kept by OpenAI in the US for up to 30 days" is right unless the
    org has ZDR. Whether it does is to be confirmed.

## Proposed ADR-0018 amendment (needs Erik)

- Client delegation instead of an `ask_jup` tool. The question comes from the input transcript.
- The session is minted by the server over SDP, with `store: false`.
- The audit transcript comes from a server sideband, not the browser.
- Optional, later: exact-playback of the governed answer as our own clip, or a check before
  playback for figures.

## Proposed tickets (TDD; each deploy and DB write gets its own OK)

1. Grant `jup.voice.live`, plus the live disclosure and its acknowledgement (rules and endpoint).
2. `POST /api/v1/voice/live/sessions`: grant, ack and voice-chat checks, then the SDP exchange with
   the fixed config (`gpt-live-1`, client delegation, Indonesian instructions, `store:false`), and a
   `voice_live` audit line.
3. Sideband worker: collect the transcripts. On `delegation.created`, build the question and run
   the governed turn on Asisten JUP — Suara in the voice chat. Seal the answer, then
   `commentary.append`. Record each spoken turn against its sealed answer; a turn with none is
   flagged `self_answered`. Settle Cloud Run CPU for long sockets first.
4. Call UI: choose the mode per call (governed stays the default), the WebRTC client, and the
   GPT-Live disclosure.
5. Live acceptance with Erik: Indonesian quality, drift and self-answered rates, cost per minute.
