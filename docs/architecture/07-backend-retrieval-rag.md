# retrieval/ — 68 files, ~15,970 lines. THE COMPLETE RAG SUBSTRATE.
Sub-packages: vector/ (storage), loaders/ (format->text), web/ (search+SSRF-hardened fetch),
models/ (reranker wrappers). utils.py + external.py = orchestration.

## VECTOR ABSTRACTION
CONTRACT VectorDBBase vector/main.py:24 — 8 abstract: has_collection, delete_collection, insert, upsert,
  search, query, get, delete, reset. hybrid_search :66 is NON-ABSTRACT OPT-IN returning None by default —
  ONLY PGVECTOR OVERRIDES IT.
DTOs VectorItem :7 GetResult :14 SearchResult :20 — all use list[list[...]] per-query shape INHERITED
  FROM CHROMA
SELECTION Vector.get_vector vector/factory.py:12 = match on VectorType vector/type.py:4, LAZILY importing
  each driver so a missing dep only breaks its own backend. Singleton VECTOR_DB_CLIENT :91 built AT IMPORT.
  Milvus/Qdrant fork on ENABLE_*_MULTITENANCY_MODE :18,:29
ASYNC FACADE AsyncVectorDBClient vector/async_client.py:67 mirrors signature-for-signature via
  asyncio.to_thread, exposes .sync escape hatch :80, supports_hybrid_search :86 detects override BY
  IDENTITY COMPARISON against base method
HELPERS vector/utils.py: process_metadata :38 strips oversized/blob keys (KEYS_TO_EXCLUDE :8),
  stringifies datetimes/lists | iter_filter_conditions :64 = THE ONLY FILTER GRAMMAR ($eq implicit,
  $in explicit, everything else RAISES) | merge_hybrid_search_results :91 = RRF rank_constant=60

### 13 BACKENDS — DISTANCE NORMALIZATION IS **NOT** UNIFORM
Chroma dbs/chroma.py:30 (2-d)/2 :90 — search/query SWALLOW ALL EXCEPTIONS -> None :102
Milvus :71 open_webui_{name}, `-`->`_` :210, (d+1)/2 :116, text clamp 65535 :38.
  Expression injection guarded _escape_milvus_string/_SAFE_METADATA_KEY_RE :42,:39 BUT query() :250 and
  delete() :403 BUILD UNESCAPED F-STRINGS
Milvus MT :64 — 5 shared collections + resource_id :33, RAW DISTANCE :244 NOT NORMALIZED.
  _get_collection_and_resource_id :84 routes BY NAME PREFIX; its own docstring WARNS OF DATA CORRUPTION
  IF NAMING CHANGES
Qdrant :40 {prefix}_{name}, payload indexes on metadata.hash/file_id :110, (score+1)/2 :175,
  NO_LIMIT=999999999 because Qdrant SILENTLY DEFAULTS TO 10
Qdrant MT :48 shared + tenant_id payload, hnsw m=0 payload_m=M :148, DEFAULT_DIMENSION=384 fallback :34
pgvector :87 SINGLE document_chunk table + collection_name column :77, (2-d)/2 :527.
  *** ONLY NATIVE HYBRID :538 via ts_rank_cd + GIN index :240. OPTIONAL PGCRYPTO AT-REST ENCRYPTION
  :79,:314 (the ONLY at-rest encryption). halfvec above 2000 dims :57. Refuses index-method change :218 ***
openGauss :95 pgvector clone, custom SQLAlchemy dialect :36,:55, ivfflat only, NO hybrid, NO pgcrypto
Elasticsearch :35 INDEX PER DIMENSION {prefix}_d{dim} :59, collection is a keyword field, RAW _score :101,
  script_score cosine :181 = BRUTE FORCE NOT ANN
OpenSearch :31 index per collection :41, script-normalized (cos+1)/2 :143, knn_vector/faiss/hnsw mapping
  :87 BUT query path uses script_score
Pinecone :46 ONE index + collection_name in metadata :179, (s+1)/2 :195, gRPC if importable :12.
  *** delete(ids=) CANNOT SCOPE BY COLLECTION :480 ***. Fixed PINECONE_DIMENSION.
