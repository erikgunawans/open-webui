# routers B — 23 routers, workspace/identity/platform-config plane
FORK-ONLY routers: skills, calendar, terminals, analytics, automations, notifications
analytics gated ENABLE_ADMIN_ANALYTICS main.py:855 | scim gated ENABLE_SCIM main.py:863

## 3-LAYER AUTH (applied in order)
1 DEPENDENCY get_admin_user|get_verified_user (ONLY FastAPI-level gate)
2 FEATURE FLAG + GROUP PERM — per-router async helper reading Config.get_many:
  check_folders_permission folders.py:66 | check_memories_permission memories.py:35 |
  check_calendar_permission calendar.py:37 | check_automations_permission automations.py:45 |
  _check_notifications_access notifications.py:34
  Each raises 403 unless role=='admin' or has_permission(uid,'features.X',perms)
  NOTES AND SKILLS INLINE THE SAME CHECK PER-HANDLER instead of centralizing
3 PER-RESOURCE ACL AccessGrants.has_access / get_accessible_resource_ids (batch, avoids N+1
  models.py:177 prompts.py:113 skills.py:97 users.py:1126)
CANONICAL WRITE CHECK repeated VERBATIM ~30x:
  resource.user_id != user.id AND not await AccessGrants.has_access(...) AND user.role != 'admin'
GRANT ESCALATION BLOCKED by filter_allowed_access_grants(perms,uid,role,grants,'sharing.public_X')
  on EVERY create/update/access-update: tools.py:383 models.py:309 prompts.py:169 notes.py:221
  skills.py:188 calendar.py:120 folders.py:519
  Strips principal_id='*' grants caller isn't entitled to set.
  SKIPPING IT ON A CREATE ENDPOINT IS THE CLASSIC HOLE THIS CODEBASE HAS PATCHED SEVERAL TIMES —
  see comments skills.py:183-187 calendar.py:116-119
BYPASS_ADMIN_ACCESS_CONTROL orthogonal: appears in query filters (user_id=None if bypass) AND in
  write_access computation

## PLUGIN SYSTEM (functions/tools/pipelines) — SHARPEST EDGE IN CODEBASE
REGISTRATION POST /api/v1/tools/create tools.py:350 w/ ToolForm.content = RAW PYTHON.
  (a) requires workspace.tools|tools_import for non-admins (b) enforces form_data.id.isidentifier()
  (c) runs replace_imports plugin.py:187 (NAIVE STRING SUBSTITUTION) (d) load_tool_module_by_id
  Functions identical but ADMIN-ONLY functions.py:199
LOADING == EXECUTION: load_tool_module_by_id plugin.py:206 parses YAML frontmatter ->
  install_frontmatter_requirements plugin.py:422 SHELLS OUT TO pip install via subprocess.check_call ->
  types.ModuleType(f'tool_{id}') -> registers sys.modules -> writes source to temp file for __file__ ->
  exec(content, module.__dict__) plugin.py:241 (functions :291) IN THE MAIN SERVER PROCESS.
  NO SANDBOX, NO NAMESPACE RESTRICTION. Then instantiates module.Tools().
  Duck-types result: Pipe->pipe Filter->filter Action->action Event->event plugin.py:296-306
STORAGE source in DB (tools.content/functions.content). Live modules in request.app.state.TOOLS/FUNCTIONS
  (get_tools_cache plugin.py:324, get_functions_cache :332), refreshed on create/update, popped on delete.
  get_tool_module_from_cache :340 LAZILY RE-EXECS FROM DB ON CACHE MISS — a row written by ANY path
  becomes EXECUTING CODE on first use.
VALVES: Valves (admin/owner) + UserValves (per-user). Routers instantiate Pydantic to validate,
  store model_dump(exclude_unset=True), expose .schema() via resolve_valves_schema_options plugin.py:27
PIPELINES ARE DIFFERENT IN KIND: not in-process Python but REMOTE servers behind an OpenAI connection.
  process_pipeline_inlet_filter/outlet_filter pipelines.py:63,129 POST {user,body} to
  {url}/{filter_id}/filter/inlet|outlet ordered by pipeline.priority :41.
  POST /pipelines/upload streams a .py file TO THE REMOTE HOST.
  EVERY task endpoint in tasks.py runs payload through process_pipeline_inlet_filter first.
SECURITY SURFACE:
  1 ANY NON-ADMIN HOLDING workspace.tools ACHIEVES RCE ON THE SERVER — BY DESIGN.
    THAT PERMISSION IS EFFECTIVELY "GRANT ADMIN".
  2 pip install of ATTACKER-CHOSEN PACKAGE NAMES runs on save, gated only by
    ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS
  3 ENABLE_PLUGINS=false is THE ONLY KILL SWITCH (plugin.py:207/260 + list endpoints)
  4 replace_imports is a REWRITING PASS NOT A SANITIZER
  5 POST /load/url tools.py:269 functions.py:106 fetches ARBITRARY URLs server-side w/ explicit
    "this is NOT SSRF because admin-only" comment
  6 Read-only callers denied source via data.pop('content') tools.py:468 — ALLOWLIST-BY-DELETION
    depending on ToolAccessResponse not re-admitting it

