# src/lib/utils (28) + workers + pyodide + src/routes (58) + build config

## ROUTING — PURE SPA
*** ONE route-level module in the ENTIRE tree: routes/+layout.js:10 `export const ssr = false`,
:16 trailingSlash='ignore'. THERE ARE NO +page.ts/+page.server.ts/load FUNCTIONS ANYWHERE — every page
fetches in onMount. Static build, adapter-static, fallback index.html. ***
ROOT routes/+layout.svelte (1438L) wraps everything: socket, i18n, session, theme, toasts.
OUTSIDE THE GROUP: /auth (640L, redirect-aware ?redirect= persisted to localStorage.redirectPath :164,
  auto-SSO redirect gated on STRICT SINGLE-PROVIDER CHECK :180-195, trusted-header/auth===false
  auto-sign-in :199, OAuth cookie pickup oauthCallbackHandler :127) | /error | /s/[id] (243L PUBLIC
  read-only shared chat, loads via getChatByShareId w/ localStorage.token ?? '' SO IT WORKS
  UNAUTHENTICATED) | /watch?v= YouTube shim
(app) GROUP routes/(app)/+layout.svelte (595L) IS THE AUTHENTICATED SHELL AND THE APP'S REAL AUTH GUARD:
  onMount redirects to /auth?redirect= when $user null :239 (gotoAuth :222), reactive $: at :441
  re-guards on later logout. Loads settings/models/banners/tools in PARALLEL :249-256, tool+terminal
  servers (setToolServers :117), registers ~18 GLOBAL KEYBOARD SHORTCUTS :276-383, renders <Sidebar> +
  <main id="main-content">, handles legacy IndexedDB Chats migration banner (checkLocalDBChats :72),
  handles ?settings= deep links openSettingsFromUrl :191 DOWNGRADING admin:* FOR NON-ADMINS
