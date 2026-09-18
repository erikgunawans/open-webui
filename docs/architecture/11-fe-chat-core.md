# chat/ CORE — Chat.svelte 4669L, MessageInput 2733L, Messages, ResponseMessage, MarkdownTokens
*** ALMOST NOTHING HERE FETCHES THE STREAM. The backend runs the completion AS A TASK and PUSHES EVENTS
TO THE SOCKET; THE FRONTEND POSTs ONCE AND THEN REACTS. ***

## Chat.svelte STATE
history = {messages:{}, currentId:null} :401-404 = THE SINGLE SOURCE OF TRUTH.
Around it: selectedModels/atSelectedModel/selectedModelIds :175-182, prompt, files, chatFiles, params,
chatVariables :409-414, selectedToolIds/SkillIds/FilterIds, pendingOAuthTools :315-318, feature toggles
:320-326, taskIds (BACKEND TASK HANDLES), chatTasks, generating, autoScroll
LIFECYCLE onMount :1532-1637 registers window.message (onMessageHandler :1401),
$socket.on('events',chatEventHandler), $socket.on('connect',handleSocketConnect), creates AudioQueue,
subscribes to page (route / => initNewChat()), showControls, selectedFolder.
loadChat() :2238-2400 fetches, restores history (or converts legacy via convertMessagesToHistory), runs
sanitizeHistory to REPAIR ORPHANED/MALFORMED NODES FROM FAILED REGENERATIONS :2316, forces non-current
assistants to done, RECONCILES SERVER TASK IDS WITH MESSAGE STATE :2345-2382 so background work
(title/tags/follow-ups) doesn't block input.

## SUBMIT -> STREAM -> RENDER
1 MessageInput dispatches submit -> submitHandler(userPrompt) :3057. Intercepts CLIENT-SIDE SLASH COMMANDS
  /compact /status /fork /model <id> :3068-3089; blocks on unauthenticated OAuth tools, empty prompt,
  unselected model, chat-variable conflicts/missing :3103-3112, file-count limits, web-search confirmation.
  If files still uploading OR a response is in flight and enableMessageQueue is on, the request is PUSHED
  INTO THE GLOBAL chatRequestQueues STORE KEYED BY CHAT ID :3136-3175 instead of being sent.
2 submitPrompt(content,files) :2869 merges doc-type files into chatFiles, creates the user message
  {id,parentId:history.currentId,childrenIds:[],role:'user',content,files,models} :2886-2895, pushes its
  id onto the parent's childrenIds, sets history.currentId, calls sendMessage.
3 sendMessage(_history,parentId,{messages,modelId,modelIdx,regenerationPrompt}) :3197-3362 creates
  ONE ASSISTANT PLACEHOLDER PER SELECTED MODEL :3236-3273, each w/ modelIdx identifying its side-by-side
  column, and builds messageIdsList:[{model_id,message_id,modelIdx}] WHICH IS ALWAYS FORWARDED so the
  backend persists column identity :3350-3354. Creates the backing chat LAZILY for embedded/temporary
  :3277-3300. Vision-capability check :3307-3329. Then A SINGLE sendMessageSocket CALL — THE BACKEND
  FANS OUT TO ALL MODELS :3331-3361.
4 sendMessageSocket :3401-3685 assembles the payload for generateOpenAIChatCompletion: system prompt
  ALWAYS included; FULL CONVERSATION MESSAGES ONLY FOR TEMPORARY CHATS (persisted chats are read from the
  DB BACKEND-SIDE) :3464-3520; tool_ids vs tool_servers split on the `direct_server:` prefix :3525-3537;
  skill_ids; terminal_id gated on model capability; features from getFeatures() :3364; params w/ stop
  normalized by getStopTokens() :3390; message_ids, parent_id, user_message, optional
  regeneration_prompt/assistant_message_id (continue); background_tasks for title/tags/follow-up.
  Response carries task_id(s) and, for new chats, chat_id — triggering chatId.set,
  history.replaceState('/c/<id>'), queue re-keying, params persist :3641-3679.
