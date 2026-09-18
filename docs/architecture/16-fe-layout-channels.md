# layout/ (58) + channel/ (17)

## APP SHELL
routes/(app)/+layout.svelte: flex row :471-473 containing <Sidebar/> :533 then
<main id="main-content" class="contents"><slot/></main> :536-538.
*** main uses display:contents, SO EACH ROUTE PAGE IS ITSELF RESPONSIBLE FOR ITS WIDTH — the standard
idiom is md:max-w-[calc(100%-var(--sidebar-width))] gated on $showSidebar (channel/Channel.svelte:320-323).
THERE IS NO SHARED CONTENT-AREA WRAPPER; the sidebar is position:fixed (Sidebar.svelte:1133) and pages
RESERVE SPACE VIA THE CSS VAR. ***
--sidebar-width IS THE SINGLE LAYOUT COUPLING. Set on documentElement from the sidebarWidth store +
localStorage.sidebarWidth seed at mount :654-665, updated live during pointer-drag resize :640-646,
CLAMPED 220-480 :599-600. Handle #sidebar-resizer :1748-1760 w/ pointer capture :609-638.
SHELL-LEVEL MODALS SettingsModal bound to $showSettings :455 | ChangelogModal :456 | UpdateInfoToast
:458-468 | AccountPending for users whose role isn't user/admin :475-476
*** GLOBAL KEYBOARD SHORTCUTS registered ONCE here :276-383 and DISPATCH MOSTLY BY CLICKING DOM IDS
(sidebar-new-chat-button, delete-chat-button, chat-input) RATHER THAN STORE CALLS — a deliberate but
BRITTLE indirection. ***
?settings=<tab> deep links consumed and stripped by openSettingsFromUrl :191-220, DOWNGRADING admin:*
REQUESTS TO general FOR NON-ADMINS.
ROUTE REACTION: the shell itself DOESN'T re-render on navigation. The sidebar does:
$: activeMenuItemId = getActiveMenuItemId($page.url.pathname) Sidebar.svelte:219 (prefix table :201-207).
RESPONSIVE: `mobile` set from a 768px resize listener in the root layout. Below the breakpoint the sidebar
renders inside MobileSwipePanel :894-903. *** DESKTOP-COLLAPSED RENDERS A SEPARATE 42px ICON RAIL :939-1112
WITH ITS OWN logo/new-chat/search/pinned-item BUTTONS — THE RAIL AND THE EXPANDED SIDEBAR ARE TWO
INDEPENDENT MARKUP TREES THAT MUST BE KEPT IN SYNC. ***
mobile.subscribe FORCE-CLOSES the sidebar on entering mobile :670-681; showSidebar.subscribe persists to
localStorage.sidebar and toggles -webkit-app-region on <nav> FOR THE ELECTRON BUILD :682-699.

