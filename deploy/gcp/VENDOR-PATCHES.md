# Patches against vendor code

ADR-0007 rebases onto upstream Open WebUI quarterly, and every patch here must survive that. Each
one is listed with what breaks if it is dropped, so a rebase can verify rather than guess.

Re-check this file after every rebase, alongside
`uv run --only-group dev pytest tests/test_boot.py` (the alembic two-heads check, ADR-0007).

## `Dockerfile` — `ENV NODE_OPTIONS="--max-old-space-size=8192"`

**What:** uncomments a line upstream already ships, commented, directly under a comment naming the
error it fixes. Raised from upstream's suggested 4096.

**Why:** `npm run build` (`pyodide:fetch && vite build`) dies with *"Ineffective mark-compacts near
heap limit — JavaScript heap out of memory"* on Cloud Build. This is node's own heap cap, not the
machine: it failed identically on an 8 GB `E2_HIGHCPU_8` and a 32 GB `E2_HIGHCPU_32`. Raising the
machine type is not a fix, and `E2_HIGHCPU_32` is quota-restricted in `asia-southeast2` on a new
project anyway.

**If dropped:** the image cannot be built at all — the failure is loud and immediate, at the
frontend build step. No silent degradation.

**Conflict risk:** low. One line, in a block upstream maintains for this purpose. If upstream
uncomments it themselves, take theirs and re-check the value is at least 8192.

## `Dockerfile` — `ARG BUILDPLATFORM=linux/amd64` above the frontend stage

**What:** declares `BUILDPLATFORM` with a default immediately before
`FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build`.

