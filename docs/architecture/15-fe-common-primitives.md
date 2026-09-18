# common/ (67 files ~13.6k) + icons/ (182) + 9 loose top-level + app/
common/ IS THE DE FACTO DESIGN SYSTEM: unopinionated, slot-driven Svelte 4-style (export let +
createEventDispatcher), with EXACTLY ONE Svelte-5-runes file (CodeEditorModal.svelte:9-26).
*** NOT a published package. NO barrel index, NO stories, NO tests, NO token layer of its own.
Visual identity lives in TAILWIND UTILITY STRINGS BAKED INTO EACH COMPONENT, overridable through a
className/*Class prop (30 of 67 export className). ***
USAGE IS EXTREMELY TOP-HEAVY: Tooltip (163 external importers), Spinner (115), Modal (60), Dropdown (51),
DropdownMenu (47), ConfirmDialog (47), Switch (44) CARRY THE SYSTEM.
*** A LONG TAIL IS NEAR-DEAD: SlideShow, Overlay, Marquee and Selector have ZERO IMPORTERS ANYWHERE. ***

## OVERLAYS
Modal.svelte — props show/size(xs->3xl mapped :19-40)/containerClassName/className. PORTALS ITSELF INTO
  document.body in a reactive block :61-103, locks body.overflow, installs focus-trap w/ an
  allowOutsideClick ESCAPE FOR SONNER TOASTS AND PORTALED DROPDOWNS :64-69, pauses/unpauses the trap on
  outside pointerdown :74-85. ESCAPE ONLY CLOSES THE TOPMOST .modal :49-52.
Drawer.svelte — bottom sheet, same portal pattern BUT **NO FOCUS TRAP** :30-42
Sidebar.svelte — absolute (not fixed) slide-over; ONE importer (playground/Chat.svelte)
Overlay.svelte — UNUSED. ImagePreview.svelte — fullscreen viewer wrapping PanzoomContainer, download path
  handling data:, blob: and authenticated backend URLs :79-161. DragGhost.svelte — body-portaled
  cursor-follower used by sidebar drag.

## MENUS
*** Dropdown.svelte (359L) IS THE WORKHORSE AND IS HAND-ROLLED, NOT bits-ui: portal action :42-65 w/ a
ResizeObserver that RE-POSITIONS ON CONTENT GROWTH, trigger action capturing the first child :68-88,
auto-flip + edge clamping :111-158, and a SEPARATE visualViewportAware PATH FOR MOBILE KEYBOARDS :160-204
with SETTLE-TIMER REPOSITIONING AT 50/150/300ms :222-229. Exposes close() :299. ***
DropdownMenu.svelte (11L) IS PURE STYLING — a single mega-class with [&>button]/[&>a] DESCENDANT SELECTORS
  :7 THAT ALL MENUS INHERIT.
DropdownSub.svelte — hover submenu w/ INVISIBLE "BRIDGE" PADDING to survive diagonal mouse travel :72-82
Select.svelte — headless portal select, exported selectItem() :119. DropdownOptions and Selector are skins.
Tooltip.svelte — tippy wrapper; *** allowHTML DEFAULTS TRUE ***; content is DOMPurify.sanitize'd :44,
  instance REBUILT when the reference element changes :48-50

## INPUTS / FEEDBACK / DATA
Textarea (auto-grow via resize() that WALKS SCROLL ANCESTORS to avoid scroll-jump :36-72 + field-sizing) |
Switch (bits-ui, props incl. `inherited`) | Checkbox (tri-state w/ correct aria-checked="mixed" :42) |
MultiSelect | NativeSelect | SettingsSelect | SensitiveInput (-webkit-text-security:disc) |
Tags + Tags/{TagInput,TagList,TagItem} | Valves (JSON-SCHEMA-DRIVEN FORM: enum->select, boolean->Switch,
input.type in password/select/color/map/multiselect) | Valves/MapSelector (lazy Leaflet + OSM)
Spinner | Loader (*** IntersectionObserver that FIRES `visible` EVERY 100ms WHILE IN VIEW :15-17, NOT
ONCE ***) | ConfirmDialog (message through DOMPurify.sanitize(marked.parse(...)) :145) | Badge/Banner |
AccessButton. *** NO TOAST PRIMITIVE HERE — svelte-sonner's <Toaster> is mounted ONCE in
routes/+layout.svelte:1421, and NotificationToast.svelte (top level) is the custom body. ***
Pagination (bits-ui + a Svelte-5 {#snippet children({pages})} :15) | Collapsible (renders reasoning/
code-interpreter status text w/ dayjs durations :96-119) | Folder (Collapsible + JSON drag-drop import,
state to localStorage[`${id}-folder-state`] :111) | ChatList | ToolCallDisplay (parseJSONString
ITERATIVELY UNWRAPS NESTED JSON :52-66, isToolResultError heuristics :93-134, 10k-char truncation)

## CONTENT / DOCUMENTS
Image (safeImageUrl gating) | PanzoomContainer | SVGPanZoom | PDFViewer (688L — pdfjs canvas + TextLayer
FOR NATIVE Ctrl+F, DPR-aware re-render debounced :93-97) | PdfPagesPreview (scale 0.28) | DocxPreview |
PptxPreview | FileItem/FileItemModal (content-type dispatch :69-139) | FullHeightIframe (sandbox flags
composed :41-50, injectCsp :216, MODULE-LEVEL embedWindows TRUST REGISTRY :3-5) | EmojiPicker | Emoji |
HotkeyHint | MobileSwipePanel (315L gesture engine, slot props {visible,progress,panelStyle,backdropStyle})
| ResizableSidePanel | SplitCreateButton | InputModal | CodeEditor/CodeEditorModal | RichTextInput (+8
support modules) | *** InterfaceSettings.svelte (1921L) IS A SCREEN, NOT A PRIMITIVE — ~45 Switch rows,
shared class constants :122-129, inheritance predicate isDefaultSetting() :150-157 driving Switch's
`inherited` prop ***

## MARKDOWN/CODE RENDERING DOES **NOT** LIVE IN common/
It is in chat/Messages/, and common/FileItemModal.svelte:13-14 REACHES ACROSS TO IMPORT IT.
CodeBlock uses highlight.js DIRECTLY :566 (theme highlight.js/styles/github-dark.min.css :17), lazy-loads
Mermaid/Vega :358-372. *** common/SVGPanZoom.svelte:40-78 DUPLICATES THE sanitizeSvg CONFIG INLINE RATHER
THAN IMPORTING IT — A DRIFT RISK. ***

## LIBRARIES WRAPPED + VERSION-COUPLING RISK
bits-ui 2.x ONLY TWICE (Switch:2, Pagination:2; elsewhere used directly for LinkPreview in 6 files) |
tippy.js (Tooltip + RichTextInput/suggestions.ts:46-81) | dompurify 3.2 (6 common/ files) | marked |
turndown + @joplin/turndown-plugin-gfm (HTML->MD w/ SIX CUSTOM RULES RichTextInput.svelte:45-131) |
*** TipTap 3 — StarterKit + TableKit/ListKit/Mention/FileHandler/Typography/Highlight/CodeBlockLowlight,
WITH BubbleMenu/FloatingMenu PINNED TO v2 AND AN EXPLICIT TODO :148-151 *** | lowlight + highlight.js |
CodeMirror 6 (theme swapped via a Compartment driven by a MutationObserver on documentElement.class
:263-287) | pdfjs-dist | panzoom | docx-preview | xlsx | leaflet | focus-trap | svelte-virtual-list |
yjs + y-prosemirror | svelte-sonner | file-saver | html-entities
RISK CONCENTRATED IN: the TipTap v2/v3 menu split | pdfjs.TextLayer + HAND-COPIED pdf_viewer.css
INTERNALS :595-688 and the --scale-factor/--total-scale-factor CONTRACT :289 | a HAND-WRITTEN
SimpleAwareness SHIM Collaboration.ts:278-356 standing in for y-protocols/awareness | a LOOKBEHIND-REGEX
MONKEYPATCH of TipTap's Code input rule RichTextInput.svelte:172-182 | *** Dropdown/Select/MultiSelect/
Tags EACH REIMPLEMENT PORTAL+POSITIONING instead of using @floating-ui/dom WHICH *IS* A DEPENDENCY ***

## STYLING
Tailwind v4 via tailwind.css, custom OKLCH grey ramp INCLUDING THE NON-STANDARD gray-850 :13-24.
darkMode:'class' toggled on documentElement (+layout.svelte:996-998); *** EVERY COMPONENT HAND-WRITES
PAIRED bg-x dark:bg-y UTILITIES — THERE ARE NO SEMANTIC COLOUR TOKENS. ***
Recurring palette: surfaces bg-white dark:bg-gray-850|900|950, borders border-gray-100 dark:border-gray-800,
hovers hover:bg-gray-50 dark:hover:bg-gray-800.
*** THERE IS NO CLASS-MERGE HELPER (no clsx/twMerge/cn); components interpolate {className} LAST and rely
on SOURCE ORDER, SO OVERRIDES ARE UNRELIABLE. ***
Shared classes in app.css: .focus-ring :417-421 | .hover-reveal :68-75 (OPACITY-BASED so it stays
focusable) | .shimmer :202-241 | .scrollbar-hidden :288-297 | .markdown-prose*/.input-prose* :110-127 |
tippy dark theme :378-380
Transitions: flyAndScale (utils/transitions/index.ts:12-48, y-8px, scale 0.95, 200ms cubicOut) IS THE
HOUSE POPOVER MOTION; fade 10ms for modal scrims; slide 300ms quintOut for disclosure.
High contrast opt-in per component via $settings.highContrastMode + html.high-contrast :423-441
*** Z-INDEX LADDER IS AD HOC AND UNENFORCED: z-999 (Drawer) -> z-9999 (Modal, Dropdown content) ->
z-99999 (DropdownSub, DragGhost) -> z-99999999 (ConfirmDialog). ***

