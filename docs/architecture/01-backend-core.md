# backend core — main.py, config.py, env.py, internal/, storage/, socket/, tasks.py, functions.py, events.py
FORK NOTE: extra routers analytics/automations/calendar/skills/terminals/notifications, AccessGrants model,
subagents, FULLY REWRITTEN config system. UPSTREAM DOCS DO NOT APPLY.

## BOOTSTRAP — import order IS the bootstrap
main.py:45 imports config -> imports env -> loads .env, logging, parses CHANGELOG.md into dict env.py:178-216,
resolves DATABASE_URL env.py:267-298, HARD-EXITS if WEBUI_SECRET_KEY unset while auth on env.py:765
Back in config.py: ALEMBIC MIGRATIONS RUN AT IMPORT TIME config.py:80-81 -> run_migrations :63;
static assets copied frontend build -> STATIC_DIR :110-144; Config.configure :3240 registers defaults
apply_orjson_http_json() main.py:484 patches JSON BEFORE app=FastAPI :489 (docs only when ENV=='dev')
app.state.startup_complete=False :498 gates /ready. OAuth managers :501-506. OTEL :527-530

### MIDDLEWARE ORDER IS INVERTED (Starlette runs LAST-ADDED OUTERMOST)
Source order: AuditLoggingMiddleware :783 (if AUDIT_LOG_LEVEL!=NONE), CompressMiddleware :793,
AppHTTPMiddleware :805, CORSMiddleware :808, then LATER at :2615-2640 session middleware
EFFECTIVE outermost->innermost: Session -> CORS -> AppHTTPMiddleware -> Compress -> Audit -> routes
Audit deliberately INNERMOST so it sees UNCOMPRESSED bodies (comment :780)
ALL HTTP middleware PURE-ASGI by design — asgi_middleware.py:1-29 explains BaseHTTPMiddleware's anyio
task group was CANCELLING IN-FLIGHT DB CALLS on client disconnect
app.mount('/ws', socket_app) :817 BEFORE routers. Routers :820-864. analytics+scim conditional :855,:863

### lifespan :338-479 ORDER
capture loop -> app.state.main_loop + resize thread pool :342-352; start_logger(); optional async_reset_config();
import_legacy_config_json() (data/config.json -> DB then RENAMES file); seed_registered_defaults();
initialize_runtime_config(app) :598 (migrates legacy access_control -> access_grants, re-registers MCP OAuth
clients, builds embedding/reranking fns onto app.state); migrate_legacy_webhook_config();
publish_event(SYSTEM_STARTUP_STARTED). License fetch background+shielded 2s :368,:452-458.
Admin bootstrap WEBUI_ADMIN_EMAIL/PASSWORD :371. Plugin dep install :382 BLOCKING BY DESIGN. Redis :384.
4 long-lived tasks: redis_task_command_listener, periodic_usage_pool_cleanup, periodic_session_pool_cleanup,
scheduler_worker_loop. Model/tool-server prefetch use HAND-BUILT FAKE Request scope :398-449 (recurring idiom).
startup_complete=True :460.
STATIC MOUNTS LAST: /static :2989, /cache auth-gated w/ traversal+content-disposition hardening :2992-3017,
/pyodide :3035, SPA catch-all / :3037-3041 via SPAStaticFiles :292 (rewrites 404->index.html EXCEPT .js)

## CONFIG — NO PersistentConfig CLASS. Upstream pattern REPLACED.
config.py = ~2800 lines of module-level os.getenv constants terminating in ONE FLAT DICT
DEFAULT_CONFIG :2835-3234 mapping ~450 DOTTED KEYS ('rag.top_k','oauth.google.client_id','ui.default_models')
models/config.py:101 real table: key TEXT PK, value JSON, updated_at
PRECEDENCE: env populates DEFAULT_CONFIG; seed_defaults models/config.py:240 inserts ONLY MISSING keys
  => ONCE A KEY EXISTS IN DB THE ENV VALUE IS IGNORED ON RESTART
