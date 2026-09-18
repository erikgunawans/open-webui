# utils A — middleware.py(6400) oauth.py(2425) tools.py misc.py anthropic.py automations.py subagents.py auth.py
# *** THE REQUEST-PATH CORE. MOST IMPORTANT BACKEND AREA. ***

## THE PIVOTAL FACT: TWO MESSAGE REPRESENTATIONS
Storage + frontend speak Responses-API-style `output` items:
  message | reasoning | function_call | function_call_output | open_webui:code_interpreter
Providers speak OpenAI Chat Completions messages.
BRIDGE: convert_output_to_messages misc.py:325 and process_messages_with_output middleware.py:2203
NEARLY EVERY SUBTLE BUG CLASS LIVES AT THIS SEAM.

## PHASE A — process_chat_payload middleware.py:2365 (ORDER IS LOAD-BEARING, documented :2370)
1 ARENA :2377 — owned_by=='arena' picks random sub-model FIRST so downstream capability/tool/param logic
  uses the real model
2 PARAMS apply_params_to_form_data :2406 pops params; model system prompt captured :2404 BEFORE the pop,
  resolved later :3062
3 HISTORY REHYDRATION :2417-2453 — for saved chats payload messages are DISCARDED and rebuilt from DB via
  load_messages_from_db :2162 (whitelist MESSAGE_REPLAY_KEYS :2159). REASON: frontend strips structured
  `output`, which would collapse tool calls into prose. Image files re-inflated to image_url parts :2431
4 CONTEXT COMPACTION :2471 compact_messages_for_request; summary appended as system message
5 NORMALIZATION — reasoning_details STRIPPED when replayed assistant msg came from a DIFFERENT model :2494
  (provider-bound signatures); then process_messages_with_output :2497 flattens output->messages;
  sanitize_tool_pairs :2501 drops orphan tool_calls/results that STRICT PROVIDERS (Anthropic, Bedrock) reject
6 extra_params :2517 UNIVERSAL INJECTION BAG: __event_emitter__ __event_call__ __user__ __metadata__
  __oauth_token__ __request__ __model__ __chat_id__ __message_id__
7 FOLDER("Project") CONTEXT :2547-2576 — folder system prompt; folder files either RAG-injected (legacy FC)
  or exposed as metadata['folder_knowledge'] for builtin tools (native FC)
8 MODEL KNOWLEDGE :2578 legacy FC only; appends collections to form_data['files']
9 PIPELINE INLET :2625 then FUNCTION INLET FILTERS :2635
10 FEATURE FLAGS :2646-2720 — `features` POPPED from body and RE-AUTHORIZED SERVER-SIDE (it is CLIENT-SUPPLIED):
   voice :2649 | memory :2660 + has_permission('features.memories') | web search :2669 ->
   chat_web_search_handler :1500 ONLY under function_calling=='legacy' | image gen :2680 -> :1768 |
   code interpreter :2691 (legacy injects XML-tag prompt; native appends ONLY pyodide filesystem note to
   the SYSTEM message TO PRESERVE PREFIX CACHING)
11 SKILLS :2731-2807 — <$skillId|label> mentions extracted :2284; mentioned skills inlined as <skill> system
   blocks; unmentioned become <available_skills> manifest loadable via view_skill builtin. Mentions stripped
   :2296 w/ empty-prompt guard :2815
12 TOOL RESOLUTION :2845-3045 — SKIPPED ENTIRELY if caller supplied `tools` in body. Branches:
   server:mcp:* -> connect_mcp_server :2314 (access-checked, name-filtered, namespaced {server_id}_{name});
   DB tools -> get_tools tools.py:269; terminal tools -> get_terminal_tools tools.py:1357 (failure = 503);
   client-side "direct" tool servers :2959; builtins -> get_builtin_tools tools.py:522 GATED ON session_id
   PRESENCE so API callers get NO hidden tools :2984.
   Resolved tools ALWAYS land in metadata['tools'] :3028.
   NATIVE FC emits form_data['tools'] specs :3032. LEGACY FC instead runs chat_completion_tools_handler :1280
   — a SEPARATE LLM CALL returning JSON tool calls, executed inline, results converted to RAG sources.
