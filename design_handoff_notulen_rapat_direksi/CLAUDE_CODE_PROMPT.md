# Claude Code prompt: Notulen & Layar Rapat Direksi (JUP)

> Paste everything below the line into your Claude Code session. First copy the `design_handoff_notulen_rapat_direksi/` folder into your repo root (or adjust the paths in the prompt).

---

You are implementing two connected screens for PT Jakarta Utilitas Propertindo (JUP) Board of Directors meetings. The design references are in `./design_handoff_notulen_rapat_direksi/`. **Read `README.md` there first, completely.** It is the spec: layout, sizes, tokens, copy and behaviour. The HTML/JSX files are high-fidelity **references**, not code to copy. Recreate them in this codebase's stack and patterns.

## 0. Before writing code
1. Inspect this repo: framework, router, state/data layer, styling approach, test setup, and whether `@jup/ui` is installed. Report what you find in 5–8 bullets.
2. If there is no app yet, scaffold **Vite + React 18 + TypeScript** (or Next.js App Router if the repo is already Next).
3. Install the `@jup/ui` package if it is available in our registry. If not, temporarily load `design_handoff_notulen_rapat_direksi/_ds/jup-ui-components-*/_ds_bundle.css` and wrap `window.JupUI` in a typed adapter (`src/ui/jup.ts`), so swapping in the real package later is a one-file change. **Do not re-implement or restyle the DS components.**
4. Propose a short plan (files and modules) and wait for my "go".

## 1. Non-negotiable design rules
- Wrap the tree in `<JupUIProvider theme>` and use `ToastProvider` / `useToast` for toasts.
- Use only `@jup/ui` components: Button, IconButton, Card, Badge, Tag, Alert, Dialog, Tabs, Field, Input, Textarea, Select, Checkbox, Avatar.
- **Never write hex values.** Use semantic CSS variables only (`--jup-surface-*`, `--jup-text-*`, `--jup-border-*`, status `-text`/`-bg`, spacing `--jup-s1…s8`).
- Square and flat: 0px cards, 4px controls, 2px chips. No shadows except dialogs and toasts. No gradients, no emoji. Icons come from `lucide-react`.
- Green text uses `--jup-text-brand`. A label on a green fill uses `--jup-text-on-brand` (ink), never white.
- One primary (green) button per view.
- Fonts: Space Grotesk (UI) and Space Mono (figures, IDs, eyebrows, metadata).
- Motion is linear, 120–200ms.
- All UI copy is Bahasa Indonesia, **exactly as in the README / reference files**.

## 2. Data model (generate from the schema, do not hand-type)
`design_handoff_notulen_rapat_direksi/notulen-data.js` contains `window.NOTULEN_DATA.schema`: 9 databases, 150 properties, each with `{name, type, options, description}`. Write a script, `scripts/gen-schema.ts`, that extracts it into `src/notulen/schema.ts` as a typed `as const` array. Then define:

```ts
export type PropType = 'title'|'rich_text'|'people'|'files'|'checkbox'|'select'|'status'|'multi_select'|'date'|'number'|'url';
export interface PropDef { name: string; type: PropType; options: string[]; description: string | null }
export interface DbDef { name: string; fields: PropDef[] }           // index 0 = Informasi & Ringkasan Rapat, 1..8 = agendas
export interface DateValue { start: string; end: string }            // ISO date or datetime-local, Asia/Jakarta
export type PropValue = string | boolean | string[] | DateValue;
export interface NotulenRecord { id: string; values: Record<string, PropValue>; body: string; time: Record<string, boolean>; origin: string }
export interface Meeting { id: string; records: NotulenRecord[][]; session: MeetingSession }  // records[0..8]
export interface MeetingSession { currentAgenda: number; doneAgendas: number[]; agendaEnteredAt: number }
```

Seed a new Meeting with the 12 initial records described in README → "Initial records".

## 3. Persistence
Create a repository interface, `MeetingRepo { get(id); save(meeting); subscribe(id, cb) }`. Implement it first with localStorage, keyed per meeting id. Keep it swappable for an API or realtime backend later. Both screens must read and write **the same Meeting**:
- A decision set on the Layar writes `records[7][i].values['Status keputusan']`.
- An action status change writes `records[8][i].values['Status']`.
- Agenda progress lives in `session`.
- With the localStorage repo, use the `storage` event for cross-tab sync, so a laptop tab and a display tab stay in step.

## 4. Routes
- `/rapat/:id/notulen` → **Notulen** (input tool). Fluid and responsive; see README "Screen 1".
- `/rapat/:id/layar` → **Layar** (boardroom display). Fixed 1920×1080 stage, scaled to fit; see README "Screen 2".
- `/rapat/demo/layar` → loads `rapat-dummy-data.js` mapped into a Meeting, for demos. Show the "Data dummy" badge **only** on this route.

## 5. Build order (commit after each step; keep components under ~200 lines)
1. `schema.ts` generation + types + seed + repo (with unit tests for seed counts: 9 dbs, 150 fields, 12 records).
2. `PropField`: the property-type → control renderer, exactly per the README mapping table (including the date block with "Sertakan waktu · Asia/Jakarta" and the date↔datetime conversion, the Rp prefix, the % suffix, and multi-select Tags).
3. Notulen: header, sidebar/tabs nav, AgendaView, RecordCard (collapse, delete with Dialog, add with toast), Informasi Rapat groupings + "Checklist n/6", derived views (Perlu Keputusan, Risiko Tinggi, Follow-up Board, Kalender), Panduan (render `NOTULEN_DATA.guide`), print mode (all agendas expanded, page break per agenda), and Reset with Dialog.
4. Layar: Stage scaler (ResizeObserver + resize + visibilitychange + 500ms interval fallback; never scale to 0), top bar with live clock + agenda timer (over-time = danger), left agenda nav with cur/done states, right rail (stats, Perlu keputusan, Tenggat terdekat), footer timeline + "← Sebelumnya" / "Selesai dibahas →", and keyboard (←/→, PageUp/PageDown, 0–8; ignored while in inputs).
5. The 9 Layar agenda views (00 Ringkasan … 08 Action Plan) bound to Meeting data via the field mapping in README → "Production data flow". Include the KPI deviation-tone rule (CAPEX/OPEX inverted) and the interactive decision buttons (clicking the active status again reverts to "Belum diputuskan"; toast on change). Action tiles advance status on click.
6. Theme toggle (light/dark) stored per user. Dark is the default suggestion for `/layar`.

## 6. Acceptance criteria
- Every one of the 150 properties is editable in Notulen, with the correct control and all options. Descriptions appear as hints.
- Changing a decision on `/layar` updates the Notulen "Tampilan pendukung" and the right-rail counts without a reload (cross-tab).
- `/layar` at 1920×1080 has no scrollbars or overflow in any agenda view with the demo data. It scales correctly at 1280×720 and at 3840×2160.
- No hex colours in source (`grep -rE "#[0-9a-fA-F]{3,6}\b" src` returns only test fixtures). No DS component re-implementations.
- Lighthouse a11y ≥ 95 on `/notulen`. All custom clickable elements are `<button>` with visible focus rings. Every IconButton has a `label`.
- Visual check: open each reference HTML in `design_handoff_notulen_rapat_direksi/` side by side with your build and match spacing, type sizes and states.

Start with step 0 now.
