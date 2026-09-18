# workspace/ (48) + notes (7) + automations (9) + playground (5) + calendar (5)
"Workspace" = end-user authoring surface for reusable artifacts: Models (presets on a base model),
Knowledge (RAG collections), Prompts (slash-commands w/ GIT-LIKE VERSION HISTORY), Tools (in-browser
Python toolkits), Skills (markdown instruction packs).
*** FUNCTIONS ARE *NOT* IN THIS TREE — they live in admin/Functions*, and
routes/(app)/workspace/functions/create/+page.svelte:6 IS A STUB that goto('/admin/functions/create').
Workspace consumes Functions READ-ONLY via the $functions store. ***

## SHARED LIST CHASSIS (all five)
debounced search (300ms) | ViewSelector (All / Created by you / Shared with you, persisted to
localStorage.workspaceViewOption) | optional TagSelector | click-to-sort headers setSortKey() |
a shiftKey listener that SWAPS THE ROW MENU FOR A ONE-CLICK DELETE | per-row write_access gating |
Badge "Read Only" | a workspaceActions store publishing Create/Import/Export into the shared layout header

## THE MODEL BUILDER Models/ModelEditor.svelte
Identity: name AUTO-SLUGS INTO id while !edit :69-76; id disabled on edit.
Profile image: file -> canvas resize 250x250 -> toDataURL('image/webp',0.8) INLINED AS BASE64
  meta.profile_image_url; GIF/WebP SKIP RESIZING to preserve animation :525-593
Base model from a filtered $models list EXCLUDING presets, arena, direct connections and (for non-admins)
  hidden models — getBaseModelItems :174-195
System prompt gets a LIVE CHAT-VARIABLE LINTER getChatVariablesPreview :121-170 extracting
  {{chat.variables.x|type}} / {{user.variables.x}}, ENFORCING lowercase snake_case, REQUIRING options=[...]
  on selects, WARNING when user variables carry metadata
Attachments: Models/Knowledge.svelte (collections/notes/files/folders + direct upload), ToolsSelector,
  SkillsSelector, FiltersSelector + DefaultFiltersSelector (only toggleable filters), ActionsSelector —
  all on Models/TypeaheadSelector.svelte with an "Enable all (n)" affordance
Capabilities.svelte:11-66 defines TWELVE flags: vision, file_upload, file_context, web_search,
  image_generation, code_interpreter, terminal, usage, citations, status_updates, memory, builtin_tools.
  file_context HIDDEN unless file_upload on :78-83. builtin_tools reveals BuiltinTools.svelte
  (16 server-side tools, *** STORED INVERTED — ONLY `false` ENTRIES ARE PERSISTED :82-89 ***).
  terminal reveals TerminalSelector.
SUBMIT :230-375 validates id/name/base-model, REFUSES while any knowledge item is status==='uploading',
  then *** DELETES EMPTY KEYS RATHER THAN SENDING NULLS *** — meta.knowledge, toolIds, skillIds, filterIds,
  defaultFilterIds, actionIds, defaultFeatureIds, builtinTools, terminalId, tts each DROPPED when empty.
  Knowledge items narrowed by toModelKnowledgeReference to a WHITELIST OF 8 KEYS :209-228.
  params.stop split on commas; access_grants attached :266.
PAYLOAD {id,name,base_model_id,meta:{profile_image_url,description,tags,suggestion_prompts,capabilities,
  knowledge,toolIds,skillIds,filterIds,defaultFilterIds,actionIds,defaultFeatureIds,builtinTools,
  terminalId,tts},params:{system,...},access_grants} -> POST /models/create or /models/model/update.
  A JSON PREVIEW PANE RENDERS IT LIVE :1057-1067.

## KNOWLEDGE UI Knowledge/KnowledgeBase.svelte (1745L, LARGEST FILE IN SCOPE)
Paged file browser with REAL DIRECTORIES. Title/description autosave 1s debounce :970-995.
searchKnowledgeFilesById returns {items,total,directories,breadcrumbs} :192-210 rendered by
KnowledgeBase/Files.svelte (directories first) w/ KnowledgeBreadcrumbs.
DRAG-MOVE uses TWO CUSTOM MIME TYPES application/x-kb-file-move and application/x-kb-dir-move
  (Files.svelte:107, DirectoryRow.svelte:68), droppable onto directory rows AND BREADCRUMB SEGMENTS.
INGESTION FEEDBACK IS TWO-LAYERED: optimistic local items w/ status:'uploading' prepended to fileItems
  :442, PLUS a server reconciliation — getPendingKnowledgeFiles merges in-flight files not yet linked and
  starts a 5s setInterval POLL that calls init() once the queue drains :212-244
