# Handoff: Notulen Rapat Direksi (Input Notulen) + Layar Rapat Direksi (Main Meeting Display)

## Overview
Two linked surfaces for PT Jakarta Utilitas Propertindo (JUP) Board of Directors (BOD) meetings:

1. **Notulen Rapat Direksi**: the *input/working* tool used by the secretariat (notulis) before, during and after the meeting. It records meeting info, the 8 standard agenda items, decisions, action plans, and closing/validation. It is a faithful rebuild of the original Notion-derived template (`reference/Template_Notulen_Rapat_Direksi_original.html`), preserving **all 150 properties across 9 databases, all select options, the 12 source records, and the full guide text**.
2. **Layar Rapat Direksi**: the *main display* projected in the boardroom and discussed by the BOD. It is a 1920×1080 presentation-style dashboard that walks through agendas 00–08. Decisions are recorded live (Setujui / Setujui bersyarat / Tunda / Tolak), and action items move through statuses. It is populated with **dummy data** in this prototype.

In production, both surfaces should read from and write to **one shared data model**: the Layar reads what the Notulen captures, and decisions/status changes made on the Layar write back into the Notulen records.

## About the Design Files
The files in this bundle are **design references created in HTML**: React-in-browser prototypes (Babel standalone) that show the intended look and behavior. They are **not production code to copy directly**. The task is to **recreate these designs in the target codebase's existing environment** (React/Next.js, Vue, etc.) using its established patterns. If no environment exists, a React + TypeScript app is recommended. It should consume the real `@jup/ui` package, which these prototypes use via a browser bundle (`_ds/…/_ds_bundle.js` → `window.JupUI`).

Open either HTML file directly from this folder to run it; all relative paths resolve.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, component choices and interactions. Recreate pixel-accurately using `@jup/ui` components and tokens. Never hard-code hex values in implementation; use the semantic CSS variables listed under Design Tokens (hex values are given for reference).

---