**Why:** `BUILDPLATFORM` is a BuildKit-*predefined* arg. Cloud Build's builder switched to the
legacy docker builder (it now prints *"the legacy builder is deprecated ... install the buildx
component"*), and the legacy builder does not define it — so `--platform=` expands to the empty
string and the build dies at step 13/65 with *"failed to parse platform: "" is an invalid
component"*. That message accuses the Dockerfile, which is why the first two attempts at this were
spent looking at the wrong file. It reproduces identically in the regional and the global build
pool, so it is not a pool or quota problem.

**Why a default is safe:** BuildKit predefines `BUILDPLATFORM` and its value takes precedence over
an `ARG` default, so a BuildKit build is unaffected and still cross-compiles correctly. Only the
legacy path changes, and only from "empty" to "linux/amd64" — which is what Cloud Build builds on
anyway.

**If dropped:** the image cannot be built at all while Cloud Build runs the legacy builder. Loud
and immediate, at the same step. No silent degradation.

**Conflict risk:** low, but it sits one line above a vendor `FROM`, so a rebase that rewrites the
frontend stage will surface it. Do **not** delete it merely because it looks redundant — it looks
redundant precisely when BuildKit is in use, which is not guaranteed.

## `backend/open_webui/main.py` — two `app.add_middleware` lines and their import

**What:** registers the fork's two ASGI middlewares, defined in `backend/jup/`:

```python
from jup.admin_allowlist import AdminAllowlistMiddleware
from jup.iap_identity import IapIdentityHeaderMiddleware

...
app.add_middleware(AdminAllowlistMiddleware)
app.add_middleware(IapIdentityHeaderMiddleware)
```

Registered in that order because Starlette runs the **last** added outermost, which puts the
normalizer outside the allowlist and outside every vendor layer that reads the identity header.

**Why:** ADR-0012. IAP sends the identity as `accounts.google.com:erik@axiara.ai`, and Open WebUI
reads that header raw in three places — `routers/auths.py:393`, `routers/auths.py:736` and
`utils/auth.py:415`. The middleware strips the provider prefix in the ASGI scope before routing, so
all three read a clean value and **none of them is patched**. `AdminAllowlistMiddleware` settles the
`admin` role from `JUP_ADMIN_EMAILS` instead of from whichever row was inserted first.

**If dropped:** silent, and the worst shape on this list. The app boots, the page loads, and every
local test that does not use a real IAP header still passes. In production, signin succeeds and the
**next request 401s**, because `utils/auth.py` is comparing `erik@axiara.ai` against the still-
prefixed header on every request. That reads as a session bug and nothing points at a prefix. ADR-
0012 chose this shape over patching the auth files precisely because a dropped registration line is
catchable and a dropped auth patch is not.

**The test that catches it:** `tests/test_jup_iap_registration.py`. Two source-level checks run
with no runtime — so they run in CI's `--only-group dev` job, on every push — and assert the
import, the two registrations and their order. A third imports the real app in a subprocess and
asserts the built stack. A fourth asserts the reverse: that **no** vendor auth read site imports
the normalizer, because a belt-and-braces patch re-adds the surface this decision exists to remove.

**Conflict risk:** moderate, and this is the one to check by hand. `main.py`'s middleware block is
upstream's and changes between releases, so a rebase can resolve a conflict there by taking
upstream's side and drop all three lines without any marker surviving. Do not resolve it by patching
`auths.py` or `utils/auth.py` instead — run the test.

## Three fail-closed governance guards — `utils/chat.py`, `routers/openai.py`, `routers/ollama.py`

**What:** one call per file, plus `from jup import governance as jup_governance`. All logic lives in
`backend/jup/governance.py`; the vendor files carry nothing but the call.

```python
# backend/open_webui/utils/chat.py — in generate_chat_completion, after the metadata merge
if refusal := jup_governance.admit(form_data, state=request.state, user_id=getattr(user, 'id', None)):
    raise HTTPException(status_code=refusal.status_code, detail=refusal.detail)

# backend/open_webui/routers/{openai,ollama}.py — at the head of generate_chat_completion
if refusal := jup_governance.refuse_if_ungoverned(form_data, state=request.state, user_id=user.id, route='openai'):
    raise HTTPException(status_code=refusal.status_code, detail=refusal.detail)
```

Two lines each, and the shape is identical in all three: the guard decides, the vendor file raises
its own framework's exception. `backend/jup/` is not allowed to import FastAPI, and a governance
refusal surfacing as a 500 would read as a server fault rather than the deliberate 403 it is.

**Why:** ADR-0002, and issue #16. `utils/chat.py`'s `generate_chat_completion` is the only in-process
funnel to every provider, so that is where the JUP operating contract is attached and the turn is
stamped governed. The two router functions are mounted directly behind only `get_verified_user`, so a
normal user's API key reaches a provider there without passing the funnel at all — they refuse any
turn that is neither stamped nor genuinely carrying the contract.

**The funnel guard refuses too, and that is not ceremonial.** `generate_direct_chat_completion` (a
direct connection) and `generate_function_chat_completion` (a pipe model) are dispatched from the
funnel and never reach a router guard, so for those two branches it is the only control in the path.
It attaches the contract and then *verifies* it attached; a payload it cannot govern — `messages`
present but not a list — is refused rather than forwarded, and is left unmodified rather than
repaired, because silently rewriting a caller's payload discards what they sent.

**Why the funnel call is not the first statement:** it sits after the `request.state` and metadata
assignments because the task exemption cannot be read before `form_data['metadata']` is merged. Those
preceding statements are pure bookkeeping — no `await`, no `return`, no `raise` — and a test asserts
exactly that rather than asserting a line number.

**Why it re-attaches on every turn:** the tool loop strips the system message before re-entering
(`utils/middleware.py:5873` calls `replace_system_message_content('', ...)`, then `:5994` and `:6214`
call back into the funnel). A contract attached once at turn one is gone by turn two. Attaching on
every pass is self-healing.

**Do not hand the guard `bypass_filter`.** It is an access-control flag that
`generate_chat_completion` sets to `True` unconditionally under `BYPASS_MODEL_ACCESS_CONTROL`, so a
guard honouring it would be off in exactly the deployments that need it. A test asserts no line
calling the guard mentions `bypass`.

**If dropped:** silent, and the same shape as the ADR-0012 registrations. The app boots, chat works,
and model calls are simply ungoverned again — which looks identical to a healthy deployment. The
audit trail stops recording, which is the only externally visible symptom.

**The test that catches it:** `tests/test_jup_governance.py`. Source-level checks run with no runtime
— so they run in CI's `--only-group dev` job, on every push — and assert, per file, that the import
and the call are present, that nothing before the call can `await`/`return`/`raise`, and that no
guard line was handed a bypass flag. The behavioural half proves the refusal path, the turn-two
tool-loop case, that a forged `metadata.task` buys nothing on a direct route, and that the trail
records admitted, exempt and refused alike.

**Conflict risk:** `utils/chat.py` is stable (nine touches in twelve months) and cheap to carry.
`routers/openai.py` is not — 59 commits in six months — which is why its guard is a head insert that
can be re-checked at a glance. Re-check all three by running the test, not by reading the diff.

## Passthrough refusals and the URL-fetch gate — `routers/openai.py`, `routers/ollama.py`, `routers/retrieval.py` (2026-09-23)

**What:** six handlers open with a refusal that always fires, and two retrieval handlers open with a
permission check.

```python
# routers/openai.py responses; routers/ollama.py generate_completion, generate_openai_completion,
# generate_openai_chat_completion, generate_anthropic_messages, generate_responses
refusal = jup_governance.refuse_passthrough(user_id=user.id, route='openai', model=form_data.model)
raise HTTPException(status_code=refusal.status_code, detail=refusal.detail)

# routers/retrieval.py process_url, process_web — helper defined above process_url
await _jup_require_web_upload(user)
```

**Why:** ADR-0002's 2026-09-23 amendment. These passthroughs reach a provider without the funnel,
nothing in the app calls them, and their payloads keep instructions outside `messages`, so the
contract check cannot be applied to them soundly. The two retrieval routes fetched any URL for any
verified user; they now enforce `chat.web_upload`, which the vendor defined and checked only in the UI.

**If dropped:** silent. The routes work again, and nothing but the audit trail's missing `refused`
lines would show it.

**The test that catches it:** `tests/test_jup_governance.py` asserts the refusal is the first
statement after the docstring in each of the six handlers, that it is raised, and that
`_jup_require_web_upload(user)` opens both retrieval handlers.

**Conflict risk:** the handler bodies below the insert are upstream's and move often; the insert is
at the head, so re-apply it there and run the test.

## Default tools settle before a `?q=` auto-submit — `src/lib/components/chat/Chat.svelte` (2026-09-23)

**What:** `setDefaults()` no longer returns early when a run is already in flight. A second caller
waits for that run through `defaultsSettled()` and then runs again. The body moved, unchanged, into
`applyDefaults()`. The `?q=` branch of `initNewChat` awaits `defaultsSettled()` before
`submitHandler(q)`.

**Why:** on a fresh load `setDefaults()` first awaits the tool, function and skill lists. The
reactive model-change handler starts that run without awaiting it, and `initNewChat`'s own call hit
the vendor's `if (settingDefaults) return;` and came straight back. The `?q=` auto-submit then sent
the turn with no `tool_ids`, so Asisten JUP was never offered `portfolio_status` and answered from
the KB instead. This was reproduced live: a fresh `/?q=` chat called only the KB tools, while a typed
chat sent `tool_ids: ["portfolio_status"]` and called it.

**If dropped:** silent. Chats still answer, but links and bookmarks that auto-submit lose the
model's default tools.

**The test that catches it:** `tests/test_chat_default_tools_patch.py`.

**Conflict risk:** moderate. `setDefaults` changes upstream now and then. Keep the waiting wrapper
and re-apply the upstream body inside `applyDefaults`.

## The fork's routers are mounted — `backend/open_webui/main.py` (2026-09-24)

**What:** four names in the `from open_webui.routers import (...)` block, `jup_kb_review`,
`jup_leadership`, `jup_portfolio` and `jup_voice`, and their four `app.include_router(...)` lines, at
`/api/v1/kb-review`, `/api/v1/leadership`, `/api/v1/portfolio` and `/api/v1/voice`. The router
modules themselves are fork-owned files. `jup_kb_review` was added 2026-09-25 (ADR-0015),
`jup_voice` 2026-09-27 (ADR-0017, #26), `jup_contracts` at `/api/v1/contracts`, and `jup_channel`
2026-10-04 at `/api/jup/channel` (E7, #86). The channel prefix must equal
`jup.iap_identity.CHANNEL_API_PREFIX`, the only path the gateway principal is let through; the
registration test holds the two together.

**Why:** Portfolio (ADR-0004), Ruang Pimpinan (P1), the KB review queue (ADR-0015) and voice calls
(ADR-0017) are served from their own routers so their rules stay out of vendor code; mounting them
is the only edit to `main.py` they need.

**If dropped:** silent. The app boots and the pages load, and the section's API answers 404, which
the Portfolio page renders as a refused load and Ruang Pimpinan as unavailable.

**The test that catches it:** `tests/test_jup_router_registration.py` (source read, runs under
`--only-group dev`).

**Conflict risk:** low to moderate. Upstream adds routers to the same import block and the same
run of `include_router` lines, so a merge can drop a neighbour. Keep every one of them.

## A voice turn is held to the voice model, tools and documents — `backend/open_webui/main.py`, `backend/open_webui/utils/middleware.py` (2026-09-27)

**What:** the rules are in `backend/jup/voice_turn.py` (#27, ADR-0006, ADR-0017); the vendor side
is one line per insert.
- `main.py`, first line of `chat_completion`: `jup_voice_turn = await jup_voice.enforce_voice_turn(form_data, user)`.
  In a chat carrying a genuine voice mark (`jup.voice.is_voice_chat`, checked against the chat's
  owner) it rewrites the request onto `asisten-jup-suara` with tool ids `portfolio_status`. It
  drops other models, direct connections, tool servers, caller `tools`, terminals, skills,
  filters, files, folder, `automation_id` and every feature but `voice`, and forces native tool
  calling. It writes a `voice_turn` audit line naming what it changed. One key in the
  server-built `metadata`: `jup_voice.VOICE_TURN_KEY: jup_voice_turn`.
- `utils/middleware.py`, four hooks that return their input unchanged unless `metadata` marks a
  voice turn:
  - after the folder-id fallback, `folder_for`. A voice chat moved into a folder gets neither the
    folder's knowledge nor its system prompt.
  - after `skill_ids` is assembled, `skills_for`. A `<$skill|label>` mention in the text would
    otherwise put the skill's full content in the prompt.
  - right after the subagent `offered_tools` line, `tools_for`. It keeps `portfolio_status` and
    the six scoped retrieval builtins, and wraps the builtins so that any `knowledge_id(s)`, or a
    `file_id` outside the model's `{type:'file'}` knowledge, is refused before vendor code runs.
    `view_file`, `view_knowledge_file` and `grep_knowledge_files` otherwise pass any file id on
    admin role.
  - the line after it, `filter_tools_for`. It drops tools an inlet filter added.

**Why:** voice answers only from the eight named documents (ADR-0006), whatever the browser sends.

**If dropped:** silent. Voice turns still answer, but from Asisten JUP's whole KB, with web search
and anything else the request asks for.

**The test that catches it:** `tests/test_jup_voice_turn_presence.py` (a source read that runs
under `--only-group dev`). The rules are tested in `tests/test_jup_voice_turn.py` and the entry
seam in `tests/test_jup_voice_turn_entry.py`.

**Conflict risk:** moderate. The head of `chat_completion` and the skill and tool-resolution
blocks in `process_chat_payload` change upstream. Keep the entry insert before anything reads
`model`, `model_item` or `tool_servers`. Keep the tool hook after the builtin tools are merged, and
before `inlet_filter_tools` is appended. A new builtin that takes a file or knowledge id needs a
look before it joins `KNOWLEDGE_TOOLS`.

## The audio endpoints are the edge of the voice boundary — `backend/open_webui/routers/audio.py`, `backend/open_webui/routers/openai.py`, `backend/open_webui/utils/middleware.py`, `src/lib/components/chat/Messages/ResponseMessage.svelte` (2026-09-28)

**What:** the rules are in `backend/jup/voice_audio.py`, the seam in `routers/jup_voice.py`
(#28, ADR-0017). There is one line per insert, plus an import in each router.
- `audio.py`, the first line of `transcribe`: `jup_stt = await jup_voice.stt_admit(request, user, file_path, metadata)`.
  - With the OpenAI engine it refuses a caller without the voice switch and the `jup.voice.call`
    grant, before any audio is converted or sent.
  - It sits in `transcribe`, so it covers both the transcription route and audio file uploads
    (`routers/files.py`).
  - Just before the return, `jup_voice.stt_audit(jup_stt, results)` writes `voice_stt`: user,
    chat (only the caller's own voice chat, from `?chat_id=`), provider, seconds, language. It
    never writes the transcript. Other engines are not gated here, but are audited.
- `middleware.py`, `publish_chat_finished_event`, after its own early return:
  `await jup_voice.seal_answer(metadata)`.
  - Both finish paths save the answer and then call this, so on a voice turn it reads the saved
    answer back and seals it.
  - The seal is `message.meta.jup_voice_seal`: a signature over the chat, the message and a hash
    of the content, made with the voice-only key.
  - It lives in `meta` because the `chat_message` table keeps only its own columns.
- `audio.py`, `speech`: `body = await jup_voice.speech_body(request, user, engine)` replaces
  `await request.body()`.
  - With the OpenAI engine the body must name `{chat_id, message_id, part}` of an assistant
    answer in the caller's own voice chat whose seal still verifies. The server builds `{input}`
    from that answer, with tool and reasoning blocks removed, in parts of at most 4000 characters.
  - Refused: free text, someone else's message, a non-voice message, and an answer edited or
    added through the chat API (`voice_tts_unsealed`).
  - Every request writes `voice_tts`, refusals included: chars, part and parts, and `cached`
    when the vendor's speech cache will answer it instead of OpenAI. It never writes the text.
    `speech_cached` mirrors the vendor's cache name, and a presence test pins that formula.
  - `GET /api/v1/voice/speech/parts` gives the call UI the part count.
  - The same holds for the `google` engine (#32, D23): `jup_voice.reads_sealed_answers` names
    both engines, and a part is at most 4000 UTF-8 bytes, under Google's 5000-byte limit.
- `audio.py`, `_TTS_ENGINES`: `'google': jup_voice.tts_google` (#32, D23). The vendor has no
  Google engine. The handler sends the sealed part to Cloud Text-to-Speech `text:synthesize`
  with the service's own identity (Cloud Run's service account, no key), in the voice-row voice
  when it names a Google voice, else `id-ID-Chirp3-HD-Kore`, and writes the vendor's speech
  cache. If dropped, the `google` engine is refused as unsupported (loud, not a leak).
- `openai.py`, the first line of the `/audio/speech` proxy: `jup_voice.refuse_speech_passthrough(user)`.
  That route forwards free text to any api.openai.com chat connection. Nothing in the app calls
  it, so it is closed.
- `audio.py`, `_tts_openai` and `_transcribe_openai`, right after the key and base URL are read:
  `api_key = jup_voice.openai_api_key(api_key, api_base_url)` (#30).
  - The key lives in Secret Manager (`openai-live-key`), reaching the service as
    `JUP_VOICE_OPENAI_API_KEY` (`deploy.sh`).
  - The vendor's own key rows were seeded into the app DB on first boot, and a DB row always wins
    over an env var, so the key is swapped in at the call instead. It never lands in the DB, in
    Admin Settings or in the config export.
  - It is used only when the base URL is exactly `https://api.openai.com…`. An admin who points
    the base URL elsewhere gets the saved key, never the secret.
- `ResponseMessage.svelte`, `speak`: `readAloudUsesBrowser($config.audio.tts.engine)`
  (`src/lib/voice/readAloud.ts`) replaces `$config.audio.tts.engine === ''`. With OpenAI or Google
  as the engine, read-aloud on a typed answer uses the browser's own voice.

**Why:** only people with the voice grant send speech to OpenAI (D16, D21), and OpenAI reads only
the stored governed answer of a voice call (ADR-0017).

**If dropped:** silent. Transcription and read-aloud keep working, but they send any user's
speech, or any text, to OpenAI.

**The test that catches it:** `tests/test_jup_voice_audio_presence.py` (a source read that runs
under `--only-group dev`). The rules are tested in `tests/test_jup_voice_audio.py`, the seam in
`tests/test_jup_voice_audio_endpoint.py`, and the helper in `src/lib/voice/readAloud.test.ts`.

**Conflict risk:** moderate. `transcribe`, `speech`, the two OpenAI handlers' key reads and the two finish paths change upstream now
and then. Keep the admit before any conversion, the audit after the gather, the body swap before
the cache hash, and the seal after the finished answer is saved. An outlet filter that rewrites
the saved answer after the seal would make it unreadable by voice; none is configured.
`CallOverlay.svelte` reads answers by message id since #29 (the entry below).

## The call UI starts voice chats through the route — `src/lib/components/chat/MessageInput.svelte`, `src/lib/components/chat/Chat.svelte`, `src/lib/components/chat/MessageInput/CallOverlay.svelte`, `src/lib/apis/audio/index.ts` (2026-09-28)

**What:** the rules are in `src/lib/voice/call.ts` (button state, call flow, disclosure text and
its version, the wait for the seal), the stores and flow in `src/lib/voice/session.ts`, the
routes in `src/lib/apis/voice/index.ts`, and the disclosure in
`src/lib/components/jup/VoiceDisclosure.svelte` (#29, ADR-0017).
- `MessageInput.svelte`, the voice button:
  - The condition is `callButton($voiceCapabilities) !== 'hidden'`, replacing the vendor
    `chat.call` check. Without the voice switch or the `jup.voice.call` grant there is no button.
  - Its click keeps the vendor microphone checks, then runs `runVoiceCall`: the disclosure if not
    yet acknowledged, `POST /voice/acknowledge`, `POST /voice/calls`, and `goto('/c/<chat_id>')`.
    It never opens the overlay on the chat at hand.
- `Chat.svelte`:
  - `onMount` reads the capabilities, and `<VoiceDisclosure />` sits beside `#audioElement`.
  - `?call=true` and the desktop call shortcut call `startVoiceCall()` (the same flow) in place
    of `openCallOverlay()`.
  - `navigateHandler` opens the overlay only on the chat `pendingVoiceCall` names, that is, the one
    the route just made.
  - GPT-Live (#37, ADR-0018): `<VoiceModeChoice />`, `<LiveDisclosure />` and `<LiveCallPanel />`
    sit beside `<VoiceDisclosure />`. When `pendingCallMode` is `live`, `navigateHandler` sets
    `liveCallChat` instead of opening the vendor overlay; the panel (`$lib/voice/liveCall.ts`)
    runs the WebRTC call and the server answers every delegation. `runVoiceCall` asks for the mode
    first, and only when the caller holds `jup.voice.live`.
- `CallOverlay.svelte`:
  - `transcribeAudio(…, chatId)` sends `?chat_id=` (`apis/audio/index.ts` gains that parameter),
    so `voice_stt` names the chat.
  - With OpenAI speech (`speaksSealedAnswers`), the streamed sentences are ignored. On
    `chat:finish` it waits for the seal (`sealedAnswerParts`, which retries `voice_tts_not_ready`
    and `voice_tts_unsealed` 10 × 500 ms), queues `<message id>#<part>` keys and fetches each part
    from `POST /audio/speech` `{chat_id, message_id, part}`. Parts play through the vendor loop.
    Any other engine keeps the vendor path.
  - A reminder line (`jup-voice-reminder`) shows above the status text on every call.
  - A new call opens with her voice (Erik, 2026-09-28): `Chat.svelte` marks the just-started chat
    in `voiceCallOpening`. After its listeners are in place, `CallOverlay`'s `onMount` sends the
    visible line `CALL_OPENING` once. The voice model's instructions (`sync-voice-model.ts`)
    answer exactly that line with a greeting by name and a Betawi pantun. A reopened voice chat
    sends nothing.
  - The call is tied to the chat it opened on: if `chatId` changes, the overlay closes, so speech
    never goes into a chat the disclosure does not cover.
  - With sealed speech, `stopAllAudio` aborts the turn's controller, and the part fetches check
    that signal. An interrupt, a hang-up or the next turn stops the rest of the answer and its
    billed requests.

**Why:** only the start-call route makes voice chats, after the disclosure (D16(e), D17, D21), and
OpenAI reads only the governed answer it stored (ADR-0017).

**If dropped:** silent. The button returns for everyone, and a call runs in whatever chat is open.
Its speech is then refused (free text) or read in the wrong chat.

**The test that catches it:** `tests/test_jup_voice_call_presence.py` (a source read). The rules
are tested in `src/lib/voice/call.test.ts`.

**Conflict risk:** moderate. The voice button's handler and the overlay's `chat` and `chat:finish`
handlers change upstream now and then. Keep the route in the click, the early return in the
sentence handler, and the queueing before `finishedMessages[id] = true`, or the play loop ends
before the parts arrive.

## The name carries no " (Open WebUI)" suffix — `backend/open_webui/env.py` (2026-09-23)

**What:** the two lines that append `' (Open WebUI)'` to any custom `WEBUI_NAME` are replaced by a
comment. With `WEBUI_NAME: "None-JUPe"` in deploy.sh, the app reads exactly "None-JUPe".

**Why:** Erik renamed the app to Asisten JUP on 2026-09-23, and to None-JUPe on 2026-09-26.
LICENSE clause 4 permits removing the Open WebUI branding while end users stay at fifty or fewer
in any rolling 30 days. That is the same ground the logo replacement already rests on (ADR-0001).

**If dropped:** silent. The name reads "None-JUPe (Open WebUI)" again.

**The test that catches it:** `tests/test_brand_none_jupe.py`.

**Conflict risk:** low. Upstream rarely touches these lines, but they carry a LICENSE comment that
merges will keep reasserting.

## One audit line per tool call — `backend/open_webui/utils/middleware.py` (2026-09-23)

**What:** one import (`from jup import governance as jup_governance`) and three calls to
`jup_governance.audit_tool_call(...)`. There is one call at each place the vendor runs a tool:

- the native tool loop in `streaming_chat_response_handler`, straight after each result is unpacked (`mode='native'`);
- `drain_approved_tool_calls`, after the status is decided (`mode='approved'`);
- the legacy prompt-based `chat_completion_tools_handler`, after the call returns (`mode='default'`).

Each writes a `tool_call` line with the user, chat, tool name, `tool_id`, outcome
(`ok`/`error`/`not_found`/`unparsed`) and argument size in bytes. It never writes argument
content. All the logic is in `jup/governance.py`, and the call never raises.

**Why:** agent-depth plan E1. `admit()` writes one line per model turn, but a turn can run several
tools, and the tool is where the agent touches data. Every later tool (subagents, code
interpreter, MCP) is only as accountable as this line.

A fourth call (added 2026-09-23 for A3) sits after `ci_item['status'] = 'completed'` in the
**legacy** code-interpreter block (`mode='code_interpreter'`, `tool_id` `builtin:code_interpreter`).
With native function calling, which Asisten JUP uses, the code interpreter runs as the builtin tool
`execute_code` and gets the native loop's line (live check 2026-09-23 on `00022-bs8`:
`execute_code · builtin:execute_code · ok`). The legacy path handles code parsed out of the model's
text in non-native mode. It is covered so that switching the mode cannot open a gap. The line
records the size of the code, never the code itself, and counts an exception or any stderr as
`error`.

**If dropped:** silent. Tools still run and answers still arrive, but the trail loses the per-tool
lines.

**The test that catches it:** `tests/test_jup_tool_call_audit.py`. Against the unpatched file,
6 of its tests fail.

**Conflict risk:** moderate. The tool loop changes upstream often. Re-apply each call right after
the site's result is known, and before any `continue` that skips a call.

## Subagent tool calls name their parent chat — `backend/open_webui/utils/subagents.py` + `middleware.py` (2026-09-23)

**What:** `run_reserved` sets `child_request.state.jup_parent_chat_id = parent_chat_id` on the
subagent's synthetic request. It's one line, marked `# JUP:`. All four `audit_tool_call` sites in
`middleware.py` pass `state=request.state`. (The fifth site, `mode='approval'` in
`utils/tool_approval.py` since #21, has no request state: it audits a person's reject or a timeout,
never a subagent's call.) Together they give a subagent's `tool_call` lines a
`parent_chat` field naming the chat that delegated them.

**Why:** A2 went live with a gap. A subagent runs in its own chat, and its audit lines carried
only that child chat's id, so the trail could link it to the delegating chat only by timing.

The stamp lives on `request.state`, like the ADR-0002 admission stamp, because a direct caller
controls `form_data`, and a forged parent would mislabel the trail.

**If dropped:** silent. Subagent lines lose `parent_chat` again.

**The test that catches it:** `tests/test_jup_tool_call_audit.py`
(`test_the_subagent_request_is_stamped_with_its_parent_chat`,
`test_every_audit_call_site_passes_the_request_state`).

**Conflict risk:** low in `subagents.py`, where `run_reserved`'s request setup is stable. The
`middleware.py` sites move with the tool loop; see the E1 entry above.

## The group editor keeps permission keys it doesn't manage — `src/lib/components/admin/Users/Groups/EditGroupModal.svelte` (2026-09-24)

**What:** `init()` and `resetToDefaultsHandler()` spread the existing permissions object first
(`...loadedPermissions,` and `...permissions,`) before rebuilding the six vendor keys.

**Why:** the editor rebuilt `permissions` from workspace, sharing, access_grants, chat, features and
settings only, and saved that object whole. A Ruang Pimpinan grant lives under `jup`, so opening a
group and pressing Save with nothing changed deleted it. Reproduced in real Chrome on the local dev
server: the board-only reader's capabilities went from `["board"]` to `[]`. Reset to defaults dropped
it the same way. After the patch, both paths keep the grant.

**If dropped:** silent, and it fails closed. Any admin who edits a leadership group revokes its
readers' access without a warning.

**The test that catches it:** `tests/test_group_editor_keeps_jup_permissions.py`.

**Conflict risk:** low to moderate. Upstream adds permission categories to the rebuild now and then.
Keep the spread as the first line of both objects.

## The shared Modal can be named — `src/lib/components/common/Modal.svelte` (2026-09-24)

**What:** one optional prop, `ariaLabelledby`, rendered as `aria-labelledby` on the `role="dialog"`
element. Unset, the attribute is omitted, so every vendor modal renders exactly as before.

**Why:** the dialog had no accessible name, so a screen reader announced Ruang Pimpinan's source
details and context preview as just "dialog". Both now point at their `<h2>`, verified live as
"Rincian sumber" and "Pratinjau konteks untuk Asisten".

**If dropped:** silent. Svelte ignores the unknown prop, and the dialogs are unnamed again.

**The test that catches it:** `tests/test_modal_accessible_name.py`.

**Conflict risk:** low. Keep the prop and the attribute.

## Ruang Pimpinan's own migration graph runs at boot — `backend/open_webui/main.py` (2026-09-24)

**What:** two imports, `run_leadership_migrations` from `jup.leadership.migrate` and
`ENABLE_DB_MIGRATIONS` from `open_webui.env`, plus one guarded call,
`if ENABLE_DB_MIGRATIONS: run_leadership_migrations(engine)`. The call sits just before the fork
routers are mounted.

**Why:** leadership tables migrate on their own alembic graph with their own version table,
`jup_alembic_version` (ADR-0014), so a quarterly rebase can't give the vendor graph a second head.
The call runs on the vendor engine after the vendor upgrade. It never raises: a failure is logged
and leaves only Ruang Pimpinan unavailable.

**If dropped:** silent. The app boots, the leadership tables never get created, and the workflow
routes refuse with 503 because the schema is not ready.

**The test that catches it:** `tests/test_leadership_migration_seam.py` (source read, runs under
`--only-group dev`), and the boot test in `tests/test_boot.py`, which asserts `schema_ready()` after
a real import.

**Conflict risk:** low. Keep the call ahead of the `jup_leadership` mount.

## Everyday control names go through i18n — twelve vendor components (2026-09-25)

**What:** literal English `aria-label`s become `$i18n.t(...)` calls: "New Chat" and "Controls"
(`chat/Navbar.svelte`), "Available Tools", "Voice Input" and "Expand input" (`chat/MessageInput.svelte`),
"Voice Input" (`channel/MessageInput.svelte`), "Fork chat" (`ResponseMessage.svelte`), "Chat Menu"
(`Sidebar/ChatItem.svelte`, `SearchModal.svelte`), "Close" (`InputModal.svelte`,
`CodeEditorModal.svelte`), and the zoom controls in `PDFViewer`, `PptxPreview` and `DocxPreview`
(the first two gain an `i18n` context). The update toast's close button gains `type="button"` and
an `aria-label`.

**Why:** no translation can reach a string literal, so under id-ID a screen reader still said "New
Chat" or "Chat Menu". The toast's close button had no name at all, and it was the third tab stop on
every page (found in the keyboard pass, 2026-09-25). Admin-only screens, parameter names such as
`top_k`, and the `aria-label` on the sidebar's non-interactive "Loading" divs are left as they are.

**If dropped:** silent. The labels read in English again, and the toast button goes back to having
no name.

**The test that catches it:** `tests/test_vendor_aria_labels_translated.py`.

**Conflict risk:** low. These are one-attribute edits. On a conflict, take the vendor's line and
wrap the label again.

## The knowledge-review entry in the sidebar — `src/lib/components/layout/Sidebar.svelte` (2026-09-25)

**What:** two imports (`DocumentArrowUpIcon`, `kbReviewAccess`), two reactive lines (`showKbReview`,
`kbReviewActive`) and two `{#if showKbReview}` blocks linking to `/kb-review`. One is in the collapsed
rail and one in the expanded list, both right after Ruang Pimpinan. Each carries a translated
`aria-label`, `aria-current` and a Tooltip. The Portfolio and Ruang Pimpinan entries beside it are
the same kind of patch; this entry covers only the new one.

**Why:** the queue (ADR-0015) needs an entry point for staff with the `jup.kb.submit` grant, for
admins, who review, and (since 2026-10-02) for Legal, who review contract cards with the
`jup.contracts.review` grant in the "Kartu Kontrak" section. The entry is presentation only. The server re-checks the grant and the role on
every request.

**If dropped:** silent. `/kb-review` still works for anyone who types it, and nobody else finds it.

**The test that catches it:** `tests/test_sidebar_kb_review_entry.py` (source read, runs under
`--only-group dev`).

**Conflict risk:** moderate. Upstream edits `Sidebar.svelte` often, in both of these regions. Keep
both blocks and their imports.

## The approval gate decides before any tool runs — `backend/open_webui/utils/middleware.py` + `utils/tools.py` (2026-09-26)

`jup_tool_policy.decide(name, tool)` is called at each of the three places the vendor runs a
tool, before the tool's code or the browser's `execute:tool` event:

- the native tool loop's `execute_tool_call`, after the tool entry is resolved. A refusal returns
  the refusal text as the tool's result, and the gate's answer is kept in `jup_gate_approvals` for
  that call's audit line;
- `execute_tool_call_for_output`, which runs the calls a user approved in `ask` mode. The gate
  still decides after the user has: a user's approval is not a Risk Class. The answer travels to
  the drain's audit line as `jup_approval` in the returned dict;
- the legacy prompt-based `tool_call_handler`, where the existing `if tool.get('direct')` becomes
  an `elif` under `if not jup_gate.runs:`.

Each `audit_tool_call` now passes `approval=` (required, no default) and the line gains `approval`
and `approval_wait_ms`. A refused call audits as `outcome: refused`, `approval: rejected`. The
legacy code-interpreter block passes `approval='not_required'`: it is `execute_code`'s capability,
classed `read`, and is not a tool dispatch.

In `utils/tools.py:get_tools`, the DB tool's entry gains `'risk_class'`, read from
`tool.meta.manifest`. The vendor already copies a tool's frontmatter into `meta.manifest` on
create and update, so a native tool declares its class in its own source (`risk_class: read`) and
`deploy/gcp/sync-tools.ts` carries it by pushing the content. All policy is in `jup/tool_policy.py`.

**Why:** A5 + E5 ticket 1/7 (#18), ADR-0013. Every tool gets a Risk Class and, until the approval
card exists, every `external` call is refused, in `ask` and `full` mode alike.

**Deploy order:** the live `portfolio_status` row predates `risk_class`, so until
`sync-tools.ts` re-pushes it the gate reads it as `external` and refuses it. Run the sync straight
after the deploy that carries this patch.

**If dropped:** silent. Every tool runs ungated, `gate_probe` included, and nothing looks wrong.

**The test that catches it:** `tests/test_jup_tool_gate_presence.py` (each gate sits before the
code that runs the tool, and there are exactly three), plus
`test_each_audit_call_site_records_the_gates_answer` in `tests/test_jup_tool_call_audit.py`.
Removing any one gate fails at least two tests.

**Conflict risk:** moderate, for the same reason as the audit line: the tool loop changes upstream
often. Re-apply the gate after the tool entry and its params are resolved and before the
`direct_tool` branch.

## Unattended paths fail closed: every gate is told the path — `backend/open_webui/utils/middleware.py` (2026-09-26)

Each of the three `jup_tool_policy.decide(...)` calls above now passes
`path=jup_tool_policy.path_of(metadata, request.state)`, and `decide` takes `path` as a required
keyword. `path_of` reads `metadata['automation_id']` (an automation run), a `channel:` chat id (a
channel chat) and the `jup_parent_chat_id` stamp `utils/subagents.py` puts on a child request (a
subagent); anything else is an attended chat. On an unattended path an `external` call is refused
as `rejected_unattended`, and the model is told why, so the reason reaches the run's chat.

This is the override of the vendor rule in `main.py` that forces `tool_approval_mode = 'full'` for
automations and channels. That rule is left as it is, for ungated tools; the gate never reads
`tool_approval_mode`, so `full` cannot let an `external` call through.

**Why:** A5 + E5 ticket 2/7 (#20), ADR-0013 §4. Where nobody is present to approve, an External
Call fails closed. Once the approval card exists (#21), attended chats get the card; these paths
stay refused.

**If dropped:** silent until #21. Today an attended refusal and an unattended one both refuse, so
losing the path only mislabels the audit line (`rejected` instead of `rejected_unattended`). After
#21 it would put an approval card in front of nobody, and the automation would hang to the timeout.

**The test that catches it:** `test_every_gate_is_told_the_path_the_call_arrived_on` and the two
tests after it in `tests/test_jup_tool_gate_presence.py` (the stamp in `subagents.py`, the
`automation_id` main.py puts in metadata); `decide` raises `TypeError` at a site that drops `path`.

**Conflict risk:** low beyond the gate entry above; it rides on the same three lines.

## A subagent is never offered an `external` tool — `backend/open_webui/utils/middleware.py` (2026-09-26)

In `process_chat_payload`, after the built-in tools are merged into `tools_dict` and before
`metadata['tools']` and `form_data['tools']` are built from it:
`tools_dict = jup_tool_policy.offered_tools(tools_dict, jup_tool_policy.path_of(metadata, request.state))`.
On a subagent's request it drops every tool whose Risk Class is `external`; every other path is
unchanged (automations and channels are offered everything and refused at the call, so the refusal
shows in the run's chat).

**Why:** A5 + E5 ticket 2/7 (#20), ADR-0013 §4: delegation stays read-and-reason. The gate would
refuse the call anyway (`rejected_unattended`); not offering the tool means the subagent never
plans around it.

**If dropped:** the subagent is offered `external` tools again and each call is refused at the
gate. Safe, but it wastes the subagent's iterations and fails nothing visible.

**The test that catches it:** `test_a_subagent_is_filtered_before_its_tools_are_offered` in
`tests/test_jup_tool_gate_presence.py`; the filter itself is tested in
`tests/test_jup_unattended_paths.py`.

**Conflict risk:** moderate: tool assembly in `process_chat_payload` changes upstream. Re-apply
after the last merge into `tools_dict` and before anything reads it.

## The decisions-register MCP server starts with the app — `backend/start.sh` (2026-09-26)

One line after `PYTHON_CMD` is set, before the final `exec`: `"$PYTHON_CMD" -m jup_mcp.decisions &`,
under a `JUP` comment. It starts the read-only decisions-register MCP server
(`backend/jup_mcp/decisions.py`) in the background. The server binds to 127.0.0.1 in code, with no
host setting, and reads `/srv/jup/DECISIONS.md` from the read-only records mount on every call
(`JUP_DECISIONS_FILE` and `JUP_DECISIONS_MCP_PORT`, default 8765, override that for tests).

**Why:** A5 + E5 ticket 5/7 (#19), D20's pre-approved class: JUP-hosted, read-only, no outbound
calls. It is not attached to the app until ticket 6/7 registers the tool-server connection.

**If dropped:** the app still boots, and the decisions tools fail once the connection is registered.
Nothing restarts the server if it dies, either; the same symptom, and the container restart fixes it.

**The test that catches it:** `tests/test_jup_decisions_mcp.py`
(`test_start_sh_starts_it_in_the_background_before_the_app`).

**Conflict risk:** low. `start.sh` changes rarely; keep the line above the final `exec`.

## An attended External Call pauses for the asking user — `backend/open_webui/utils/middleware.py` + `utils/tool_approval.py` (2026-09-26)

Seven inserts, each under a `JUP` comment (the new imports in `tool_approval.py` serve inserts 5–6), that route an `external` call in a chat through the
vendor's own pause-and-resume machinery whatever the chat's `tool_approval_mode`. The rules live in
`backend/jup/approval.py` and `jup.tool_policy.must_pause` / `preapprove_ungated`; the inserts only
call them.

1. **The native loop's pause** (`streaming_chat_response_handler`, where the vendor paused only on
   `tool_approval_mode == 'ask'`): the condition is `jup_must_pause`, true when any call in the batch
   `must_pause` (every attended `external` call, plus every call in `ask` as before). In `full` mode
   `preapprove_ungated` marks the batch's ungated calls approved, so only the gated ones wait. This
   is the forced-pause patch.
2. **`pause_for_tool_approval`**: an approved call is never given the card (`approved is not True`),
   and the call that is given it is armed (`jup_approval.arm`): its 10-minute clock starts when it
   is shown. After the upsert, `arm_jup_approval_timeout` schedules the server-side timeout.
3. **`drain_approved_tool_calls`**: both re-pause conditions use `must_pause` instead of the vendor's
   `ask`-only test, and each approved call carries `jup_approval.verified(...)` (keyed with
   `WEBUI_SECRET_KEY`, imported from `open_webui.env`) into `execute_tool_call_for_output`, which
   passes it to `decide(..., approval=)`. The drain's audit line gains `approved_by` and
   `approval_wait_ms`.
4. **`resolve_tool_call_output`** (`utils/tool_approval.py`): only the chat's owner resolves a call.
   The vendor also let any admin resolve any chat's call, for every tool.
5. **Same function**: a gated call (`jup_approval.is_gated`) is approved or rejected by
   `jup_approval.resolve` before the vendor's branches. Approve signs the approval to exactly that
   call and user; reject, and any click after the deadline (`timed_out`), append a refusal for the
   model and write the audit line (`_jup_record_refusal`). A second decision is a 409.
6. **`arm_jup_approval_timeout` / `_jup_time_out`** (new, same file): after 10 minutes an unanswered
   armed call is refused as `timed_out`, audited, and the turn is resumed through
   `app.state.CHAT_COMPLETION_HANDLER` so the model is told, as the resolve route does after a reject.
7. **`src/lib/components/chat/Chat.svelte`, `handleToolApprovalModeChange`**: switching a chat to
   `full` auto-approves its pending card; a call carrying `jup_gate` is skipped, so changing the
   preference never approves an External Call.

**Why:** A5 + E5 ticket 3/7 (#21), ADR-0013 §2–§3 and §5: an attended External Call waits for the
user whose turn produced it, one approval covers one call, and the decision is in the audit line.

**If dropped:** without (1) or (3) no card appears in `full` mode and every attended External Call is
refused as `rejected` (safe, but nothing external ever runs). Without the signature check in (3) an
approved call is still refused: `decide` runs an `external` call only with a verified approval.
Without (4) an admin can approve a call in someone else's chat. Without (6) a call left open in a
closed tab stays pending until someone next clicks it (the click is then a timeout, never an
approval, because `resolve` enforces the deadline).

**Known limit:** the timer is an in-process `asyncio` task. An instance restart inside the 10
minutes loses it, and the call then times out on its next resolve instead. With throttled CPU it can
also fire late, and `approval_wait_ms` records the actual wait.

**The test that catches it:** the `#21` tests at the end of
`tests/test_jup_tool_gate_presence.py`; the rules in `tests/test_jup_approval.py`; the route and the
timer against an in-memory chat store in `tests/test_jup_approval_resolve.py` (skipped without the
runtime tree).

**Conflict risk:** moderate. The pause and drain conditions are upstream's approval flow and move
with it; re-apply each JUP condition where the vendor tests `tool_approval_mode == 'ask'`.

## The approval card shows the class and masks secrets — three vendor Svelte/TS files (2026-09-27)

The rules live in `src/lib/gate/card.ts` (`maskedArguments`, `gateRiskClass`, tested in
`card.test.ts`); `backend/jup/approval.py` records `risk_class` on the armed call. The vendor
inserts, each under a `JUP` comment:

1. **`src/lib/components/chat/Messages/structuredOutput.ts`**: `buildToolCallToken` adds
   `risk_class: gateRiskClass(item)` to the tool-call attributes ('' for an ungated call).
2. **`src/lib/components/common/ToolCallDisplay.svelte`**: for a call with a `risk_class`, the
   Input section shows `maskedArguments(args)` (secret-looking values masked, the rest in full), the
   Output section masks the result the same way (`gate_probe` echoes its token), a
   `jup-risk-label` chip names the class, and a pending card opens itself so the arguments are on
   screen when the user decides.
3. **`src/lib/components/chat/Messages/Markdown/ConsecutiveDetailsGroup.svelte`**: when a pending
   call is gated, the group opens and its collapsed-header Allow/Deny shortcuts are hidden (they
   approve without showing the arguments); the decision is made on the call's own card.
4. **`src/lib/components/chat/MessageInput/InputMenu.svelte`**: the "Full access" tooltip read
   "Run tools without asking for approval.", which is false for External Calls since #21; it is now
   a literal `$i18n.t` (`jupFullAccessDescription`) saying External Calls always ask. The vendor's
   mode descriptions go through a non-literal `$i18n.t(mode.description)` the extractor cannot see.

Styling is one rule, `.jup-risk-label`, in `src/jup-skin.css` (the defer pair: 5.66:1 light,
6.81:1 dark). New strings are literal `$i18n.t` calls with id-ID translations.

**Why:** A5 + E5 ticket 4/7 (#22), ADR-0013 §3: the user sees the full call, secrets masked, and the
class that made it stop. The vendor card never offered "allow for this chat" or "always allow";
the one standing choice, switching the chat to `full`, stopped approving gated calls in #21.

**If dropped:** the gate still holds (the server decides), but the user approves blind: without (2)
the arguments stay collapsed and unmasked with no label; without (3) the group header's Allow runs
the call with no arguments on screen. Losing (1) silently disables all of (2) and (3).

Masking (`card.ts`): a key that names a secret (`token`, `password`, `api_key`, `session_id`…) and,
inside any text, a credential shape (`Bearer …`, `sk-…`, a JWT…) or a `secret_key=value` pair. Words
that are ordinary alone (`key`, `auth`, `session`, `pin`) stay visible.

**The test that catches it:** the `#22` tests at the end of `tests/test_jup_tool_gate_presence.py`.

**Conflict risk:** moderate. `ToolCallDisplay.svelte` and the group change upstream with the tool UI;
re-apply the three conditions where the vendor decides what a pending card shows.

## An MCP tool carries its server's audit id and admin-set Risk Class — `backend/open_webui/utils/middleware.py` (2026-09-27)

Two inserts, each under a `JUP` comment:

1. **`connect_mcp_server`**: after listing the tool specs,
   `client.jup_connection_config = mcp_server_connection.get('config') or {}`, so the connection's
   settings reach the loop that builds the tool entries.
2. **The MCP loop in `process_chat_payload`**: each MCP tool entry gains
   `**jup_tool_policy.mcp_tool_fields(server_id, tool_spec['name'], …)`: `tool_id` `mcp:<server_id>`
   and `risk_class`, resolved from `config.jup_tool_risk_classes[<tool>]`, then
   `config.jup_risk_class`, else `external` (`backend/jup/tool_policy.py`).

**Why:** A5 + E5 ticket 6/7 (#23), ADR-0013 §1: an MCP server gets one class for all its tools, set by
an admin, overridable per tool, `external` when unset. The vendor's MCP entries had no `tool_id`, so
the gate treated every MCP tool as `external` and the audit line named no server.

**Where the class is set:** on the connection in `/api/v1/configs/tool_servers` (admin-only); the
vendor keeps unknown keys in `config`. Editing the connection in the admin UI may drop them, so
re-check `jup_risk_class` after any UI edit of a JUP-classified server.

**If dropped:** every MCP tool is gated as `external` again (a card for every decisions lookup) and
its audit line has no `tool_id`. Safe, but noisy and untraceable.

**The test that catches it:** `test_an_mcp_tool_entry_carries_its_audit_id_and_admin_set_class` in
`tests/test_jup_tool_gate_presence.py`; the resolution in `tests/test_jup_mcp_risk_class.py`.

**Conflict risk:** low to moderate: the MCP loop moves upstream. Re-apply inside the tool entry dict.

## IAP session expiry is not app sign-out, and it unsticks the chat — `src/routes/+layout.svelte`, `src/lib/components/chat/Chat.svelte` (2026-10-01, #47)

**What:** fork logic lives in `src/lib/iap/session.ts` (unit-tested). The vendor files get hooks only:

- `+layout.svelte`, the `window.fetch` wrapper: `withIapAjaxHeader` adds `X-Requested-With:
  XMLHttpRequest` to same-origin URL requests; `isIapExpiry` (a 401 carrying
  `x-goog-iap-generated-response: true`) is checked **before** the vendor's 401 branch and calls
  `handleIapExpiry`, which sets `iapSessionExpired` and shows one persistent Indonesian toast with a
  "Muat ulang halaman" action. The socket's `connect_error` calls `probeIapSession` (one
  `/api/v1/auths/` request, at most every 30 s), because a stream can die with no fetch in flight.
- `Chat.svelte`: `$: if ($iapSessionExpired) interruptForIapExpiry();` marks a `done: false`
  assistant answer done with an interrupted note and hands any queued messages back to the
  composer; `submitHandler` refuses to send or queue while the session is expired and keeps the text.

**Why:** the IAP/GCIP session ends about an hour after sign-in (seen live 2026-09-30). Without the
hint IAP answers a script with a 302 to the cross-origin sign-in page, which `fetch` reports as a
bare network error: the answer stopped with no message, stayed `done: false`, and every later
message was silently queued behind it. With the hint IAP answers 401
(https://docs.cloud.google.com/iap/docs/sessions-howto), which the vendor's wrapper would have read
as app-session expiry and **signed the user out**, hence the ordering.

**If dropped:** silent. Without the layout hook staff get the stuck chat back; if only the ordering is
lost while the header stays, every hourly IAP expiry signs staff out of the app.

**The test that catches it:** `tests/test_iap_session_expiry_patch.py`; logic in
`src/lib/iap/session.test.ts`.

**Conflict risk:** low to moderate. The fetch wrapper and `submitHandler` change upstream now and
then; keep the IAP check first in the wrapper and the guard first in `submitHandler`.

## `backend/open_webui/tools/builtin.py` — model-attached collections are readable by the model's users

**What:** `_model_attached_collection_ids` and `_can_read_knowledge` replace the inline
admin / owner / grant check in `search_knowledge_files`, `grep_knowledge_files`, `view_knowledge_file`
(which now also takes `__model_knowledge__`), `list_knowledge` and `query_knowledge_files`, and
`_has_read_access_to_file` also accepts a file inside a model-attached collection. Only items whose
`source` is `'model'` count; a collection a user attaches to their own chat still needs a grant.

**Why:** ADR-0015 §1 keeps the KB collections private (no grants) and makes them reachable only by
attaching them to the model. The vendor already allows a model-attached *file* without a grant, but
not a model-attached *collection*, so every non-admin got empty knowledge results from Asisten JUP
and the voice model while admins saw answers (found 2026-10-02).

**If dropped:** silent. Staff answers lose every KB source and the assistant says the information is
not available; admins see no difference, which is how it went unnoticed.
`tests/test_kb_model_attached_access.py` notices.

**Conflict risk:** medium. Five vendor tool bodies are touched; on a rebase, re-apply the helper at
every model-knowledge access check (the static test lists them).

## `Dockerfile` + `deploy/gcp/deploy.sh` — multilingual embedding model

**What:** `USE_EMBEDDING_MODEL=intfloat/multilingual-e5-small` (MiniLM stays baked as well), and
`RAG_EMBEDDING_QUERY_PREFIX` / `RAG_EMBEDDING_CONTENT_PREFIX` = `query: ` / `passage: ` in deploy.sh.

**Why:** the KB is Indonesian; MiniLM is English-only and vector search missed the right file for
plain Indonesian questions (2026-10-02 probe). The live embedding model is DB-persisted config: the
switch is `POST /api/v1/retrieval/embedding/update` followed by `POST /api/v1/knowledge/reindex`.
Chat uploads embedded under MiniLM are not re-indexed by that route.

**If dropped:** the DB still names e5 but the image no longer contains it, so RAG degrades (the
embedding function raises; boot does not crash). Keep the prefixes only while the model is e5.

## `backend/open_webui/tools/knowledge_fs.py` — `is_regex_pattern` recognises `(?` and `\b`

**What:** two more checks in the regex-or-literal detector shared by `grep_knowledge_files` and
`kb_exec`.

**Why:** the model writes `(?i)direktur`. Without these checks the pattern was matched as the literal
text "(?i)direktur", grep answered "No matches" across a KB full of "Direktur", and Asisten JUP told
the user the board of directors was not in the knowledge base (live, 2026-10-02).

**If dropped:** silent — grep returns no matches for those patterns and the answer degrades.
`tests/test_kb_grep_inline_flags.py` notices.

**Conflict risk:** low. Two lines appended to one boolean expression.

## `src/lib/components/admin/Users/UserList.svelte` — the contract title column (2026-10-02, contract KB D3)

**What:** one import, one header (`Title group` / "Jabatan") and one cell rendering the fork component
`src/lib/components/contracts/ContractTitleSelect.svelte`, which reads and sets the user's title through
`/api/v1/contracts/titles` (`routers/jup_contracts.py`).

**Why:** Erik's decision D3: contract access comes from one place, a title per user (Direksi, Legal,
Manager, Staff). Each title is a managed group (`group.data.jup_contract_title`) whose `jup.contracts`
grants are fixed in `jup.contracts.titles`; the endpoint moves the user so exactly one remains.

**If dropped:** silent — the API still works and nobody can set a title from the UI.
`tests/test_admin_user_list_contract_title.py` notices.

**Conflict risk:** low. Three added lines; the cell sits between the role and email cells.

## `backend/open_webui/main.py` — the contract KB's migration graph and router (2026-10-02)

**What:** `run_contract_migrations(engine)` beside `run_leadership_migrations` under
`ENABLE_DB_MIGRATIONS`, and `jup_contracts.router` mounted at `/api/v1/contracts`.

**Why:** the contract tables (`jup_contract`, `jup_contract_event`, `jup_contract_party`,
`jup_contract_party_link`) sit on their own graph and version table (`jup_contracts_alembic_version`),
so a broken contract migration disables only contracts — not chat and not Ruang Pimpinan.

**If dropped:** the app boots; contract routes and the tool refuse with "schema not ready" or 404.
`tests/test_contract_migration_seam.py`, `tests/test_jup_router_registration.py` and the boot test notice.

**Conflict risk:** low. Two lines next to the leadership ones.

## `src/lib/components/chat/Messages/ContentRenderer.svelte` — names beside contract codes (2026-10-02, D2)

**What:** `formatMessageContent` becomes reactive and passes its result through `withContractNames`
(`src/lib/stores/contractNames.ts`); `loadContractNames($user?.id)` asks `/api/v1/contracts/capabilities`
once per account. Both render paths (plain markdown and structured `output`) use that function.

**Why:** the model only ever reads "Perorangan A". Erik's D2: Legal and Direksi see the name. The
server returns names from `/parties/resolve` only to a reader holding `jup.contracts.names`; everyone
else gets an empty map and sees the code. Display only — the stored message keeps the code.

**If dropped:** silent — Legal and Direksi see codes. `tests/test_admin_user_list_contract_title.py` notices.

**Conflict risk:** medium. The vendor expression is wrapped, not changed; re-wrap it after a rebase.

## `ChatControls.svelte`, `FileItem.svelte`, `Chat.svelte` — office files open in the chat column (2026-10-03, O4)

**What:** three small hooks into the fork module `src/lib/office/preview.ts` and the fork component
`src/lib/components/jup/OfficePreviewPanel.svelte`:

- `ChatControls.svelte`: marks the column available while mounted, shows the panel when
  `$officePreview` belongs to the open chat (beside the vendor's Artifacts/Embeds branches, in both
  the desktop column and the phone drawer), and closes it in `closeHandler`.
- `FileItem.svelte`: a click on a stored .docx/.xlsx/.pptx calls `openOfficePreview(item)` first;
  it returns false outside a chat column (knowledge, workspace), for composer chips (`dismissible`)
  and in edit mode, and then the vendor modal opens as before.
- `Chat.svelte`: in the `files` event handler, a newly attached office file on an assistant
  message opens by itself on a large screen (`autoOpenOfficePreview`).

**Why:** Erik's call 10-03: a generated file should open beside the chat, as in other assistants,
view-only with Download, showing its Draf status and classification. The renderers are the
vendor's own (SheetJS + `excelToTable`, `DocxPreview`, `pptxToImages`).

**If dropped:** silent — office files open in the vendor modal again and nothing auto-opens.
`src/lib/office/preview.test.ts` still passes (it tests the module, not the hooks).

**Conflict risk:** low. Additive lines; the `files` branch keeps the vendor assignment.
