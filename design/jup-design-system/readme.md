# JUP Design System

**PT Jakarta Utilitas Propertindo (JUP)** — Badan Usaha Milik Daerah (BUMD) DKI Jakarta, part of the **Jakpro** group, focused on managing utilities and distributing sustainable energy for the development of Jakarta.

> _"With better energy will come better quality for people in future."_ — the tema besar of the 2023 identity.

This project is the digital design system built from the company's official **Graphic Standard Manual (Brand Guideline), Jakarta Utilitas Propertindo, 2023** — the single source provided. Everything here is either lifted directly from that manual (colours, typeface, logo, graphic elements, layout formats) or derived from it and clearly marked as such.

---

## 1. Sources

| Source                                                                           | Where                                                     | Status                                                             |
| -------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------ |
| `JUP_Brand Guideline_260519_170910.pdf` — Graphic Standard Manual 2023, 63 pages | `uploads/` in this project                                | Read in full; the authority for everything below                   |
| Company website                                                                  | `www.jakarta-utilitas.com` (printed on every manual page) | **Not accessible to this build** — no live product UI was provided |
| Codebase / Figma                                                                 | —                                                         | None provided                                                      |

**What that means.** There is no product UI, no component library and no screenshots of a live JUP interface in the source material. The manual covers identity (logo, colour, type, graphic elements) and print/OOH applications (banner, spanduk, PDH, lanyard, stationery, social formats). So:

- **Foundations, logo, colour, type, graphic elements, layout formats** — faithful to the manual.
- **UI components and UI kits** — an honest extension of the manual into screen. They follow its palette and typeface; their component geometry (pill controls, 24px containers, hairline elevation) follows the interface reference `uploads/DESIGN.md` — see §4.6. The manual does not specify buttons, inputs or web pages. Treat them as the house interpretation, not as a reproduction of an existing JUP product. Every such extension is listed under _Intentional additions_ below.

### Relationship to the older "JupDS v0.1.0"

A separate internal JUP system exists (namespace `JupDS`, Fraunces + IBM Plex, green `#079F4E`, evidence tiers and G1–G4 gates). **It is not this system.** Where the two disagree on identity — typeface, green, logo — the 2023 Graphic Standard Manual in `uploads/` wins, and this project follows it. If you are producing governance artefacts that need the D11 evidence tiers or the gate cadence, keep that editorial machinery and re-skin it with the tokens here.

---

## 2. Index

| File / folder    | What it is                                                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DESIGN.md`      | Build rules — decision table, token cheat-sheet, component API, ship checklist. Read this while building.                                         |
| `styles.css`     | The one entry point consumers link. `@import` list only.                                                                                          |
| `tokens/`        | `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `radius.css`, `elevation.css`, `motion.css`, `layout.css`, `ui.css` (interface layer) |
| `base/`          | `base.css` (element defaults, utilities), `components.css` (every `.jup-*` class)                                                                 |
| `assets/`        | Logo lockups, logogram, sector marks, pattern bands, webfonts, UI icons                                                                           |
| `components/`    | React primitives — `brand/`, `core/`, `forms/`, `feedback/`, `navigation/`                                                                        |
| `guidelines/`    | Foundation specimen cards (Colors, Type, Spacing, Brand)                                                                                          |
| `ui_kits/`       | Full-surface applications — `website/`, `media/`                                                                                                  |
| `templates/`     | Reusable starting artefacts — `pitch-deck/`                                                                                                       |
| `ai-prompts.md`  | Paste-ready JUP brand prompts for NotebookLM, ChatGPT, Gemini, Claude                                                                             |
| `SKILL.md`       | Agent-Skills wrapper so this folder works in Claude Code                                                                                          |
| `thumbnail.html` | Homepage tile                                                                                                                                     |

### Components

**Brand** — `Logo`, `Logogram` (via `Logo variant="logogram"`), `SectorIcon`, `PatternBand`, `SectionHeading`, `Icon`
**Core** — `Button`, `IconButton`, `Badge`, `Tag`, `Card`, `StatBlock`
**Forms** — `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Switch`
**Feedback** — `Alert`, `Toast`, `Tooltip`, `Dialog`
**Navigation** — `Tabs`, `Breadcrumb`

Each component directory holds `<Name>.jsx`, `<Name>.d.ts`, `<Name>.prompt.md` and one `@dsCard` demo page.