S3Vector :21 index per collection, RAW AWS DISTANCE :351 NOT NORMALIZED/INVERTED.
  metadata HARD-CAPPED AT 10 KEYS :80. query() FETCHES ALL THEN FILTERS CLIENT-SIDE :427.
  delete(filter=) is query-then-delete :620. HAS A SECOND FILTER ENGINE _matches_filter :674 DIVERGING
  from vector/utils.py
Oracle 23ai :85 single document_chunk table, RAW COSINE DISTANCE :611 **INVERTED VS EVERYTHING ELSE**.
  oracledb pool + health monitor thread :188. get() HARDCODES limit=1000 :711.
  query/delete INTERPOLATE $.{key} UNPARAMETERIZED :657,:789
Weaviate :71 class per collection, name mangled to PascalCase :95, (2-d)/2 :218, metadata becomes
  TOP-LEVEL PROPERTIES. *** reset() DROPS ALL CLASSES INCLUDING NON-OPEN-WEBUI ONES :339 ***
MariaDB :82 single table VECTOR(n)+VECTOR INDEX :166, 1-d / 1/(1+d) :229,
  requires mariadb+mariadbconnector:// :113. Dimension regex :202 IS DOUBLE-ESCAPED AND NEVER MATCHES.
Valkey :151 HASH + FT index per collection :336, metric-aware :756, enforces core>=9.0.1 /
  valkey-search>=1.2.0 at init :251,:284, TAG escaping :105, dimension verification :400
ONLY VALKEY AND PGVECTOR GUARD DIMENSION MISMATCH. pgvector/openGauss/MariaDB instead PAD OR TRUNCATE
  query AND stored vectors to fixed VECTOR_LENGTH pgvector.py:287.
DIMENSION HANDLING SPLITS 3 WAYS: fixed-and-padded | index-per-dimension (ES) | first-insert-wins
  (Chroma/Milvus/Qdrant/Weaviate/S3Vector). ELSEWHERE SWITCHING EMBEDDING MODELS SILENTLY CORRUPTS A COLLECTION.

## LOADERS — single if/elif ladder Loader._get_loader loaders/main.py:486, ENGINE-FIRST then ext/MIME
ENGINES external (external_document.py:14 PUT /process, custom headers + user-group header injection) |
tika (:197, v3/v4 endpoint split :218) | datalab_marker (:15, poll-or-direct dual protocol :127) |
docling (:238, page-split on \f) | document_intelligence (Azure, key or DefaultAzureCredential :616) |
mineru (:15 local sync /file_parse vs cloud presigned-upload+poll+ZIP :72/:178) |
mistral_ocr (:17 upload->sign->OCR->delete w/ retry classification :114) | paddleocr_vl (:18)
FALLBACK CHAIN :668 PyPDFLoader, CSVLoaderWithSummary :156, Unstructured RST/XML/EPub/Word/Excel/
  PowerPoint/Email/ODT each w/ graceful ImportError degradation, BSHTMLLoader, TextLoader
ENCODING custom CJK-aware _detect_text_encoding :345 + _has_cjk_characters :447 — treats chardet as a
  HINT, maps GB2312->GB18030. Zip-bomb guard :489. All output passes ftfy.fix_text :316.
  aload :318 offloads to thread; GROUP LOOKUP MUST HAPPEN FIRST because it's async-only.
WEB LOADERS youtube.py:77 (allowlisted netlocs, manual-transcript preference, proxy) | tavily.py:12 |
  external_web.py:11 | microsoft_web_iq.py:17

## WEB SEARCH — 22 provider files
CONTRACT SearchResult(link,title,snippet) web/main.py:47 + get_filtered_results :11 (allow/block domain
  filter, optionally resolves hostnames to IPs)
*** DISPATCH IS OUTSIDE THIS PACKAGE — search_web() in routers/retrieval.py ~:2500-2795, an engine
string if/elif, most sync providers wrapped asyncio.to_thread ***
PROVIDERS searxng(client-cert) google_pse brave(+429 retry) brave_llm_context kagi mojeek bocha serpstack
serper serply serpapi searchapi serphouse openserp(6-engine, KEYLESS) duckduckgo bing azure(schema-guessing)
yandex(base64->XML) yacy(digest auth) exa linkup ydc jina sougou tavily perplexity perplexity_search
ollama-cloud microsoft_web_iq firecrawl(accepts v1 flat AND v2 {web:[]}) external
RESULTS->CONTEXT process_web_search routers/retrieval.py:2795 — parallel search under optional semaphore,
URL dedup, then 3 branches: BYPASS_WEB_SEARCH_WEB_LOADER uses snippets as documents :2875 |
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL returns raw docs consumed by item.get('docs') branch
retrieval/utils.py:1602 | else save_docs_to_vector_db into OWNER-BOUND EPHEMERAL collection
web-search-{user.id}-{sha256}[:63] :2779

