# backend/open_webui/models/ — 26 files, 16,468 lines

## Structure
Each module = one bounded concept: SQLAlchemy table class -> Pydantic mirrors/forms/responses
-> `*Table` class with async CRUD -> module-level singleton (`Chats`, `Users`, `Knowledges`).
NO SQLAlchemy relationship() anywhere. All traversal is explicit join or manual ID lookup.
Cascade is hand-written Python. No repository/service layer — routers call singletons directly.
Every method async, optional `db: AsyncSession|None`, wrapped `async with get_async_db_context(db)`.

## Entities
- User users.py:45 — role pending/user/admin, presence, JSON bags info/variables/settings/oauth/scim.
  ApiKey users.py:142 separate table, one-per-user via delete-then-insert users.py:758
- Auth auths.py:26 — id MIRRORS User.id. bcrypt/argon2. PLACEHOLDER_HASH auths.py:23 (CWE-208 timing)
- OAuthSession oauth_sessions.py:23 — Fernet-encrypted tokens, undecryptable rows self-delete :247
- Group groups.py:37 + GroupMember :73 (FK CASCADE — only real membership FK).
  sync_groups_by_group_names :516 = SSO/OIDC group-claim reconciler
- Chat chats.py:129 — `chat` JSON = {title, history:{messages:{id:msg}, currentId}} PLUS
  denormalized cols title/folder_id/share_id/archived/pinned/summary/tasks/current_message_id/meta
- ChatMessage chat_messages.py:127 — NORMALIZED mirror. Composite PK f'{chat_id}-{message_id}' :282.
  Backs all analytics. DUAL-WRITE alongside JSON blob.
- Message messages.py:38 — DIFFERENT entity: channel/Slack-like. + MessageReaction :19
- Channel channels.py:40 — type standard/group/dm, soft-delete archived_at/deleted_at.
  ChannelMember :97, ChannelFile :157, ChannelWebhook :186 (token impersonates user messages.py:196)
- Knowledge knowledge.py:48 + KnowledgeFile :99 + KnowledgeDirectory :63 (self-ref tree per KB)
- File files.py:18 — `data` holds full extracted text, routinely defer()'d knowledge.py:444
- Folder folders.py:22 — self-ref chat folder tree
- Model models.py:117 — base_model_id NULL => is base. strip_extracted_content_from_model_knowledge :37
- Tool tools.py:21 / Function functions.py:19 / Skill skills.py:20 — Python content + encrypted valves
- Prompt prompts.py:23 + PromptHistory prompt_history.py:19 — git-like parent_id commit chain, difflib :148
- Note notes.py:20 + PinnedNote :82; Memory memories.py:15 (apply_memory_operations :168);
  Feedback feedbacks.py:20 (RLHF/arena); Tag tags.py:18 (composite PK id+user_id);
  SharedChat shared_chats.py:18 (immutable SNAPSHOT not live view);
  Automation/AutomationRun automations.py:20/:42 (RRULE, claim_due FOR UPDATE SKIP LOCKED :308);
  Calendar/CalendarEvent/CalendarEventAttendee calendar.py:38/:55/:82
- Config config.py:101 — DEVIANT: KV table, staticmethods only, no Pydantic, no singleton
- AccessGrant access_grants.py:25 — the cross-cutting ACL row

## Relationships
User is root via bare `user_id: str` — NO FK. Real FKs only: chat_message.chat_id, chat_file.*,
shared_chat.chat_id, pinned_note.note_id, group_member.group_id, knowledge_file.*,
knowledge_directory.*, channel_file.* — all ondelete CASCADE.
Users.delete_user_by_id users.py:737 LEAVES Notes/Files/Memories/Knowledge ORPHANED.
Delete of Model/Tool/Note/Prompt/Knowledge/Channel calls AccessGrants.revoke_all_access first —
Files do NOT, so grants leak.
Model.meta.knowledge[] references file ids INSIDE JSON; get_model_owners_attaching_file models.py:293
does LIKE '%"file_id"%' scan then re-filters in Python.

## Triad pattern (reference: tools.py)
table class :21 -> Pydantic mirror :42 (from_attributes=True, + synthetic access_grants) ->
forms/response ladder :67-85 -> ToolsTable :99 with _get_access_grants/_to_tool_model :100-113 ->
singleton `Tools = ToolsTable()` :337.
_to_X_model exists because access_grants is NOT a column — every read must hydrate.
Followed exactly by: tools, skills, notes, models, prompts, knowledge, channels, calendar.
DEVIATIONS: config.py (no model/singleton); automations & calendar export MULTIPLE singletons;
feedbacks.py:108 redefines its own UserResponse shadowing users.UserResponse;
chats.py mixes pure static graph algos (merge_history :917, delete_message_from_history :940);
auths.py returns UserModel never AuthModel; oauth_sessions hand-constructs (decrypt first).