Reads: Config.get(key) -> DB row, fallback DEFAULTS :140-147
persistent_enabled_for :132 escape hatch: ENABLE_PERSISTENT_CONFIG=False => every read short-circuits to env
  default. oauth.* NON-PERSISTENT unless ENABLE_OAUTH_PERSISTENT_CONFIG=True
Config.upsert :197 writes non-persistent keys into IN-MEMORY DEFAULTS — PROCESS-LOCAL, does NOT propagate
  across workers
Setting becomes live by being READ FRESH — nearly every call site awaits Config.get/get_many per request
  (get_app_config main.py:2229-2278). NO CACHE, NO RELOAD SIGNAL, but a DB round-trip per read;
  get_many exists to amortize.
Boot repair passes: rename_prefix('rag.web'->'web') and repair_config_rows() models/config.py:302
GROUPS: ollama.* openai.* tool_server.* terminal_server.* | rag.* (engines/chunking/rerankers/~15 extractors)
  | web.* (~30 engines) | images/audio | ui.* | user.permissions (nested from DEFAULT_USER_PERMISSIONS
  config.py:1954) | task.* prompt templates | chat.context_compaction.* | oauth.* | ldap.*
  | FORK-SPECIFIC automations.* calendar.* subagents.* memories.*

## SOCKET LAYER
AsyncServer :89 Redis-managed / :104 single-process, wrapped socketio.ASGIApp :295, mounted /ws path /ws/socket.io
Custom JSONOnlyPacket :70 disables per-emit binary scan. Websocket-only unless ENABLE_WEBSOCKET_SUPPORT=False
3 shared stores = plain dict OR RedisDict per WEBSOCKET_MANAGER :125-184:
  MODELS (also aliased app.state.MODELS main.py:771), SESSION_POOL (sid->sanitized user + last_seen_at),
  USAGE_POOL (model_id->{sid:updated_at})
2 reaper loops hold Redis locks: periodic_session_pool_cleanup :200 (SESSION_POOL_TIMEOUT),
  periodic_usage_pool_cleanup :250 (3s)
EVENTS: connect :405 (token-auth, joins user:{id}) | user-join :432 (+channel:{id} if permitted) |
  heartbeat :473 (presence + Users.update_last_active_by_id) | join-channels :481 | join-note :503 |
  usage :391 | events:channel :539 (typing/last_read_at) | events:chat :586 (last_read_at + folder unread
  rollup) | Yjs CRDT ydoc:document:join|state|update|leave + ydoc:awareness:update :639-923 | disconnect :926
ROOMS = addressing: user:{id} channel:{id} note:{id} doc_{document_id}
  EVERY Yjs handler RE-CHECKS AccessGrants — room membership proves READ only, writes re-verify :801-824
  normalize_document_id :626 closes a PREFIX-VARIANT AUTH BYPASS (note_abc vs note:abc)
OUTBOUND get_event_emitter(request_info) :1057 -> closure emitting to user:{id} AND persisting selected
  types (status,message,replace,embeds,files,source) into chat record. chat_id starting 'channel:' swaps in
  throttled channel emitter :946 writing Messages rows.
  get_event_call :1181 round-trips sio.call and VERIFIES client-supplied session_id belongs to requester :1186-1189

## KEY SYMBOLS
lifespan main.py:338 | initialize_runtime_config :598 | chat_completion (770-LINE CORE) :1085 |
app.state.CHAT_COMPLETION_HANDLER :1888 | get_app_config :2197 | SPAStaticFiles :292 / CORSStaticFiles :307
Config models/config.py:101 | DEFAULT_CONFIG config.py:2835 | load_oauth_providers config.py:2666 (inv :2795)
AppHTTPMiddleware utils/asgi_middleware.py:51
sync engine/Base/ScopedSession internal/db.py:277-413 | async_engine :435 get_async_session :497 get_async_db :507
JSONField (TEXT-backed JSON) internal/db.py:124
get_event_emitter socket/main.py:1057 | get_event_call :1181 | RedisDict socket/utils.py:64 RedisLock :17
  YdocManager :192
create_task tasks.py:131 stop_task :232 | Storage singleton storage/provider.py:348 get_storage_provider :334
generate_function_chat_completion functions.py:153
EVENTS events.py:664 | publish_event :1174 | EVENT_SINKS :1171