## EMBEDDING & RERANKING
get_embedding_function utils.py:1098 returns an AWAITABLE CLOSURE. engine '' = local sentence-transformers,
.encode in a thread, DEFERRED None-check so a missing model DEGRADES RATHER THAN CRASHES BOOT :1113.
ollama|openai|azure_openai batch by embedding_batch_size then asyncio.gather under optional
Semaphore(concurrent_requests) or sequential :1149-1168; ANY None BATCH RAISES rather than silently
short-filling :1174. Providers: agenerate_openai_batch_embeddings :912 | azure :988 | ollama :1061;
sync Azure retries 429 FIVE TIMES w/ Retry-After :975.
PREFIX DUAL-MODE: injected as JSON field when RAG_EMBEDDING_PREFIX_FIELD_NAME set, else STRING-CONCATENATED
  generate_embeddings :1202
RERANKING get_reranking_function :1245 -> predict([(query,text)...]) closure.
  ExternalReranker models/external.py:13 (Cohere-style /rerank, re-sorts by index) |
  ColBERT models/colbert.py:13 (MaxSim + softmax) | local CrossEncoder
  RerankCompressor utils.py:1731 applies reranker or FALLS BACK TO COSINE SIMILARITY OF EMBEDDINGS :1772;
  applies r_score threshold :1787, truncates to top_n
HYBRID query_doc_with_hybrid_search :485 builds LangChain EnsembleRetriever over BM25Retriever +
  VectorSearchRetriever :299 weighted by hybrid_bm25_weight, DEDUPED ON CHUNK_HASH_KEY = SHA-256 OF CHUNK
  TEXT :291,:561 so BM25 "enriched texts" (get_enriched_texts :364 — filename repeated for weight,
  headings, snippet) DON'T DEFEAT RRF. Native path tried first :422 and SILENTLY FALLS BACK on any
  exception :480.

## QUERY PATH
1 QUERY GEN utils/middleware.py:2003 -> generate_queries routers/tasks.py:404; LLM JSON rescued by
  LAST-BRACE SLICING middleware.py:2018, falling back to [last_user_message] :2043
2 ENTRY get_sources_from_items utils.py:1334. Folders expand to member files FIRST :1357. Each item type
  resolves to either a direct query_result or a list of collection_names. EVERY branch enforces ownership
  or AccessGrants.has_access :1412,:1537; untrusted raw collection_name on untyped items IGNORED unless
  BYPASS_RETRIEVAL_ACCESS_CONTROL :1612
3 *** AUTHZ filter_accessible_collections :1268 = THE SINGLE AUTHORIZATION CHOKE POINT FOR RETRIEVAL.
  regex ^[A-Za-z0-9_-]{1,255}$ applied BEFORE the admin bypass :1290, then PREFIX POLICY —
  file-* -> has_access_to_file | user-memory-* -> SELF ONLY | web-search-* -> web-search-{user.id}-* |
  knowledge-bases -> ALWAYS DENIED | else KB ACL or ENABLE_RETRIEVAL_UNSCOPED_COLLECTIONS ***
4 RETRIEVAL query_collection :697. Hybrid -> :782: native first across all (collection x query) pairs,
  ACCEPTED ONLY IF EVERY PAIR RETURNED NON-NONE :814; else prefetch all collections concurrently :834 +
  BM25+vector ensemble. Non-hybrid embeds all queries in ONE call :759, fans out query_doc via to_thread :762
5 THRESHOLD+MERGE RerankCompressor drops below r; merge_and_sort_query_results :637 dedups on
  CHUNK_HASH_KEY, keeps MAX score, sorts desc, slices to k. k < k_reranker triggers a SECOND sort/cut :594
6 CITATIONS sources = {source:item, document:[], metadata:[], distances:[]} :1671.
  get_source_context utils/middleware.py:942 assigns STABLE INTEGER IDS keyed on metadata.source and emits
  <source id="N" name= resource-type= resource-id=>body</source>, injected via rag_template :994
