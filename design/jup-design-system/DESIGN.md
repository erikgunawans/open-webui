# DESIGN.md — JUP build rules

The working companion to `readme.md`. `readme.md` explains _why_; this file is what you consult _while building_. Source of truth: **Graphic Standard Manual, Jakarta Utilitas Propertindo, 2023** (`uploads/`) for foundations — logo, colour, type, Elemen Grafis, layout formats. **Interface components** follow the UI reference `uploads/DESIGN.md` (achromatic chrome, pill controls, 24px containers, hairline elevation), rebuilt in JUP neutrals and Space Grotesk via `tokens/ui.css`.

Setup:

```html
<link rel="stylesheet" href="styles.css" />
<script src="_ds_bundle.js"></script>
<script>
	const { Button, Card } = window.JUPDesignSystem_7e98d0;
</script>
```

Namespace: `JUPDesignSystem_7e98d0`. Plain HTML deliverables can skip the bundle and use the `.jup-*` classes in `base/components.css` directly.

---

## 1. Decision table

Reach for this before writing any CSS.

| Question                                      | Answer                                                                                                                                                            |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Page background?                              | `--jup-ui-canvas` (Anti-flash White `#F0F1F1`). Never pure white as a canvas.                                                                                     |
| Card background?                              | `--jup-ui-paper` `#FFFFFF`, 1px `--jup-ui-hairline`, `--jup-ui-shadow-card`, **24px radius**, 20px padding.                                                       |
| Primary action?                               | Rich Black filled pill (`Button` default). Tonal grey `secondary` beside it.                                                                                      |
| The one hero / marketing CTA?                 | `Button variant="brand"` — Pigment Green. Max one per view.                                                                                                       |
| Navigation, governance, institutional weight? | Polynesian Blue `#004999`.                                                                                                                                        |
| Dark section?                                 | `class="jup-inverse"` on the container + `background: var(--jup-rich-black)`. Nothing else changes.                                                               |
| Need a gradient?                              | No.                                                                                                                                                               |
| Need a shadow?                                | Only the two UI levels: `--jup-ui-shadow-card` (cards, tables) and `--jup-ui-shadow-pop` (dialogs, toasts, menus). Never coloured.                                |
| Corner radius?                                | UI: `18px` controls/badges/inputs, `24px` containers, `10px` nested, `6px` tooltips. Print/brand formats (decks, posters, Elemen Grafis): square, per the manual. |
| Input styling?                                | Tonal fill `--jup-ui-fill`, no border at rest; focus → paper + hairline + `--jup-ui-ring`.                                                                        |
| Arbitrary spacing value?                      | No — a step from `--jup-space-1…11` (4 → 120).                                                                                                                    |
| Decoration?                                   | Only the Elemen Grafis band (`PatternBand`) and the 45° diamond on eyebrows/kickers. Nothing else.                                                                |
| Hero headline?                                | `.jup-display` — Space Grotesk 500, fluid 44–84px, −0.045em. Wrap the key phrase in `<em>` for brand green.                                                       |
| Feature grid?                                 | `.jup-bento` — one `jup-card--brand` (Polynesian Blue) 2×2 tile + white `interactive` cards.                                                                      |
| Closing CTA?                                  | `.jup-band` (green-50, 24px radius) + primary button + `PatternBand tone="green"`.                                                                                |
| An icon the set doesn't have?                 | Take it from Lucide (same family as `assets/icons/ui/`). Never draw one.                                                                                          |
| Emoji?                                        | Never.                                                                                                                                                            |

---

## 2. Tokens you will actually type

### Colour

```css
/* identity — exact, never altered */
--jup-pigment-green    #00A550
--jup-polynesian-blue  #004999
--jup-rich-black       #011627
--jup-antiflash-white  #F0F1F1

/* semantic — reference these, not the raw hexes */
--jup-text-primary  --jup-text-secondary  --jup-text-muted  --jup-text-brand
--jup-surface-page  --jup-surface-card  --jup-surface-sunken  --jup-surface-inverse
--jup-border-subtle  --jup-border-default  --jup-border-strong
--jup-link  --jup-link-hover  --jup-focus-ring
```

Ramps `--jup-{green,blue,neutral}-{50…900}` exist for interface states only. **Never recolour the logo or a sector mark with a ramp step** — those take identity colours, white or Rich Black only.

### Type

