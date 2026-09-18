# AGENTS.md

Guidance for AI agents working in this repo.

This tree descends from [`open-webui/open-webui`](https://github.com/open-webui/open-webui).
The working repo is `erikgunawans/ent-os-new-jup` (private); upstream is tracked as the
`upstream` remote and pulled from, never pushed to.

## Agent skills

### Issue tracker

GitHub Issues on `erikgunawans/ent-os-new-jup` via the `gh` CLI. External PRs are **not**
a triage surface. Note this clone has three remotes and `gh` will target `upstream` unless
the default is pinned — see `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical labels, unchanged: `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`. All exist on the repo. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` and one `docs/adr/` at the repo root, covering both the
SvelteKit frontend and the Python backend. Both are created lazily; neither exists yet.
See `docs/agents/domain.md`.