### Intentional additions

Things the Graphic Standard Manual does not define, added because a screen system cannot work without them. All are built from the manual's own colours and geometry.

| Addition                                                    | Why                                                                                                                                                                                                                                   |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Green / blue / neutral **ramps**                            | Four flat colours cannot express hover, disabled, subtle backgrounds and borders.                                                                                                                                                     |
| **Status colours** (`success`, `info`, `warning`, `danger`) | Success and info reuse Pigment Green and Polynesian Blue so state never invents a hue; warning `#8A5200` and danger `#B3261E` are new and are the only non-manual colours in the system.                                              |
| **Space Mono**                                              | For tabular figures and codes. It is the monospaced family Space Grotesk was drawn from, so it shares the identity's skeleton. Flagged in `tokens/fonts.css`.                                                                         |
| **Lucide** UI icon set                                      | The manual defines only the five sector marks; there is no interface icon set. Lucide's 2px square-cut stroke is the nearest match to the logogram's bar geometry. Shipped in `assets/icons/ui/`. **Substitution — see Iconography.** |
| **UI primitives and UI kits**                               | No product UI was provided. See §1.                                                                                                                                                                                                   |
| `Icon` **component**                                        | A wrapper so glyph _files_ (not inlined paths) can take `currentColor`.                                                                                                                                                               |

---

## 3. Content fundamentals — how JUP writes

The manual's own body copy is the reference sample. It is corporate-institutional Bahasa Indonesia: measured, explanatory, third-person, and completely free of hype.

**Language.** Bahasa Indonesia is the default for all public and internal material. English appears only for the tema besar and for international-facing summaries. When both run together, Indonesian leads.

**Person.** Third person, named in full: _"Jakarta Utilitas Propertindo percaya, dengan budaya kolaborasi..."_, _"Perubahan PT. JUP terdiri atas 4 pilar dasar..."_. Never "kami" in body copy; never "Anda" outside a direct service instruction. The company is a subject, not a personality.

**Register.** Explanatory and slightly formal — sentences state a fact and then its reason. Typical rhythm from the manual:

> _"Penetapan ukuran minimal berikut ini berguna untuk menjaga keterbacaan logo pada penerapan di berbagai media cetak dan digital."_

Rule first, purpose second. Carry that pattern into product copy: say what the thing is, then why it exists.

**Instructions are imperative and absolute.** The manual's rule voice is short and unhedged — _"Logo harus selalu ditampilkan dengan tepat dan konsisten"_, _"Dilarang mengubah proporsi logo"_, _"tanpa pengecualian"_. Prohibitions start with **Dilarang**. Do not soften them with _sebaiknya_ or _diharapkan_.

**Casing.**

- Headings and titles: **sentence case**, noun phrases — _"Konfigurasi Logo"_, _"Zona Aman Logo"_, _"Penggunaan Logo yang Salah"_. Title Case appears on section labels only.
- Eyebrows, badges, table heads, the logotype line: **UPPERCASE with wide tracking**. This is the identity's signature and the only place caps are allowed.
- Never all-caps a sentence.

**Numbers.** Indonesian convention — decimal comma, thousands dot, unit spaced: `12,4 MWp` · `Rp 18.400.000.000` · `2,3 cm` · `65 px`. Ratios keep the colon: `2:1`, `9:18`. A figure is always attached to a period or a source.

**Naming.** _PT Jakarta Utilitas Propertindo_ in full on first mention in legal, financial and Pemprov documents; **JUP** or _Jakarta Utilitas Propertindo_ thereafter and in public material. The Jakpro endorsement (`by JAKPRO`) rides with the logo, not with the name in running text.

**Emoji.** Never. Not in product UI, not in social captions, not in decks. The manual's entire iconographic vocabulary is the five sector marks.

**Vibe.** Civic infrastructure, not a startup. The tone a resident of Jakarta would expect from the utility that lights their street: confident, unglamorous, specific, accountable. Words the manual reaches for — _berkelanjutan, kolaborasi, tumbuh, terkoneksi, tangguh, majemuk_. Words it never uses — _revolusioner, terdepan, solusi inovatif, game-changing_.

**Examples.**

