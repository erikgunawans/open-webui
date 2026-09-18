# utils B — 51 files, ~10.4k lines. Policy+shaping between routers and models.
FORK CHARACTERISTIC: already migrated off upstream's access_control JSON blob onto first-class
access_grants relation. Old shape survives only as one-way migration fn + in-memory list for
config-driven resources.

## ACCESS CONTROL — EXACT SEMANTICS
PERMISSIONS (boolean feature flags):
  get_permissions access_control/__init__.py:32 deep-copies default_permissions, merges EVERY group's
  permissions dict MOST-PERMISSIVE-WINS (permissions[key] or value, :54), back-fills missing keys
  fill_missing_permissions :18
  has_permission :72 takes dot path ('access_grants.allow_groups'), splits :94, returns True if ANY
  group grants :99-101; only if NO group does does it fall back to default_permissions merged with
  DEFAULT_USER_PERMISSIONS :104. MISSING KEY AT ANY LEVEL => DENY :88-89.
  *** NO ADMIN BYPASS HERE — has_permission treats admins like anyone else. Admin bypass lives at
  the CALL SITES. ***
GRANTS (resource ACLs):
  has_access :108 is the IN-MEMORY variant, used ONLY for config-driven resources storing grants as
  JSON rather than the grant table (arena models, tool servers) — docstring says so :117-119.
  empty/None => DENY (private, owner-only) :126
  grant matches when permission EXACTLY EQUAL :136 — READ DOES NOT IMPLY WRITE, WRITE DOES NOT IMPLY READ
  and either principal_type=='user' w/ id equal or literal '*' (public) :140, or 'group' w/ id in
  caller's group set :142. Group ids fetched lazily :129-131
CONNECTIONS has_connection_access :148: admin + BYPASS_ADMIN_ACCESS_CONTROL => True :163;
  *** NO GRANTS CONFIGURED => ADMIN-ONLY, NOT PUBLIC :166-171 — INVERSE of many "empty means open"
  conventions, DELIBERATE ***; else delegate to has_access with 'read'
LEGACY MIGRATION migrate_access_control :179 converts {read:{group_ids,user_ids},write:{...}} to flat
  grant list IN PLACE and deletes old key. Idempotent via grants_key in data early return :186
SHARE-SCOPE CLAMPING filter_allowed_access_grants :220 = WRITE-PATH GUARD: strips `anyone` grants unless
  admin or holds anyone_permission_key :236-248; admins return early :250; non-admins lose public
  (principal_id=='*') without public_permission_key :254-271, individual-user grants without
  access_grants.allow_users :274-280, group grants without access_grants.allow_groups :282-296.
  Every branch handles BOTH dict AND Pydantic-object grants.
MODEL ACCESS check_model_access access_control/__init__.py:345 raises 403 "Model not found" —
  DELIBERATELY INDISTINGUISHABLE FROM A REAL 404. bypass_filter short-circuits :365.
  Non-admins INCLUDING `pending` role :369-370 need ownership or model/read grant.
  has_base_model_access :301 walks base_model_id chain w/ `seen` CYCLE GUARD :324;
  *** AN UNREGISTERED BASE MODEL IS ADMIN-ONLY :328 — so a shared preset CANNOT LAUNDER ACCESS to a
  base model the caller couldn't use directly. ***
FILES has_access_to_file access_control/files.py:19 = OR over five reachability paths: ownership,
  KBs containing the file, file's meta.collection_name KB, channels, shared chats, workspace models
  attaching the file.
  *** CRITICAL INVARIANT (documented files.py:45-48, CWE-863): for WRITE/DELETE the containing object
  confers access ONLY when knowledge_base.user_id == file.user_id :63,:73 / owner_id == file.user_id
  :111 — otherwise a user could drop a read-only file into a KB they own and GAIN WRITE ON IT. ***
  Channels and shared chats grant READ ONLY :90,:95.
  get_accessible_folder_files :127 filters folder entries by type (file/collection/note :16) —
  unknown shapes DROPPED because they cannot be checked :143 — short-circuits for admins :145
FOLDERS has_folder_access folders.py:6 walks up parent_id, True on owner or grant at ANY ANCESTOR
  (inheritance downward), seen_ids loop guard :9-10

## PLUGIN LOADING (see also routers-B brief)
NO SANDBOXING. Plugin code runs in server process w/ full interpreter privileges, module-level side
effects included. Temp file deleted in finally :256,:315 but module object + sys.modules entry PERSIST.
install_frontmatter_requirements :422 runs pip install as subprocess against COMMA-SPLIT FRONTMATTER
  STRINGS :441-443, gated on ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS and OFFLINE_MODE
