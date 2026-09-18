# chat/ PERIPHERY — 103 smaller components
GROUPS: markdown leaf renderers (11) | citations & sources (5) | code execution & artifacts |
structured output / agentic UI (tool calls, todo lists, subagent delegation, AskUserCard) |
settings panes (17) | composer command palettes (12) | terminal/FileNav panel (9) | placeholders |
chrome/modals/overlays | conversation graph (@xyflow/svelte DAG)

## MESSAGE RENDERING PIPELINE
1 EXTENSION REGISTRATION (module scope, ONCE per bundle) Messages/Markdown.svelte:1-29 registers IN ORDER:
  katex -> core extension -> citation -> footnote -> colonFence -> disableSingleTilde -> THREE
  mentionExtension instances for @ # $.
  *** ORDER MATTERS: katex FIRST so $...$ isn't eaten by the mention $ tokenizer; citation BEFORE footnote
  so [1] and [^1] don't collide (citation-extension.ts:14 EXPLICITLY BAILS ON ^[\^). ***
2 PRE-PROCESS + LEX :69-78 replaceTokens(processResponseContent(content), model?.name, $user?.name) then
  marked.lexer(processed). TWO MEMO GUARDS (lastContent, lastParsedContent) short-circuit identical input.
3 STREAMING THROTTLE :80-95 while done===false, re-lex AT MOST ONCE PER requestAnimationFrame; when done
  flips true it cancels the pending frame and parses synchronously. onDestroy cancels :98-100.
  THE WHOLE SUBTREE IS WRAPPED IN {#key id} :103 — CHANGING id BLOWS AWAY AND REBUILDS THE TREE.
4 BLOCK DISPATCH :104 -> MarkdownTokens.svelte, switching :180-635 over hr/heading/code/table/blockquote/
  list/detail_group/details/html/iframe/paragraph/text/inlineKatex/blockKatex/colonFence/space.
  Three branches land back in the periphery: blockquote -> alertComponent() AlertRenderer.svelte:46 |
  colonFence -> ColonFenceBlock | html -> HTMLToken
5 INLINE DISPATCH MarkdownInlineTokens.svelte:70-144 one {#each}, recursing <svelte:self> for
  strong/em/del/underline/link. LEAF MAP: escape->unescapeHtml | html->HtmlToken | link->NoteLinkToken if
  same-origin /notes/:id :33-46 else <a> w/ SPA interception for /notes/,/c/,/channels/ :51-67 |
  image->common/Image | codespan->CodespanToken | inlineKatex->KatexRenderer | mention->MentionToken |
  footnote->{@html DOMPurify.sanitize(...)} :132 | citation->SourceToken ONLY IF sourceIds.length>0 ELSE
  PLAIN TextToken :135-140
6 SANITIZATION three {@html} sites, all guarded: MarkdownInlineTokens:132 (DOMPurify) |
  HTMLToken.svelte:14 (DOMPurify.sanitize(text)) | KatexRenderer.svelte:61 (katex output, trusted-by-
  construction, w/ a MANUALLY-ESCAPED FALLBACK :41-46 BECAUSE throwOnError:false ONLY SUPPRESSES
  ParseError, NOT THE RangeError THROWN ON DEEPLY-NESTED INPUT)
7 KATEX :5-15 a MODULE-LEVEL PROMISE SINGLETON lazily import()s katex+mhchem+CSS ONCE for all instances;
  :37-47 caches renderedHTML in a reactive block so streaming re-renders don't re-run renderToString
8 MERMAID/CODE live in CodeBlock.svelte: :358-372 lazy-inits mermaid and ONLY RENDERS ONCE THE FENCE IS
  CLOSED (token.raw.slice(-4).includes('```')), :440 gates mermaid|vega|vega-lite, :219-223 routes Python
  to executePythonAsWorker

## CITATIONS & SOURCES
Backend RAG returns message.sources[], each {source,document[],metadata[],distances[]}.
Citations.svelte:98-143 FLATTENS them: ONE ENTRY PER DOCUMENT keyed by metadata.source ?? source.source.id,
merging duplicates and promoting bare http(s) ids into {name,url}.
TWO HEURISTICS: shouldShowPercentage :93 requires EVERY distance in [-1,1]; calculateShowRelevance :74
SUPPRESSES the display when EXACTLY ONE distance is an outlier.
Inline, the citation extension emits {ids[],citationIdentifiers[]} citation-extension.ts:57-62, where an
identifier MAY CARRY A #suffix for granular targeting. SourceToken.svelte:43-46 renders a single Source
pill for one id, or a LinkPreview popover listing all :48-76. Clicking calls onSourceClick(identifier) ->
Citations.showSourceModal :26-72, which parses "3#anchor" and BRANCHES: if the source has an embed_url and
not readOnly, it sets showControls/showEmbeds/embed stores and the right-hand ChatControls/Embeds.svelte
renders it in a FullHeightIframe w/ chat_id/message_id/source_id appended :9-39; otherwise CitationModal.
CitationModal re-merges documents :42-57, sorts by distance DESC, renders metadata.html in a SANDBOXED
CSP-INJECTED IFRAME :215-229 or markdown-truncates at CONTENT_PREVIEW_LIMIT=10000 :15,:231-259, and builds
#:~:text=first,last SCROLL-TO-TEXT DEEP LINKS via getTextFragmentUrl :67-95

## ARTIFACTS — STORE-DRIVEN, NOT PROP-DRIVEN
Artifacts.svelte:94-121 subscribes to artifactContents (AUTO-CLOSES the panel when empty, AUTO-SELECTS the
newest version when the list grows) and to artifactCode (JUMPS to the version containing that code).
type==='iframe' -> srcdoc={injectCsp(content,$config?.ui?.iframe_csp)} :249 (utils/csp.ts:6) w/ a sandbox
string assembled from FOUR $settings.iframeSandbox* FLAGS :254-262; type==='svg' -> common/SVGPanZoom.
iframeLoadHandler :41-70 INTERCEPTS in-iframe anchor clicks, rewriting same-origin navigation to pushState.

## SHARED PATTERNS
i18n universally const i18n=getContext('i18n') then $i18n.t(...). DYNAMIC KEYS ARE KEPT DISCOVERABLE FOR
THE i18next PARSER VIA DEAD {$i18n.t('...')} COMMENT BLOCKS — Settings/Shortcuts.svelte:161-206,
Placeholder/ChatList.svelte:189-206.
CALLBACK PROPS OVER EVENTS: newer components take onSelect/onSubmit/onDelete/onChange; only older ones use
createEventDispatcher (AskUserCard, RateComment, Controls, Artifacts, Overview/Flow, Tags, PortList,
CellEditor). BOTH IDIOMS COEXIST.
COMMAND-PALETTE CONTRACT: every Commands/* child EXPORTS selectUp(), selectDown(), select() and binds
filteredItems; CommandSuggestionList.svelte:54-87 drives them by keyboard and finds the active row VIA THE
DOM (document.querySelector('[data-selected="true"]')) RATHER THAN COMPONENT STATE.
DEBOUNCED PAGINATED LISTS: InputMenu/{Files,Chats,Notes} share a near-identical 200ms debounce +
MONOTONIC requestId GUARD + Loader on:visible infinite scroll.
IFRAME SANDBOX STRING: the same four-flag ternary chain appears VERBATIM in Artifacts.svelte:254,
HTMLToken.svelte:112, CitationModal.svelte:218.

## GOTCHAS
- *** HTMLToken.svelte IS THE SHARPEST EDGE: it sanitizes into `html` :14 but then does its REGEX
  EXTRACTION AGAINST THE **RAW** token.text, NOT the sanitized string, for the iframe/status/file branches
  :49,:66,:86,:103. The extracted iframeSrc :67-72 is interpolated into src with a BARE sandbox attribute
  (fully restrictive) — safe today, but ANY LOOSENING OF THAT ATTRIBUTE WOULD BE EXPLOITABLE FROM MODEL
  OUTPUT. allow-same-origin defaults FALSE everywhere (Artifacts:260, HTMLToken:118, CitationModal:224) —
  combined with allow-scripts (default TRUE) THAT COMBINATION IS THE THING TO NEVER FLIP TOGETHER. ***
- REACTIVITY TRAPS: Citations.svelte:98 is a BARE $:{...} block recomputing the whole citation reduce on
  ANY referenced store/prop change AND console.logs EVERY TIME — hot path during streaming.
  XTerminal.svelte:272 uses the COMMA-OPERATOR IDIOM $: if(($selectedTerminalId,chatId,term)) to force a
  multi-dependency reactive statement; it DISCONNECTS AND RECONNECTS ON EVERY TRIGGER, so an accidental
  extra dependency causes WEBSOCKET CHURN. Markdown's {#key id} DISCARDS ALL CHILD STATE (open
  collapsibles, mermaid renders). Suggestions.svelte:62 RESHUFFLES sortedPrompts WITH Math.random() INSIDE
  A REACTIVE BLOCK — any upstream change reorders the list.
- DEAD CODE: Placeholder/FolderKnowledge.svelte IS A ZERO-BYTE FILE still imported at
  FolderPlaceholder.svelte:7; its render path is unreachable only because selectedTab is hard-coded to
  'chats' :26 and the tab switcher is commented out :171-197.
- Citations.svelte:178 and WebSearchResults.svelte:69 LEAK EVERY CITED DOMAIN TO
  google.com/s2/favicons — A THIRD-PARTY REQUEST PER SOURCE.
- Settings/General.svelte:135-187 writes theme colors DIRECTLY onto document.documentElement.style,
  BYPASSING TAILWIND.
- FolderPlaceholder registers socket handlers in onMount AGAINST A CAPTURED $socket SNAPSHOT :147, so a
  SOCKET RECONNECT THAT SWAPS THE STORE VALUE LEAKS THE OLD LISTENERS.
EXTENSION: new markdown syntax = extension under utils/marked/, register in Markdown.svelte:16-28
(MIND THE ORDERING), branch in MarkdownTokens (block) or MarkdownInlineTokens:70 (inline).
New slash-command = component exporting selectUp/selectDown/select + branch in
CommandSuggestionList.svelte:93-249. New status type = branch in StatusHistory/StatusItem.svelte:14-147.