| Off-brand                                   | On-brand                                                                              |
| ------------------------------------------- | ------------------------------------------------------------------------------------- |
| "Solusi energi revolusioner untuk Jakarta!" | "Pengelolaan utilitas dan distribusi energi berkelanjutan untuk pembangunan Jakarta." |
| "Kami siap membantu Anda 🚀"                | "Layanan sambungan gas kota tersedia di enam kecamatan."                              |
| "Kapasitas besar"                           | "Kapasitas terpasang 12,4 MWp, per Desember 2024."                                    |
| "Sebaiknya logo tidak diubah"               | "Dilarang mengubah proporsi logo."                                                    |

---

## 4. Visual foundations

### 4.1 The idea

The identity is built on four pillars — **FUTURE, SPIRIT "KITA", ENERGY, UTILITY**. The logogram is a set of square-cut bars and 45° diamonds converging on a centre, with an inward notch adapted from the `J` of the previous Jakpro-family mark: JUP as a _pillar_ of utilities and energy holding the city together. Everything visual in this system inherits that geometry — orthogonal bars, 45° cuts, hard ends, one radius.

### 4.2 Colour

Four fixed identity colours (`tokens/colors.css`):

|                      | Hex       | Meaning in the manual                                                               |
| -------------------- | --------- | ----------------------------------------------------------------------------------- |
| **Pigment Green**    | `#00A550` | Growth, health, sustainable change. The brand colour and the action colour.         |
| **Polynesian Blue**  | `#004999` | Trust, stability, authority, knowledge, technology. The institutional second voice. |
| **Rich Black**       | `#011627` | Ink, covers, dark sections. A blue-cast black, never pure `#000`.                   |
| **Anti-flash White** | `#F0F1F1` | The page. Never pure `#FFF` for a canvas — white is for cards sitting on the page.  |

Green and blue are **peers, not primary/secondary decoration**: the logogram gives the top half to green (growth/future) and the bottom half to blue (structure/trust). In interfaces, green carries action and affirmation; blue carries institution, governance and navigation weight. Never put them in a gradient together — _dilarang merubah warna logo menjadi gradasi_, and the prohibition holds for the wider system.

Ramps (50–900) exist only so interfaces have hover, disabled, border and tint steps. They are never used to recolour the logo.

**Two background colours per artefact, maximum**: Anti-flash White and one of {white, Rich Black, Pigment Green, Polynesian Blue}.

#### Contrast — read before using green as a fill

Pigment Green is fixed by the manual, and **white on Pigment Green measures 3.23:1** — below the 4.5:1 AA threshold for normal text. The system resolves this deliberately:

| Pair                                  | Ratio  | Where it may be used                                                                                                                  |
| ------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| White on `#00A550`                    | 3.23:1 | **Button labels only** (`.jup-btn--primary`, ≥14px / 500 weight), and large display type ≥24px. Never body copy, never an 11px badge. |
| Rich Black on `#00A550`               | 13.8:1 | The safe pairing — used for `.jup-badge--brand` and any small or dense type on a green fill.                                          |
| White on `#004999`                    | 9.9:1  | Anything.                                                                                                                             |
| White on `#011627`                    | 18.1:1 | Anything.                                                                                                                             |
| `--jup-text-brand` `#008A43` on white | 4.6:1  | Eyebrows, links, small text. Do **not** use `#00A550` as a text colour on white — it measures 3.1:1.                                  |

Everything else in `tokens/colors.css` clears 4.5:1 against its paired background: success 5.68:1, info 8.7:1, warning 5.3:1, danger 5.58:1.

### 4.3 Typography

**Space Grotesk** is the identity typeface for every JUP application (manual p.28), free from Google Fonts. It does all the work — display, headings, UI, body. Space Mono is reserved for figures and codes.

- Display and headings: 700, tracking `-0.025em` to `-0.015em`, line-height 1.12–1.28, `text-wrap: balance`.
- Body: 400 / 16px / 1.62, measure capped at `68ch`, `text-wrap: pretty`.
- Eyebrows, badges, table heads: 500, uppercase, `+0.18em`.
- The logotype line `J A K A R T A   U T I L I T A S` sits at `+0.34em`. Reserve that extreme for the lockup itself.

Things that break the voice: body copy in mono, sentence-case eyebrows, a paragraph past 68ch, a heading in a weight lighter than 500.

### 4.4 Layout

