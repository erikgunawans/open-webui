# Import record

Reference copy of the claude.ai/design project **JUP Design System**
(`7e98d0d9-8cf7-450f-a44f-e02efed2743a`), imported 2026-10-03 for the app-wide UI layer
(`.planning/jup-ds-ui-layer-plan-2026-10-03.md`). Nothing here is served by the app; the app's own
tokens live in `src/jup-tokens.css` and the vendor restyle in `src/jup-skin.css`.

## Provenance

- Read live with DesignSync `get_file` on 2026-10-03: `tokens/ui.css`, `base/base.css`,
  `base/components.css`, `DESIGN.md`, `readme.md`, `styles.css` (these had changed since the
  2026-09-14 export).
- Identical to the live project on 2026-10-03 and taken from the 2026-09-14 export
  (`~/Downloads/JUP Design System`): the other `tokens/*.css`, `SKILL.md`,
  `components/**/*.prompt.md`. Spot-checked by content.
- Binary assets (logos, pattern bands, sector marks, Lucide SVGs) from the 2026-09-14 export; the
  manual's logo files do not change. Fonts are not copied — the app ships them in
  `static/assets/fonts/`.
- Not imported: React sources, `_ds_bundle.js`, guideline cards, UI kits, the deck template, the
  brand-guideline PDF in `uploads/`.

## Where the kit contradicts itself (resolved for this app)

| Kit says                                                    | Also says                                                                   | This app does                                     |
| ----------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------- |
| `components.css`, `DESIGN.md`: primary = Rich Black pill    | `Button.prompt.md`, readme §4.2: primary = Pigment Green                    | Rich Black (Erik, 2026-10-03)                     |
| `DESIGN.md` §3: nothing lifts, scales or translates         | `ui.css` `--jup-ui-lift`, readme §4.6: cards lift 2px, buttons press to 98% | No geometry motion                                |
| readme §4.2: `--jup-text-brand` `#008A43` is 4.6:1 on white | Measured: 4.45:1 on white, 3.93:1 on `#F0F1F1`                              | Brand text uses green-700 `#006C34` (6.57 / 5.81) |

The repo formatter (`npm run format`, enforced by CI) re-wraps these files; the content is the
kit's, the layout is Prettier's.
