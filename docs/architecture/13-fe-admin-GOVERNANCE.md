# admin/ — 63 files, 23,272 lines. *** THE ENTIRE GOVERNANCE SURFACE OF THE PRODUCT. ***
*** ADMIN SETTINGS PANES DO NOT LIVE BEHIND /admin/settings — that route IMMEDIATELY REDIRECTS to
/?settings=admin%3Ageneral (routes/(app)/admin/settings/+page.svelte:6), so ALL PANES RENDER INSIDE THE
SHARED SettingsModal (chat/SettingsModal.svelte:41-56, tab registry :679-790, group map :152-168).
Only Users, Groups, Functions, Evaluations and Analytics have REAL ROUTES. ***
Every pane is a <form> with a SINGLE Save that PUTs A WHOLE CONFIG OBJECT — NO PER-FIELD SAVE.
Layout primitives AdminSettingSection.svelte (17L) / AdminSettingRow.svelte (26L, generates labelId via
uuid :9) / AdminSettingField.svelte (24L). Icons resolve by tab id AdminTabIcon.svelte:22-89.

## SETTINGS PANES
General — getAdminConfig/updateAdminConfig :90,:76 + getBanners/setBanners :61. ENABLE_COMMUNITY_SHARING,
  ENABLE_MESSAGE_RATING, ENABLE_FOLDERS+FOLDER_MAX_FILE_COUNT, ENABLE_MEMORIES+
  ENABLE_MEMORY_SYSTEM_CONTEXT, ENABLE_NOTES, ENABLE_CHANNELS+CHANNEL_MODEL_RESPONSE_MODE(thread|channel),
  ENABLE_CALENDAR, ENABLE_AUTOMATIONS, ENABLE_USER_WEBHOOKS, ENABLE_USER_STATUS, RESPONSE_WATERMARK,
  WEBUI_URL, DEFAULT_INTERFACE_SETTINGS. Also version/update check, license metadata :199-221, <Events/> :384
*** Events (762L) — OUTBOUND EVENT WEBHOOKS = THE AUDIT/SIEM INTEGRATION POINT. getEvents(catalog),
  get/create/update/deleteEventWebhook :7-16. Per-webhook: name,url,enabled,events[] (EXACT NAMES OR
  prefix.* GLOB, validated :209-220), targets — null=ALL USERS+SYSTEM, []=SYSTEM-ONLY, or explicit
  {type:'user'|'group',id} list :239-251 ***
Authentication (863L) — THREE INDEPENDENT CONFIG OBJECTS SAVED SEQUENTIALLY :98-107.
  Admin: DEFAULT_USER_ROLE, DEFAULT_GROUP_ID, ENABLE_SIGNUP, ENABLE_API_KEYS,
  ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS, API_KEYS_ALLOWED_ENDPOINTS, JWT_EXPIRES_IN, SHOW_ADMIN_DETAILS,
  ADMIN_EMAIL, PENDING_USER_OVERLAY_*.
  LDAP: ENABLE_LDAP, label/host/port/app_dn/app_dn_password/attribute_for_mail/attribute_for_username/
  search_base/search_filters/use_tls/validate_cert/certificate_path/ciphers + enable_group_management,
  enable_group_creation, attribute_for_groups (defaults memberOf, FORCED :65-67).
  OAuth/OIDC: ENABLE_OAUTH, OAUTH_PROVIDER_NAME, OPENID_PROVIDER_URL, OAUTH_CLIENT_ID/SECRET,
  OPENID_REDIRECT_URI, OAUTH_SCOPES, OAUTH_EMAIL/USERNAME/PICTURE/SUB_CLAIM, ENABLE_OAUTH_SIGNUP,
  OAUTH_MERGE_ACCOUNTS_BY_EMAIL, OAUTH_AUTO_REDIRECT, OAUTH_ALLOWED_DOMAINS,
  ENABLE_OAUTH_ROLE_MANAGEMENT+OAUTH_ROLES_CLAIM/ADMIN_ROLES/ALLOWED_ROLES,
  ENABLE_OAUTH_GROUP_MANAGEMENT+GROUP_CREATION/GROUP_CLAIM/BLOCKED_GROUPS,
  OAUTH_UPDATE_EMAIL/NAME/PICTURE_ON_LOGIN.
  *** GOVERNANCE GOTCHA: THE WHOLE OAUTH FIELDSET IS DISABLED WHEN ENABLE_OAUTH_PERSISTENT_CONFIG IS FALSE
  :52,:543 — ENV VARS THEN WIN. ***