## ICONS — 182 flat files, no subfolders, no barrel
UNIFORMITY NEAR-TOTAL: all <script lang="ts">, ZERO script logic beyond export let, NONE animated.
ONLY TWO PROPS EXIST ANYWHERE — className (177 files; 104 default 'size-4', 69 'w-4 h-4') and strokeWidth
(155 files; 148 default '1.5'). *** NO COLOUR/SIZE/FILL PROP: colour is ALWAYS currentColor inherited from
the parent's text colour. *** 157 outline, 26 solid (*Solid suffix). viewBox 0 0 24 24 in 173.
~130 Heroicons-derived. Only Github and Youtube are brand-ish.
~699 imports across 188 files, ALWAYS DEFAULT IMPORTS — 527 via $lib/components/icons/X.svelte, 172 via
relative '../icons/X.svelte'. Most used XMark(98) ChevronDown(47) GarbageBin(30) Search(29) Plus(26).
*** 39 ICONS ARE IMPORTED NOWHERE. ***
TO ADD: icons/<PascalCase>.svelte exporting className='size-4' and strokeWidth='1.5', one
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width={strokeWidth} class={className}
aria-hidden="true">. NO REGISTRATION STEP.
VIOLATIONS NOT TO COPY: 7 icons HARDCODE stroke-width (CheckBox, Collapse, Expand, FilePlusAlt,
NewFolderAlt, PenAlt, TaskList — the last three DON'T EVEN EXPORT THE PROP); 4 LACK aria-hidden.
XMark.svelte:14 is the ONLY icon with a <slot/>, for injecting a <title>.

## LOOSE COMPONENTS (9 at components/ root)
ORGANIZING RULE: SHARED ACROSS TWO OR MORE FEATURE FOLDERS.
AddConnectionModal (799) / AddToolServerModal (1080) / AddTerminalServerModal (1006) — OpenAI+Ollama,
  OpenAPI+MCP, terminal connection editors, each imported by BOTH chat/Settings/* AND admin/Settings/*;
  all three share props show/edit/direct/connection/onSubmit/onDelete and ALL THREE INLINE THE SAME
  VERIFY-SPINNER AND CHEVRON SVGs INSTEAD OF USING ICON COMPONENTS
AutomationModal (224) — the ONLY one using createEventDispatcher ('save')
ChangelogModal (203) | OnBoarding (125) | ImportModal (126, workspace/Tools + admin/Functions) |
NotificationToast (127) | AddFilesPlaceholder (27) | app/AppSidebar (77, Electron icon rail)

## GOTCHAS
- *** SIX {@html} SINKS IN common/: Banner:103, ConfirmDialog:145-146, Valves:224, SVGPanZoom:40,
  FileItemModal:545 (pre-sanitized :166), DocxPreview:187. NOTE DocxPreview's *PRIMARY* PATH —
  renderAsync(...) :114-124 — WRITES DOCX-DERIVED DOM STRAIGHT INTO containerEl **UNSANITIZED**;
  ONLY THE docxToHtml FALLBACK :134 IS PURIFIED. ***
- *** Tooltip DEFAULTS allowHTML=true, so ANY UNSANITIZED content PASSED BY A CALLER BECOMES AN INJECTION
  VECTOR even though the component purifies :44. ***
- *** FullHeightIframe DEFAULTS allowScripts=true and exposes a MODULE-LEVEL isEmbedWindow TRUST LIST :3-5
  that chat/Chat.svelte uses to accept prompt messages — TURNING ON allowSameOrigin (A USER SETTING)
  REMOVES THE SANDBOX BOUNDARY and additionally enables Alpine/Chart.js BLOB-URL INJECTION :91-141. ***
- AddToolServerModal:291-325 EXPORTS BEARER TOKENS IN PLAINTEXT JSON
- A11Y GAPS: 12 common/ files carry svelte-ignore a11y-* suppressions. Drawer has NO FOCUS TRAP and NO
  role="dialog" DESPITE BEING A MODAL SURFACE. Collapsible's no-title branch :139-145 is a clickable
  <div> w/ NO KEYBOARD HANDLER. Dropdown's trigger is <span role="button" style="display:contents"> :333-341
  — display:contents REMOVES IT FROM THE A11Y TREE IN SOME ENGINES, and it has NO tabindex.
  NotificationToast's clickable container is role="status" w/ on:keydown but NO tabindex, SO IT IS
  KEYBOARD-UNREACHABLE.
- *** common/Selector.svelte IS DEAD *AND BROKEN* — it dereferences $i18n at :8,:10,:83 WITHOUT EVER
  CALLING getContext('i18n'), SO IT WOULD THROW ON MOUNT. ***
- AddTerminalServerModal:104-116 declares `const p = {}` and IMMEDIATELY READS p.image/p.env/p.cpu_limit,
  SILENTLY RESETTING POLICY FIELDS ON EDIT
- Modal/Drawer/ImagePreview EACH SET document.body.style.overflow='unset' UNCONDITIONALLY on teardown,
  SO STACKING TWO OF THEM UNLOCKS PAGE SCROLL EARLY (ImagePreview:44-46 EVEN CARRIES A TODO SAYING SO)
- Select/MultiSelect/Tags POSITION ONLY ON OPEN, SCROLL AND RESIZE — NO ResizeObserver, UNLIKE Dropdown —
  SO ASYNC CONTENT OVERFLOWS
- Textarea:25-33 LEAKS A setInterval that is only cleared once the element appears
- 11 common/ files SHIP LIVE console.log CALLS (Folder.svelte HAS 6)
EXTENSION: export className (+ *Class for compound parts), append it LAST, read $settings.highContrastMode
where focus/hover contrast matters, use flyAndScale for popovers, route menus through DropdownMenu.
PREFER CALLBACK PROPS (19 components) OVER createEventDispatcher (14) — THE CODEBASE IS MID-MIGRATION.
*** THERE IS NO THEMING SEAM BEYOND TAILWIND CLASSES: RESTYLING MEANS EDITING COMPONENTS OR FIGHTING
SPECIFICITY, BECAUSE NOTHING MERGES CLASSES. ***