```css
--jup-font-sans   "Space Grotesk"   /* everything */
--jup-font-mono   "Space Mono"      /* figures and codes only */

--jup-type-display   /* 60/1.12 700 */    --jup-type-h1  /* 48/1.12 700 */
--jup-type-h2        /* 38/1.28 700 */    --jup-type-h3  /* 30/1.28 500 */
--jup-type-h4        /* 24/1.28 500 */    --jup-type-lead /* 20/1.62 400 */
--jup-type-body      /* 16/1.62 400 */    --jup-type-small /* 14/1.5 400 */
--jup-type-eyebrow   /* 12 500 uppercase */

--jup-tracking-display  -0.025em
--jup-tracking-heading  -0.015em
--jup-tracking-wide      0.08em   /* badges, table heads */
--jup-tracking-wider     0.18em   /* eyebrows */
--jup-tracking-widest    0.34em   /* the logotype line — nothing else */
--jup-measure            68ch
```

### Space, radius, motion

```css
--jup-space-1…11      4 8 12 16 20 24 32 40 56 80 120
--jup-radius-xs/sm/md/lg/pill      2 4 6 10 999   (print / brand formats)
--jup-ui-radius-control/card/nested/small   18 24 10 6   (interface components)
--jup-ui-h-sm/md/lg   32 36 44    --jup-ui-font-control 14px   --jup-ui-card-pad 20px
--jup-duration-instant/fast/base/slow   80 140 200 320 ms
--jup-ease-out        cubic-bezier(.22,.61,.36,1)
--jup-container       1200px    --jup-gutter   24px    --jup-header-h  72px
```

---

## 3. Interaction states — the whole rulebook

| State    | What changes                                                                                                                                                                                    |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hover    | Ink darkens one neutral step; tonal/outline/ghost take a `--jup-ui-fill` wash; inputs → `--jup-ui-fill-hover`; interactive cards → stronger hairline + pop shadow. Brand CTA `green-500 → 600`. |
| Focus    | 3px soft ring `--jup-ui-ring` (green `--jup-ui-ring-brand` on brand CTA / switch). Always visible.                                                                                              |
| Disabled | 45% opacity, `pointer-events: none`.                                                                                                                                                            |
| Selected | Tabs: 2px green underline, or paper segment in `pill`. Tags, checkbox, radio: Rich Black. Switch: Pigment Green.                                                                                |
| Error    | `--jup-danger` border + soft red ring. Red is never decorative.                                                                                                                                 |

Nothing scales, lifts, translates, bounces or fades on interaction. Colour, border and shadow transition; geometry does not.

---

## 4. Layout recipes

**Section opener** — every major block starts this way:

```jsx
<SectionHeading eyebrow="Portofolio" title="Aset dan proyek" lead="…" />
```

Eyebrow (uppercase, `+0.18em`, green) → hairline rule extending right → sentence-case noun-phrase title → lead. The trailing rule is the system's signature; keep it.

**Page shell**

```html
<div class="jup-container">…</div>
<!-- 1200px, 24px gutter -->
```

72px header, `--jup-section-y` (120px) between sections, content left-aligned. Centred layouts are for covers and 1:1 social only. No sticky sidebars, no floating action buttons.

**Figures** — always `StatBlock`, never hand-set:

```jsx
<StatBlock
	label="Kapasitas terpasang"
	value="12,4"
	unit="MWp"
	note="Per Desember 2024"
	tone="brand"
/>
```

`note` is not optional. A figure without a period or source does not ship.

**Tables** — 1px hairline under the head row, uppercase wide-tracked column labels, no zebra striping, no vertical rules. See `ui_kits/website/PortfolioScreen.jsx`.

**Dark section**

```html
<section class="jup-inverse" style="background:var(--jup-rich-black)">…</section>
```

**Graphic element**

```jsx
<PatternBand orientation="row" tone="white" opacity={0.18} align="right" height={52} />
```

`row` for horizontal media, `column` for portrait/vertical. On an edge, never behind running text, never over 50% of the layout.

---

## 5. Component API quick reference