5 *** STREAMING LANDS ON THE SOCKET, NOT THE FETCH. chatEventHandler(event,cb) :1194-1399 filters on
  event.chat_id===$chatId, looks up history.messages[event.message_id], switches on event.data.type: ***
  response:completion -> responseCompletionEventHandler :2731 folding through
    applyResponseStreamEvent(message.output,data), appending response.output_text.delta to message.content
  chat:completion -> chatCompletionEventHandler :2752 handling output (structured), choices (OpenAI
    delta/non-stream), plain content, sources, usage, selected_model_id (arena)
  plus status, context_compaction, chat:active, chat:tasks:cancel, chat:message:{delta,files,embeds,error,
    follow_ups,tasks,favorite}, chat:outlet (BACKEND FILTER REWROTE MESSAGES — patches history.messages
    DIRECTLY and RETURNS to SKIP THE TRAILING WRITE-BACK :1277-1293), chat:title, chat:tags,
    source/citation, notification, confirmation, execute (EVALUATES SERVER-SENT JS VIA new Function :1354-1367),
    input, request:user_input (ask_user dialog), terminal:* (terminalEventHandler :1144)
6 On done :2813-2857: mark done, optional auto-copy/auto-playback, dispatch chat:finish on the LOCAL
  eventTarget (consumed by CallOverlay), scroll, fire-and-forget chatCompletedHandler, processNextInQueue

## WRITE-BACK DISCIPLINE
Every branch mutates the local `message` object and the handler ENDS WITH history.messages[event.message_id]
= message :1393 TO TRIGGER SVELTE INVALIDATION.
*** THE chat:outlet BRANCH EARLY-RETURNS PRECISELY BECAUSE IT ALREADY PATCHED history :1277-1293 —
COPYING THAT BRANCH WITHOUT THE RETURN WILL CLOBBER. ***
onHistoryChange :1874-1886 debounces getContents(), scanning for HTML/SVG code blocks -> artifactContents store

## MESSAGE MODEL
history.messages = FLAT id->node MAP + currentId. The conversation is THE PATH FROM currentId UP VIA
parentId, REVERSED (Messages.svelte:89-107).
NODE: {id,parentId,childrenIds[],role,content,output?:OutputItem[],files,models,model,modelName,modelIdx,
done,timestamp,usage,sources,code_executions,statusHistory,followUps,embeds,error,annotation,feedbackId,
merged,contextSummary,originalContent,meta}
BRANCHING = multiple childrenIds on one parent. showPreviousMessage/showNextMessage/gotoMessage
Messages.svelte:199-342 pick a sibling then WALK DOWN childrenIds.at(-1) TO THE DEEPEST LEAF before
assigning currentId. deleteMessage :453-503 RE-PARENTS GRANDCHILDREN onto the deleted node's parent.
editMessage :353-438 FORKS: user+submit => new sibling user message + send | user+no submit => in-place |
assistant+submit => "Save As Copy" as a new sibling | assistant+no submit => in-place stashing originalContent
SIDE-BY-SIDE uses modelIdx AS THE COLUMN KEY: MultiResponseMessages.svelte:161-201 groups
parentMessage.childrenIds by modelIdx (legacy fallback matching on model) into groupedMessageIds

## structuredOutput.ts — THE MODERN CONTENT MODEL
OutputItem types: message | reasoning | function_call | function_call_output | open_webui:code_interpreter
| web_search_call | file_search_call | computer_call
applyResponseStreamEvent :515-643 is A REDUCER over response.* SSE events (output_item.added/done,
  content_part.added, *.delta, *.done, response.completed) RETURNING A NEW ARRAY — ensureOutputItem/setPart
  EXPLICITLY GUARD AGAINST HOLES
buildOutputDisplayItems :344-435 collapses consecutive groupable items into detail_group tokens and
  extracts inline display_file tool results into file display items
getOutputText :437 is THE CANONICAL "VISIBLE TEXT" EXTRACTOR used everywhere message.content used to be

## MessageInput
RichTextInput (ProseMirror/TipTap) :2015-2174 keyed on richTextInput/showFormattingToolbar. onChange sets
prompt=content.md and recomputes command=getCommand(); showCommands true when the word at the cursor starts
with / # @ $ : :673-674
SUGGESTIONS registered onMount :1346-1551 as FIVE ProseMirror suggestion plugins rendering
CommandSuggestionList: @ (models+knowledge/files/filesystem) | / (client commands compact/fork/status/
model/settings/temporary + prompts + skills; selection goes through replaceSlashRangeWithPrompt :614-669
WHICH CAN INSERT MARKDOWN AS RICH TEXT) | # (knowledge) | $ (variables) | : (emoji -> codepoint :1535-1539)
VARIABLES textVariableHandler :272-391 expands {{CLIPBOARD}},{{USER_*}},{{CURRENT_*}};
  inputVariableHandler :252-270 extracts {{var}} and BLOCKS ON InputVariablesModal until resolved