## SIDEBAR (1771L — THE DENSEST SURFACE)
Sections via Sidebar/Section.svelte, a Collapsible PERSISTING OPEN/CLOSED to
localStorage["{id}-folder-state"] :27-31,:90-94, optionally accepting drops :33-88.
ORDER: pinned menu items -> Models -> Notes -> Channels -> Folders -> Chats
CHAT LIST STATE LIVES IN stores/chatList.ts, NOT THE COMPONENT (see brief 09). Sidebar calls
refreshChatList :416-424 and loadNextChatListPage :426-437; infinite scroll is an IntersectionObserver
<Loader on:visible> at the list tail :1674-1689. Time-range headers come from SERVER-SUPPLIED
chat.time_range :1618-1645.
FOLDERS Folders.svelte splits roots into owned vs shared :19-38, renders RecursiveFolder.svelte which
recurses via <svelte:self> :911-929. *** EACH INSTANCE SELF-REGISTERS INTO A SHARED folderRegistry MAP ON
MOUNT AND DELETES ITSELF ON DESTROY :352-409,:430-431, exposing setFolderItems, upsertChat, setChatActive,
setChatReadAt, setAllChatsRead. The sidebar FANS SOCKET/READ-STATE UPDATES ACROSS THAT REGISTRY
:439-483,:762-810. *** Folder chats paginate 10 at a time via getSharedFolderChats w/ a
getChatListByFolderId fallback :523-590, w/ a queuedReload GUARD against concurrent reloads. Expanded
state debounced to the backend :505-521. CLOSING A FOLDER NULLS ITS CHAT ARRAY :616-620, so reopening
ALWAYS REFETCHES.
DRAG & DROP IS HAND-ROLLED HTML5 DnD, NOT sortablejs. Payload JSON.stringify({type:'chat'|'folder',id}) in
text/plain PLUS a marker application/x-open-webui-drag (ChatItem.svelte:330-348,
RecursiveFolder.svelte:320-336). A shared 1x1 TRANSPARENT PNG is the drag image, HOISTED TO MODULE SCOPE
in ChatItem :1-15. Drops on Chats UNPIN/UNFOLDER :1424-1490; on Pinned PIN :1527-1575; on a folder MOVE
:239-287. Dropping a JSON FILE anywhere IMPORTS CHATS :511-529,:557-572.
*** SORTABLEJS IS USED ONLY for reordering pinned menu items :221-238, pinned models
(PinnedModelList.svelte:21-52) and pinned notes (PinnedNoteList.svelte:27-54) — each writing order into
$settings and PUTting via updateUserSettings. ***
UNREAD ChatItem computes unread from updatedAt > max(lastReadAt, viewedAt) where viewedAt is LOCAL STATE
THAT SURVIVES STALE SERVER REFRESHES :122-136. Folders show a compact-formatted unread_count badge :850-857.
HOVER PREVIEW each desktop row wraps in bits-ui LinkPreview and LAZILY FETCHES THE CHAT to render a
miniature Messages view :652-677, ChatHoverPreview.svelte:51-91. *** A MODULE-LEVEL
closeActiveHoverPreview SINGLETON FORCE-CLOSES THE PREVIOUS PREVIEW BECAUSE bits-ui's SAFE-POLYGON ONLY
RE-EVALUATES ON POINTERMOVE :7-14,:117-120. ***

## USER SETTINGS MODAL chat/SettingsModal.svelte (1325L)
NON-ADMIN PANES from allSettings :180-676 filtered by getAvailableSettings :798-833:
General (theme, language, system prompt, default/advanced params) | Interface (GATED ON
permissions.settings.interface — chat bubble/width/direction, landing page mode, rich-text input,
formatting toolbar, auto-title/tags, image compression, high-contrast, background image, PDF export) |
Notifications | Keyboard | Connections (only when config.features.enable_direct_connections) |
Integrations (id `tools`, only with permissions.features.direct_tool_servers) | Personalization (only when
enable_memories AND permissions.features.memories) | Audio | Data Controls | Usage | Archived Chats |
Account | About
Admin tabs (adminSettings :679+, ids prefixed admin:) APPENDED ONLY FOR role==='admin' :832
*** PERSISTENCE IS SPLIT. Almost everything funnels through saveSettings :864-874: write $settings ->
updateUserSettings(token,{ui:$settings}) -> RE-MERGE OVER config.ui.default_interface_settings.
SO THE SETTINGS OBJECT IS SERVER-SIDE USER STATE, NOT localStorage.
GENUINELY BROWSER-LOCAL KEYS ARE NARROW and set OUTSIDE the modal: localStorage.token, sidebar,
sidebarWidth, showControls, selectedTerminalId, theme, locale, dismissedUpdateToast,
{section}-folder-state, sessionStorage.selectedModels. ***