CHILDREN / -> Chat | /c/[id] | /channels/[id] | /folders/[folderId] | /calendar (380L self-contained
  month/week/day) | /notes,/notes/[id],/notes/new (layout guards enable_notes + permissions.features.notes
  :11-19) | /automations,/automations/[id] (guards enable_automations :57, setContext('automationsLayout')
  contract :48; list page 691L w/ search debounce, paging, bulk enable/disable, RRULE pretty-print
  formatRRule :308, JSON import/export) | /playground/{,completions,images} | /workspace/* (layout 253L IS
  THE PERMISSION GATE, per-section goto('/') :80-102, tab counts loadWorkspaceCounts :48) | /admin/*
  (layout:16 redirects non-admins, bounces /admin/functions when enable_plugins off)
*** /admin/settings, /admin/settings/[tab] and /admin/analytics[/tab] ARE PURE REDIRECT SHIMS into
/?settings=admin%3A... — ADMIN SETTINGS LIVE IN THE MODAL, NOT A ROUTE. ***
*** /home/+page.svelte IS A ZERO-BYTE FILE and its layout's nav links point at /playground/notes and
/playground/completions. DEAD/INCOHERENT ROUTE. ***
EDITOR ASYMMETRY: models/edit, skills/edit, tools/edit, functions/edit read the record id from ?id= QUERY
  PARAMS, while prompts/[id], knowledge/[id], notes/[id], automations/[id] use PATH PARAMS.

## APP BOOTSTRAP
1 app.html:47-126 BLOCKING INLINE IIFE reads localStorage.theme (default 'system' :53), applies
  dark/light/her classes + OLED CSS-var overrides :60-66 BEFORE PAINT, preloads splash, injects splash
  logo on DOMContentLoaded. #splash-screen is fixed z-100 over the app.
2 SvelteKit hydrates; +layout.js forces CSR only
3 +layout.svelte onMount :1064 MONKEY-PATCHES window.fetch :1066 so any 401 on an authenticated
  same-origin request triggers confirm-then-clearExpiredSession() :913; registers pull-to-refresh touch
  handlers :1090-1115; calls window.applyTheme() if static/loader.js defined it :1118; detects Electron
  via window.electronAPI :1123 wiring desktopEventHandler :961; sets up
  BroadcastChannel('active-tab-channel') LAST-ACTIVE-TAB ELECTION :1148 + visibility/pageshow :1176
4 CONFIG getBackendConfig() :1226. On error.authRedirect does a FULL-PAGE window.location.href='/' SO A
  FORWARD-AUTH PROXY CAN REDIRECT NATIVELY :1229-1233
5 I18N initI18n(localStorage?.locale) :1240 UNCONDITIONALLY, EVEN WHEN CONFIG FAILED, so /error renders
  text. bestMatchingLanguage(languages, navigator.languages, 'en-US') utils/index.ts:1364, then dayjs.locale
6 SOCKET setupSocket($config.features?.enable_websocket ?? true) :1263 -> io(WEBUI_BASE_URL,
  {path:'/ws/socket.io', auth:{token:localStorage.token}}) :166. On connect calls getVersion() and
  *** HARD-RELOADS THE PAGE IF version OR deployment_id DRIFTED :205-213 ***, starts heartbeat, emits
  user-join. Disconnect toasts SUPPRESSED for mobile tab-resume (isLikelyResumeDisconnect :142)
7 SESSION getSessionUser(localStorage.token) :1267; on success re-fetches config, pushes timezone,
  relays token to Electron. On failure clears the token. No config -> goto('/error') :1303
8 Splash removed, loaded=true :1332/:1335. `her` theme drives a spring progress bar + greeting.mp3
*** THE ROOT LAYOUT IS ALSO THE RPC ENDPOINT FOR THE BACKEND: chatEventHandler :558 dispatches
execute:python -> Pyodide :624, execute:tool -> executeTool :497, request:chat:completion -> DIRECT-
CONNECTION STREAMING RELAYED BACK OVER THE SOCKET :630-716. Session-targeted events processed REGARDLESS
OF VISIBILITY because the server's sio.call BLOCKS ON THE CALLBACK :618-621. ***

## UTILS — utils/index.ts is 2334 lines
SANITIZATION/MARKDOWN sanitizeResponseContent :88 | processResponseContent/processChineseContent :99,:109
  (inserts spaces around ** when Chinese delimiters break the parser) | replaceOutsideCode :49 (the
  CODE-FENCE-AWARE substitution primitive) | replaceTokens :58 ({{char}},{{user}},{{VIDEO_FILE_ID_}},
  {{HTML_FILE_ID_}}) | removeAllDetails/removeDetails/processDetails :1050,:1038,:1062 | removeFormattings
  | removeEmojis :993 (\p{RGI_Emoji}/gv) | cleanText | unescapeHtml
MARKED EXTENSIONS utils/marked/: extension.ts (<details>/<summary> block tokenizer w/ nesting via
  findMatchingClosingTag, <u> inline, lheading override) | katex-extension.ts (delimiter table :1,
  PRECOMPILED Unicode-property regex :20 — a DELIBERATE PERF FIX WORTH ~87% OF RENDER TIME) |
  citation-extension.ts ([1],[1,2],[1#anchor]) | footnote-extension.ts | mention-extension.ts (<@id|label>)
  | colon-fence-extension.ts (:::writing{} from newer OpenAI models; HAS A VITEST SUITE) |
  strikethrough-extension.ts (disables single-tilde del)
RENDERING sanitizeSvg :2107 | initMermaid :2084 (securityLevel:'loose') | renderMermaidDiagram :2143
  (sanitizes + cleans leaked temp nodes) | renderVegaVisualization :2162 (OVERRIDES loader.load/
  loader.sanitize TO BLOCK EXTERNAL FETCHES) | getCodeBlockContents :2202 (groups html/css/js into artifacts)
FILES extractContentFromFile :1864 (PDF via lazy pdfjs, DOCX via mammoth, ODS/ODT/ODP, text fallback) |
  docxToHtml.ts | excelToTable.ts | pptxToHtml.ts (1075L FROM-SCRATCH PPTX->canvas->PNG renderer:
  relationships, theme colors, placeholders, text layout, tables, bar/line charts, connectors) |
  hash.ts computeFileHash (PURE-JS SHA-256 FALLBACK for non-secure contexts) | compressImage/
  resizeImageToDataURL :366 (ANDROID toBlob WARM-UP HACK) | convertHeicToJpeg | formatFileSize
CHAT/HISTORY convertMessagesToHistory :198 | createMessagesList :1406 | sanitizeHistory :238 (REPAIRS
  MALFORMED NODES FROM FAILED REGENERATIONS) | convertOpenAIChats/Messages :930,:832 |
  getUsageTokenCount :1427 (normalizes across OpenAI/Ollama/llama.cpp field names)
MODEL/TOOL convertOpenApiToToolPayload :1554 + resolveSchema :1467 (FULL $ref/oneOf/anyOf/allOf
  resolution, path-level parameter merging) | connections.ts
SMALL MODULES safeImageUrl.ts (allowlist: relative, data:, same-origin, Gravatar; external only when
  opted in) | csp.ts injectCsp | chatId.ts (temporary:/local:/channel: prefixes) | text-scale.ts |
  codeHighlight.ts (ext->Shiki lang map + lazy import('shiki'), EXPLICITLY REPLACING a bundledLanguages
  import THAT COST 5-10 MB) | codemirror.ts | transitions (flyAndScale) | characters/index.ts (TavernAI
  PNG tEXt chunk parsing w/ CRC validation) | google-drive-picker.ts | onedrive-file-picker.ts (MSAL)

## WORKERS & PYODIDE
KOKORO TTS workers/kokoro.worker.ts loads kokoro-js + @huggingface/transformers, picking webgpu when
navigator.gpu exists else wasm :23, env.backends.onnx.wasm.wasmPaths='/wasm/' :5 matching viteStaticCopy.
KokoroWorker.ts main-thread facade: serialized FIFO requestQueue, init/generate/terminate, blob URLs.
PYTHON two interchangeable backends selected at runtime pyodide/createPyodideWorker.ts:7 — a REAL Web
  Worker (workers/pyodide.worker.ts) when config.features.enable_pyodide_file_persistence is on,
  OTHERWISE PyodideSandboxHost — an <iframe sandbox="allow-scripts"> WITH srcdoc
  (pyodideSandboxHost.ts:211) THAT QUACKS LIKE A WORKER (postMessage/addEventListener/terminate).
  Host filters by event.source :218 BUT POSTS WITH '*' AS TARGET ORIGIN :286 — acceptable ONLY because
  the frame is opaque-origin.
  Real worker MOUNTS IDBFS AT /mnt pyodide.worker.ts:52 + syncfs in/out; the sandbox has NO PERSISTENCE.
  Both support untyped/execute + fs:upload|list|read|delete|mkdir|sync, install via micropip, and PATCH
  matplotlib.pyplot.show TO PRINT A BASE64 DATA URI :194-219.
  *** PACKAGE SELECTION IS REGEX SNIFFING OF THE SOURCE IN THE LAYOUT, NOT THE WORKER
  (+layout.svelte:300-314). Execution capped at 60s, and A TIMEOUT TERMINATES AND NULLS THE WORKER
  :346-370 — WHICH SILENTLY DESTROYS THE IDBFS-BACKED SESSION STATE. ***

## BUILD
svelte.config.js adapter-static fallback:'index.html' -> build/. version.name is the GIT HEAD SHA :24
  (package-version/timestamp fallbacks), polled every 60s :38; beforeNavigate in root layout :99 uses
  updated.current to UNREGISTER SERVICE WORKERS AND HARD-NAVIGATE on a new deploy.
vite.config.ts proxies /api /ollama /openai /oauth /ws to WEBUI_BACKEND_URL||http://localhost:8080 in dev,
  ws:true on /api and /ws. IN PROD THE PYTHON BACKEND SERVES build/ AND THOSE PATHS NATIVELY — NO PROXY.
  APP_VERSION/APP_BUILD_HASH are define'd globals. viteStaticCopy copies onnxruntime-web JSEP wasm to /wasm.
  *** esbuild.pure STRIPS console.log/debug/ERROR UNLESS ENV=dev — console.error IS DROPPED IN PRODUCTION
  BUILDS. *** sourcemap:true SHIPS MAPS TO PROD.
TAILWIND v4: tailwind.css uses @import 'tailwindcss' + @config + an @theme block redefining the gray ramp
  in OKLCH and --font-sans fed by var(--app-font-family). tailwind.config.js keeps darkMode:'class' and
  DISABLES the typography plugin's pre/code styling. app.css (1003L) holds prose presets, ProseMirror/
  TipTap styling, scrollbars, and a large HIGH-CONTRAST ACCESSIBILITY LAYER :873-1003 toggled reactively
  from $settings.highContrastMode (+layout.svelte:1359).
npm run dev/build FIRST RUN node scripts/prepare-pyodide.js to vendor Pyodide into /pyodide/.
package.json scripts are NPM-BASED. tsconfig sets strict:true w/ checkJs BUT most route files are plain
  JS or loosely typed.

## GOTCHAS
- *** GUARDS ARE ADVISORY, NOT ENFORCING. Every guard is a client-side goto in onMount, so the page
  component MAY BRIEFLY MOUNT BEFORE THE REDIRECT LANDS, and ROUTE PROTECTION IS ENTIRELY COSMETIC —
  THE BACKEND MUST AUTHORIZE INDEPENDENTLY. ***
- ssr=false IS GLOBAL so window/localStorage/document are used freely at MODULE TOP LEVEL. Any future
  attempt to re-enable SSR WOULD BREAK BROADLY.
- SANITIZATION RISKS: Mermaid runs securityLevel:'loose' so EVERYTHING it emits MUST go through
  sanitizeSvg before any {@html} sink; renderMermaidDiagram does, BUT A DIRECT mermaid.render CALL WOULD
  NOT. auth/+page.svelte:612 renders DOMPurify.sanitize(marked(login_footer)). marked/extension.ts
  detailsRenderer INTERPOLATES token.text AND ATTRIBUTE VALUES UNESCAPED into HTML, so <details> handling
  DEPENDS ON A DOWNSTREAM DOMPurify PASS.
- postMessage ORIGIN ALLOWLIST ['https://openwebui.com','https://www.openwebui.com',
  'http://localhost:9999'] IS DUPLICATED IN FOUR PLACES (+layout.svelte:1051, admin/functions/create:74,
  workspace/models/create:69, workspace/tools/create:60). ADD A SOURCE -> EDIT ALL FOUR.
- +layout.svelte GLOBALLY MONKEY-PATCHES window.fetch — EVERY network call in the app carries an extra
  401 probe path. The root layout is ~1400 lines mixing socket transport, RPC dispatch, Electron bridge,
  auth expiry and theming — IT IS THE SINGLE HIGHEST-RISK FILE IN THIS SCOPE.