The manual builds every format on a margin equal to the logo clear zone — 4× the logogram bar — and defines four families: **horizontal** (2:1, 4:1), **portrait** (A-series, 4:6), **vertical** (1:2,5, 1:3, 9:18) and **square** (1:1 social). On screen that becomes: 1200px content measure, 24px gutter (40px at large), 12 columns, generous vertical rhythm from the spacing ladder (`--jup-section-y` = 120px). Content is left-aligned by default; centred layouts are for covers and social squares only. Fixed elements: a 72px header; no sticky sidebars, no floating action buttons.

### 4.5 Backgrounds and imagery

No gradients, no noise, no blurred blobs, no generated textures. Backgrounds are **flat fields of one identity colour**, or photography. The manual's photography is documentary: real sites, plant, streets and staff of Jakarta, natural light, neutral-to-cool cast, no heavy grading, no duotone. Logos go on light photos as full colour and on dark photos as the white knockout — never as a colour lockup fighting a busy image.

The only decoration is the **Elemen Grafis** — the logogram and the five sector marks, set in a row (horizontal media) or a column (portrait/vertical). It lives on an edge, never behind running text, and **must not cover more than 50% of the layout** (manual p.43).

### 4.6 Surfaces, borders, radii — the interface layer

Print foundations (logo, colour, type, Elemen Grafis, formats) stay square-cut and flat, exactly as the manual draws them. **Interface components** sit on a separate layer, `tokens/ui.css`, modelled on the "clinical blueprint on frosted paper" reference (`uploads/DESIGN.md`), rebuilt with JUP's own neutrals and typeface:

- **Achromatic chrome.** Surfaces stack canvas (Anti-flash White `#F0F1F1`) → surface-alt `#F7F8F8` → paper `#FFFFFF`. Text and the filled primary are Rich Black. Green and blue appear only where they mean something: the one brand CTA (`Button variant="brand"`), selection, focus, status dots, sector marks.
- **Radius hierarchy.** 18px on every interactive control (pill at 36px height), 24px on containers (cards, dialogs, tables), 10px nested, 6px tooltips. Nothing else.
- **Hairline + whisper elevation.** Cards: 1px `--jup-ui-hairline` plus `--jup-ui-shadow-card`. Popovers/dialogs/toasts: `--jup-ui-shadow-pop`. Never a coloured shadow.
- **Compact density.** 14px body and controls, 12px captions, 20px card padding, 8px element gap, 36px default control height.
- **Tonal controls.** Inputs and secondary buttons are filled `--jup-ui-fill`, no border at rest; focus swaps the fill for paper + hairline + a 3px soft ring.
- **Display type.** Space Grotesk at 500 (not bold), fluid 44–84px, −0.045em — `.jup-display`; an `<em>` inside takes the brand green. Lighter, tighter display is the main "fresh" lever; the face is unchanged.
- **The diamond.** Eyebrows and the `.jup-kicker` pill are prefixed with a 6px 45° diamond lifted from the logogram — the identity's own geometry as the system's signature.
- **Bento + tint.** `.jup-bento` grids mix one Polynesian Blue hero tile (`jup-card--brand`) with white cards; `.jup-band` is a green-50 CTA field with the Elemen Grafis band. `Card` also takes `tint` / `tint-alt`.
- **Motion.** Interactive cards lift 2px, trailing arrows nudge 2–3px, buttons press to 98%. 160–220ms, `--jup-ui-ease`. Reduced-motion still zeroes durations.
- Rules remain hairlines.

### 4.7 Transparency and blur

Used sparingly and only for legibility, never for style. The permitted cases: the modal scrim `rgba(1,22,39,.62)`; white at 12–40% for borders and secondary text inside `.jup-inverse`; a solid-to-transparent **protection gradient** from Rich Black at the foot of a photo when text must sit on it. No frosted glass, no backdrop blur on chrome, no translucent cards.

### 4.8 Interaction states (interface layer)

- **Hover** — filled ink darkens one neutral step; tonal/outline/ghost controls take a `--jup-ui-fill` wash; inputs step to `--jup-ui-fill-hover`; interactive cards gain a stronger hairline and pop shadow. Brand CTA: `green-500 → green-600`.
- **Focus** — 3px soft ring `--jup-ui-ring` (green `--jup-ui-ring-brand` on the brand CTA and switch). Always visible.
- **Disabled** — 45% opacity, no pointer events.
- **Selected** — tabs: 2px green underline, or the active segment lifts to paper in the segmented (`pill`) variant; tags: Rich Black fill; checkbox/radio: Rich Black; switch: Pigment Green.
- **Error** — destructive red (`--jup-danger`) border + soft ring; red is never decoration.