Connections (437L) — see below. Models (1261L) — see below.
Subagents — ENABLE_SUBAGENTS, SUBAGENTS_BACKGROUND_ENABLED, MAX_CONCURRENT, MAX_ASYNC, MAX_ITERATIONS,
  MAX_OUTPUT, SYSTEM_PROMPT :41-49
Evaluations — ENABLE_EVALUATION_ARENA_MODELS + EVALUATION_ARENA_MODELS[] :43-81
Integrations (334L) — TOOL_SERVER_CONNECTIONS :63 | TERMINAL_SERVER_CONNECTIONS :76 each
  {id,url,name,key,enabled,contexts,config} mirrored into terminalServers store :88-100 | <ExternalKnowledge/> :315
ExternalKnowledge (888L) — externally-hosted vector stores as KBs. Providers qdrant|milvus|pgvector w/
  per-provider schemaDefaults :90-119. Connection {name,provider,endpoint,auth_config:{type:'bearer',
  api_key},config:{timeout,db_name},capabilities:{retrieve:true},enabled} :214-237; source {type:
  'collection',name,config:{content_field,vector_field,metadata_field,document_id_field,table_name,
  collection_field}} :239-261. *** A PASSING TEST IS MANDATORY BEFORE CREATE/SAVE :308,:344, disabled
  submit :784. *** AccessControl w/ accessRoles=['read'] :770-776
Documents (1600L, LARGEST PANE) — RAG + embedding. CONTENT_EXTRACTION_ENGINE (''|external|tika|docling|
  datalab_marker|document_intelligence|mistral_ocr|paddleocr_vl|mineru) + per-engine keys; PDF_EXTRACT_IMAGES,
  PDF_LOADER_MODE, CONTENT_EXTRACTION_SUPPORTED_MEDIA_MIME_TYPES. Chunking: BYPASS_EMBEDDING_AND_RETRIEVAL,
  TEXT_SPLITTER, RAG_TOKENIZER_MODEL, ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER, CHUNK_SIZE/OVERLAP/
  MIN_SIZE_TARGET. Embedding: RAG_EMBEDDING_ENGINE(''|ollama|openai|azure_openai), MODEL, BATCH_SIZE,
  ENABLE_ASYNC_EMBEDDING, CONCURRENT_REQUESTS + nested openai_config/ollama_config/azure_openai_config
  {key,url,version} :133-149. Retrieval: RAG_FULL_CONTEXT, ENABLE_RAG_HYBRID_SEARCH, ENRICHED_TEXTS,
  RAG_RERANKING_ENGINE, EXTERNAL_RERANKER_URL/API_KEY, RERANKING_MODEL/BATCH_SIZE, TOP_K, TOP_K_RERANKER,
  RELEVANCE_THRESHOLD, HYBRID_BM25_WEIGHT, RAG_TEMPLATE. Files: ALLOWED_FILE_EXTENSIONS, FILE_MAX_SIZE/
  COUNT, FILE_IMAGE_COMPRESSION_WIDTH/HEIGHT. DANGER ZONE: deleteAllFiles, resetVectorDB, reindex*.
WebSearch (1437L) — writes the `web` sub-object :100. 30 ENGINES :20-51 + per-engine credentials.
  *** WEB_SEARCH_DOMAIN_FILTER_LIST (comma list, ! prefix excludes) = THE DATA-EGRESS ALLOWLIST. ***
  BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL, BYPASS_WEB_SEARCH_WEB_LOADER, WEB_SEARCH_TRUST_ENV.
  Loader: WEB_LOADER_ENGINE(playwright|firecrawl|tavily|microsoft_web_iq|external), timeouts, SSL verify.
CodeExecution — ENABLE_CODE_EXECUTION, ENGINE(pyodide|jupyter), JUPYTER_URL/AUTH/TOKEN/PASSWORD/TIMEOUT +
  mirrored ENABLE_CODE_INTERPRETER, CODE_INTERPRETER_*. Jupyter FLAGGED AS ARBITRARY CODE EXECUTION :66,:170
Interface (582L) — WRITES *TWO* CONFIGS IN PARALLEL (updateTaskConfig + updateChatConfig :70-73).
  Task: TASK_MODEL, TASK_MODEL_EXTERNAL, TASK_MODEL_PARAMS, ENABLE_TITLE_GENERATION+template,
  FOLLOW_UP, IMAGE_PROMPT, AUTOCOMPLETE(+INPUT_MAX_LENGTH), TAGS, SEARCH_QUERY, RETRIEVAL_QUERY,
  QUERY_GENERATION_PROMPT_TEMPLATE, TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE, VOICE_MODE.
  Chat: ENABLE_TOOL_PERMISSIONS, ENABLE_CONTEXT_COMPACTION, COMPACTION_MODEL/TOKEN_THRESHOLD/TOKEN_CAP/
  RETENTION_PERCENTAGE/PROMPT_TEMPLATE. normalizeModelSelection :93-113 WARNS BUT DOES NOT BLOCK when a
  non-public model is chosen as a task model.