## Access control — access_grants.py is now SINGLE AUTHORITY
Legacy access_control JSON columns GONE from tables.
Grant = (resource_type, resource_id, principal_type, principal_id, permission) unique :36
principal_type in {user, group, anyone}. principal_id='*' + type='user' => any authenticated.
type='anyone' => genuinely unauthenticated, restricted to permission='read' (normalize :177)
Converters: access_control_to_grants :83 (None => public read EXCEPT files; {} => owner-only),
grants_to_access_control :276
HOT PATH: has_permission_filter :723 — SYNCHRONOUS query-builder appending
WHERE (owner OR EXISTS(correlated grant subquery)). Ownership always wins, owners need no grant.
permission='read_only' -> _has_read_only_permission_filter :832 (read AND NOT write, "shared with me")
Batch N+1 killers: get_accessible_resource_ids :622, get_grants_by_resources :518
HOLES: Files.check_access_by_user_id files.py:215 owner-only w/ literal TODO;
Channel group/dm BYPASSES grants entirely, requires active ChannelMember channels.py:796;
Chat uses none except resource_type='shared_chat' + folder inheritance chats.py:1756

## Key symbols
AccessGrants.has_permission_filter access_grants.py:723 — every list endpoint's authz
ChatTable.merge_history chats.py:917 — prevents concurrent message loss, rebuilds childrenIds
ChatTable._repair_chat_current_id chats.py:476 — self-heals corrupted message trees on read
ChatTable.get_messages_map_by_chat_id chats.py:1053 — 3-tier: normalized -> JSON gap-fill -> backfill
ChatMessageTable.get_messages_map_by_chat_id chat_messages.py:361 + DB_TO_JSON_KEY_MAP :351
  (snake_case cols -> frontend camelCase)
ChatTable.get_chats_by_user_id_and_search_text chats.py:1966 — filter DSL tag:/folder:/pinned:/
  archived:/shared: + dialect-specific raw JSON SQL chats.py:59
AutomationTable.claim_due automations.py:289 — distributed job claiming
Config.repair_config_rows config.py:303 — runtime legacy row-shape migration

## Extension points
New entity = copy Tools triad verbatim. Add resource_type string to comment access_grants.py:29.
MUST write Alembic migration — nothing auto-creates tables in production.
Extend without migration via meta/data JSON (ConfigDict(extra='allow') on ModelMeta/FileMeta/FunctionMeta).
Enterprise seams: (a) new permission value beyond read/write -> touch normalize_access_grants +
has_permission_filter; (b) Group.permissions JSON for entitlement bundles; (c) ChatMessage.usage for
billing/chargeback — already has per-model/per-user/per-group aggregation chat_messages.py:585-681;
(d) User.scim for directory sync.

## GOTCHAS
- TIMESTAMP UNITS INCONSISTENT. Most int(time.time()) SECONDS; but messages/channels/notes/
  automations/calendar use time_ns(). _normalize_timestamp chat_messages.py:34 copes with mixed ms/s.
  Mixing units silently yields wrong analytics.
- CHAT DUAL-WRITE IS THE CENTRAL FRAGILITY. Row write wrapped try/except, only logged on failure
  chats.py:1190 — JSON and rows can diverge. flag_modified(chat_item,'chat') chats.py:1173 MANDATORY
  after in-place mutation or SQLAlchemy won't notice.
- Errors swallowed wholesale: dozens of `except Exception: return None` — DB failure indistinguishable
  from not-found. Several typed -> list[X] return None on error (memories.py:115).
- Raw dialect SQL embedded in ORM layer: chats.py:59, chat_messages.py:69, prompts.py:336 branch
  sqlite/postgresql, raise NotImplementedError otherwise. ONLY those two DBs supported.
- JSON queried 3 ways: safe subscripting; cast(col,String).like('%"id"%') substring scans
  (models.py:299, automations.py:194) which CAN FALSE-POSITIVE; raw json_each/json_array_elements.
  users.py:365 explicit warning: never .contains() on JSON.
- No soft deletes except Channel. archived/is_active are visibility toggles NOT deletes.
- tags.py:25-31 defines __table_args__ TWICE — second wins, silently drops Index('user_id_idx').
- shared_chats.py:173 SharedChatResponse sets id=sc.chat_id while share_id=sc.id — field named `id`
  is NOT the row PK.
- Secrets at rest: valves + OAuth tokens ENCRYPTED, Auth.password hashed, but
  ChannelWebhook.token and ApiKey.key stored PLAINTEXT.
- has_permission_filter is sync inside async layer BY DESIGN (builds expressions only) — refactor tripwire.
