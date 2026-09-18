# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues in **`erikgunawans/ent-os-new-jup`** (private). Use the `gh` CLI for all operations.

## Repo resolution — read this first

This clone has **three** remotes:

| Remote     | Repo                          | Role                                            |
| ---------- | ----------------------------- | ----------------------------------------------- |
| `origin`   | `erikgunawans/ent-os-new-jup` | **Where issues live.** The working repo.        |
| `fork`     | `erikgunawans/open-webui`     | Legacy fork of upstream. Not an issue surface.  |
| `upstream` | `open-webui/open-webui`       | Vendor upstream. Pull only. Never file here.    |

`gh` prefers a remote literally named `upstream` when guessing the repo, so a bare
`gh issue list` will silently target `open-webui/open-webui`. Two guards:

1. `gh repo set-default erikgunawans/ent-os-new-jup` has been run in this clone
   (stored in `.git/config`). Re-run it if the config is ever reset.
2. When in doubt, pass `--repo erikgunawans/ent-os-new-jup` explicitly. Prefer this
   in any scripted or non-interactive command.

Verify before a batch of writes: `gh repo set-default --view`.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

## Pull requests as a triage surface

**PRs as a request surface: no.**

This is a private, single-maintainer repo — there is no external contributor PR flow,
so `/triage` should read issues only and ignore PRs entirely.

_(Set to `yes` if this ever changes. When `yes`, PRs run through the same labels and
states as issues, using the `gh pr` equivalents: `gh pr view <n> --comments`,
`gh pr diff <n>`, `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`
keeping only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` or `NONE`,
and `gh pr comment` / `gh pr edit --add-label` / `gh pr close`. GitHub shares one number
space across issues and PRs, so a bare `#42` may be either — resolve with `gh pr view 42`
and fall back to `gh issue view 42`.)_

## When a skill says "publish to the issue tracker"

Create a GitHub issue in `erikgunawans/ent-os-new-jup`.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`), plus `wayfinder:claimed` once claimed.
- **Blocking**: native issue relationships where available; otherwise a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every issue it lists is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open `Blocked by` issue or the `wayfinder:claimed` label; first in map order wins.
- **Claim**: `gh issue edit <n> --add-label wayfinder:claimed` — the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.

The `wayfinder:*` labels are created on demand — `gh label create` them the first time
`/wayfinder` runs, since they are not part of the base triage vocabulary.
