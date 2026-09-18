# src/lib/apis (30 files, 16.4K) + stores + types + i18n
~330 exported async fns wrapping fetch. NO generated client, NO OpenAPI codegen, NO query cache
(no TanStack/SWR), NO interceptor. Every call is a FREE FUNCTION WHOSE FIRST ARG IS THE BEARER TOKEN,
supplied by callers as localStorage.token.
BASE URLS constants.ts:9-17 — WEBUI_BASE_URL='' WEBUI_API_BASE_URL='/api/v1' + /ollama /openai
  /api/v1/audio /api/v1/images /api/v1/retrieval. SAME-ORIGIN BY DESIGN (backend serves the frontend).
TWO EXCEPTIONS ESCAPE SAME-ORIGIN: getToolServerData/executeToolServer apis/index.ts:394,541 call
  ARBITRARY THIRD-PARTY OpenAPI servers FROM THE BROWSER; all of apis/terminal/index.ts talks to an
  Open Terminal instance at a CALLER-SUPPLIED baseUrl w/ CALLER-SUPPLIED apiKey.

## THE FETCH CONVENTION — COPY-PASTED ~330 TIMES
  let error=null; const res=await fetch(url,{method,headers:{Accept,Content-Type,
    authorization:`Bearer ${token}`},body})
    .then(async r=>{if(!r.ok) throw await r.json(); return r.json();})
    .catch(err=>{console.error(err); error=err.detail; return null;});
  if(error) throw error; return res;
CONSEQUENCES:
- REJECTION VALUES ARE NOT Error OBJECTS. A failed call throws the FastAPI `detail` — usually a string,
  sometimes an ARRAY of Pydantic {msg} objects. Callers do toast.error(err). NEVER catch(e){e.message}.
- HEADER CASING INCONSISTENT: authorization vs Authorization; some gate on (token && {...}), others always send
- ERROR EXTRACTION INCONSISTENT — FOUR normalizers: bare err.detail (most) | 'detail' in err?err.detail:err
  (apis/index.ts) | getErrorDetail joining Pydantic arrays (chats/index.ts:4) | getErrorMessage walking
  detail.error.message (openai/index.ts:3) | `Ollama: ${err?.error?.message}` prefixes |
  'Server connection failed' fallback (ollama, images)
- *** A TypeError FROM A NETWORK FAILURE HAS NO .detail, so error becomes undefined, the if(error) GUARD
  PASSES, AND THE FUNCTION SILENTLY RETURNS null. THE SINGLE MOST COMMON LATENT BUG CLASS IN THE LAYER.
  Callers doing res.map(...) (chats:252,306,355) THEN CRASH ON null. ***