## EXTENSION POINTS
NEW ROUTER: add to routers import main.py:145-177, app.include_router(prefix='/api/v1/x') near :860.
  Gate w/ config flag like analytics/scim.
NEW CONFIG KEY: env constant in config.py + dotted key in DEFAULT_CONFIG :2835 (auto-seeded). Surface to SPA
  by adding to get_many list AND response dict in get_app_config :2229/:2296
MIDDLEWARE: append after :814 = OUTERMOST, before :783 = innermost. REMEMBER THE REVERSAL.
AUTH INTERCEPT: AppHTTPMiddleware._set_token asgi_middleware.py:126 = SINGLE POINT where Bearer / token cookie
  / CUSTOM_API_KEY_HEADER collapse into request.state.token. Per-route = Depends(get_verified_user|get_admin_user).
  WEBUI_AUTH_TRUSTED_*_HEADER env.py:787-790 = reverse-proxy SSO hook. OAuth/OIDC main.py:2738-2831 +
  back-channel logout :2824
EVENT/AUDIT: implement sink class w/ handle_event(app,event,request), append to EVENT_SINKS events.py:1171
  = CLEANEST ENTERPRISE HOOK FOR SIEM/COMPLIANCE. Or runtime webhook CRUD main.py:2465-2549
  (per-event glob filters + user/group targeting).
PIPE FUNCTIONS: functions.py loads user modules w/ valves/UserValves, injects __event_emitter__,
  __oauth_token__, __request__, __tools__ :268-283
STORAGE: subclass StorageProvider, extend get_storage_provider storage/provider.py:334
CHAT PIPELINE REUSE: call request.app.state.CHAT_COMPLETION_HANDLER main.py:1888 — EXPLICITLY provided so
  internal callers avoid importing main

## GOTCHAS
- IMPORT-TIME SIDE EFFECTS: migrations, static copy, OAuth registration, Storage instantiation ALL on import.
  Importing config or storage.provider IN A TEST touches disk and DB.
- TWO ENGINES TWO LIFETIMES internal/db.py: sync engine/ScopedSession for startup/Alembic/health/legacy
  pgvector ONLY; runtime uses async_engine. AppHTTPMiddleware commits + remove()s thread-local ScopedSession
  per request and SKIPS /health /ready /health/db asgi_middleware.py:115 — which is exactly why
  _sync_db_ping main.py:2905 uses raw engine.connect()
- GLOBAL MUTABLE STATE: app.state.*, module-level tasks/item_tasks/response_streams tasks.py,
  SESSION_POOL/USAGE_POOL/MODELS socket/main.py. WITHOUT REDIS ALL PER-WORKER =>
  UVICORN_WORKERS>1 SILENTLY BREAKS task cancellation, socket fan-out, non-persistent config writes.
- FAKE Request objects from raw ASGI scope dicts in lifespan :398,:422 — any helper reading request.state
  or headers MUST tolerate them
- chat_completion IS THE HOT SPOT ~770 lines mixing access control, persistence, multi-model fan-out, task
  registration, error-to-socket translation. Its finally block :1696-1773 carries a LONG COMMENT FORBIDDING
  asyncio.wait_for/shield around MCP client teardown (anyio cancel-scope ownership). DO NOT "CLEAN THAT UP."
- Event payloads SANITIZED not raw: _sanitize events.py:958 recursively drops SENSITIVE_KEYS/*_token/*_key,
  truncates strings at 1000 chars, actors reduced to SAFE_ACTOR_FIELDS. Sinks dispatch via
  asyncio.create_task FIRE-AND-FORGET — failures logged never surfaced.
- config.py DELETES FILES IN STATIC_DIR ON EVERY IMPORT :99-108 before recopying. Hand-dropped files LOST.
- Ollama port autodetection does BLOCKING TCP PROBES AT IMPORT config.py:263-291 when no explicit URL —
  startup latency in locked-down networks
- LICENSE-PROTECTED BRANDING COMMENTS scattered through main.py config.py env.py constants.py.
  Enterprise rebranding of marked identifiers is CONTRACTUALLY CONSTRAINED, not merely a code change.
