# Plan — React design system for Claude Design

**Goal:** a React + Tailwind v4 component library that (a) matches this product's visual language and
(b) satisfies `/design-sync`'s contract, so Claude Design builds on-brand JUP UI from real components.

**Why it's a new repo, not this one:** `/design-sync` is React-only — it externalizes `react`/`react-dom`
to `window.React`/`window.ReactDOM`, shims JSX to `React.createElement`, and emits `.jsx` + `<Name>Props`
`.d.ts`. This repo is 662 Svelte files with zero React. Details in `.design-sync/NOTES.md`.

## What the sync contract requires

Non-negotiable, because the converter reads them:

- A **real `dist/`** from the repo's own build, esbuild-bundlable, with `react`/`react-dom` as
  **externals** (if `react-dom` leaks into `dist/`, the converter throws `SCHEDULER_MISSING`).
- `package.json` with a proper `exports` map — **not** `"private": true`.
- Per-component **prop types** that survive to `.d.ts` (so the design agent codes against a real API).
- **Storybook** — optional but strongly preferred: with it, previews come from the repo's own stories
  and are verified against its own Storybook render. Without it, every preview must be authored and
  graded on an absolute rubric instead. Build the Storybook; it makes the sync cheaper and the
  fidelity higher.
- All real component CSS must be reachable from `styles.css`'s `@import` closure — rendered designs
  receive **only** that closure. A card linking CSS directly proves nothing.

## Phases

**1. Scaffold.** New repo. Vite library mode or tsup → `dist/`. React 18+, TypeScript strict,
Tailwind v4, `exports` map, `peerDependencies: {react, react-dom}`, externals configured. Storybook 8.

**2. Token layer.** Port `docs/design-system/TOKENS.md` verbatim into a Tailwind v4 `@theme` block —
the full 12-step OKLCH ramp **including `gray-850`** — then add the semantic layer the original lacks
(`--surface-1`, `--border-subtle`, `--accent`, …) mapped onto those exact values. Add a real `cn`
(`clsx` + `tailwind-merge`); its absence is the original's worst architectural flaw. Define a 4-step
elevation scale to replace the `z-999 → z-99999999` ladder. Carry the pre-paint theme script.

**3. Primitives (~20, in dependency order).** Button, Input, Textarea, Select, Switch, Checkbox,
Badge, Spinner, Tooltip, Modal, Drawer, Dropdown/Menu, Collapsible, Tabs, Pagination, Avatar, Card,
Toast, ConfirmDialog, Skeleton. Match the original's *look* and fix its *a11y gaps* — real focus trap
and `role="dialog"` on Drawer, a focusable Dropdown trigger, keyboard handling on Collapsible.
Keep `.hover-reveal`'s opacity behavior (it preserves keyboard focus) and the `flyAndScale` motion.
Reference inventory: `docs/architecture/15-fe-common-primitives.md`.

**4. Composites (~10).** The pieces that make designs look like *this* product rather than generic
Tailwind: ChatMessage, MessageInput, Sidebar + SidebarItem, ModelSelector, SettingsRow/Section/Field,
FileChip, EmptyState, PageHeader. These carry more brand signal than the primitives do.

**5. Stories + conventions.** One story per component covering real states. Then author
`.design-sync/conventions.md` — the file that gets inlined into the design agent's system prompt.
It must **enumerate the actual class vocabulary**, not say "follow the design system": name the
semantic tokens, the provider wrapper, and load order. Validate every name against the built
artifacts before shipping — a conventions file naming things that don't exist is worse than none.

**6. Sync.** `/design-sync` in the new repo. Shape will be `storybook`. Expect iteration on preview
fidelity — a component that renders wrong there renders wrong in every design the agent ever builds.

## Decisions still open (ask before phase 1)

- **Name and scope** of the package (`@axiara/ui`? `@jup/ui`?) and whether it's public or private.
- **Brand divergence:** match Open WebUI exactly, or shift the accent off `blue-500` to a JUP/Axiara
  brand color? The token spec makes either cheap, but it changes phase 2.
- **Repo location** — sibling of this one, or elsewhere.
- Whether composites (phase 4) are in scope for v1 or deferred; primitives alone are syncable.

## Realistic effort

Phases 1–3 are ~1–2 focused sessions. Phase 4 adds one. Phases 5–6 (stories, conventions, sync
iteration) are where fidelity is won and can take a full session on their own. This is days, not hours.