| Component             | Key props                                                                                                          |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `Button`              | `variant` primary·secondary·outline·ghost·inverse·danger · `size` sm·md·lg · `block` · `as` · `iconLeft/iconRight` |
| `IconButton`          | `label` **(required)** · `variant` ghost·outline·solid · `size`                                                    |
| `Badge`               | `tone` neutral·brand·alt·success·info·warning·danger · `outline`                                                   |
| `Tag`                 | `selected` · `onRemove` · `onClick`                                                                                |
| `Card`                | `variant` default·flat·raised·accent·accent-alt·inverse·interactive · `title` · `eyebrow` · `footer`               |
| `StatBlock`           | `label` · `value` · `unit` · `note` · `tone` default·brand·alt                                                     |
| `SectionHeading`      | `eyebrow` · `title` · `lead` · `align` · `as`                                                                      |
| `Logo`                | `variant` primary·primary-white·secondary·compact·logogram·logogram-white · `height` · `base`                      |
| `SectorIcon`          | `sector` solar·listrik·gas·air·parkir · `tone` ink·white·green·blue · `size` · `showLabel` · `base`                |
| `PatternBand`         | `orientation` row·column · `tone` · `align` · `opacity` · `height` · `base`                                        |
| `Icon`                | `name` (stem in `assets/icons/ui`) · `size` · `base` · `src`                                                       |
| `Field`               | `label` · `hint` · `error` · `required` · `htmlFor`                                                                |
| `Input`               | `size` · `invalid` · `icon` · all native props                                                                     |
| `Textarea` / `Select` | `invalid` · `options` / `placeholder`                                                                              |
| `Checkbox` / `Radio`  | `label` · `description` (share `name` on radios)                                                                   |
| `Switch`              | `label` — only when the change applies immediately                                                                 |
| `Alert`               | `tone` info·success·warning·danger · `title` · `icon`                                                              |
| `Toast`               | `tone` · `title` · `message` · `onClose`                                                                           |
| `Tooltip`             | `label` **(required)** · `placement`                                                                               |
| `Dialog`              | `open` · `title` · `footer` · `wide` · `tone` · `onClose`                                                          |
| `Tabs`                | `items` · `value` · `onChange` · `variant` underline·pill                                                          |
| `Breadcrumb`          | `items` (last item is current, not a link)                                                                         |

`base` props are page-relative: pass `"../../assets"` from `ui_kits/<x>/`, `"assets"` from the project root.

Every component has a `.prompt.md` next to it with a usage example and variant notes.

---

## 6. Copy rules

- Formal Bahasa Indonesia. Third person — the company is named, never "kami" in body copy.
- Fact first, reason second: _"Penetapan ukuran minimal berikut ini berguna untuk menjaga keterbacaan logo."_
- Instructions are imperative and unhedged. Prohibitions begin **Dilarang**. No _sebaiknya_, no _diharapkan_.
- Headings: sentence case, noun phrases. Eyebrows, badges, table heads: UPPERCASE, wide-tracked. Never all-caps a sentence.
- Numbers: decimal comma, thousands dot, unit spaced — `12,4 MWp`, `Rp 18.400.000.000`. Ratios keep the colon.
- Use: _berkelanjutan, kolaborasi, tumbuh, terkoneksi, tangguh, majemuk_. Avoid: _revolusioner, terdepan, solusi inovatif, game-changing_.
- No emoji. No exclamation marks in body copy.

---

## 7. Logo — hard constraints

Use the files in `assets/` as supplied. Do not redraw, recolour, stretch, rotate, outline, shadow, gradient, re-typeset or fill them with imagery.

- Clear zone on all sides = **4× the logogram bar**.
- Minimum size: primary 1cm / 28px · secondary 2,3cm / 65px · logogram 0,5cm / 14px.
- Below 5cm printed, drop the JAKARTA UTILITAS line and the Jakpro endorsement → `variant="compact"`.
- Single-colour applications: white or black only.
- White knockout on Rich Black, Pigment Green, Polynesian Blue and photography; full-colour only on Anti-flash White or white.
- In a `flex-direction: column` parent, add `align-self: flex-start` or the `width:auto` image stretches to the column and distorts.

Twelve prohibitions are listed in `guidelines/brand-logo-misuse.card.html`.

---

## 8. Before you ship

- [ ] Only tokens — no raw hexes, no off-ladder spacing.
- [ ] At most two background colours in the artefact.
- [ ] Body copy ≤ 68 characters per line; slide text ≥ 24px; print ≥ 12pt.
- [ ] Every figure carries a period or a source.
- [ ] Focus rings visible on every interactive element.
- [ ] Logo clear zone respected; correct variant for the ground; not distorted.
- [ ] Pattern band on an edge and under 50% of the layout.
- [ ] No gradient, no glassmorphism, no emoji, no drawn SVG icon.
- [ ] Text contrast ≥ 4.5:1 (3:1 headline scale).
- [ ] `prefers-reduced-motion` honoured (automatic if you use the duration tokens).

---

## 9. Where things live

| Need                                                                 | File                                     |
| -------------------------------------------------------------------- | ---------------------------------------- |
| Brand context, content fundamentals, visual foundations, iconography | `readme.md`                              |
| Tokens                                                               | `tokens/*.css`                           |
| Class vocabulary for plain HTML                                      | `base/components.css`                    |
| Component source, types, usage notes                                 | `components/<group>/`                    |
| Full-surface examples                                                | `ui_kits/website/`, `ui_kits/media/`     |
| Ready 16:9 deck                                                      | `templates/pitch-deck/PitchDeck.dc.html` |
| Prompts for NotebookLM / ChatGPT / Gemini                            | `ai-prompts.md`                          |
| Agent-Skills wrapper                                                 | `SKILL.md`                               |