EXTERNAL KNOWLEDGE BYPASSES ALL OF THE ABOVE: retrieve_external_knowledge external.py:292 dispatches
  _retrieve_qdrant/_retrieve_milvus/_retrieve_pgvector :89,:136,:208 against CUSTOMER-OWNED stores w/
  configurable field mappings (_normalize_result :34) and SQL identifiers validated by _safe_identifier :83

## SSRF HARDENING — SOPHISTICATED AND LOAD-BEARING
DNS re-resolution ELIMINATED by replacing urllib3's _new_conn web/utils.py:184
Playwright navigation INTERCEPTED and fetched OUT-OF-BROWSER w/ per-hop re-validation :720,:774
Parser-confusing characters rejected :138. IPv6-embedded IPv4 unwrapped :82.
_SSRFSafeConnector/_SSRFSafeAdapter :254/:238 | validate_url :129 | _assert_addresses_allowed +
WEB_FETCH_FILTER_LIST :111 = THE EGRESS CONTROL POINT
BUT trust_env=True PROXIES BYPASS THE CONNECT-TIME IP CHECK BY DESIGN (documented :276)

## EXTENSION POINTS
VECTOR STORE: subclass VectorDBBase, add enum to vector/type.py, add lazy-import case factory.py:16.
  Override hybrid_search for native fusion. MUST NORMALIZE DISTANCES TO ASCENDING-GOOD [0,1] —
  NOTHING ENFORCES THIS.
LOADER: implement .load()->list[Document], branch in loaders/main.py:486, register keys in
  LOADER_CONFIG_KEYS utils.py:70 so admin settings reach it
SEARCH PROVIDER: (...,query,count,filter_list)->list[SearchResult], elif in search_web.
  ZERO-CODE ALTERNATIVE: `external` provider web/external.py + EXTERNAL_DOCUMENT_LOADER_URL +
  external knowledge connections already give a FULL OUT-OF-PROCESS INTEGRATION SURFACE
GOVERNANCE/DATA-RESIDENCY LANDING ZONES:
  filter_accessible_collections utils.py:1268 = single authz choke point -> AUDIT HOOKS BELONG THERE
  process_metadata vector/utils.py:38 = where PII redaction/classification tags attach
  retrieval/external.py = READY-MADE "DATA NEVER LEAVES THE CUSTOMER'S STORE" PATH
  pgvector pgcrypto dbs/pgvector.py:79 = only at-rest encryption
  _assert_addresses_allowed web/utils.py:111 = egress control
  save_docs_to_vector_db routers/retrieval.py:1637 = where retention/lineage metadata would be stamped

## GOTCHAS
- CONFIG COUPLING IS BIMODAL: vector backends read MODULE-LEVEL constants from open_webui.config AT
  IMPORT TIME — changing VECTOR_DB or any PGVECTOR_* REQUIRES A RESTART. Loaders and web loaders read a
  RUNTIME DB-BACKED config dict (get_loader_config utils.py:130, cfg() web/utils.py:1031). TWO CONFIG
  SYSTEMS IN ONE PACKAGE.
- COLLECTION NAMING IS A CROSS-CUTTING CONTRACT WITH NO OWNER. file-*, user-memory-*, web-search-*,
  63-hex-char hashes, bare KB UUIDs pattern-matched INDEPENDENTLY in filter_accessible_collections :1307,
  _get_collection_and_tenant_id qdrant_multitenancy.py:100, _get_collection_and_resource_id
  milvus_multitenancy.py:84, s3vector.py:589. MT modules carry ALL-CAPS WARNINGS that a naming change
  causes SILENT DATA CORRUPTION. Milvus mangles `-`->`_`, Weaviate to PascalCase — BOTH LOSSY, CAN COLLIDE.
- BROAD EXCEPTION SWALLOWING returns None/empty: Chroma search :102, OpenSearch :157,
  Weaviate delete/reset :334,:341, native-hybrid fallback utils.py:480 — FAILURES PRESENT AS "NO RESULTS"
- SHARP: Datalab writes to HARDCODED /app/backend/data/uploads/marker_output datalab_marker.py:211 |
  kagi.py:36 and mojeek.py:28 contain STRAY print() | Kagi applies the domain filter to SearchResult
  OBJECTS rather than dicts kagi.py:39 SO THE FILTER NEVER MATCHES