13 RAG :3050 chat_completion_files_handler :1989 — generates retrieval queries, get_sources_from_items w/
   top_k/reranker/hybrid, emits sources_retrieved status
14 PRE-RAG SNAPSHOT :3060-3073 — metadata['system_prompt'],['user_prompt'],['sources'] captured BEFORE
   injection so the tool loop can later RESTORE and avoid duplicating the RAG template
15 INJECTION :3076 -> apply_source_context_to_messages :968 wraps docs in <source id= name=> via rag_template,
   into system (RAG_SYSTEM_CONTEXT) or user message
16 `request` FILTERS :3102, then normalize_messages_for_model :190 = strip empty content blocks +
   MERGE ALL SYSTEM MESSAGES INTO ONE AT INDEX 0

## PHASE B — process_chat_response :6387 forks 3 ways: non-streaming :4033 | non-SSE passthrough | streaming :4217
streaming+emitter runs response_handler :4257 as BACKGROUND TASK. stream_body_handler :4673 is SSE consumer:
- every data: line JSON-decoded and passed through STREAM FILTERS :4841 BEFORE interpretation
- response.* events -> handle_responses_streaming_event :599 (near-pure reducer over output list handling
  output_item.added, content_part.added, generic *.delta w/ deep_merge :561, *.done, response.completed)
- Chat-Completions deltas SYNTHESIZED INTO THE SAME output SHAPE: reasoning :5197, message :5276,
  streaming function_call emitted as response.output_item.added / function_call_arguments.delta :5075-5142
  SO THE FRONTEND SEES ONE PROTOCOL
- DELTA COALESCING :4735-4798 same-key string deltas concatenated, flushed every
  CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE; each flush also writes Redis via save_response_stream.
  TOKENS ARE NOT WRITTEN TO DB MID-STREAM :6249
- TAG SCANNING tag_output_handler :4263 detects <think>/<code_interpreter>/<|begin_of_solution|> using
  CACHED SCAN POSITIONS :4299, converts to typed output items
- URL citations from annotations (Responses :4883, ChatCompletions :4995) emitted as source events
TOOL-CALL LOOP :5576-6042 bounded by CHAT_RESPONSE_MAX_TOOL_CALL_ITERATIONS (per-request override :5552):
  ask_user staging :5582 | tool_approval_mode=='ask' pause :5619 -> pause_for_tool_approval :3438 |
  execute_tool_call :5671 SEQUENTIAL except delegate_task which runs asyncio.gather :5711 |
  function_call_output appended :5823 w/ images split input_image (for LLM) vs files (for display) :5812 |
  citation sources extracted for WHITELIST OF SIX builtins :5770 |
  RAG context RESTORED to pre-RAG state and RE-APPLIED w/ tool sources as content-free citation markers
  :5845-5904 | input_image parts stripped from frontend copy :5909 |
  continuation generate_chat_completion(...,bypass_system_prompt=True) :5994 |
  on new stream accumulated output moved to prior_output and output RESET so Responses output_index
  values stay aligned :6008
CODE-INTERPRETER LOOP :6044-6232 legacy-FC analogue, up to 5 retries via pyodide(event_caller) or Jupyter,
  rewriting base64 images to URLs
FINALIZATION :6234-6279 mark in-progress complete, SINGLE DB WRITE, clear Redis stream,
  publish_chat_finished_event :196, then outlet_filter_handler :3872, background_tasks_handler :3654

## PHASE C — background_tasks_handler :3654
strips <details> blocks + images from history, then follow-ups :3711, TITLE :3762 (fallback to first message
when model returns nothing and chat has <=2 messages :3812), TAGS :3824, review_memory_after_turn :3861
ALL THREE parse JSON by slicing between first { and last } — RECURRING FRAGILE IDIOM

