# tools/ (5730L) + migrations/ (58 revisions) — NO backend/open_webui/test/ EXISTS

## BUILTIN TOOLS — builtin.py 4519L + knowledge_fs.py 1205L, re-exported builtin.py:66
builtin.py:6 WARNS: never import this module directly elsewhere — THE SINGLE LEGAL CONSUMER IS
utils/tools.py:47
REGISTRATION get_builtin_tools() utils/tools.py:522-802 IS THE WHOLE REGISTRY — NO decorator, NO manifest.
Tools appended to a plain builtin_functions list under nested gates. Each passes UP TO FIVE checks:
 (a) is_builtin_tool_enabled(category) reading model.info.meta.builtinTools :540 (DEFAULTS TRUE)
 (b) get_model_capability(name) from model.info.meta.capabilities :535
 (c) a global Config flag batch-fetched :546-558
 (d) a per-request features dict
 (e) has_permission(user,'features.X') w/ admins short-circuiting :560-567
INJECTION ONLY for UI-originated requests utils/middleware.py:2984-3026, gated by use_builtin_tools :2769
 (requires capabilities.builtin_tools). *** API CALLERS GET NOTHING IMPLICITLY. ***
Each entry -> {tool_id: f'builtin:{name}', callable, spec, type:'builtin'} :795-800

CATALOGUE BY CATEGORY GATE:
time :579 — get_current_timestamp builtin.py:160, calculate_timestamp :196 (dateutil.relativedelta,
  naive-day fallback :254). Both enrich w/ user's timezone.
user_input :582 — ask_user builtin.py:517. 1-3 questions, 2-3 options each, label<=80/desc<=240/
  question<=500, unique ids, timeout CLAMPED 60k-240k ms :584. Requires __event_call__ (WS round-trip
  request:user_input)
files :595-602 (needs chat files + file_upload capability + NOT file_context) — list_chat_files,
  query_chat_files :2498, grep_chat_files :2443, view_file :2737
knowledge :608-643 THREE-WAY BRANCH. With ENABLE_KB_EXEC (env DEFAULT FALSE env.py:955): kb_exec +
  query_knowledge_files, plus query/search_knowledge_bases when no model knowledge attached.
  With attached knowledge: list_knowledge, search_knowledge_files, grep_knowledge_files,
  query_knowledge_files, conditionally view_file/view_knowledge_file/view_note.
  Bare: the full seven-tool browsing set.
  query_knowledge_bases :3357 embeds the query + PAGED HEAP-SEARCH over KNOWLEDGE_BASES_COLLECTION,
  capped MAX_KNOWLEDGE_BASE_SEARCH_ITEMS=10_000 :74
chats :646 — search_chats :1502 (EXCLUDES current chat), view_chat :1600 (walks currentId->parentId
  w/ visited CYCLE GUARD)
subagents :649-655 — delegate_task :1670 (REFUSES RECURSION via request.state.internal), timer :1711
memory :658-675 — EIGHT tools: search_memories, list_memory_paths, read_memory_path, list_memories,
  update_memory :961 (batch add/replace/move/remove), add_memory, replace_memory_content, delete_memory
web_search :678 — search_web :293 (count clamped to web.search.result_count), fetch_url :332
image_generation :689-704 — generate_image :369, edit_image :439. Both PERSIST FILES TO THE CHAT ROW and
  emit chat:message:files, then TELL THE MODEL THE IMAGE IS ALREADY VISIBLE :427
code_interpreter :708 — execute_code :631. Sanitizes, PREPENDS AN __import__ MONKEY-PATCH blocking
  CODE_INTERPRETER_BLOCKED_MODULES :665-684, dispatches pyodide (frontend via __event_call__) or jupyter,
  rewrites base64 PNGs in stdout/result into uploaded URLs :744-778
notes :718 — search_notes, view_note, write_note, replace_note_content :1333 (whole-content replace OR
  NON-OVERLAPPING replace_range ops w/ optional `expected` OPTIMISTIC-CONCURRENCY text; typed error codes
  expected_mismatch, overlapping_operations)
channels :724 — search_channels, search_channel_messages, view_channel_thread, view_channel_message
skills :735 — view_skill :3467, added only when __skill_ids__ present
tasks :740 — create_tasks/update_task :3567,:3617, ONLY for saved chat IDs; TaskItem is a real Pydantic
  model :3533