Audio (734L) — {tts:{...},stt:{...}} :146-180. TTS ENGINE ''|transformers|openai|elevenlabs|azure|mistral.
  STT ENGINE ''|openai|web|deepgram|azure|mistral + WHISPER_MODEL etc.
Images (1004L) — IMAGE_GENERATION_ENGINE openai|comfyui|automatic1111|gemini + edit variants. ComfyUI node
  maps BUILT AT SAVE TIME from REQUIRED_WORKFLOW_NODES :41-72 / REQUIRED_EDIT_WORKFLOW_NODES :75-101
Pipelines (486L) — only rendered when a Pipelines server is reachable. Valve widgets GENERATED FROM THE
  JSON-SCHEMA properties (enum->select, boolean->switch, else text) :392-442
Database — importConfig/exportConfig (FULL ADMIN CONFIG JSON ROUND-TRIP), downloadDatabase, getAllUserChats
  ->JSON, getAllUsers->CSV. Gated on $config.features.enable_admin_export :121

## USERS & GROUPS
Users.svelte two-tab shell (overview|groups) driven by pathname :17-21, client-side role redirect :61-63,
shows SEAT USAGE against $config.license_metadata.seats :40-47
UserList (544L) paginated perPage=30, SERVER-SIDE search/sort getUsers(token,query,orderBy,direction,page)
  :99. Row actions: chats (gated enable_admin_chat_access :404), *** Preview Access UserPreviewModal :420 ***,
  edit, delete. Admin rows CANNOT be deleted or previewed :419,:447.
AddUserModal (343L) single form or CSV import (Name,Email,Password,Role) BATCHED 10 AT A TIME :94-119
EditUserModal (256L) + read-only OAuth sub ids :187-200 + group chips. SELF-DEMOTION BLOCKED CLIENT-SIDE ONLY :145
UserPreviewModal (175L) getUserPreview returns effective accessible groups/models/knowledge/tools w/ totals
  — *** THE CLOSEST THING TO AN ACCESS-REVIEW REPORT ***
Groups (245L) list + a distinguished "Default permissions" entry :207-233 opening EditGroupModal w/
  custom=false, tabs=['permissions'], writing updateUserDefaultPermissions :87
Groups/General.svelte holds name, description, data.config.share (false|'members'|true — WHO MAY SHARE
  *INTO* THIS GROUP) :79-98
Groups/Users.svelte (516L) membership checkboxes, sorts by SYNTHETIC KEY group_id:<id> :99, CSV import by
  email parseCsvRows :65-84
EditGroupModal (386L) IS THE MERGE POINT: init() :86-104 AND resetToDefaultsHandler() :63-84 BOTH REBUILD
  permissions BY OVERLAYING THE STORED OBJECT ONTO DEFAULT_PERMISSIONS PER TOP-LEVEL BUCKET, SO ABSENT
  KEYS SILENTLY TAKE THE COMPILED-IN DEFAULT.

## *** PERMISSIONS MATRIX — COMPLETE (Users/Groups/Permissions.svelte 1194L; defaults
## src/lib/constants/permissions.ts). fillMissingProperties :19-30 merges SIX BUCKETS.
## NESTED TOGGLES ONLY RENDER WHILE THEIR PARENT IS ON. WHEN A TOGGLE IS OFF BUT THE *DEFAULT* IS ON THE
## UI PRINTS "This is a default user permission and will remain enabled" — i.e.
## **GROUP PERMISSIONS ARE ADDITIVE OVER DEFAULTS, THEY CANNOT REVOKE.** ***
workspace.* (all default FALSE) — models -> models_import, models_export | knowledge |
  prompts -> prompts_import, prompts_export | tools -> tools_import, tools_export (ONLY shown when
  $config.features.enable_plugins :141; tooltip warns "upload arbitrary code on the server") |
  skills -> skills_import, skills_export (same warning :190)
sharing.* (all FALSE) — models->public_models | knowledge->public_knowledge | prompts->public_prompts |
  tools->public_tools | skills->public_skills | notes->public_notes | folders | public_chats and
  open_chats (only when chat.share is on :478) | public_calendars (only when features.calendar :518).
  The public_* pair is the "MAY PUBLISH TO EVERYONE" gate DISTINCT FROM "may share at all".