## FILTERS — 4 types: inlet, request, stream, outlet
resolve_filter_pipeline filter.py:68 = global filters UNION model.info.meta.filterIds, intersect active,
filter by toggle state vs user-enabled :76-85, SORT BY Valves.priority ASC w/ filter id tiebreak :103
ERROR ISOLATION IS WEAK BY DESIGN: process_filter_function :165 logs and RE-RAISES :205.
  Failing inlet or request filter ABORTS THE WHOLE REQUEST :2643,:3112.
  In stream path exceptions SWALLOWED by per-line except :5449.
inlet filter w/ file_handler=True => files DELETED from body and metadata filter.py:244
OUTLET RUNS INLINE :3872 (replaced old POST /api/chat/completed round trip). Deep-copies output so in-place
  filter mutation doesn't alias DB baseline :3954, diffs content/output, persists originalContent, emits
  chat:outlet. Early-returns when no filters :3908. API/temp chats gated behind ENABLE_API_OUTLET_FILTERS :4202,:6325

## TOOL CALLING
SPECS by introspection: docstring->description parse_description tools.py:805 | :param lines->property
descriptions parse_docstring :831 | type hints->Pydantic convert_function_to_pydantic_model :869 ->
OpenAI function spec | clean_openai_tool_schema :941 collapses anyOf-with-null, fills missing types.
Builtin specs cached as JSON and RE-PARSED PER CALL because callers mutate them :993.
PARAMS STARTING __ ARE STRIPPED FROM SPECS :333 — that's the injection convention.
CALLABLES get_async_tool_function_and_apply_extra_params tools.py:191 — functools.partial the __ extras in,
  REWRITES __signature__ to hide them (needed by python-genai), coerces str<->int mismatches, stashes
  __function__/__extra_params__ so get_updated_tool_function :255 rebuilds w/ fresh __messages__/__files__
  at call time middleware.py:5699
INVOCATION: args parsed JSON w/ ast.literal_eval fallback :5656, FILTERED TO DECLARED PROPERTIES ONLY :5683
  (undeclared args SILENTLY DROPPED), then event_caller('execute:tool') for direct/client tools or the callable.
  Results normalize process_tool_result :1006 (HTMLResponse inline embeds, (data,headers) tuples w/
  Content-Disposition inline, MCP content arrays text/image/audio/resource, base64 data URIs).
  _split_tool_calls :334 splits concatenated JSON arg objects some models emit under one index.
  Results feed back via function_call_output -> convert_output_to_messages -> role:tool messages,
  flatten_tool_images moves images to a TRAILING USER MESSAGE for ChatCompletions providers :5950
TOOL-NAME COLLISIONS resolved by prefixing {tool_id}_{name} tools.py:367, {server_id}_{name} :473 —
  THE NAME THE MODEL SEES MAY DIFFER FROM THE UNDERLYING FUNCTION

## AUTH
auth.py: create_token :229 HS256 + jti + iat | is_valid_token :251 DUAL REVOCATION: per-jti keys AND
  per-user revoked_at watermark rejecting iat<=revoked_at (password change, OIDC back-channel logout).
  BOTH REQUIRE REDIS — without it revoke_user_tokens :307 LOGS A WARNING AND DOES NOTHING.
  get_current_user :347 resolves bearer -> cookie -> request.state.token, dispatches sk-* to
  get_current_user_by_api_key :461 which re-checks auth.enable_api_keys, features.api_keys permission,
  and endpoint allowlists using the RAW ASGI PATH request.scope['path'] :496
  (explicitly NOT spoofable via Host — CVE-2026-48710).
  Family: get_verified_user :522, get_admin_user :577, non-Depends variants for WebSocket handshakes :531,
  optional resolution :555.
  PASSWORDS argon2 or bcrypt in asyncio.to_thread; bcrypt input TRUNCATED to 72 bytes :215 while NEW
  passwords over 72 bytes are REJECTED :189