automations :744 — create_automation (iCalendar RRULE, validated, limit-checked), update_automation,
  list_automations, toggle_automation, delete_automation
calendar :754 — search/create/update/delete_calendar_event. Times are NS-SINCE-EPOCH, converted through
  user's ZoneInfo :4085-4102
notifications :759 — notify :130

kb_exec knowledge_fs.py:1147 IS A SHELL EMULATOR: ls/cat/head/tail/grep/find/wc/stat/sed/tree
  (COMMAND_MAP :1101) w/ quote-aware pipe splitting (_parse_pipeline :148) and piping into
  head|tail|grep|wc|sed :1134. REAL ReDoS DEFENCE: 2.0s per-call MatchBudget in a contextvar :34-63 +
  counted-quantifier rejection validate_regex_quantifiers :90
*** ACCESS CONTROL IS ENFORCED PER-TOOL, NOT BY THE FRAMEWORK. Every knowledge/note/file path re-checks
ownership -> admin -> AccessGrants.has_access. Helpers _has_write_access_to_note:77,
_has_read_access_to_file:104, _get_accessible_chat_files:2319, _get_accessible_kb_ids:319 ***

## TOOL CONTRACT
async def returning str (JSON via JSONCodec.dumps, or plain text for fetch_url/kb_exec/_grep_file_models).
Model-visible params are ORDINARY TYPED ARGS; CONTEXT IS INJECTED BY DUNDER-NAMED KEYWORD PARAMS:
__request__ __user__(dict) __event_emitter__ __event_call__ __metadata__ __files__ __chat_id__
__message_id__ __model_knowledge__ — bound utils/tools.py:771-786
SPEC GENERATION docstring+type-hint driven: convert_function_to_pydantic_model :869 reads get_type_hints
and reST :param x: lines (parse_docstring :831, parse_description :805), then
langchain_core.convert_to_openai_function + clean_openai_tool_schema :941 (collapses anyOf null unions,
drops null defaults, defaults missing types to string). Cached as JSON and RE-PARSED PER CALL so mutation
is safe :986-995.
*** DUNDER PARAMS NEVER REACH THE SCHEMA because PYDANTIC TREATS LEADING-UNDERSCORE FIELD NAMES AS
PRIVATE ATTRIBUTES and drops them from model_fields (agent verified empirically). DB-backed tools instead
strip them EXPLICITLY utils/tools.py:332-334 ***
get_async_tool_function_and_apply_extra_params :191 binds extras via functools.partial, rebuilds
__signature__ WITHOUT them (for python-genai), wraps sync fns into coroutines, coerces str<->int from
sloppy LLM args (coerce_kwargs :203)
BUILTINS HAVE NO VALVES — Valves/UserValves are DB-TOOL-ONLY :316-322
Two runtime spec mutations: `background` STRIPPED from delegate_task when disabled :789-793;
`display_file` gets inline/page INJECTED :951

## MIGRATIONS — 58 revisions STRICTLY LINEAR, 7e5b5dc7342b (2024-06-24) -> d4c1a8e37b62
*** THE PEEWEE->ALEMBIC BRIDGE IS THE INIT REVISION ITSELF: 7e5b5dc7342b_init.py:182-186 iterates
_INITIAL_TABLES and creates each table ONLY IF ABSENT (get_existing_tables() from migrations/util.py),
so a PRE-EXISTING PEEWEE DB ADOPTS THE ALEMBIC CHAIN WITHOUT RECREATING ANYTHING. That defensive
INSPECT-THEN-ACT idiom is repeated in ESSENTIALLY EVERY LATER REVISION. ***

ARC IN FOUR MOVEMENTS:
1 2024 DENORMALIZED JSON EVERYWHERE. Init ships 12 tables, chat.chat as Text, prompt keyed on command,
  user.api_key/oauth_sub as scalar columns. 242a2047eae0 converts chat.chat Text->JSON via an old_chat
  SHUTTLE COLUMN. 1af9b942657b/3ab32c4b8f59 fold chatidtag join table into chat.meta.tags + chat.pinned
  and repoint tag's PK to (id,user_id)
