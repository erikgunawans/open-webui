# Design tokens — extracted from Open WebUI v0.11.3 (`0a7c158`)

Source of truth for a React design system that matches this product's look. Every value below was
read out of the repo, not invented. Sources: `src/tailwind.css` (`@theme`), `tailwind.config.js`,
`src/app.css`, and frequency analysis across the 662 `.svelte` components.

## Neutral ramp — OKLCH, fully desaturated

The whole product is built on one **pure-gray** ramp (chroma 0, hue 0). Note `gray-850`, which is
**not a stock Tailwind step** — it is the single most-used dark surface in the app and must exist.

| Token | OKLCH | Role (by observed usage) |
|---|---|---|
| `gray-50`  | `oklch(0.98 0 0)` | subtle light hover |
| `gray-100` | `oklch(0.94 0 0)` | light borders |
| `gray-200` | `oklch(0.92 0 0)` | **default border color** (set globally in `@layer base`) |
| `gray-300` | `oklch(0.85 0 0)` | input borders (light) |
| `gray-400` | `oklch(0.77 0 0)` | **placeholder text** |
| `gray-500` | `oklch(0.69 0 0)` | muted text |
| `gray-600` | `oklch(0.51 0 0)` | input borders (dark) |
| `gray-700` | `oklch(0.42 0 0)` | secondary text (dark) |
| `gray-800` | `oklch(0.32 0 0)` | dark borders, dark hover |
| `gray-850` | `oklch(0.27 0 0)` | **dominant dark surface + dark border** — non-standard, required |
| `gray-900` | `oklch(0.20 0 0)` | deep dark surface |
| `gray-950` | `oklch(0.16 0 0)` | deepest surface (rare) |

## Surfaces — observed frequency

| Pair | Count | Use |
|---|---|---|
| `bg-white` | 431 | the light surface; essentially the only one |
| `dark:border-gray-850` | 132 | dominant dark border |
| `dark:bg-gray-850` | 109 | dominant dark surface |
| `dark:border-gray-800` | 72 | secondary dark border |
| `dark:bg-gray-900` | 62 | deeper panels |
| `dark:bg-gray-950` | 9 | rare |

Idiom: **light = `bg-white`, dark = `dark:bg-gray-850`**, border `gray-200` / `dark:gray-850`.
There are no semantic surface tokens in the original — inventing them (`--surface-1`, `--border-subtle`)
is the main improvement the new DS should make, mapped onto these exact values.

## Accent and semantic color

| Role | Value | Evidence |
|---|---|---|
| **Accent / focus** | `blue-500` | focus ring (`outline: 2px solid`), 82× `border-blue-500`, 80× `border-blue-400` (dark pair) |
| Error | `red-500` / `red-400` (dark) | 24× / 10× |
| Success | `green-500` / `green-400` | 18× / 7×, plus `emerald-400` |
| Warning | `yellow-500`, text `yellow-700` | 15× / 13× |

Accent use is deliberately sparse — the product is near-monochrome and leans on the gray ramp.
Checkboxes are the one filled-accent control: `bg-blue-600 border-blue-600` when checked.

## Typography

```
--font-sans: var(--app-font-family, -apple-system), BlinkMacSystemFont, 'Inter', 'Vazirmatn',
  ui-sans-serif, system-ui, 'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif,
  'Helvetica Neue', Arial, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
```

- `--font-primary` and `--font-secondary` both alias `--font-sans` — there is **one typeface**.
- `--app-font-family` is a runtime user override (set via `text-scale.ts`); keep that seam.
- `'Vazirmatn'` is present for Arabic/Persian — keep it, the product is multilingual (66 locales).
- `<pre>` uses the **same sans stack**, not a mono font, plus `white-space: pre-wrap`.
- A `--app-text-scale` custom property drives user-adjustable sizing.

## Radius — observed frequency

| Token | Count | Use |
|---|---|---|
| `rounded-lg` | 468 | **the default** |
| `rounded-xl` | 358 | cards, panels, inputs |
| `rounded-full` | 304 | avatars, pills, icon buttons |
| `rounded-md` | 63 | dense controls |
| `rounded-2xl` / `3xl` | 40 / 21 | large surfaces, modals |

Ship `md | lg | xl | 2xl | 3xl | full`; default components to `lg`.

## Focus, motion, and shared utilities

- **Focus ring:** `outline: 2px solid blue-500; outline-offset: -2px` — applied globally to
  `:focus-visible` *excluding* `input`, `textarea`, `[contenteditable]` and `.ProseMirror`, which get
  their own treatment. Reproduce the exclusion; it matters for the editor surfaces.
- **`.hover-reveal`** (`app.css:68`) — opacity-based, **not** `display:none`, so revealed actions stay
  keyboard-focusable. Preserve this property.
- **`.shimmer`** (`:211`) — in-flight status text.
- **`.scrollbar-hidden`** (`:288`) — thumb appears only on hover/focus/active.
- **Popover motion:** `flyAndScale` — y `-8px`, scale `0.95`, 200ms `cubicOut`. The house transition.
- Modal scrims fade at 10ms; disclosure slides 300ms `quintOut`.
- `@custom-variant hover (&:hover)` is declared — hover styles are **not** wrapped in
  `@media (hover:hover)`, which is why they apply on touch.

## Dark mode

`darkMode: 'class'`, toggled on `documentElement`. A blocking inline IIFE in `app.html:47-126` reads
`localStorage.theme` and applies the class **before first paint** — carry this pattern over or the new
DS will flash. An `oled` variant overrides CSS vars for true black.

## Accessibility

`html.high-contrast` (`app.css:873-1003`) re-colors the muted grays; it is a user setting, not a media
query. ~12 primitives carry `svelte-ignore a11y-*` suppressions — **do not port the gaps**: `Drawer`
lacks a focus trap and `role="dialog"`, `Dropdown`'s trigger is a `display:contents` span with no
`tabindex`, and `Collapsible`'s untitled branch is a click-only `div`. The React rebuild should fix
all of these rather than reproduce them.

## What to change, deliberately

The original has no token layer — components hand-write `bg-x dark:bg-y` pairs, there is **no
`cn`/`twMerge` helper** (so `className` overrides are unreliable, resolved by source order), and the
z-index ladder runs `z-999 → z-9999 → z-99999 → z-99999999`. The new DS should keep the *values* above
exactly and fix the *architecture*: semantic tokens, a real `cn`, and a sane 4-step elevation scale.
