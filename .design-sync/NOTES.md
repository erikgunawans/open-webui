# design-sync notes

## 2026-09-18 — /design-sync cannot run against this repo (framework mismatch)

Checked and confirmed, so a future run doesn't rediscover it:

- No prior sync state, no `.storybook/` anywhere, zero `*.stories.*`.
- `package.json` is `"private": true` with no `main`/`module`/`exports`/`files` and no `dist/`.
  This is an **application**, not a publishable component library.
- **662 `.svelte` files, 0 `.jsx`, 0 `.tsx`, no React dependency anywhere** (single package.json).

**The blocker is the framework, not the missing Storybook.** The converter is React-only:
`lib/bundle.mjs` externalizes `react`/`react-dom` to `window.React`/`window.ReactDOM` and shims the
automatic JSX runtime to `React.createElement`; components ship as `.jsx` + a `<Name>Props` `.d.ts`
and are rendered by Claude Design's React runtime. The skill contains 162 references to React, 68 to
JSX, and **zero to Svelte**. Svelte 5 compiles to a runes runtime instantiated via `mount()` —
`React.createElement` cannot render one, and no config override changes that.

**Do not attempt a sync of this repo.** The agreed path (2026-09-18) is to build a separate React
design system that mirrors this product's visual language and sync *that*. Token spec extracted to
`docs/design-system/TOKENS.md`; build plan in `docs/design-system/PLAN.md`.