DEVIATIONS: getSubagentsConfig/setSubagentsConfig throw RAW JSON w/ no catch | getOrchestratorPolicy/
  Lifecycle throw REAL Error objects w/ .status | updateUserTimezone NEVER THROWS | terminal/* swallow
  everything returning null/[] | getFileContentById SENDS NO TOKEN AT ALL (credentials:'include')

## STREAMING — TWO PATHS, THE PRIMARY ONE IS NOT SSE
*** PRIMARY (chat): Chat.svelte:3547 calls generateOpenAIChatCompletion — a PLAIN JSON POST
/api/chat/completions carrying session_id: $socket?.id :3587. TOKENS THEN ARRIVE OVER SOCKET.IO,
dispatched Chat.svelte:1234 as chat:completion, w/ chat:message:delta APPENDING and chat:message
REPLACING content :1249-1252. Socket created +layout.svelte:166. CANCELLATION IS SERVER-SIDE:
stopTasksByChatId/stopTask Chat.svelte:3738,3744, w/ chat:tasks:cancel marking messages done. ***
SECONDARY (SSE): apis/streaming/index.ts createOpenAITextStream :28 pipes Response.body through
TextDecoderStream -> EventSourceParserStream, yields {done,value,sources?,selectedModelId?,error?,usage?}
:28-93. Terminates on [DONE] or parsedData.error; routes sources/selected_model_id/usage as OUT-OF-BAND
FRAMES before falling through to choices[0].delta.content.
streamLargeDeltasAsRandomChunks :97 re-chunks deltas >5 chars into 1-3 char pieces w/ 5ms sleep, skipped
when tab hidden. GATED BY settings.splitLargeChunks AT THE CALL SITE BUT DECLARED AS splitLargeDeltas in
stores/index.ts:272 — A REAL NAMING MISMATCH.
This path is NOW ONLY USED FOR MoA MERGES Chat.svelte:3893 and MultiResponseMessages.svelte, using
AbortController from generateMoACompletion/chatCompletion + generationController?.abort() :3771.
STRAY console.log(parsedData) ON EVERY EVENT streaming/index.ts:63.
OTHER HAND-ROLLED READERS: getAllChats NDJSON chats:434 | uploadFile progress via splitStream('\n')
files:50 | streamPendingKnowledgeFiles raw SSE Response

## GLOBAL STATE stores/index.ts (389L) — ~60 flat writables, NO factory, NO namespacing, NO persistence mw
Backend-sourced: WEBUI_NAME WEBUI_VERSION WEBUI_DEPLOYMENT_ID config(Config|undefined) user(SessionUser|undef)
  — written +layout.svelte:1255,1273 and auth/+page.svelte:55
Transport: socket socketConnected activeUserIds USAGE_POOL — written ONLY by +layout.svelte:166-255
Electron: isApp appInfo appData + one-shot desktopEvent :162 (set by layout, consumed+cleared by Chat.svelte)
Chat: chatId chatTitle temporaryChatEnabled chatRequestQueues channels channelId
*** CHAT LIST IS THE ONLY ENCAPSULATED STORE — stores/chatList.ts exports chats/pinnedChats as READONLY
:12-13, mutated exclusively through refreshChatList, loadNextChatListPage, setChatActive, setChatReadAt,
setAllChatsRead, resetChatListState. Holds module-level pagination (currentPage, paginationReady,
allLoaded, loadingNextPage) and a requestGeneration COUNTER TO DISCARD STALE RESPONSES :46,:94. Also owns
a handler-registry bridge registerFolderRefreshHandler :68 because the sidebar owns folder state. ***
Workspace: models knowledge tools skills functions folders selectedFolder tags pinnedNotes toolServers
  terminalServers workspaceCounts workspaceActions admin*Count
settings :104 IS THE GOD-OBJECT — ~70 optional fields, written from users/settings on load
  ((app)/+layout.svelte:96) and by many components (Chat.svelte:430,1546, EmojiPicker.svelte:48)
Derived: pinnedModels :107 (falls back to config.default_pinned_models when user never pinned),
  visiblePinnedModels :114
UI flags: showSidebar showSearch showSettings showChangelog showControls showEmbeds showOverview
  showArtifacts showCallOverlay showFileNav* selectedTerminalId sidebarWidth theme mobile banners
  artifactCode artifactContents embed isLastActiveTab playingNotificationSound audioQueue TTSWorker
  pyodideWorker MODEL_DOWNLOAD_POOL shortCodesToEmojis
*** NO STORE PERSISTS ITSELF. Durable state lives in localStorage (token, locale, ad-hoc) or on the server
via updateUserSettings. AUTH TOKEN IS NEVER IN A STORE — every API call reads localStorage.token AT THE
CALL SITE. ***

## TYPE CONTRACTS — THIN
app.d.ts is EMPTY boilerplate. types/index.ts has ONLY Banner and TTS_RESPONSE_SPLIT (15 lines).
GENUINELY TYPED: UserUsageResponse users:675 | Calendar* calendar:3-70 | Automation* automations:3-58 |
  NotificationTarget/Event | EventWebhook/EventCatalogItem | Prompt*/PromptDiff | Terminal* | SearchDocument