2 ACCESS CONTROL GROWS IN THEN IS NORMALIZED OUT. 922e7a387820 adds `group` + access_control JSON on
  model/knowledge/prompt/tool; later file/channel/note too. Then f1e2d3c4b5a6 creates access_grant and
  BACKFILLS + DROPS ALL SEVEN access_control COLUMNS, w/ explicit semantics: NULL -> public (user:* read
  grant), {} -> private, else per-group/per-user rows. FILE IS THE EXCEPTION (NULL means private).
3 JSON ARRAYS -> REAL JOIN TABLES. 37f288994c47 (group.user_ids->group_member), 3e0e00844bb0
  (knowledge.data.file_ids->knowledge_file), then channel_file, chat_file. 374d2f66af06 rebuilds prompt
  entirely under a prompt_new->rename dance, adding prompt_history versioning and stripping leading `/`
  from commands. 8452d01d26d7 IS THE HEAVIEST: explodes chat.chat.history.messages into chat_message,
  streaming w/ yield_per=1000, 5000-row batches, SAVEPOINT-PER-ROW FALLBACK (_flush_batch), timestamp
  sanitisation.
4 2026 PRODUCT SURFACE + CONFIG RESHAPE. skill, automation/automation_run, calendar/calendar_event/
  calendar_event_attendee, shared_chat (migrating the user_id LIKE 'shared-%' HACK into a real table and
  DELETING THE FAKE CHAT ROWS), pinned_note (extracting note.is_pinned), knowledge_directory
  (+knowledge_file.directory_id, ENABLING kb_exec PATHS). 461111b60977 promotes legacy UNIQUE(id) to real
  PRIMARY KEYs. 3ff2c63645b8 (584 lines) reshapes config from ONE JSON BLOB to PER-KEY ROWS, renaming
  config->config_old for rollback and mapping ~400 dotted paths to legacy env keys.

## SCHEMA AT HEAD (~40 tables)
auth user api_key oauth_session group group_member access_grant chat chat_message chat_file shared_chat
folder file knowledge knowledge_file knowledge_directory note pinned_note tag prompt prompt_history model
tool function memory feedback config skill automation automation_run calendar calendar_event
calendar_event_attendee channel channel_member channel_file channel_webhook message message_reaction
PLUS LEGACY LEFTOVERS NEVER DROPPED: document, chatidtag, config_old
CONSTRAINTS uq_access_grant_grant (5-col), uq_knowledge_file_knowledge_file, uq_chat_file_chat_file,
uq_group_member_group_user, uq_pinned_note, uq_event_attendee, uq_knowledge_directory_knowledge_parent_name
PARTIAL/EXPRESSION INDEXES uq_user_email_lower (unique on lower(email) WHERE email IS NOT NULL),
timer_at_idx/user_id_timer_at_idx (WHERE timer_at IS NOT NULL) — both spelled w/ postgresql_where AND
sqlite_where
HOT-PATH COMPOSITES user_id_updated_at_id_idx (user_id, updated_at DESC, id), user_id_folder_unread_idx
(6 cols), chat_message_chat_role_done_idx, ix_memory_id_user_id
TIMESTAMP UNITS INCONSISTENT AND LOAD-BEARING: chat.updated_at SECONDS, note.updated_at and
message.created_at NANOSECONDS — tools convert w/ *1_000_000_000 builtin.py:1165,:1841.
folder timestamps were DateTime, converted to BigInteger seconds by 4ace53fd72c8

## MECHANICS
alembic.ini script_location=migrations, prepend_sys_path=..
*** MIGRATIONS RUN AT IMPORT TIME OF config.py, NOT FROM A CLI: config.py:62-80 defines run_migrations()
and INVOKES IT UNCONDITIONALLY AT MODULE SCOPE when ENABLE_DB_MIGRATIONS (env default True env.py:151).
FAILURES RE-RAISE, SO A BAD MIGRATION KILLS STARTUP. ***
migrations/env.py uses Auth.metadata as target metadata, imports Calendar/ChatMessage/Chat for noqa
registration, strips/reattaches SSL query params from DATABASE_URL, escapes %->%%, handles
sqlite+sqlcipher:// w/ a custom creator applying PRAGMA key, calls enable_iam_token_auth.
migrations/util.py supplies get_existing_tables() and get_revision_id()

