#!/usr/bin/env bun
/**
 * Upsert the tools under `tools/` into the live app's Tools system.
 *
 * `tools/*.py` is the source of truth; the DB rows are a copy. A tool is Python the backend
 * `exec`s, so each file here must stay a thin wrapper over a tested `jup.*` module (see
 * `tests/test_portfolio_tool.py`, which enforces that for `portfolio_status`).
 *
 * Each file declares its Risk Class in its frontmatter (`risk_class: read`); the app copies
 * frontmatter into the stored tool, and `jup.tool_policy` gates the tool by it (ADR-0013).
 *
 * Tool authoring is admin-only on this deployment (`workspace.tools*` is false for users). New
 * tools get empty access grants, so they are admin-only; an update never sends `access_grants`,
 * which the route treats as "leave unchanged", so grants given in the UI survive a re-sync.
 *
 *   bun deploy/gcp/sync-tools.ts            # upsert
 *   bun deploy/gcp/sync-tools.ts --check    # report drift only, exit 1 if any; writes nothing
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { runInTab } from "./lib/in-tab";

const ROOT = join(import.meta.dir, "..", "..", "tools");

type Tool = { id: string; name: string; description: string; content: string };
type Result = { created: string[]; updated: string[]; unmodified: string[]; drift?: boolean; failed: string[] };

const mode = process.argv[2] === "--check" ? "check" : process.argv[2] ? "usage" : "sync";
if (mode === "usage") {
  console.error("usage: bun deploy/gcp/sync-tools.ts [--check]");
  process.exit(2);
}

function load(file: string): Tool {
  const content = readFileSync(join(ROOT, file), "utf8");
  const header = content.match(/^"""\n([\s\S]*?)\n"""/);
  if (!header) throw new Error(`${file}: no frontmatter docstring`);
  const fm: Record<string, string> = {};
  for (const line of header[1].split("\n")) {
    const i = line.indexOf(":");
    if (i > 0) fm[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  const id = file.replace(/\.py$/, "");
  if (!/^[a-z0-9_]+$/.test(id) || !fm.title) throw new Error(`${file}: bad id or missing title`);
  // The Risk Class travels in the content: the app copies frontmatter into the stored tool's
  // meta.manifest, which is where jup.tool_policy reads it. A tool without one would be gated as
  // `external`, which is safe but is never what the author meant, so refuse to push it.
  if (!["read", "write_own", "external"].includes(fm.risk_class ?? ""))
    throw new Error(`${file}: risk_class must be read, write_own or external (ADR-0013)`);
  return { id, name: fm.title, description: fm.description ?? "", content };
}

const tools = readdirSync(ROOT)
  .filter((f) => f.endsWith(".py"))
  .sort()
  .map(load);
console.log(`${mode}: ${tools.length} tools from ${ROOT}`);

// Runs in the tab with P = { tools, check }.
const PROGRAM = `
  const existing = await call('/api/v1/tools/export', { headers: h });
  const byId = Object.fromEntries(existing.map((t) => [t.id, t]));
  const out = { created: [], updated: [], unmodified: [], failed: [] };
  for (const t of P.tools) {
    const cur = byId[t.id];
    const same = cur && cur.name === t.name && cur.content === t.content
      && ((cur.meta && cur.meta.description) || '') === t.description;
    if (same) { out.unmodified.push(t.id); continue; }
    const bucket = cur ? out.updated : out.created;
    if (P.check) { bucket.push(t.id); continue; }
    const form = { id: t.id, name: t.name, content: t.content, meta: { description: t.description } };
    if (!cur) form.access_grants = [];
    try {
      await call(cur ? '/api/v1/tools/id/' + t.id + '/update' : '/api/v1/tools/create', {
        method: 'POST', headers: json, body: JSON.stringify(form),
      });
      bucket.push(t.id);
    } catch (err) { out.failed.push(t.id + ': ' + err.message); }
  }
  if (P.check) out.drift = out.created.length + out.updated.length > 0;
  return out;
`;

const result = await runInTab<Result>({ tools, check: mode === "check" }, PROGRAM);
console.log(JSON.stringify(result, null, 2));
if (mode === "check" && result.drift) process.exit(1);
if (result.failed.length) process.exit(1);