## SEARCH — TWO LAYERS
Sidebar/SearchInput.svelte is a TOKEN-COMPLETING input offering five filter prefixes — tag:, folder:,
pinned:, shared:, archived: :25-46 — w/ live completion lists built CLIENT-SIDE from $tags and $folders
:63-186; selecting REPLACES THE LAST WHITESPACE-DELIMITED WORD :335-345
SearchModal.svelte (bound to $showSearch, ⌘K) IS THE PALETTE. *** SEARCH IS BACKEND-SIDE:
getChatListBySearchText(token,query,page) -> GET /api/v1/chats/search?text=&page= (apis/chats:484-491),
DEBOUNCED 500ms :411-419; empty query falls back to getChatList. *** The server returns snippet and
time_range; THE CLIENT ONLY HIGHLIGHTS, windowing ±60/80 chars around the match after stripping filter
tokens :289-322. Results paginate via Loader :870-883. Arrow-key nav uses [data-arrow-selected] DOM
QUERIES :466-526, w/ an actions block (new chat, new note) OCCUPYING INDICES BEFORE THE CHAT ROWS
:258-268,:357. A right-hand pane renders a READ-ONLY LIVE PREVIEW of the selected chat :890-919.
Rows carry the full ChatMenu, so rename/archive/delete/pin ALL WORK FROM SEARCH.

## CHANNELS — Slack-style, ENTIRELY SEPARATE FROM THE LLM CHAT SURFACE
THREE KINDS: '' admin-scoped "channel", group, dm (ChannelModal.svelte:29,:79-82).
Persistent messages w/ reactions, threads, pins, replies, @/# mentions, file attachments, INBOUND WEBHOOKS.
*** MESSAGES CAN ALSO BE AUTHORED BY MODELS (meta.model_id), SO A CHANNEL DOUBLES AS A SHARED AGENT
SURFACE. ***
MESSAGE MODEL {id,channel_id,user_id,user,content,data:{files[],output[]},meta:{model_id,model_name,done},
parent_id,reply_to_id,reply_to_message,reactions[{name,count,users[]}],is_pinned,pinned_by,pinned_at,
reply_count,latest_reply_at,created_at,updated_at}
*** TIMESTAMPS ARE NANOSECONDS — every render DIVIDES BY 1e6 (Messages/Message.svelte:414-445) or 1e9
:651. `data` MAY ARRIVE AS LITERAL `true`, A LAZY-LOAD SENTINEL that triggers getMessageData :140-151. ***
ROUND TRIP MessageInput.submitHandler :542-564 emits {content,data:{files}} -> Channel.submitHandler
:211-249 MINTS A temp_id, OPTIMISTICALLY unshifts a synthetic message w/ created_at=Date.now()*1e6, then
POSTs /channels/{id}/messages/post. The backend broadcasts events:channel; Channel.channelEventHandler
:136-209 matches event.channel_id===id, and for type==='message' w/ parent_id===null PREPENDS THE REAL
MESSAGE WHILE FILTERING OUT THE ROW WHOSE temp_id MATCHES :141-157 — *** THE DE-DUP KEY. ***
It also clears the sender from typingUsers and auto-scrolls if scrollEnd. Other types: message:update,
message:delete, message:reply, message:reaction* :158-180.
*** THE SAME SOCKET EVENT IS *ALSO* HANDLED GLOBALLY in routes/+layout.svelte:777-872 for unread badges
and toasts. ***
REACTIONS/PINS/EDIT/DELETE are OPTIMISTIC MUTATIONS applied in Messages.svelte BEFORE the API call,
*** WITH NO ROLLBACK ON FAILURE :141-255. ***
TYPING is SOCKET-ONLY, NEVER PERSISTED: onChange emits events:channel {type:'typing'} ON EVERY CONTENT
CHANGE :251-264, reactively fired MessageInput.svelte:566-568 — i.e. ON EACH KEYSTROKE. Receivers add the
user and arm a 5s per-user timeout :200-206. Self-events ignored by id :182-184.
THREADS threadId in Channel swaps in Thread.svelte — a Drawer below 1024px, a ResizableSidePanel above
:410-449. *** Thread registers its OWN events:channel listener :165-171 and filters on
parent_id===threadId :72, SO A CHANNEL WITH AN OPEN THREAD HAS THREE CONCURRENT HANDLERS ON THE SAME
EVENT NAME. ***
MENTIONS Tiptap suggestion plugins for @ (users+models), # (channels), / (commands), : (emoji) wired
MessageInput.onMount :570-646. MentionList MERGES CHANNEL MEMBERS (getChannelMembersById) AHEAD OF GLOBAL
searchUsers RESULTS, DE-DUPLICATED BY ID, w/ getAbortSignal() cancelling in-flight requests :43-82.
The inserted id is PREFIX-ENCODED U:|M:|C: plus |label :84-96.
PERMISSIONS channel.write_access disables the input :391-394. Edit/delete require
message.user_id===$user.id || role==='admin' :276. Channel settings gear shows for owner/admin
ChannelItem:230; member add/remove requires channel.is_manager ChannelInfoModal:119-128.
*** Public vs private computed from is_private OR a wildcard read grant (principal_id==='*') — THE SAME
isPublicChannel HELPER IS COPY-PASTED IN **FOUR** FILES: ChannelItem:29-46, channel/Navbar:28-45,
ChannelInfoModal:25-42, MentionList:167-184. ***