SYNC IS THE SOPHISTICATED PATH: collectDirectoryFiles() uses showDirectoryPicker w/ a FIREFOX
  webkitdirectory FALLBACK :509-578, buildDirectoryManifest hashes each file (computeFileHash),
  syncKnowledgeDiff returns {added,modified,deleted,unmodified_count,mkdir,rmdir,directory_map}, then
  cleanup -> mkdir -> UPLOAD ONLY THE DELTA :710-779

## TOOLS EDITOR + SECURITY FRAMING
Tools/ToolkitEditor.svelte wraps CodeMirror CodeEditor lang="python" w/ a ~100-line Tools class
boilerplate :54-159 demonstrating __user__, Field(...) descriptions, docstring-as-spec.
submitHandler :176-193 RUNS codeEditor.formatPythonCodeHandler() (Pyodide/black) BEFORE SAVING and
PROCEEDS UNFORMATTED ON FAILURE. Ctrl/Cmd+S -> formElement.requestSubmit(). While creating, FRONTMATTER IN
THE CODE AUTO-FILLS name/id/description :307-319.
SECURITY FRAMING IS EXPLICIT AND APPEARS TWICE: inline footer "Warning: Tools can execute arbitrary code.
Only install tools from sources you trust." :328-336 AND a BLOCKING ConfirmDialog ON FIRST CREATE :353-377
listing "Tools have a function calling system that allows arbitrary code execution". Tools.svelte:658-700
repeats it for JSON import.
*** NOTE THE EDITOR NEVER SHOWS THE CONFIRM ON EDIT — ONLY ON CREATE. ***
VALVES common/ValvesModal.svelte shared by tools AND functions, owner vs user scope, fetching
{...}/valves + /valves/spec, posting /valves/update :48-151. *** IT PERFORMS A LOSSY ROUND-TRIP ON ARRAY
VALVES — arrays JOINED TO A COMMA STRING for display and RE-SPLIT on save, skipping
input.type==='multiselect' :52-64,:129-144. ***

## ACCESS CONTROL UI — common/AccessControl.svelte (705L) IS THE SINGLE SHARING COMPONENT
Used by ModelEditor, CreateKnowledgeBase, KnowledgeBase, PromptEditor, SkillEditor, ToolkitEditor,
NoteEditor — always through common/AccessControlModal.svelte, opened by the shared AccessButton.
INTERNAL MODEL IS A FLAT GRANT LIST {id?,principal_type:'user'|'group'|'anyone',principal_id,
permission:'read'|'write'} :17-22. IT DUAL-BINDS accessGrants (new API) AND accessControl (legacy
{read:{group_ids,user_ids},write:{...}}). Two reactive blocks :435-457 CONVERT IN BOTH DIRECTIONS ON
EVERY CHANGE, guarded by stableStringify equality to avoid loops.
*** MAPPING RULES:
  accessControl===null <=> a single grant user:*:read => PUBLIC (legacyAccessControlToGrants :66-75;
    grantsToLegacyAccessControl RETURNS null whenever a public read grant exists :103-107)
  anyone:*:read => OPEN ("anyone with the link"), A STATE WITH **NO LEGACY REPRESENTATION** — it
    round-trips to an empty {read:{},write:{}} AND IS SILENTLY LOST BY ANY CONSUMER STILL ON accessControl
  otherwise => PRIVATE plus explicit group/user grants ***
Visibility is a three-option <select> :523-539 whose Public/Open entries are HIDDEN unless the caller
passes sharePublic/shareOpen — each caller derives these from
$user.permissions.sharing.{models,knowledge,prompts,skills,tools,notes} and public_*.
*** GRANTING WRITE ALWAYS UPSERTS READ ALONGSIDE IT (togglePrincipalWrite :312-326, handleAddAccess
:355-372), SO write ⊃ read IS AN INVARIANT THE UI ENFORCES BUT THE BACKEND MUST NOT ASSUME. ***
Group/user names LAZILY HYDRATED by ensureGroupsByIds/ensureUsersByIds — ONE REQUEST PER ID, NO BATCHING
:327-353,:375-405

## NOTES / AUTOMATIONS / PLAYGROUND / CALENDAR
NOTES (MATURE) NoteEditor.svelte (1512L) drives a TipTap RichTextInput w/ collaboration={true} over the
  shared socket, documentId='note:'+id. Remote edits arrive on events:note -> applyExternalNoteContent
  :230-316 which DROPS STALE EVENTS, *** DEFERS FOR 850ms AFTER A LOCAL KEYSTROKE
  (lastLocalContentChangeAt) *** and RESTORES THE CARET SELECTION after setContent. Title generation calls
  generateOpenAIChatCompletion w/ a JSON-only prompt :341-413. A NotePanel side drawer EMBEDS THE FULL
  Chat COMPONENT w/ onInsertToNote. Export txt/md/pdf (notes/utils.ts:6 jsPDF + html2canvas-pro,
  DOMPurify-sanitized). *** AIMenu.svelte IS DEAD CODE — nothing imports it. ***
