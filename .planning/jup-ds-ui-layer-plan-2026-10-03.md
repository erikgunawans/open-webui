# JUP Design System → None-JUPe, whole app (2026-10-03)

Source: claude.ai/design project `7e98d0d9-8cf7-450f-a44f-e02efed2743a` "JUP Design System" (Erik, editable).
Read with DesignSync (`get_file`) after `/design-login`; subagents do not get the DesignSync tool, so the
import runs in the main session. Scope (Erik, 2026-10-03): **the whole app, both layers** — outer
(sidebar + rail + page canvas) and inner (`#main-content` panel, vendor screens via `src/jup-skin.css`,
fork pages via `.jlp-*`). Keep the outer/inner framework.

## What is already the same (no work)
- Identity colours and ramps: `src/jup-tokens.css` already carries GSM 2023 values (paper `#F0F1F1`,
  surface white, neutral-100/200 lines, Rich Black, Pigment Green, Polynesian Blue).
- Fonts: Space Grotesk + Space Mono woff2 already in `static/assets/fonts/` and loaded.
- Elevation tokens `--jup-shadow{,-md,-lg}` equal the kit's `--jup-shadow-sm/md/lg`.

## What the kit changes — its interface layer (`tokens/ui.css`, DESIGN.md §1–3)
| | Kit | Live |
|---|---|---|
| Primary action | Rich Black filled **pill** (`--jup-ui-ink`), tonal grey secondary | Polynesian Blue `--jup-action` |
| Blue | navigation, governance, institutional weight only | the action colour |
| Green | one brand CTA per view, focus on brand controls, selected switch, tab underline | brand moments |
| Control radius | 18px (pill at 36px) | 8px |
| Container radius | 24px, nested 10, tooltip 6 | 12 / modal 14 |
| Control heights | 32 / 36 / 44, 14px text | vendor mixed |
| Inputs | tonal `--jup-ui-fill` (#F0F1F1), no border at rest; focus → white + hairline + 3px soft ring | vendor borders |
| Cards | white, 1px hairline neutral-100, `--jup-ui-shadow-card`, 20px pad | `--jup-panel-shadow` |
| Pop (menus, dialogs, toasts) | `--jup-ui-shadow-pop` | `--jup-shadow-lg` |
| Focus | 3px soft ring rgba(1,22,39,.12); green ring on brand controls | mixed |
| Tabs | 2px green underline, or paper segment in a pill track | `.jup-seg` segments |
| Display type | Space Grotesk 500, −0.045em; headings −0.025em | 700-ish, looser |
| Eyebrow | 12px 500 uppercase +0.18em green, 45° diamond, hairline rule to the right (`SectionHeading`) | none |
| Motion | colour/border/shadow 140–220ms; geometry never moves | mixed |
| Decoration | only the Elemen Grafis band (`PatternBand`) on an edge, <50%; no gradients/glass/emoji | none |
| Dark | kit has only `.jup-inverse` (D18a: GSM has no dark mode) | derived dark theme exists |

## Decisions — SETTLED by Erik 2026-10-03: all three as recommended (Rich Black primary, soft geometry, dark kept and re-derived)
1. **Primary action becomes Rich Black (dark: white ink), blue leaves actions.** The kit is explicit;
   it reverses the 09-26 skin's blue `--jup-action`.
2. **Geometry goes soft: 18px pill controls, 24px containers.** The kit splits print (square) from
   interface (soft); the app is interface. This supersedes the "square, controls 4" line of D18 for UI.
3. **Dark mode stays**, re-derived from the kit's `.jup-inverse` UI values (`--jup-ui-*` inverse block).

## Build order (each step: preview with interceptor style inject, contrast measured, then commit)
1. Import: write the kit's `tokens/*.css`, `base/*.css`, DESIGN.md, readme.md, SKILL.md and needed
   assets (logos, pattern bands, sector icons; fonts already shipped) to `design/jup-design-system/`.
2. Tokens: add the `--jup-ui-*` layer to `src/jup-tokens.css` (light + dark), keep existing names as
   aliases so nothing downstream breaks. Gray ramp untouched (memory `openwebui-gray-ramp-is-text`).
3. Outer layer: canvas, sidebar/rail surfaces, nav item states (blue for selected nav), focus ring.
4. Inner layer via `jup-skin.css` hooks only: primary/secondary buttons, inputs + chat composer,
   cards/list rows, menus/dialogs/toasts (pop shadow, 24/10 radii), tabs (underline/pill).
5. Fork pages: `.jlp-*` (Ruang Pimpinan, Tinjauan Pengetahuan incl. Kartu Kontrak, Portfolio) adopt
   `SectionHeading` eyebrow + rule, `StatBlock` figures (with notes), table rules from the kit.
6. Brand moments: logo files per the clear-zone rules; one `PatternBand` on an edge (sign-in / home).
7. Verify: Interceptor on the live build, light + dark, desktop + mobile; contrast ≥ 4.5:1; then PR,
   CI (both workflows), deploy with Erik's OK.