UNTYPED: almost every request body is `object`, almost every response is inferred `any` from res.json().
  err is any. getModelItems/getPromptItems/getFeedbackItems have UNTYPED PARAMETERS.
  ollama:3 uses a NONEXISTENT `dict` type. ModelParams is {} and ModelMeta.toolIds is never[].
DRIFT: Config.features stores:335 is a HAND-MAINTAINED MIRROR of the backend config payload;
  SessionUser.permissions is `any` while constants/permissions.ts declares a 5-group DEFAULT_PERMISSIONS
  shape THAT NOTHING TYPE-CHECKS AGAINST. Settings stores:217 carries a BOGUS METHOD MEMBER
  splitLargeChunks?(body,splitLargeChunks):unknown :247. DEFAULT_CAPABILITIES constants.ts:109 duplicates
  capability names that only exist as `any` on model.info.meta.capabilities.

## I18N i18n/index.ts (90L)
initI18n(defaultLocale?) configures i18next w/ resourcesToBackend doing dynamic
import('./locales/{lang}/translation.json') :49 — VITE CODE-SPLITS ALL 66 LOCALES so only the active
one ships. Detection ['querystring','localStorage','navigator'] or ['querystring','localStorage'] when
admin sets a default :44. fallbackLng maps fr->fr-FR + configured default (else en-US).
*** keySeparator/nsSeparator are FALSE — TRANSLATION KEYS ARE FULL ENGLISH SENTENCES. *** escapeValue:false.
Two derived stores: default export i18n (writable re-set on initialized/loaded/added/languageChanged,
also setting <html lang>) and isLoading (true when a load returns {} or fails :26-41).

## GOTCHAS
- NAME COLLISIONS ACROSS MODULES — ALWAYS IMPORT NAMESPACED: getModels (apis/index.ts AND apis/audio) |
  synthesizeOpenAISpeech (apis/openai AND apis/audio, DIFFERENT ENDPOINTS) | unloadModel (apis/index.ts
  AND apis/ollama) | getConfig/updateConfig (images AND evaluations) | searchFiles (files AND terminal) |
  getUserValvesById (tools AND functions)
- TOKEN PLUMBING IS MANUAL. No refresh, no 401 interceptor, no central sign-out on expiry.
- STREAMING IS BIMODAL. Adding a chat feature means touching SOCKET EVENT HANDLING IN Chat.svelte,
  NOT the SSE parser. createOpenAITextStream is legacy-adjacent.
- executeToolServer builds requests from an UNTRUSTED OpenAPI spec and SENDS THE SESSION TOKEN TO A
  THIRD-PARTY ORIGIN when auth_type==='session' apis/index.ts:453
- IMPLICIT BACKEND COUPLING: snake_case bodies built inline (access_grants, folder_id, file_id, user_ids);
  Config/Settings/DEFAULT_PERMISSIONS hand-mirrored from Pydantic w/ NOTHING ENFORCING AGREEMENT.
  *** getNotes DIVIDES updated_at BY 1e9 (NANOSECONDS) while chat lists treat updated_at AS SECONDS —
  THE TIMESTAMP UNIT IS NOT UNIFORM ACROSS ROUTERS. ***
- getFileContentById RELIES ON COOKIE AUTH so it BREAKS UNDER BEARER-ONLY DEPLOYMENTS
- DEBUG NOISE SHIPS TO PRODUCTION: console.log in streaming:63, apis/index.ts:433, files:66-79, notes:230
- WHERE TO ADD API SURFACE: one folder per backend router under apis/<router>/index.ts, import the base-URL
  constant, copy the 30-line boilerplate. notifications/index.ts:24 `jsonRequest` IS THE EXISTING PRECEDENT
  FOR A SHARED HELPER — adopting it broadly would DELETE ~8,000 LINES.
