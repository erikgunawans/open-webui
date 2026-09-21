# JUP brand, applied at the token layer

How this fork's UI carries the JUP identity. Three files, no component edits.

## Which identity

**`~/jup/brand/tokens/colors.css` is canonical** — the layer Erik ratified 2026-09-18 over the
Graphic Standard Manual 2023 palette, and the same layer that feeds `@jup/ui` and
`@jup/design-system`. Green `#079F4E`, blue `#1E6FB0`, IBM Plex Sans / Fraunces / IBM Plex Mono,
16px panels and 10px controls, real elevation.

**The `jup-design` skill ships the rejected GSM palette** (`#00A550` Pigment Green, Space Grotesk,
square geometry, shadows near-banned). Do not copy tokens out of it. Its content rules — third-person
Bahasa Indonesia, no emoji, a figure always carries a period or a source, `Dilarang` for prohibitions
— still apply; only its palette was superseded.

Re-confirmed with Erik 2026-09-22 before this work, because invoking the skill and following the
ratified layer point in opposite directions.

## The three files

| File | What it carries |
|---|---|
| `src/jup-tokens.css` | The vendored canonical layer under `--jup-*` names. **Do not hand-edit values** — re-vendor from canonical. |
| `src/tailwind.css` | The `@theme` mapping that makes the vendor's own utility classes emit JUP values. |
| `src/app.css` | Page surface, and the hardcoded colours that sat outside any token. |

One deliberate adaptation: canonical expresses dark mode as `@media (prefers-color-scheme: dark)`,
but this app toggles `.dark` on `<html>` and offers an explicit light theme. Honouring the media
query would darken the UI of someone who chose light while their OS is dark, so the dark values hang
off `.dark` only. Values are unchanged; only the selector differs.

## Why the gray ramp is re-tinted, not re-pointed

The obvious move is to map each gray step onto a canonical surface — `gray-200` to `--jup-line`,
`gray-850` to `--jup-surface`. **That breaks the product.** This ramp is overwhelmingly *text*, not
surfaces, and most steps serve both themes:

| Step | Total uses | of which text | light / dark |
|---|---|---|---|
| `gray-500` | 1095 | 1078 | 846 / 249 |
| `gray-400` | 899 | 866 | 467 / 432 |
| `gray-700` | 685 | 555 | 584 / 101 |
| `gray-300` | 617 | 584 | 324 / 293 |

Re-pointing a step to a canonical surface moves its lightness, and every `text-gray-400
dark:text-…` pair the components were built around silently loses contrast.

So **each step keeps its exact lightness and gains only JUP's green cast** — hue drifting 134°→158°
light-to-dark, chroma peaking around 0.030 mid-ramp, both measured off the canonical neutrals
(`--jup-paper` is L .9725 C .0073 H 132.4; `--jup-ink` is L .2284 C .0227 H 165.8).

Adding chroma at a fixed OKLCH `L` still nudges relative luminance, so the WCAG ratios were measured
rather than assumed. Across all 12 steps against both white and the dark surface, **the largest shift
is 0.17** and most are under 0.10. The hierarchy survives; the dead gray becomes JUP's neutral.

## Contrast — the part the palette does not encode

The canonical accents are tuned as **fills**, and several fail AA as text. Verified in real Chrome:

| Pair | Ratio | Use |
|---|---|---|
| `#026E35` (`brand-text`, `brand-600`) on paper | 5.92:1 | **words** |
| `#079F4E` (`brand`, `brand-500`) on paper | 3.20:1 | fills, borders, icons — **never body text** |
| white on `#026E35` | 6.39:1 | anything |
| white on `#079F4E` | 3.45:1 | large/non-text only |
| white on `#1E6FB0` | 5.31:1 | anything |
| `--jup-ink` on paper | 15.58:1 | anything |
| `--jup-ink-soft` on paper | 7.48:1 | anything |

Labels on filled surfaces differ **per hue**: brand and amber want the ink label, blue and red want
white — hence `--jup-text-on-{brand,amber,blue,red}` rather than one value. In dark every accent is a
pastel on near-black, so accents clear AA as text unmodified and every filled surface wants the dark
label; darkening them in dark makes contrast worse.

## What changed visibly

- **Page is paper, cards are white.** `body` was `background: #fff; color: #000` in light and
  `#171717` in dark — a neutral matching no token here. Canonical is explicit that a canvas is never
  pure `#FFF` and ink never pure `#000`.
- **Geometry is rounded.** `rounded-lg` (480 uses) is the workhorse control radius and now resolves
  to canonical 10px; `rounded-xl` (365) to the 16px panel radius.
- **Focus and selection carry the brand.** `border-blue-400` / `border-blue-500` (80 and 82 uses)
  already were the selection pair and land exactly on the canonical light/dark blue, so the retint
  needed no component change.
- **A checked checkbox is green, not blue** — canonical gives green action and affirmation, blue
  institution and navigation. `brand-600` rather than `brand-500` so the white checkmark clears
  contrast.
- **Elevation is real**, green-cast to match the surfaces it sits on.

## Open

**The webfonts are not served yet.** The stacks name IBM Plex Sans, Fraunces and IBM Plex Mono and
degrade to the system face until the files exist — no IBM Plex or Fraunces file is anywhere on this
machine, and only `Inter-Variable.ttf` and `Vazirmatn-Variable.ttf` ship in `static/assets/fonts/`.
Until that is decided (self-host the files, or load from Google Fonts and accept the external
request), the UI is JUP in colour and geometry but not yet in typeface. `--app-font-family`, the
user's own override in the Interface settings panel, still wins over all of it.

Placeholder text keeps the vendor's lightness (`gray-400`, ~2.1:1 on white) — unchanged from
upstream, and raising it is a legibility decision beyond a brand retint.