### 4.9 Motion

Utility-company motion: things move because state changed. Durations 80 / 140 / 200 / 320ms, `cubic-bezier(.22,.61,.36,1)`. Colour, border and shadow transition; geometry does not. No bounce, no spring, no parallax, no scroll-triggered reveals, no looping background animation. `prefers-reduced-motion` zeroes every duration.

---

## 5. Iconography

**What the brand actually owns.** Five marks, drawn in the manual as _Elemen Grafis_ (p.37) from the same bar-and-diamond vocabulary as the logogram:

| Mark         | Line of business | Asset                           |
| ------------ | ---------------- | ------------------------------- |
| Solar        | Solar energy     | `assets/icons/icon-solar.png`   |
| Listrik      | Electricity      | `assets/icons/icon-listrik.png` |
| Gas          | Gas              | `assets/icons/icon-gas.png`     |
| Air          | Water            | `assets/icons/icon-air.png`     |
| Lahan Parkir | Parking land     | `assets/icons/icon-parkir.png`  |

These are **brand marks, not UI icons**: heavy, square-cut, used at 48px and above, in one identity colour, white or Rich Black. Use `SectorIcon`. They are also the source of the pattern bands (`assets/pattern-row.png`, `assets/pattern-column.png`) — the row for horizontal media, the column for portrait, coloured through `PatternBand`.

**Interface icons — a flagged substitution.** The manual defines no interface icon set and none was supplied. This system ships **Lucide** (v0.454.0, `assets/icons/ui/*.svg`, MIT) because its 2px square-cut stroke and flat terminals sit closest to the logogram's geometry. 28 glyphs are included; add more from the same family and nothing else. **If JUP has a house UI icon set, send it and this substitution should be replaced.**

Glyphs are rendered through the `Icon` component, which paints the file as a CSS mask so it takes `currentColor` — so a JUP artefact never contains a hand-drawn or approximated path.

**Emoji and unicode symbols are not icons.** Neither is used anywhere in JUP material. The one exception in code is the `×` glyph inside dismiss controls, where it is a typographic character rather than an illustration.

---

## 6. Logo

Files in `assets/`, all extracted from the manual at 6× and keyed to transparency:

| File                                           | Use                                                                               |
| ---------------------------------------------- | --------------------------------------------------------------------------------- |
| `logo-primary.png`                             | Horizontal lockup — the default, for spanduk, billboard, LED, web headers         |
| `logo-secondary.png`                           | Stacked lockup — **vertical media only** (umbul-umbul, x-banner, folded brochure) |
| `logo-compact.png`                             | Mark + `JUP` without the JAKARTA UTILITAS line — for small sizes                  |
| `logogram.png`                                 | Mark alone                                                                        |
| `logo-primary-white.png`, `logogram-white.png` | Single-colour knockouts for dark grounds and photography                          |

**Rules that are not negotiable.** Clear zone on all sides = 4× the logogram bar. Minimum size with text: 1cm / 28px (primary), 2,3cm / 65px (secondary), logogram 0,5cm / 14px. Below 5cm printed, drop the JAKARTA UTILITAS line and the Jakpro endorsement. Single-colour applications may use **white or black only**. Twelve prohibitions are listed in `guidelines/brand-logo-misuse.card.html` — orientation, proportion, colour composition, off-palette colour, gradient, shadow, outline form, effects, substituted type, photo or pattern fills, altered composition, crowding another logo.

**No logo was drawn for this system.** Every mark here is lifted from the supplied manual.

---

## 7. Using the system

```html
<link rel="stylesheet" href="styles.css" />
```

Then either use the React components, or the `.jup-*` classes directly — `base/components.css` carries the full class vocabulary so decks, emails and exported documents can share it without React.

```jsx
import { Button } from './components/core/Button.jsx';
<Button variant="primary" size="lg">
	Lihat portofolio
</Button>;
```

Dark sections: wrap in `class="jup-inverse"` and every token flips; components need no change.