access_grants.* (both default TRUE) — allow_users, allow_groups. THESE GATE THE AccessControl PICKER EVERYWHERE.
chat.* (all TRUE except temporary_enforced:false) — file_upload, web_upload, controls -> valves,
  system_prompt, params | edit, delete, delete_message, continue_response, regenerate_response,
  rate_response, share, export, import, stt, tts, call, multiple_models, temporary -> temporary_enforced
  (*** FORCES EVERY CHAT EPHEMERAL — THE RETENTION/DLP LEVER ***)
features.* — api_keys(false), notes(true), channels(true), folders(true), direct_tool_servers(false —
  lets users register THEIR OWN OpenAPI tool servers), web_search(true), image_generation(true),
  code_interpreter(true), memories(true), automations(false, warned "run scheduled prompts automatically"),
  calendar(true), webhooks(false)
settings.* — interface(true) — whether a user may open personal interface settings (SettingsModal.svelte:812)

## CONNECTIONS
FOUR PARALLEL ARRAYS: OPENAI_API_BASE_URLS[], OPENAI_API_KEYS[], OPENAI_API_CONFIGS{} INDEXED BY *POSITION*
(legacy URL-keyed fallback :186-190) + OLLAMA_BASE_URLS[]/OLLAMA_API_CONFIGS{} (Ollama stores its key
*INSIDE* the config object :148-151).
updateOpenAIHandler :56-91 trims trailing slashes and PADS/TRUNCATES THE KEY ARRAY TO MATCH THE URL ARRAY
— *** A LENGTH MISMATCH SILENTLY DROPS KEYS. *** Deleting a connection RE-INDEXES CONFIGS BY SHIFTING
:286-292 — *** CONFIG OBJECTS ARE POSITIONAL, SO AN OUT-OF-BAND REORDER RE-ASSOCIATES API KEYS WITH THE
WRONG ENDPOINT. ***
Pipeline-backed OpenAI endpoints detected by probing getOpenAIModels(idx) for a `pipelines` field :197-200.
User Connections section: ENABLE_DIRECT_CONNECTIONS + ENABLE_BASE_MODELS_CACHE + manual refresh :125.
Keys use SensitiveInput BUT ARE RETURNED IN CLEARTEXT BY THE GET ENDPOINTS.

## MODELS ADMIN
init() :255-318 merges THREE SOURCES: getModelsConfig (order/defaults), getBaseModels(token,selectedTag),
getModels() + getModels(...,true) (live provider catalogs), then JOINS base-model records onto provider
records by id :282-301. Anything not in baseModels is SYNTHESISED with is_active:true.
VISIBILITY/ACCESS isPublicModel :114-118 tests for an access grant {principal_type:'user',principal_id:'*',
  permission:'read'}; isSharedModel = any grants but not public. toggleModelPrivacyHandler :554-589 adds or
  clears that WILDCARD GRANT via updateModelAccessGrants.
  *** SEPARATE FROM ACCESS: meta.hidden (hide from pickers, hideModelHandler :525) and is_active
  (enable/disable, toggleModelHandler :499). THREE ORTHOGONAL AXES. ***
ORDERING drag-to-reorder w/ SortableJS, ONLY ALLOWED WHEN NO SEARCH/FILTER/TAG IS ACTIVE
  (canReorderModels :179); persisted as MODEL_ORDER_LIST + DEFAULT_MODELS (comma string) +
  DEFAULT_PINNED_MODELS via setModelsConfig :320-347,:363-392
BASE-MODEL DERIVATION isPresetModel :122-123 = preset || base_model_id || info.base_model_id. Preset models
  open /workspace/models/edit; raw provider models open the INLINE ModelEditor :1241. upsertModelHandler
  :468 FORCIBLY SETS base_model_id:null for non-presets — that's how a bare provider id gets a persisted
  workspace record on first edit. cloneHandler :617 sets base_model_id = source.id.
ModelDefaultsPanel (251L) writes DEFAULT_MODEL_METADATA {capabilities,defaultFeatureIds,builtinTools} +
  DEFAULT_MODEL_PARAMS + setDefaultPromptSuggestions. Dirty tracking SNAPSHOT-BASED getSnapshot :44-51
MODEL MANAGEMENT ManageModelsModal picks Ollama or "model providers" (ONLY llama.cpp and lmstudio,
  MANAGEMENT_PROVIDERS :24). ManageOllama (1147L) pull/update-all/delete/create/GGUF-upload w/ streamed
  NDJSON progress and a 3-DOWNLOAD CAP :45.