install_tool_and_function_dependencies :453 pip-installs deps for ALL ACTIVE FUNCTIONS and
  ADMIN-OWNED TOOLS ONLY :476 at startup
CACHING IS CONTENT-HASH-FREE: get_tool_module_from_cache :340 / get_function_module_from_cache :375
  compare RAW SOURCE STRING against app.state.TOOL_CONTENTS/FUNCTION_CONTENTS and RE-EXEC on any change;
  load_from_db=False (used for the hot `stream` filter hook) SKIPS THE FRESHNESS CHECK ENTIRELY
resolve_valves_schema_options :27 CALLS ARBITRARY NAMED CLASSMETHODS on valve classes to populate
  dropdown options :108-126 — another arbitrary-call surface, scoped to the plugin's own class
_installed_requirements is a PROCESS-GLOBAL SET :419 — in multi-worker each worker pip-installs
  independently into the SAME site-packages

## TASK & TEMPLATE SYSTEM — two-stage substitution, all in task.py
STAGE 1 CONTENT: replace_prompt_variable :108 handles {{prompt}}, {{prompt:start:N}}, {{prompt:end:N}},
  {{prompt:middletruncate:N}} CASE-INSENSITIVELY. replace_messages_variable :197 handles {{MESSAGES}},
  :START:N, :END:N, :MIDDLETRUNCATE:N, each optionally piped through per-message content filter
  ({{MESSAGES|middletruncate:500}}) via apply_content_filter :159 / truncate_content :136.
  THE VARIABLE NAME IS PARAMETERIZED :198 — that's how context_compaction.py reuses it for
  {{COMPACTED_MESSAGES}} and {{RECENT_MESSAGES}} (context_compaction.py:361-362)
STAGE 2 IDENTITY/TIME: prompt_template :36 substitutes {{CURRENT_DATE/TIME/DATETIME/WEEKDAY}} and
  {{USER_NAME/EMAIL/BIO/GENDER/BIRTH_DATE/AGE/LOCATION/GROUPS}}. {{USER_GROUPS}} triggers a DB fetch
  ONLY IF THE LITERAL APPEARS IN THE TEMPLATE :61. Unresolved user fields become 'Unknown' :96-102
PER-TASK WRAPPERS title_generation_template :304, follow_up :314, tags :323, image_prompt :332,
  emoji :341, autocomplete :348 (also {{TYPE}}), query_generation :363 — ALL THE SAME THREE-LINE BODY.
  Only moa_response_generation_template :372 and tools_function_calling_generation_template :407 differ.
*** rag_template :265 IS THE SECURITY-SENSITIVE ONE: it UUID-PLACEHOLDERS any [query]/{{QUERY}} that
  appear INSIDE THE RETRIEVED CONTEXT before substitution :281-299 so retrieved documents CANNOT INJECT
  a query placeholder, and logs a warning when context contains <context> tags :274-279 ***
Model selection get_task_model_id :16: LOCAL connections use task_model, REMOTE use task_model_external,
  falling back to the chat's own model

## TELEMETRY
telemetry/setup.py:27 entry, called w/ FastAPI app AND THE SYNC SQLAlchemy ENGINE.
TRACES (ENABLE_OTEL_TRACES): TracerProvider + BatchSpanProcessor over OTLP gRPC or HTTP, optional basic-auth.
Instrumentor._instrument instrumentors.py:176 enables FastAPI, SQLAlchemy, Redis, requests, logging,
  httpx (sync+async hooks), aiohttp-client, system metrics. Hooks rename spans to "METHOD url" and set
  LEGACY semconv keys from _incubating modules to avoid http.request.method rename constants.py:17-27
*** REDIS HOOK SETS db.statement TO THE SPACE-JOINED COMMAND ARGUMENTS instrumentors.py:90 —
  THAT EXPORTS KEY NAMES AND VALUES INTO TRACES. ***
METRICS metrics.py:151: http.server.requests counter + http.server.duration histogram by
  method/route-template/status, w/ Views pinning attribute set to BOUND CARDINALITY :123-141; plus 3
  observable gauges webui.users.{total,active,active.today} whose callbacks run SYNCHRONOUS SQL on the
  sync engine FROM THE OTEL COLLECTION THREAD because the SDK does not await callbacks (documented :56-66).
  Metrics middleware is BaseHTTPMiddleware-style @app.middleware('http') :226 UNLIKE the pure-ASGI
  AppHTTPMiddleware.
LOGS telemetry/logs.py builds LoggingHandler AT IMPORT TIME (otel_handler = setup_logging() :54).
  logger.py InterceptHandler.emit :99 bridges stdlib->Loguru, injects trace_id/span_id into extra when a
  span is active :125-136, forwards to otel_handler when ENABLE_OTEL_LOGS.
  LOG_FORMAT='json' swaps in _json_sink :50 w/ nested try/except so serialization failure can never crash.