oauth.py TWO MANAGERS:
  OAuthClientManager :816 per-tool-server OAuth 2.1: RFC 9728 protected-resource discovery :377,
    RFC 8414 well-known probing :457, dynamic client registration :490 or static creds :634,
    PKCE S256 default :852, client info Fernet-encrypted at rest :265. Fails fast when no
    authorization_endpoint discoverable :563; passes endpoints EXPLICITLY to authlib as defense-in-depth :844
  OAuthManager :1317 SSO: handle_login :1828 | handle_callback :1850 merges ID-token claims UNDER userinfo
    claims :1902-1916, extracts sub/email (GitHub email fallback :1945), enforces OAUTH_ALLOWED_DOMAINS,
    JIT-provisions via Auths.insert_new_auth :2095 w/ random password, promoting to admin ONLY AFTER insert
    when get_num_users()==1 :2111 (TOCTOU-safe).
    ROLE MAPPING get_user_role :1507 reads dot-path nested claim; IF ROLES PRESENT BUT MATCH NOTHING => 403.
    Absent roles PRESERVE existing role.
    GROUP MAPPING update_user_groups :1621 creates missing groups when enabled, REMOVES user from groups no
    longer in claim, adds new, honoring OAUTH_BLOCKED_GROUPS w/ exact/regex/fnmatch :313
    BACK-CHANNEL LOGOUT :2240 fully validates logout_token (kid->JWKS->aud/iss, REQUIRES events claim,
    REJECTS nonce) then deletes sessions + sets revocation watermark.
    TOKEN REFRESH DUPLICATED across both managers :1096,:1424 and A FAILED REFRESH DELETES THE SESSION
    :1061,:1388 — MCP-provider guard :1367,:3642 exists precisely because cross-manager refresh used to
    destroy sessions (#24618)

## EXTENSION POINTS (enterprise)
- FILTER FUNCTIONS (inlet/request/stream/outlet) = ONLY SUPPORTED IN-TREE HOOK. inlet/request raising
  ABORTS the request so a policy filter can HARD-BLOCK. Priority ordering filter.py:103 lets a governance
  filter run first or last deterministically.
- process_chat_payload EXIT AT :3115 = LAST POINT where the full resolved payload (messages, tools, sources,
  metadata) exists before the provider call. DLP/redaction/prompt-injection gate belongs HERE or in a
  max-priority `request` filter.
- TOOL GATING get_builtin_tools tools.py:522 already threads FIVE-WAY authorization (builtinTools category x
  global config x model capability x feature flag x user permission). Adding an org policy dimension here
  covers every builtin at once. metadata['tools'] :3028 = single registry. execute_tool_call :5671 =
  SINGLE EXECUTION CHOKEPOINT for allow/deny/audit.
- TOOL APPROVAL tool_approval_mode :5619,:3264 = WORKING human-in-the-loop primitive; enterprise build would
  key it off TOOL RISK CLASS instead of a global mode.
- AUTH PROVIDERS OAUTH_PROVIDERS registration oauth.py:1324 accepts arbitrary authlib clients;
  claim->role/group mapping fully config-driven :131. get_current_user auth.py:347 = THE ONE DEPENDENCY TO
  WRAP for mTLS/SAML/header-trust. WEBUI_AUTH_TRUSTED_EMAIL_HEADER :415 existing reverse-proxy trust hook.
- EGRESS CONTROL build_tool_server_headers tools.py:127 and execute_tool_server :1622 = ONLY outbound tool
  paths. is_host_allowed misc.py:153 already implements label-boundary + CIDR allow/block = right primitive.
- AUDIT publish_event/EVENTS used consistently (chat finished/failed, user created/updated/role,
  group membership, automation runs, auth login)
- *** HEADLESS RE-ENTRY: automations.py:_build_request :276 and subagents.py:_build_request :47 FORGE a
  synthetic Request w/ a MINTED JWT and call app.state.CHAT_COMPLETION_HANDLER.
  ANY POLICY THAT LIVES IN HTTP MIDDLEWARE RATHER THAN IN THE PIPELINE WILL NOT RUN FOR THESE PATHS. ***

## GOTCHAS
- SHARED-PAYLOAD MUTATION: form_data, messages, metadata, output mutated IN PLACE across ~15 stages.
  add_or_update_system_message misc.py:682 mutates AND returns the same list. Filters receive LIVE form_data.
  Tool loop rewrites form_data['messages'] :5857 and restores system content BY REPLACEMENT :5863.
  drain_approved_tool_calls does form_data.clear(); form_data.update(...) :3427 TO PRESERVE IDENTITY across
  a filter that returned a new dict.
- metadata CARRIES NON-SERIALIZABLE OBJECTS — tools (callables), mcp_clients (live connections).
  sanitize_metadata misc.py:947 exists SOLELY to strip these before any JSON/DB write; forgetting it causes
  POSTGRES INSERT FAILURES.
- TWO EVENT CHANNELS DIFFERENT REQUIREMENTS: event_emitter needs only chat_id+message_id and persists to DB
  (WORKS HEADLESS). event_caller needs session_id and round-trips to a LIVE WEBSOCKET — direct tools and
  pyodide SILENTLY DEGRADE without it :3187. get_event_emitter_and_caller :3120
- EVERYTHING DOWNSTREAM OF THE EMITTER IS FIRE-AND-FORGET. Whole streaming handler is a background task;
  errors surface ONLY as chat:message:error events.
- BROAD except SWALLOWING: outlet_filter_handler wraps entire body in except Exception: log.debug :4029.
  Per-SSE-line handler does `continue` on any exception :5449. apply_system_prompt_to_body failures
  silently passed :2509.
- prior_output/output SPLIT IS SUBTLE: Responses output_index is relative to the CURRENT response, so the
  loop REBASES indices (get_response_data_with_full_output_index :4727) and RESETS output per continuation
  :6020. OFF-BY-ONE HERE PRODUCES DUPLICATED OR GHOST UI ITEMS.
- LEGACY VS NATIVE FUNCTION CALLING FORKS NEARLY EVERY FEATURE. metadata.params.function_calling=='legacy'
  changes web search, image gen, code interpreter, knowledge, folder-file handling.
  ANY NEW FEATURE MUST BE IMPLEMENTED TWICE OR EXPLICITLY SCOPED.
- `features` IS CLIENT-SUPPLIED and each consumer re-checks permissions INDEPENDENTLY :2660,:2669,:2680,
  tools.py:678. A NEW FEATURE THAT FORGETS THE RE-CHECK IS A PRIVILEGE ESCALATION.
- JSON EXTRACTION BY BRACE-SLICING content[find('{'):rfind('}')+1] in title, tags, follow-ups, queries,
  image prompts. BREAKS ON PROSE CONTAINING BRACES.
- REASONING REPLAY IS PROVIDER-BOUND: reasoning_details dropped when model differs :2494; Anthropic-format
  details WITHOUT a signature filtered out misc.py:520
- CONCURRENCY: subagent limits use PROCESS-LOCAL asyncio.Semaphore + module-level set subagents.py:41-44 —
  DO NOT HOLD ACROSS WORKERS OR INSTANCES. Parent-chat serialization _parent_locks :44 also process-local,
  backed by Postgres SELECT...FOR UPDATE :92 for the DB-level race.
- asyncio.create_task(Users.update_last_active_by_id(...)) auth.py:436 is UNAWAITED AND UNREFERENCED —
  COLLECTIBLE MID-FLIGHT — and fires on EVERY authenticated request.
- Scheduler runs on EVERY INSTANCE automations.py:211 w/ random jitter + DB-level claim_due for exclusion;
  calendar alert dedup is meta.alerted_at in DB not in-memory.