## NOTIFICATIONS
svelte-sonner + Web Notification API, CENTRALISED in routes/+layout.svelte. Two socket handlers attached
on user.subscribe, detached on logout :1204-1221: `events`->chatEventHandler,
`events:channel`->channelEventHandler.
Chat completions notify ONLY when the event isn't for the active chat OR the tab is backgrounded :717-721,
firing toast.custom(NotificationToast) w/ a goto click handler plus an optional new Notification() GATED
ON $settings.notificationEnabled **AND** $isLastActiveTab SO MULTI-TAB USERS GET ONE OS NOTIFICATION :733-772.
Channel messages do the same but SKIP SELF-AUTHORED EVENTS and increment unread_count :807-872.
Calendar alerts handled BEFORE chat-id checks :581-614. Connection state surfaces as toasts w/ a delay
heuristic SUPPRESSING SPURIOUS WARNINGS DURING MOBILE TAB RESUME :140-162,:253-267.

## GOTCHAS
- *** DOUBLE SOCKET REGISTRATION: Sidebar, Channel, Thread and the root layout EACH attach to
  events/events:channel. Channel and Thread CAPTURE $socket AT MOUNT TIME :279,:291 — IF THE SOCKET
  INSTANCE IS REPLACED ON RECONNECT, THE off() IN onDestroy TARGETS THE OLD INSTANCE AND THE NEW ONE KEEPS
  A LEAKED HANDLER. Sidebar GETS THIS RIGHT by caching socketInstance :715-717,:755-756. ***
- sidebarWidth.subscribe Sidebar.svelte:663-665 IS NEVER UNSUBSCRIBED
- TYPING SPAM: $: if(content) onChange() MessageInput:566 emits a socket event PER KEYSTROKE, UNTHROTTLED;
  it ALSO calls updateLastReadAt on every change Channel:263
- DUPLICATE IDS: Message.svelte renders id="message-{renderedMessageId}" ON TWO NESTED DIVS :190 and :377;
  #sidebar is on BOTH the rail :942 AND the panel :1120
- *** FOUR COPIES OF isPublicChannel and TWO COPIES OF THE ENTIRE downloadPdf/getChatAsText BLOCK
  (Sidebar/ChatMenu.svelte:66-255 vs Navbar/Menu.svelte:60-257) — FIX ONE, FIX BOTH. ***
- folderRegistry IS A PLAIN OBJECT mutated by child onMount/onDestroy and bind:-passed down TWO LEVELS;
  SVELTE REACTIVITY ON IT IS NOT GUARANTEED, and a collapsed folder's entry STILL EXISTS but returns false
  from setChatActive because chats is null
- REBRANDING: Open WebUI name/logo at Sidebar:969-973 (rail), :1155-1172 ($WEBUI_NAME + favicon),
  Channel:296-318 (<title>), UserMenu:467-498 (docs/releases links), UpdateInfoToast:24, and EVERY
  new Notification() in routes/+layout.svelte. *** ALL CARRY EXPLICIT "LICENSE COVERS THIS" COMMENTS —
  CHECK docs.openwebui.com/license BEFORE TOUCHING THEM. ***
- RESTRUCTURING THE SHELL: new top-level nav needs menuItemPathPrefixes + getMenuItemMeta +
  isMenuItemVisible :157-217 **AND BOTH ICON BRANCHES** :1053-1063 (rail) and :1275-1285 (expanded)