## *** FORK-VS-UPSTREAM MIGRATION COLLISION — THE SHARP EDGE ***
The chain is a SINGLE LINEAR LIST OF 58 NODES WITH ONE HEAD. Any fork revision inserted at the tip will
COLLIDE the moment upstream adds its own — alembic will see TWO HEADS and command.upgrade(cfg,'head')
config.py:74 WILL RAISE, which (because migrations run at config.py IMPORT TIME) means
*** THE APP WILL NOT BOOT AT ALL. THE FAILURE MODE IS A STARTUP CRASH, NOT A DEGRADED FEATURE. ***
FORENSIC EVIDENCE OF EXACTLY THIS BEING FIXED BY HAND: d4e5f6a7b8c9_add_automation_tables.py has a
docstring claiming `Revises: f1e2d3c4b5a6` while its actual down_revision = 'a3dd5bedd151' — THE ONLY
such mismatch in all 58 files (agent checked every one). Someone RE-PARENTED that revision during a
rebase and didn't update the docstring.
*** TREAT THE DOCSTRING `Revises:` LINE AS UNRELIABLE; ONLY down_revision IS REAL. ***
MITIGATIONS: keep fork revisions on a NAMED BRANCH LABEL, or accept that every upstream merge requires
re-pointing fork revisions' down_revision to the new upstream head and RE-STAMPING DEPLOYED DATABASES.
Fork revision IDs use READABLE HEX-ISH SEQUENCES (a1b2c3d4e5f6, d4e5f6a7b8c9, 9a1b2c3d4e5f) vs upstream's
RANDOM 12-HEX — a useful if informal PROVENANCE MARKER.

## ADDING THINGS
BUILTIN TOOL: async def in builtin.py w/ typed args, reST docstring (:param x: per model-visible arg),
dunder context params defaulting None, str return; guard __request__ is None and __user__; enforce access
w/ AccessGrants.has_access; return JSONCodec.dumps(...,ensure_ascii=False). Import it in utils/tools.py:47
and append under a category gate in get_builtin_tools. IF IT MUTATES MEMORY add the name to
MUTATING_MEMORY_TOOLS so sub-agents can't call it :766-769. Frontend toggles read
model.info.meta.builtinTools[category] so a new category NEEDS A UI ENTRY TOO.
MIGRATION IN A FORK: NEVER autogenerate blind. House style is INSPECT-THEN-ACT
(inspector.get_columns/get_indexes/get_table_names, if 'x' not in cols) — makes revisions IDEMPOTENT and
SURVIVABLE when upstream later adds the same column. Use op.batch_alter_table for anything SQLite can't
ALTER. Handle context.is_offline_mode() if you touch indexes (959eaac8f909, f0bd01a18a3d).
Call inspector.clear_cache() after a rename/rebuild before re-inspecting (374d2f66af06, f1e2d3c4b5a6,
d4e5f6a7b8c9). SQLite needs MANUAL INDEX DROPS before DROP COLUMN (_drop_sqlite_indexes_for_column
in b10670c03dd5).

## OTHER GOTCHAS
- config.py HAS AN IMPORT-TIME SIDE EFFECT THAT MUTATES THE DATABASE. Importing it anywhere (script, test)
  runs migrations to head.
- kb_exec IS OFF BY DEFAULT (ENABLE_KB_EXEC=False) so the tool contract the model actually sees for
  knowledge is the SEVEN-TOOL BROWSING SET, not the shell
- f0bd01a18a3d DELIBERATELY RAISES AND BLOCKS STARTUP if duplicate case-insensitive user emails exist.
  NO AUTOMATIC REMEDIATION.
- 3ff2c63645b8 leaves config_old behind PERMANENTLY; its downgrade silently returns if it finds neither shape
- 461111b60977's downgrade() is `pass` — PK PROMOTION IS IRREVERSIBLE
- 856c5b02fb54 and d4c1a8e37b62 call op.add_column WITHOUT an existence check — WILL FAIL on a
  partially-migrated database
- builtin.py RE-IMPORTS Literal at line 3526 despite importing at line 12
- _has_read_access_to_file only consults __model_knowledge__ when the caller passes it — view_knowledge_file
  uses a SEPARATE KB-WALK PATH, so THE TWO FILE-READING TOOLS HAVE SUBTLY DIFFERENT AUTHZ SEMANTICS