## Design System Rules (`@jup/ui`, GSM 2023 identity)
- Wrap every tree in `<JupUIProvider theme="light|dark">`. It renders `.jup-root`, where all tokens are scoped.
- **Square and flat:** panels/cards 0px radius; controls 4px; chips 2px; pill only for avatars/dots. 1px `--jup-border-default` does structural work. No shadows except modals/menus/toasts.
- **Paper, not white:** page ground `--jup-surface-page` (#F0F1F1); cards white.
- **One primary (green) action per view.** Blue = navigation/institutional.
- Green as text must use `--jup-text-brand` (#006C34), never `--jup-brand`. A label on a green fill is ink (`--jup-text-on-brand`), not white.
- Status words use `-text` tokens; fills use the base status token.
- No gradients, no emoji. Icons: Lucide (stroke 2, round caps).
- Motion: short and linear (≈120–200ms), no bounce.
- Fonts: Space Grotesk (UI/display), Space Mono (figures, IDs, metadata, eyebrows).

Components used: `JupUIProvider`, `ToastProvider/useToast`, `Button`, `IconButton`, `Card`, `Badge`, `Tag`, `Alert`, `Dialog`, `Tabs`, `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `Avatar`.

---

## Screen 1 — Notulen Rapat Direksi (`Notulen Rapat Direksi.html`)

### Purpose
The notulis fills in all meeting data: Informasi Rapat plus agendas 1–8. They add or delete records and review four derived views. The full template guide is available in the app. Output: a saved/printed notulen.

### Layout (fluid, responsive)
- **Sticky top header** (`.nt-top`): white card surface, 1px bottom border. Inner max-width 1360px, padding 20px 26px. Flex row, space-between, wraps.
  - Left: eyebrow "RAPAT DIREKSI / NOTULEN" (Space Mono 12px, letter-spacing .12em, uppercase, `--jup-text-brand`). Below it, an H1 with the meeting name (from Informasi record "Nama rapat"; fallback "Notulen Rapat Direksi"), Space Grotesk 30px/1.15, semibold, letter-spacing −0.02em. Then a meta row: Status validasi `Badge` (dot), Klasifikasi `Badge` (outline; Rahasia=danger, Internal=info), formatted Tanggal & waktu, Ruang / lokasi, "Checklist n/6" (mono).
  - Right actions: `Button ghost` "Reset" (reset icon) → confirm `Dialog`; `Button secondary` "Cetak / PDF" (printer icon); `Button primary` "Simpan HTML terisi" (download icon).
- **Shell** (`.nt-shell`): max-width 1360px, padding 26px, CSS grid `236px | minmax(0,1fr)`, gap 26px.
  - **Sidebar nav** (sticky top 150px): white, 1px border. 11 items, each 10px 12px padding, 14px text, with a record count (mono 11px, muted) on the right. Items: Informasi Rapat, 1. Strategic Update … 8. Action Plan, a separator, Tampilan pendukung (badge = pending decisions count), Panduan & checklist. Active item: 3px left border `--jup-brand`, bg `--jup-surface-brand-subtle`, weight medium. Hover: `--jup-surface-hover`.
  - **Main column**: flex column, gap 20px.
- **≤860px**: single column. The sidebar becomes a horizontal scroll row with a bottom-border active state, and the header stops being sticky.
- **Tweak `nav = tabs`**: the sidebar is replaced by `Tabs size="sm"` under the header (same items, with counts as tab badges).

### Agenda view (one per database 0–8)
- Header block (bottom 1px border): eyebrow ("INFORMASI RAPAT" / "AGENDA 01"…), H2 24px semibold, then "**Fokus:** …" text plus the unit sentence (e.g. "— satu baris untuk setiap indikator."), max 72ch, `--jup-text-secondary`. Row below: "N properti · M record" (mono, muted) on the left. On the right: `Button ghost sm` "Buka semua / Tutup semua" (only if >1 record) and `Button secondary sm` "+ Tambah record".
- Agenda 2 shows `Alert tone="info" title="Catatan angka"`: "Deviasi dan progres diisi manual, bukan dihitung otomatis. Masukkan angka persen langsung: 10 berarti 10%."
- Informasi Rapat (view 0) shows `Alert info` "HTML mandiri · bukan koneksi langsung ke Notion" (prototype-only copy; replace with real persistence messaging).
- **Record card** (`Card padding="md"`), stacked with a 12px gap:
  - Header title: a toggle button with a chevron (rotates −90° when collapsed, 120ms linear) and the record title (semibold). Untitled records show "Tanpa judul" (muted).
  - Header description: "01 / 09" (mono), origin label ("Record sumber", "Indikator awal", "Record kosong dari sumber", "Formulir kosong — belum ada record di sumber", "Record baru"), "n/N terisi" (mono), plus status badges for any filled summary keys (Status validasi, Status, Status keputusan, Status progres, Status mitigasi, Tingkat risiko, Urgensi, Evaluasi strategi, Basis pelaporan, Kategori, Jenis stakeholder).
  - Header action: `IconButton sm label="Hapus record"` (trash) → confirm `Dialog` ("Hapus record?", Batal / Hapus [danger]).
  - Body (when open), sections with a 20px gap:
    1. Title field (`Input`).
    2. Groups, each with an H4 heading (Space Mono 12px uppercase, .1em tracking, 1px bottom border `--jup-border-subtle`).
       - **Informasi Rapat groups** (32 props): *Informasi rapat* (Tanggal & waktu, Ruang / lokasi, Tautan meeting, Periode pelaporan) · *Peserta* (Pimpinan rapat, Peserta, Peserta berhalangan, Peserta eksternal & jabatan, Notulis) · *Dokumen* (Dokumen pendukung, Tautan bahan rapat, Klasifikasi dokumen) · *Ringkasan eksekutif* (Kondisi perusahaan, Pencapaian & deviasi utama, Isu perhatian Direksi, Ringkasan keputusan utama, Tindak lanjut mendesak) · *Penutupan & validasi* (Topik rapat berikutnya, Rapat berikutnya, Waktu rapat ditutup, Disusun oleh, Tanggal penyusunan, Diperiksa / disetujui oleh, Tanggal validasi, Status validasi) · *Checklist finalisasi* (Delapan agenda dicatat, Keputusan jelas, PIC & tenggat lengkap, Basis angka lengkap, Bukti ditautkan, Siap didistribusikan), whose heading shows a "· n/6" count.
       - **Agendas 1–8**: "Properti" (all non-long-text fields) and "Uraian, pembahasan & arahan" (rich_text + files).
    3. "Isi halaman / catatan panjang": auto-resizing `Textarea` (record page body).
  - Grids: short fields `repeat(auto-fill,minmax(240px,1fr))` gap 16px; date and multi-select blocks span 2 columns. Long text `minmax(320px,1fr)`. Checklist `minmax(220px,1fr)` gap 12px.
- Default expansion: all records open if count ≤2; otherwise only the first (Tweak `expand = semua` opens all).

### Property type → control mapping
| Type | Control |
|---|---|
| title | `Field` + `Input` |
| rich_text | `Field` + `Textarea autoResize rows=3 maxRows=14`, placeholder "Isi catatan…" |
| people | `Field` + `Input` placeholder "Nama orang" (production: replace with a person picker bound to the user directory) |
| files | `Field` + `Textarea rows=2`, hint "Nama dokumen dan tautan — bukan unggahan file." (production: real file upload) |
| checkbox | `Checkbox` in a bordered 12px-padded tile |
| select / status | `Field` + `Select`, first option "— Pilih —" (value "") |
| multi_select | label + row of interactive `Tag`s (`selected` toggles), hint "Pilih satu atau lebih." |
| date | sunken bordered block: label, two `Input`s "Mulai" / "Selesai (opsional)" (type date ↔ datetime-local), and `Checkbox` "Sertakan waktu · Asia/Jakarta". Toggling converts values (append `T00:00` / truncate to date). |
| number | `Field` + `Input type=number`; prefix "Rp" if the name ends with "Rp"; suffix "%" if the name contains "persen" |
| url | `Field` + `Input type=url` placeholder "https://" |

Property descriptions from the schema become `Field` hints (e.g. Periode pelaporan, Tanggal & waktu, Deviasi persen, Progres persen, Tingkat risiko, ID keputusan "Contoh D-01", ID tindakan "Contoh A-01"). Tweak `showTypes` shows a lowercase mono type label next to each field label.

**The complete schema (9 databases, 150 fields, all options) is in `notulen-data.js` → `NOTULEN_DATA.schema`.** Use it as the source of truth for the data model.

### Initial records (12)
- Informasi Rapat: (1) empty; (2) "Isi nama rapat", Status validasi = Draft, body = instruction text (`NOTULEN_DATA.info2body`).
- 1. Strategic Update: 1 empty.
- 2. Kinerja: Revenue, EBITDA, Laba bersih, Arus kas operasi, Saldo kas akhir, CAPEX, OPEX, "KPI utama — isi nama KPI", plus 1 empty.
- 3–8: one empty form each.

### Tampilan pendukung (derived views)
H2 "Review keputusan, risiko & tindak lanjut". 2-column card grid (1 column ≤900px):
- **Perlu Keputusan**: agenda-7 records with a Topik and Status keputusan ∈ {empty, Belum diputuskan, Ditunda}. Row: "ID — Topik", meta "Agenda · PIC pelaksanaan", status badge. The count shows as a warning badge.
- **Risiko Tinggi**: agenda-5 records with Tingkat risiko = Tinggi. Meta: Mitigasi · Risk owner · Tenggat. Badge = Status mitigasi.
- **Follow-up Board** (full width): 5 columns (Belum mulai, Berjalan, Terhambat, Selesai, Belum diisi) of agenda-8 tiles (ID — Tindakan; PIC · Target waktu or "Tanpa target"; Indikator).
- **Kalender Tindak Lanjut** (full width): agenda-8 records with a Target waktu, sorted ascending. Columns: date (mono, brand text, 170px) | title + PIC | status badge.
- Empty state: dashed-border box, "Belum ada record yang sesuai."

### Panduan
A `Card padding="lg"` rendering the original guide HTML (`NOTULEN_DATA.guide`) at max 78ch. h2 20px with a top border; tables use mono uppercase header cells.

### Footer
Muted 13px source note (`NOTULEN_DATA.footer`).

---

## Screen 2 — Layar Rapat Direksi (`Layar Rapat Direksi.html`)

### Purpose
A shared boardroom display. The chair or secretariat steps through agendas. The BOD sees the facts, decides each proposal live, and sees action items and deadlines.

### Canvas
A fixed **1920×1080** stage, scaled with `min(vw/1920, vh/1080)` and centered (letterbox bg `--jup-surface-inverse`). Scale recalculates via ResizeObserver, window resize, visibilitychange, and a 500ms interval fallback (for loads in hidden tabs). Base font 22px/1.4. **Minimum on-screen text is about 15px at 1920 width**; keep primary content ≥20px.

### Grid
`grid-template-columns: 360px minmax(0,1fr) 420px; grid-template-rows: 136px minmax(0,1fr) 88px`. Tweak "Panel kanan" off → `360px minmax(0,1fr)`.

**Top bar** (spans all columns): white, 6px top border `--jup-brand`, 1px bottom border, padding 0 40px.
- Left: eyebrow "PT JAKARTA UTILITAS PROPERTINDO · NOTULEN RAPAT DIREKSI" (mono 16px, .12em, brand text). H1 meeting name, Space Grotesk 40px/1.1 semibold, −0.02em. Meta row 18px secondary: nomor (mono) · tanggal · waktu · lokasi · `Badge danger outline` "Rahasia" · `Badge warning` "Data dummy" (remove in production).
- Right: live clock "HH.MM" (mono 52px bold) with " WIB". Below it, the agenda timer chip "AGENDA 02  mm:ss / 25:00" (22px, sunken bg, 1px border). When over the allotment, it switches to danger-bg/danger-border/danger-text.

**Left nav** (white, right border, padding 16px 0): header "AGENDA · 175 MENIT" (mono 15px uppercase). 9 items in a grid of `44px | 1fr | auto`, padding 12px 20px, 6px left border:
- Number box 40×40, 1px `--jup-border-strong`, mono 16px.
- Title 20px medium, with the presenter on a 15px muted line (ellipsis).
- Minutes "25′" (mono, muted).
- States: **current** = bg `--jup-surface-brand-subtle`, left border `--jup-brand`, number box filled `--jup-surface-brand` with `--jup-text-on-brand` bold. **Done** = Lucide check icon in a sunken box with brand text; title secondary. Hover `--jup-surface-hover`.

**Main** (padding 28px 40px 24px): the current agenda view, which fades in (180ms linear). Common header: eyebrow "AGENDA 02 · DIR. KEUANGAN & SDM", H2 42px semibold, focus line 22px secondary, a 2px bottom border `--jup-border-strong`, and optional right-side summary.

**Right rail** (white, left border):
- A 3-column stats strip: Keputusan "n/5", Tindakan baru (count of asal = Rapat ini), Risiko tinggi (danger text). Label mono 13px uppercase; value mono 44px bold.
- "PERLU KEPUTUSAN" + warning count badge: rows (ID mono bold | topic 18px | "Ditunda" badge if applicable). Click → jump to agenda 07 with that decision selected.
- "TENGGAT TERDEKAT": the 4 nearest open actions (date mono brand | title + PIC). Click → agenda 08.

**Footer** (spans all columns, white, top border, padding 0 40px):
- Timeline: flex segments sized by `flex-grow = minutes`, 28px tall, 3px gaps, mono 13px number label. Done = brand-subtle bg with brand border/text; current = brand fill with on-brand bold.
- Buttons: `Button ghost` "← Sebelumnya" (disabled at 00) and `Button primary` "Selesai dibahas →". The label becomes "Lanjut →" once done, with no arrow on the last agenda. Both are 52px tall, 19px text.

### Agenda views
- **00 Pembukaan & Ringkasan**: a 2×2 card grid. Kondisi perusahaan (22px lead) · Kehadiran (4 `Avatar` + name/position in 2 columns; description "4 dari 4 Direksi hadir · kuorum terpenuhi"; undangan line) · Isu perhatian Direksi (ordered list) · Tindak lanjut mendesak (ordered list).
- **01 Strategic Update**: a table with columns `2.3fr 1.1fr .9fr 1.5fr 1fr` (Sasaran + pemapar/deviasi sub · Target (mono) · Posisi (mono bold) · progress bar + % · Evaluasi badge). Bar tone is brand if ≥75%, else warning.
- **02 Kinerja**: header right shows `Badge info outline` "YTD September 2026" and "Rp miliar kecuali dinyatakan lain".
  - 4×2 KPI tiles: name, a deviation badge (±x,x%), the value (mono 36px bold), a bar (real/target), and "Target / Anggaran x".
  - Deviation tone: for revenue-type rows, real ≥ target = success. For cost rows (CAPEX, OPEX), real ≤ target = success. Otherwise |dev| ≤10% = warning and >10% = danger.
  - Below: a "Revenue bulanan vs target" bar chart (Jan–Sep). The bar is brand if ≥ target and warning if under; the target is a 3px ink line; there is a legend. Next to it, a "Penyebab & langkah koreksi" definition list (Penyebab / Koreksi / Likuiditas).
- **03 Isu Lintas Direktorat**: stacked cards in a grid of `64px | 1fr | 220px`. Large mono index in brand text · issue title 26px + units + 2-col Dampak / Keputusan yang diperlukan (bold) · right meta column with a left border (PIC, Target, ref badge such as "D-02").
- **04 Program Prioritas**: header right shows "Serapan anggaran" with the % (mono 44px) and "Rp x M dari Rp y M". Table columns `2.3fr 1.3fr 1.1fr 1.4fr .8fr`: program + kategori/PIC · progress · anggaran · realisasi · milestone · status badge (On track=success, At risk=warning, Delayed=danger, Selesai=success).
- **05 Risk & Compliance**: header right shows solid badges "n Tinggi / n Sedang / n Rendah". Rows use grid `130px 1fr 200px 120px 150px` with an 8px left border (danger for Tinggi, warning for Sedang, strong for Rendah): level · title + mitigation + kategori `Tag`s · owner · tenggat · status badge.
- **06 Stakeholder Issues**: table with columns `1.4fr 2fr 1.1fr .6fr .8fr` (Stakeholder + jenis · Isu · PIC · Target · Urgensi badge).
- **07 Decision Making** (interactive): header right shows "Diputuskan n/5".
  - Left 440px list of decision buttons (ID mono bold, topic, status badge). The selected item gets a 6px blue left border and bg `--jup-surface-alt-subtle`.
  - Right detail `Card`: "ID · agenda" + status badge; topic 32px; "Keputusan yang dimohonkan" 22px lead; a 3-column row (Rekomendasi · Kewenangan `Tag`s · PIC pelaksanaan); and action buttons pinned to the bottom (size lg): **Setujui** (primary when active, else outline), **Setujui bersyarat** (secondary), **Tunda** (outline → secondary when active), **Tolak** (danger when active).
  - Clicking the active status again reverts it to "Belum diputuskan". Each change fires a toast `"D-0x · <status>"` with the topic as description (tone: success / danger / warning / neutral).
- **08 Action Plan** (interactive): a 4-column board (Belum mulai, Berjalan, Terhambat, Selesai). Columns are sunken and scroll internally. Tiles are buttons: ID + target date (mono), title 18px, PIC, indicator (ellipsis), and a "Sebelumnya" outline badge when asal = Rapat sebelumnya. Clicking a tile advances its status cyclically. The header hint reads "Klik kartu untuk memajukan status".

### Keyboard
← / PageUp = previous agenda; → / PageDown = next; 0–8 jump directly. Ignored while focus is in input/textarea/select.

---

## Interactions & Behavior (both)
- Toasts via `useToast().toast({title, description, tone})`, bottom-right.
- Dialog confirmations for destructive actions (delete record, reset).
- Transitions: background/border 120ms linear; chevron rotate 120ms; progress width 200ms linear; view fade 180ms.
- Focus: visible 2–3px `--jup-focus-ring` outlines on custom buttons (nav items, tiles, list items).
- **Print (Notulen)**: renders every agenda expanded plus the derived views. It hides nav/actions/delete buttons and starts each agenda on a new page (`break-before: page`). The state resets on `afterprint`.
- **Save (Notulen prototype)**: serialises state into `<script id="saved-state" type="application/json">` and downloads the HTML. On load, the state comes from that script, then localStorage, then the initial template. **Production:** replace with server persistence and versioning per meeting.

## State Management
**Notulen**
- `state: Record[][]` with 9 arrays (index = database). `Record = { id, values: {[propName]: value}, body: string, time: {[dateProp]: boolean}, origin: string }`.
- Value shapes: text/people/url/select/number → string; checkbox → boolean; multi_select → string[]; date → `{start, end}` ISO strings (date or datetime-local).
- `view: '0'..'8' | 'views' | 'guide'`; `printing: boolean`; per-agenda `openIds: Set`.
- Derived: header meeting = the first Informasi record whose Nama rapat ≠ "Isi nama rapat"; checklist count; pending decisions.

**Layar**
- `{ cur: number, done: number[], dec: {[decisionId]: status}, acts: {[actionId]: status}, sel: decisionId }`, persisted to localStorage (`jup-layar-rapat-v1`).
- `enteredAt` timestamp resets on agenda change, which drives the agenda timer. `now` ticks every 1s.

**Production data flow (recommended)**
- One `Meeting` aggregate holding meta plus the 8 agenda collections (schema in `notulen-data.js`).
- Layar = a read model of the Meeting. Decision status changes write to `7. Decision Making.Status keputusan`; action status changes write to `8. Action Plan.Status`. Agenda "done" flags and timers live in a meeting-session record.
- Consider realtime sync (websocket) so the secretariat's laptop and the boardroom display stay consistent.
- Map Layar fields to the schema. Strategic: Sasaran strategis, Target & indikator, Posisi terkini, Evaluasi strategi. Kinerja: Indikator, Satuan, Target / anggaran, Realisasi, Deviasi persen. Program: Progres persen, Anggaran Rp, Realisasi Rp, Status progres, Target milestone/Tanggal milestone. Risk: Tingkat risiko, Kategori dampak, Status mitigasi, Risk owner / PIC, Tenggat. Stakeholder: Jenis stakeholder, Urgensi, PIC komunikasi, Target tindak lanjut. Decisions and actions: as named.

## Design Tokens (light theme; dark values are in `_ds_bundle.css` under `[data-jup-theme=dark]`)
**Primitives**: paper #F0F1F1 · surface #FFFFFF · surface-2 #E3E6E9 · surface-3 #CED4DA · ink #011627 · ink-soft #35485C · ink-faint #536679 · line #CED4DA · line-soft #E3E6E9 · brand #00A550 · brand-deep #006C34 · blue #004999 · navy #003066 · red/down #B3261E · amber #8A5200 · up-bg #E6F6EE · down-bg #FBE9E7 · gate-bg #E6EDF5 · defer-bg #FBF0DE.

**Semantic (use these)**: `--jup-surface-page` (paper) · `--jup-surface-card` (#FFF) · `--jup-surface-sunken` / `--jup-surface-hover` (#E3E6E9) · `--jup-surface-brand` (#00A550) · `--jup-surface-brand-subtle` (#E6F6EE) · `--jup-surface-alt-subtle` (#E6EDF5) · `--jup-surface-inverse` (#011627) · `--jup-border-subtle` (#E3E6E9) · `--jup-border-default` (#CED4DA) · `--jup-border-strong` (#536679) · `--jup-border-brand` (#00A550) · `--jup-text-primary` (#011627) · `--jup-text-secondary` (#35485C) · `--jup-text-muted` (#536679) · `--jup-text-brand` (#006C34) · `--jup-text-on-brand` (#011627) · `--jup-success` (#00A550) · `--jup-warning` (#8A5200) · `--jup-danger` (#B3261E) · `--jup-info` (#004999) · `--jup-danger-text` (red mixed 10% to ink) · `--jup-danger-bg` (#FBE9E7) · `--jup-link` (#004999) · `--jup-focus-ring` (3px brand @38%).

**Spacing**: layout `--jup-s1…s8` = 4, 8, 12, 16, 20, 26, 40, 84px; component `--jup-space-0…11` (4px ladder).
**Type**: Space Grotesk / Space Mono. Sizes `--jup-size-3xs…5xl` = 11, 12, 13, 14, 16, 18, 20, 24, 30, 38, 48, 60px. The Layar uses explicit display sizes: 52 (clock), 48/42 (H2), 44 (big numbers), 40 (H1), 36 (KPI value), 32 (decision title), 26 (H3), 22 (body), 20, 18, 17, 15, 13.
**Radius**: `--jup-radius` 0 · `--jup-radius-sm` 4px (controls) · `--jup-radius-chip` 2px · pill (avatars/dots).
**Elevation**: `--jup-shadow-sm` 0 1px 2px rgba(1,22,39,.06) · md 0 2px 8px rgba(1,22,39,.08) · lg 0 10px 30px rgba(1,22,39,.12) (modals/toasts only).
**Control heights**: 28 / 36 / 44px.

## Tweaks (prototype-only controls; decide which become user settings)
- Notulen: theme light/dark · navigation sidebar/tabs · records open first/all · show property types.
- Layar: theme light/dark (dark is recommended for projectors) · right rail on/off · agenda timer on/off · reset meeting status.

## Assets
- Fonts: Space Grotesk, Space Mono (woff2 in `_ds/…/fonts/`).
- Icons: Lucide paths inlined (plus, trash-2, chevron-down, printer, download, rotate-ccw, check). In production use `lucide-react`.
- No images or logos are used. If a JUP logo is required in the Layar top bar, use the official asset from the brand system.

## Files
- `Notulen Rapat Direksi.html`: input app shell + page CSS (`.nt-*`).
- `notulen-app.jsx`: app, agenda/record views, derived views, guide, save/print, tweaks.
- `notulen-fields.jsx`: property-type → control renderer (`PropField`), date field, Lucide `Icon`.
- `notulen-data.js`: **full schema (150 properties), guide HTML, footer and notes**.
- `Layar Rapat Direksi.html`: display shell + CSS (`.lr-*`).
- `layar-app.jsx`: stage scaling, layout (top bar, nav, rail, footer), state, keyboard.
- `layar-views.jsx`: the 9 agenda views.
- `rapat-dummy-data.js`: **dummy meeting data** (fictional names/figures; replace with real data).
- `tweaks-panel.jsx`: prototype tweak panel (not for production).
- `_ds/jup-ui-components-…/`: `@jup/ui` browser bundle, CSS tokens and fonts (in production, install the `@jup/ui` package instead).
- `reference/Template_Notulen_Rapat_Direksi_original.html`: the original source template.