## KEY SYMBOLS
plugin.load_tool_module_by_id :206 | load_function_module_by_id :259 | install_frontmatter_requirements :422
get_tool_module_from_cache :340 | files.upload_file_handler files.py:315 (reused images.py:532)
files.process_uploaded_file files.py:128 (audio->STT->index | video->store-only | else->process_file;
  auto-links KB when metadata.knowledge_id present :204-248 re-checking write access FIRST)
images.image_generations :597 / image_edits :895 | images._is_same_origin :458
models._safe_static_redirect_path models.py:60 | models._verify_knowledge_file_access :95
terminals._sanitize_proxy_path :45 | terminals._resolve_authenticated_connection :242
pipelines.get_sorted_filters :41 | tasks.get_task_model_generation_config :80
memories.reindex_memory_vectors_for_user :128 | evaluations._calculate_elo :81
scim.get_scim_auth :232 | folders.get_folder_unread_counts :48 | calendar._check_calendar_access :62

## EXTENSION POINTS
NEW RESOURCE TYPE: COPY skills.py WHOLESALE — newest+cleanest instance of the pattern
  (permission gate -> filter_allowed_access_grants -> AccessGrants.set_access_grants -> publish_event).
  Add resource to AccessGrants, add workspace.X/sharing.public_X to users.py:209-301, mount in main.py
OVERRIDE ENDPOINT: FastAPI FIRST-MATCH-WINS so you must mount BEFORE to shadow. Cleaner: middleware, or
  replace the include_router line.
CONFIG: add *_CONFIG_KEYS map + get_config_values/config_updates pair
  (idiom images.py:105-115 configs.py:80-86 tasks.py:64-70 evaluations.py:36)
AUDIT: publish_event already on nearly every mutation — enterprise audit log hooks events.py NOT routers
AUTH: replace get_admin_user/get_verified_user in utils/auth.py for SSO/tenant scoping.
  SCIM already provides IdP-driven lifecycle.
POLICY CHOKEPOINTS WORTH WRAPPING: has_permission, filter_allowed_access_grants, AccessGrants.has_access
TERMINALS/TOOL SERVERS configs.py:328-545 proxies to an EXTERNAL ORCHESTRATOR with a policy/lifecycle API
  = NATURAL SEAM FOR ENTERPRISE SANDBOXING

## GOTCHAS
- ERROR CONVENTION INCONSISTENT: missing resource = 404 in notes/skills/calendar but 401 in
  tools.py:499 functions.py:277 models.py:791. Access denial = 401 in tools/models/prompts,
  403 in notes/folders/memories. Files DELIBERATELY 404 (not 403) to avoid existence leaks files.py:604
- ROUTE ORDERING LOAD-BEARING: calendar.py places /events* BEFORE /{calendar_id} (comment :386).
  files.py DEFINES get_file_content_by_id TWICE (:783 and :895) — second shadows first in module
  namespace, but request.app.url_path_for('get_file_content_by_id') in images.py:554 resolves BY NAME
  so may resolve to /{id}/content/{file_name}. FRAGILE.
- DELIBERATE SESSION OMISSION w/ explicit comments files.py:617 memories.py:190/337/489 — holding a
  pooled connection across SSE stream or embedding call EXHAUSTS THE POOL
- N+1 AVOIDANCE IS MANUAL (get_groups_by_member_ids, get_users_by_user_ids,
  get_accessible_resource_ids, AutomationRuns.get_latest_batch). EASY TO REGRESS.
- KNOWN RACES DOCUMENTED: POST /user/info/update users.py:681 merges over auth-time snapshot,
  ADMITS LOST UPDATES. get_folders SILENTLY REPAIRS cyclic/orphaned parents BY WRITING DURING A GET
  folders.py:118-120
- CONFIG ASYNC EVERYWHERE, re-fetched per check, often SEVERAL TIMES IN ONE HANDLER
  users.py:506/520/537 — NO request-scoped memoization
- SILENT SKIPPING IN BULK PATHS: import_models models.py:371 logs-and-continues on EVERY denial,
  caller gets True regardless. Same in folders.get_folders (silently truncates inaccessible files).
- TWO DISTINCT ACL SYSTEMS COEXIST: AccessGrants rows for most resources, AND connection-embedded
  config.access_grants lists for tool/terminal servers via has_access/has_connection_access
  tools.py:178-190 terminals.py:95
- SCIM WILL NOT DEMOTE AN ADMIN (guarded scim.py:695,:765) to prevent IdP misconfig lockout.
  SCIM METADATA ENDPOINTS scim.py:401/423/453 ARE UNAUTHENTICATED.
- PROFILE-IMAGE ENDPOINTS users.py:855 models.py:642 = repeated XSS/SSRF surface: data-URI MIME allowlist
  PROFILE_IMAGE_ALLOWED_MIME_TYPES, X-Content-Type-Options nosniff, ENABLE_PROFILE_IMAGE_URL_FORWARDING
  gating 302s, _safe_static_redirect_path models.py:60 w/ DECODE-UNTIL-STABLE loop that FAILS CLOSED
- DECODE-UNTIL-STABLE APPEARS 3x (models.py:70-77, terminals.py:54-62, _sanitize_proxy_path) — shared
  lesson: single-pass unquote lets %252e%252e through to an upstream that decodes again