FILES inputFilesHandler :1066-1176 enforces max_count/max_size, converts HEIC, compresses per
  settings+config bounds, then uploadFileHandler :898-1064. THREE UPLOAD TARGETS: terminal filesystem when
  the selected terminal declares chat_uploads==='filesystem' (getFilesystemUploadTerminal :879) | normal
  uploadFile to the server | IN-MEMORY extractContentFromFile FOR TEMPORARY CHATS.
  onDrop :1220-1305 also accepts SIDEBAR PAYLOADS (application/x-open-webui-drag): chat/folder/note become
  reference attachments, model sets atSelectedModel. Paste :2138-2173 turns >PASTED_TEXT_CHARACTER_LIMIT
  text into a .txt attachment when largeTextAsFile is on (SHIFT BYPASSES).
  Screen capture getDisplayMedia :841-877.
*** CAPABILITY GATING IS ALL-OR-NOTHING — a toggle only shows if EVERY selected model supports the
capability :741-831/:804-821, SO MULTI-MODEL SELECTIONS SILENTLY LOSE FEATURES. ***

## KEY SYMBOLS
Chat.svelte submitHandler:3057 submitPrompt:2869 sendMessage:3197 sendMessageSocket:3401
chatEventHandler:1194 chatCompletionEventHandler:2752 responseCompletionEventHandler:2731
regenerateResponse:3813 continueResponse:3846 stopResponse:3729 loadChat:2238 initNewChat:1993
setDefaults:985 processNextInQueue:2457 saveChatHandler:3973 saveControls:3987 getContextUsage:264
findPendingAskUser:525 handleToolApprovalModeChange:423 getChatVariablesForm:675
Messages.svelte buildMessages:89 handleHistoryChange:111 editMessage:353 deleteMessage:453
structuredOutput.ts applyResponseStreamEvent:515 buildOutputDisplayItems:344 getOutputText:437
MessageInput setText:408 inputFilesHandler:1066 uploadFileHandler:898 onDrop:1220 suggestions:1346

## EXTENSION POINTS
New socket event type -> branch in chatEventHandler. New request field -> sendMessageSocket:3548-3612.
New output item type -> structuredOutput.ts (buildDetailToken, GROUPABLE_OUTPUT_TYPES) + MarkdownTokens/
ConsecutiveDetailsGroup if bespoke UI. New input affordance -> suggestion char :1346 + list component.
New side panel -> tab in ChatControls.svelte. New settings pane -> allSettings entry + {#if selectedTab} branch.

## GOTCHAS
- FETCH RETURNS IMMEDIATELY; THE STREAM IS SOCKET-BORNE. Anything assuming the POST resolves when
  generation ends IS WRONG. taskIds + chat:active are THE REAL LIVENESS SIGNALS.
- STRUCTURED VS LEGACY CONTENT: message.content AND message.output COEXIST; ALWAYS read visible text
  through getOutputText(output) || removeAllDetails(content). ResponseMessage CLONES the source message
  and uses a HAND-WRITTEN FAST-PATH DIFF :126-145 instead of deep equality — adding a field that changes
  without touching content/done/output.length FALLS TO THE SLOW equal() PATH, and MUTATING message IN
  PLACE WON'T PROPAGATE BACK.
- modelIdx IS LOAD-BEARING. Duplicate models in side-by-side chat COLLAPSE ON RELOAD if messageIdsList
  isn't forwarded :3350.
- REACTIVITY TRAPS: $: if(chatIdProp!==loadedChatIdProp) and the selectedModelIds watcher :721-728 fire on
  ANY assignment — resetInput() WIPES tool/skill/feature selection, which is why initNewChat RESTORES THE
  DRAFT *BEFORE* resetInput() :2121-2123.
- PERFORMANCE: Messages throttles list rebuilds to ONE rAF while streaming and only materialises
  messagesCount(8) until scrolled; getContents() RE-SCANS THE WHOLE CONVERSATION on every history change;
  scrollToBottom TRIPLE-SCROLLS across two rAFs TO DEFEAT content-visibility:auto HEIGHT RESOLUTION
  :2402-2433. Long chats with many code blocks are the main hazard.
- SECURITY: chatEventHandler's `execute` branch RUNS SERVER-SUPPLIED JS VIA new Function :1359;
  onMessageHandler only trusts prompt-driving postMessage from same-origin, our own embed iframes, or with
  iframeSandboxAllowSameOrigin opted in :1406-1424.