AUDIT audit.py = SEPARATE NON-OTEL trail. ASGI middleware, 4 levels NONE/METADATA/REQUEST/REQUEST_RESPONSE
  :53, body capture capped MAX_BODY_LOG_SIZE :107-113, compiled include/exclude path regexes :149-154
  (WHITELIST WINS), unauth requests skipped unless /auths/{signin,signout,signup} :229-250, and
  *** EXACTLY ONE REDACTION RULE — a regex on "password": "..." :285-290.
  API KEYS, TOKENS AND PII IN BODIES ARE NOT REDACTED. ***

## GOTCHAS
1 DUPLICATED check_model_access — TWO FUNCTIONS, SAME NAME, DIFFERENT MODULES, DIFFERENT EXCEPTION TYPES
  (HTTPException vs bare Exception), DIFFERENT FEATURE COVERAGE (only models.py:454 handles arena).
  chat.py:204, actions.py:59, embeddings.py:71 import the models.py one; other callers import the
  access_control one. ANY GOVERNANCE CHANGE MUST PATCH BOTH.
2 check_model_access ONLY CALLED WHEN user.role=='user' in chat.py:202 and embeddings.py:70 — so a
  `pending` user reaching those paths is NOT ACCESS-CHECKED THERE (the access_control variant does
  handle pending :369)
3 ARENA FALLBACK RE-RANDOMIZES WITHOUT FULL GATING chat.py:220-246 picks a random sub-model when
  process_chat_payload didn't resolve one, then RECURSES with bypass_filter=True :260 — the guard
  :243-246 exists precisely because of that, but it's a SECOND SEPARATE ENFORCEMENT POINT
4 replace_imports MUTATES DB CONTENT plugin.py:219/:271/:356/:397 write rewritten source back ON EVERY
  LOAD. A string literal containing 'from main' inside a plugin is SILENTLY REWRITTEN AND PERSISTED.
5 exec() w/ no sandbox + pip install from user frontmatter. ANYONE WHO CAN CREATE A FUNCTION HAS RCE.
  ENABLE_PLUGINS=false is the only kill switch.
6 Redis span attributes LEAK COMMAND PAYLOADS instrumentors.py:90
7 Audit redaction is ONE REGEX audit.py:285. Response bodies captured VERBATIM at REQUEST_RESPONSE.
8 IMPLICIT COUPLING VIA request.state: bypass_filter, bypass_system_prompt, direct, model, metadata,
  filter_context, token all passed as UNTYPED ATTRIBUTES across module boundaries
  (chat.py:165-166, filter.py:39, asgi_middleware.py:132). NO SCHEMA; a missing getattr default is a
  latent AttributeError.
9 open_webui_params DEFINED TWICE VERBATIM payload.py:90 and :145 — new internal param requires BOTH
10 *** TWO METADATA-DRIVEN BACKDOORS INTO TEMPLATES: prompt_variables_template task.py:30 does
   UNGUARDED str.replace over caller-supplied metadata['variables'], and render_user_variables
   chat_variables.py:276 over user.variables. NEITHER ESCAPES, so a user-controlled variable value can
   INJECT ARBITRARY SYSTEM-PROMPT TEXT. Only rag_template defends against placeholder re-injection. ***
11 has_access REQUIRES EXACT PERMISSION EQUALITY :136 — no implication lattice.
12 *** TIMERS CONSTRUCT A SYNTHETIC Request w/ state.token=None and enable_api_keys=False
   timers.py:393-408 and invoke app.state.CHAT_COMPLETION_HANDLER DIRECTLY — a FULLY AUTHENTICATED CODE
   PATH WITH NO HTTP IDENTITY. ANY MIDDLEWARE-BASED GOVERNANCE IS BYPASSED for timer-triggered
   completions. Same for background memory review memory.py:562 and context compaction
   context_compaction.py:385. ***

## ENTERPRISE HOOK CHOKEPOINTS
has_permission / has_access / filter_allowed_access_grants (all async + DB-session-aware => external PDP fits)
generate_chat_completion chat.py:151 + generate_embeddings embeddings.py:24 = SINGLE EGRESS FUNNELS for
  every model call INCLUDING BACKGROUND TASKS
AuditLoggingMiddleware audit.py:116 request-level capture | merge_usage response.py:100 cost/quota metering
RateLimiter rate_limit.py:7 per-tenant throttling
include_user_info_headers headers.py:50 + parse_custom_headers :105 identity propagation upstream
process_filter_functions filter.py:212 existing pre/post chain — DLP/redaction fits here
resolve_tool_call_output tool_approval.py:20 approval workflows