## EVALUATIONS / ANALYTICS
Leaderboard (265L) getLeaderboard merges Elo entries w/ $models, SYNTHESISING ROWS FOR MODELS THAT NO
  LONGER EXIST :68-80. LeaderboardModal -> getModelHistory(model,days) -> ModelActivityChart (DIVERGING
  Chart.js bar, wins up/losses down, WEEKLY AGGREGATION FOR 1Y/All :33-55)
Feedbacks (522L) paginates getFeedbackItems, filters by getFeedbackModelIds, exports JSON or CSV
  (feedbacksToCsv :157-187 — id/user_id/chat_id/model_id/sibling_model_ids/rating/reason/comment/
  created_at/updated_at). FeedbackModal reconstructs the prompt/response pair FROM THE STORED CHAT
  SNAPSHOT :76-98
Analytics/Dashboard (626L) READ-ONLY: getSummary, getModelAnalytics, getUserAnalytics(limit 50),
  getDailyStats(granularity), getTokenUsage, each taking (start,end,groupId) — *** THE GROUP FILTER IS
  THE MULTI-TENANT SLICE :123-127 ***. Period persists in localStorage.
  ChartLine.svelte is a HAND-ROLLED SVG multi-series line chart written IN SVELTE 5 RUNES ($props,$state,
  $derived :12-18) — *** THE ONLY RUNE-BASED FILE IN THE DIRECTORY, A LIVE MIGRATION HAZARD. ***

## EXTENSION POINTS
ADD A SETTINGS PANE: component under Settings/, import in SettingsModal.svelte ~:41-56, entry in
  adminSettings :679, group in adminSettingGroups :152, icon branch in AdminTabIcon.svelte:22.
  *** THERE IS NO REGISTRY FILE — FOUR EDITS IN TWO FILES. ***
ADD A PERMISSION: key in src/lib/constants/permissions.ts (*** A NEW *BUCKET* ADDITIONALLY NEEDS A LINE IN
  fillMissingProperties Permissions.svelte:23-28 **AND** IN BOTH OVERLAY BLOCKS OF EditGroupModal.svelte
  :72-78/:93-98, OR IT WILL BE DROPPED ON SAVE ***), then the Switch block. Consumers read
  $user.permissions.<bucket>.<key>.

## GOTCHAS
- CONFIG ROUND-TRIP: each pane GETs its own config on mount, mutates a local object, PUTs the whole thing.
  Several do LOSSY string<->array/JSON conversions at the boundary (ALLOWED_FILE_EXTENSIONS,
  WEB_SEARCH_DOMAIN_FILTER_LIST, DOCLING_PARAMS, LINKUP_SEARCH_PARAMS, *_OPENAI_PARAMS...).
  CLEARED NUMBER INPUTS BECOME null AND ARE COERCED TO '' so the backend can distinguish "clear" from
  "unchanged" Documents.svelte:265-270. Authentication and Interface ISSUE MULTIPLE PUTs PER SAVE —
  *** A PARTIAL FAILURE LEAVES THE INSTANCE HALF-CONFIGURED WITH ONLY A TOAST. ***
- *** ADMIN-ONLY ENFORCEMENT IS CLIENT-SIDE ONLY. +layout.svelte:16-18, Users.svelte:61, Groups.svelte:101,
  Analytics.svelte:13 ALL JUST goto('/'). Several panes SKIP THEIR FETCH ENTIRELY when role!=='admin'
  (Connections:157, Images:222, Evaluations:84, ManageModelsModal:35) RATHER THAN FAILING CLOSED.
  Individual controls are hidden the same way. EVERY GUARANTEE MUST BE RE-ASSERTED SERVER-SIDE. ***
- HYBRID_BM25_WEIGHT and pipeline valves use a null SENTINEL for "use default" Documents:1369, Pipelines:402
- BULK MODEL OPS issue N REQUESTS with NO TRANSACTIONALITY OR RATE LIMITING Models.svelte:186
- ADMIN BULK EXPORTS — all chats JSON, all users CSV, FULL CONFIG JSON, all feedback CSV — LIVE BEHIND
  PLAIN BUTTONS WITH NO CONFIRMATION, and *** EXPORTED CONFIG INCLUDES PROVIDER CREDENTIALS. ***
- Functions and Pipelines both EXECUTE ARBITRARY PYTHON; the only barrier is an ACKNOWLEDGMENT DIALOG
  Functions.svelte:816-832, FunctionEditor.svelte:500
- *** GROUP PERMISSIONS CAN ONLY *ADD* CAPABILITY OVER THE DEFAULTS, so GENUINE LEAST-PRIVILEGE REQUIRES
  EDITING THE GLOBAL DEFAULT PERMISSION SET FIRST. ***
