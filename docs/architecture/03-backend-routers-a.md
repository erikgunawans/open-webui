# routers A — 8 largest routers, 17,053 lines
Mount prefixes main.py:820-844: /ollama /openai /api/v1/{audio,retrieval,auths,channels,chats,knowledge}

## AUTH LAYERS (3 stacked)
Dependencies utils/auth.py: get_current_user (incl. `pending`) < get_verified_user (user|admin) < get_admin_user
Admin-only on shared handler = 2nd decorator w/ dependencies=[Depends(get_admin_user)] (openai.py:867, ollama.py:481)
Orthogonal checks on top:
1. FEATURE PERMS has_permission(uid,'features.web_search'|'chat.tts'|'chat.stt'|'workspace.knowledge'|
   'chat.share'|'chat.delete'|'chat.import'|'features.api_keys'|'features.channels', Config 'user.permissions')
   ALWAYS with user.role!='admin' short-circuit. retrieval.py:2808 audio.py:567 knowledge.py:310 chats.py:232
2. RESOURCE ACL AccessGrants.has_access(uid,resource_type,rid,perm) for knowledge/model/channel/shared_chat.
   Lists use batched get_accessible_resource_ids (knowledge.py:178 openai.py:774 ollama.py:465).
   Grant WRITES laundered via filter_allowed_access_grants(...,'sharing.public_knowledge'|'public_channels'|
   'public_chats') so user CANNOT self-grant public. knowledge.py:318 channels.py:312 chats.py:2034
3. COLLECTION RAG ACL _validate_collection_access retrieval.py:2967 wraps filter_accessible_collections —
   SINGLE gate for every vector store query/write
ENV BYPASS: BYPASS_ADMIN_ACCESS_CONTROL, BYPASS_MODEL_ACCESS_CONTROL. check_model_access(user,model_info,bypass)

## PROVIDER PROXY SHAPE (openai.py + ollama.py identical)
config -> model index -> connection resolve -> payload reshape -> stream|JSON
Connections = PARALLEL-ARRAY config: openai.api_base_urls/api_keys/api_configs keyed by STRINGIFIED INDEX
  w/ legacy URL-keyed fallback openai.py:340-345. Ollama: ollama.base_urls/api_configs, resolve_api_config:372
Model lists fanned out asyncio.gather + merged. OpenAI name->urlIdx map app.state.OPENAI_MODELS :798-863.
Ollama name->urls[] enabling RANDOM LOAD-BALANCE across replicas :389-456, merge_models_lists:354
Both @cached(ttl=MODELS_CACHE_TTL, per-user key)
SHAPING: strip_provider_model_prefix; apply_model_params_to_body_openai; apply_system_prompt_to_body;
  reasoning rewrites openai_reasoning_model_handler:133 is_openai_new_model:1193
  (max_tokens->max_completion_tokens, system->developer);
  Azure deployment-URL rewrite + param allow-list convert_to_azure_payload:1220 get_azure_allowed_params:1153;
  FULL ChatCompletions<->Responses translator convert_to_responses_payload:1275 convert_responses_result:1430
AUTH PER CONNECTION: auth_type in bearer|none|session|system_oauth|azure_ad get_headers_and_cookies:154
  Anthropic URLs get x-api-key + anthropic-version NOT Bearer. get_anthropic_request_target:456
STREAMING: SSE detect Content-Type text/event-stream -> stream_wrapper from utils/session_pool.
  _clean_proxy_headers STRIPS Content-Encoding/Length/Transfer-Encoding (aiohttp already decompressed)
  openai.py:77-85 ollama.py:58-65
  Non-SSE 4xx/5xx RETURNED as JSONResponse at upstream status, NOT raised, after
  publish_model_provider_request_failed(). Ollama funnels all via send_request() :96,
  passthrough=False reserved for /api/chat so middleware parses NDJSON line-by-line

## RAG PIPELINE
INGEST process_file retrieval.py:1857 — 3 branches: explicit content (replace file-{id}) |
  KB-add (reuse file-{id} chunks, or REPAIR from SQL file.data.content when vectors missing :1917-1949) |
  fresh load build_loader_from_config (Tika/Docling/Datalab/Mistral-OCR/MinerU/external)
CHUNK save_docs_to_vector_db :1637 — dedupe by SHA-256 hash :1667, optional Markdown-header split,
  then Recursive/Token/TokenTransformers splitter, then merge_docs_to_target_size :1516 grows undersized
  chunks forward-then-backward WITHOUT crossing file_id/source boundaries
EMBED get_embedding_function(engine in ''|openai|ollama|azure_openai). save_docs_to_vector_db is SYNC so
  called via run_in_threadpool, and INSIDE hops back with
  asyncio.run_coroutine_threadsafe(...,app.state.main_loop).result(timeout=RAG_EMBEDDING_TIMEOUT) :1813
  Chunk metadata carries embedding_config{engine,model} for drift detection
STORE VECTOR_DB_CLIENT (sync) and ASYNC_VECTOR_DB_CLIENT COEXIST.
  Collection naming: file-{file_id} | {knowledge_id} | web-search-{user_id}-{hash} (owner-scoped so
  filter_accessible_collections can scope) | knowledge-bases (KB-metadata embeddings for semantic KB
  discovery knowledge.py:89-118)
QUERY query_doc[_with_hybrid_search] / query_collection[...] — BM25+dense fusion HYBRID_BM25_WEIGHT,
  reranker (local CrossEncoder|ColBERT|external), TOP_K/TOP_K_RERANKER/RELEVANCE_THRESHOLD
  knowledge.py lifecycle: add/update/remove reindex KB collection, delete by file_id THEN by hash
  to catch duplicates :1645-1651. External KBs = read-only proxies to Qdrant/Milvus/pgvector via
  retrieve_external_knowledge_for_connection, guarded by is_external_knowledge()/external_knowledge_error() :143-151

