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
SvelteKit frontend and the Python backend. Both now exist.
See `docs/agents/domain.md`.

## Backend tests

One command, from a clean checkout:

```
uv run --only-group dev pytest
```

`--only-group dev` installs the test tooling **without** the project and its runtime tree
(chromadb, transformers, sentence-transformers and the rest), so the suite is seconds, not
minutes. A ticket that needs to import `open_webui` drops the flag and pays for the full
environment: `uv run --group dev pytest`.

Tests live in `tests/` (plural) at the repo root, deliberately outside `backend/` so the
quarterly upstream rebase in ADR-0007 never has to merge them. `test/` (singular) is the
vendor tree's own directory — do not add to it. Fixture data goes in `tests/fixtures/`,
reached through the `fixtures_dir` / `fixture_path` fixtures in `tests/conftest.py`.

### After every upstream rebase

```
uv run --only-group dev pytest tests/test_boot.py
```

Asserts alembic resolves to exactly one head — a fork revision colliding with an upstream
one is the failure that stops the app booting at all, because migrations run at
config-import time (ADR-0007). It reads `down_revision` from each version file's AST and
never the docstring, which `d4e5f6a7b8c9` already contradicts. The same file also imports
the real app to prove it starts; that test skips under `--only-group dev` and runs in the
`boot` CI job, which triggers on migration changes or on `workflow_dispatch`.

### Authoring records in the JUP tree

A value containing ` #` **must be quoted**: in YAML a bare hash opens a comment, so
`purpose: The 5 mmscfd allocation — Gate #1 of the gas pillar` parses as `... — Gate` and
the rest is silently gone. No parser guard can catch it, because what arrives is a shorter
valid string. This bites the single most likely phrase in JUP's records, and the worked
example in the spec for #1 is itself written unquoted.