AUTOMATIONS (LEAN) AutomationEditor.svelte is a READ-ONLY DETAIL PANEL pushing its header into an
  automationsLayout CONTEXT :246-259; the ACTUAL FORM is components/AutomationModal.svelte.
  *** ScheduleDropdown.svelte IS THE REAL LOGIC: a BIDIRECTIONAL RRULE BUILDER/PARSER (buildRrule :86,
  parseRrule :107) supporting ONCE (encoded as DTSTART:...\nRRULE:FREQ=DAILY;COUNT=1), HOURLY/DAILY/
  WEEKLY/MONTHLY and a RAW CUSTOM ESCAPE HATCH. ***
  DestinationDropdown is a two-level drill-down (new chat/folder/channel).
PLAYGROUND (ADMIN-ONLY, DATED) All three pages goto('/') if role!=='admin'. Chat.svelte HAND-ROLLS SSE
  PARSING over chatCompletion :140-189, maintains a FLAT messages array of EDITABLE TEXTAREAS. No shared
  message renderer, no markdown, no attachments — *** CLEARLY THE LEAST-MAINTAINED AREA. ***
CALENDAR (YOUNG) CalendarView.svelte renders month/week/day FROM SCRATCH (42-cell month grid, 24-hour
  week/day), pre-grouping into eventsByDay, clamping to 3 chips per cell. *** TIMESTAMPS ARE NANOSECONDS
  (NS = 1_000_000). *** CalendarEventModal maps a 5-option repeat select to FIXED RRULE STRINGS :39-45 —
  FAR LESS EXPRESSIVE THAN AUTOMATIONS' BUILDER — and treats events carrying meta.automation_id as
  IMMUTABLE :139,:183. A __scheduled_tasks__ calendar is FILTERED OUT of the event form :217.

## GOTCHAS
- AccessControl MUTATES ITS OWN accessGrants/accessControl PROPS INSIDE REACTIVE BLOCKS :435-457.
  Passing a non-bound prop, or a parent that rewrites on every tick, CAUSES FLAPPING.
- THE 'anyone' PRINCIPAL HAS NO LEGACY access_control ENCODING; any consumer reading accessControl
  SEES OPEN AS PRIVATE.
- ModelEditor stores profile images as INLINE BASE64 WEBP in meta.profile_image_url — model records GROW
  LARGE and are SHIPPED WITH EVERY /models/list ROW (the list itself uses the profile/image endpoint).
- BuiltinTools PERSISTS ONLY DISABLED TOOLS (builtinTools[x]=false); AN ABSENT KEY MEANS ENABLED.
  *** INVERTING THIS SILENTLY FLIPS EVERY MODEL. ***
- Tools.svelte NEVER PAGINATES :252 while Models/Prompts/Skills do — TOOL LISTS DEGRADE LINEARLY.
- Models.svelte bulk handlers issue ONE REQUEST PER ITEM WITH NO CONCURRENCY CAP :341,:353,:369,:389
- KnowledgeBase attaches drag listeners to document.querySelector('body') :1126-1129 — FRAGILE if another
  body-level dropzone mounts. :171-180 re-runs getItemsPage() from a reactive block on SIX VARIABLES;
  combined w/ the pending-file setInterval :229 it CAN PRODUCE OVERLAPPING FETCHES.
- PromptEditor debouncedSaveMetadata :218-255 REVERTS name/command/tags TO original* ON ANY ERROR,
  INCLUDING TRANSIENT NETWORK FAILURES — *** THE USER'S TYPING DISAPPEARS. ***
- *** THREE TIMESTAMP CONVENTIONS IN ONE TREE: note timestamps are NANOSECONDS divided by 1000000
  (Notes.svelte:609); calendar uses NS=1_000_000 (CalendarView.svelte:15); workspace records use
  SECONDS x 1000. ***
- CalendarSidebar.navigateMini() writes to REACTIVELY-DERIVED miniMonth/miniYear :38-39,:81-91 — the
  mini-calendar SNAPS BACK whenever currentDate changes.
- Prompts.svelte:303-313 accepts postMessage from http://localhost:9999 in addition to openwebui.com
EXTENSION: add a capability -> Capabilities.svelte:11 + an {#if capabilities.x} block ModelEditor:987-997.
Add a builtin tool -> one entry BuiltinTools.svelte:11-76 (BACKEND MUST AGREE ON THE KEY).
Add a workspace header action -> push to workspaceActions + bump workspaceCounts.
New schedule frequency -> ScheduleDropdown:27 + buildRrule/parseRrule + AutomationEditor.formatSchedule
:97-147 — *** THREE PLACES, EASY TO DESYNC. ***