## KEY SYMBOLS
save_docs_to_vector_db retrieval.py:1637 | process_file :1857 | merge_docs_to_target_size :1516
_validate_collection_access :2967 | search_web :2442 (25-ENGINE dispatch)
RetrievalConfig :417 (dirty-tracking SimpleNamespace -> Config.upsert)
embed_knowledge_base_metadata knowledge.py:92 | _verify_knowledge_write_access :2205 | delete_file_resource :64
get_headers_and_cookies openai.py:154 | get_all_models openai.py:798 / ollama.py:389
convert_to_responses_payload openai.py:1275 | generate_chat_completion openai.py:1464 / ollama.py:1093
send_request ollama.py:96 | validate_ollama_backend_idx :1060
create_session_response auths.py:166 | signup_handler :840
channel_has_access channels.py:61 | new_message_handler :1144
model_response_handler channels.py:976 (channel @-mention -> FULL chat pipeline)
overlay_response_streams chats.py:62 | transcription_handler audio.py:910 | _TTS_ENGINES audio.py:549

## EXTENSION POINTS
NEW PROVIDER: add api_config.provider branch. MODEL_MANAGEMENT_ENDPOINTS openai.py:248 is an explicit
  DATA-DRIVEN per-provider endpoint table (llama.cpp, lmstudio) — cleanest place to add managed backend.
  Hooks: get_headers_and_cookies (auth), convert_to_*_payload (body)
AUTH: auth_type already supports session + system_oauth (forwards CALLER'S OWN token upstream) = hook for
  per-user upstream identity. SSO extends auths.py OAUTH_CONFIG_KEYS/LDAP_SERVER_CONFIG_KEYS +
  oauth_manager.update_user_role_from_oauth / update_user_groups
RAG: build_loader_from_config (ingestion); EXTERNAL_KNOWLEDGE_PROVIDERS knowledge.py:542 (read-only external
  vector stores); RAG_RERANKING_ENGINE='external'; EXTERNAL_WEB_SEARCH_URL / EXTERNAL_WEB_LOADER_URL /
  EXTERNAL_DOCUMENT_LOADER_URL. search_web elif-chain = the one place to add an engine
POLICY/AUDIT: every mutation ALREADY calls publish_event(request, EVENTS.X, actor=, subject_id=, data=)
  — a ready-made AUDIT SPINE. EVENTS + open_webui/events.py = where enterprise audit/DLP sink plugs in
  WITHOUT touching handlers. <-- HIGHEST LEVERAGE FOR GOVERNANCE PRODUCT
ACL: AccessGrants generic over resource_type; new resource needs has_access/get_accessible_resource_ids
  pair + a filter_allowed_access_grants sharing key

## GOTCHAS
- Config is ASYNC DB-BACKED not module constants. Idiom = Config.get_many(*keys) + FIELD->'dotted.key' map
  (RETRIEVAL_CONFIG_KEYS, OPENAI_CONFIG_KEYS, ADMIN_CONFIG_KEYS, TTS_CONFIG_KEYS).
  ollama.py:612-616 and audio.py:922-932 await Config.get INSIDE LOOPS — repeated round-trips.
- DELIBERATE SESSION AVOIDANCE. Handlers document NOT using Depends(get_async_session) because an
  LLM/embedding call pins a pool connection 30-60s (openai.py:1473 knowledge.py:306 chats.py:576,
  streaming per-batch chats.py:986). ADDING a session dependency = latent POOL-EXHAUSTION BUG.
- SYNC/ASYNC VECTOR CLIENT SPLIT used interchangeably across files; sync one MUST be run_in_threadpool
  or it DEADLOCKS the loop (retrieval.py:2027-2030 spells it out).
- request.state.bypass_filter / bypass_system_prompt read from STATE never query params, precisely so
  external clients can't set them (openai.py:1478 ollama.py:1108). PRESERVE when adding call paths.
- ERROR CONVENTION INCONSISTENT BY LAYER: upstream provider errors RETURNED as JSONResponse at upstream
  status; local failures RAISE HTTPException. `except HTTPException: raise` guards everywhere to stop
  broad except Exception swallowing 403/404. Explicit bug note retrieval.py:3179-3182, metadata=->filter= fix :3158
- SHARP: channels.py:1993 webhook POST UNAUTHENTICATED by design (bearer = URL token), NO rate-limiting
  or abuse controls. openai.py:1908 references `cookies` before assignment on some paths.
  auths.py:706 wraps ENTIRE LDAP flow in except Exception -> generic 400, MASKS config errors.
  retrieval.py:3265 process_files_batch takes db=None and passes down.
  chats.py:99 get_optional_verified_user silently returns None on ANY auth failure — shared-chat access
  then hinges on is_open_shared_chat.
- IMPLICIT app.state COUPLING: MODELS, OPENAI_MODELS, OLLAMA_MODELS, BASE_MODELS, ef, rf,
  EMBEDDING_FUNCTION, RERANKING_FUNCTION, main_loop, redis, CHAT_COMPLETION_HANDLER, oauth_manager,
  faster_whisper_model, speech_synthesiser. Cache invalidation must clear aiocache entry AND Redis
  BASE_MODELS_CACHE_KEY AND state dicts. clear_openai_model_cache openai.py:348 = canonical;
  ollama.py:323-333 DUPLICATES it inline.

## ENDPOINT COUNTS (full inventory in agent transcript)
retrieval 18 | knowledge ~30 | chats ~50 | openai 15 | ollama ~30 | auths ~20 | channels ~28 | audio 6
