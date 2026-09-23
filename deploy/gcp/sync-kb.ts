#!/usr/bin/env bun
/**
 * Load the JUP Strategy KB and the record tree into the live app's knowledge base.
 *
 * Agentic-capabilities plan, Phase 1. The document set is the one `~/jup/kb/serve.ts` loads, so
 * the chat and the Worker assistant answer from the same material: every `kb/*.md` except
 * `CONTEXT.md` (that is the assistant's operating contract, not reference material), plus
 * `DECISIONS.md`, plus every `records/**\/*.md` (Erik's call, 2026-09-23).
 *
 * It uses the vendor's own incremental directory sync over the public API, the same sequence the
 * knowledge page's "Sync directory" button runs: `sync/diff` against a sha256 manifest, then
 * `sync/cleanup` for deleted and stale files, `dirs/create` for missing folders, and an upload per
 * added or changed file carrying `knowledge_id`, which the server links after processing. No
 * vendor code is patched.
 *
 * The app sits behind IAP, so the calls run inside Erik's signed-in tab through Interceptor
 * (`lib/in-tab.ts`, which also holds the payload-size and host-guard rules).
 *
 *   bun deploy/gcp/sync-kb.ts            # sync
 *   bun deploy/gcp/sync-kb.ts --check    # report drift only, exit 1 if any; writes nothing
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { runInTab } from "./lib/in-tab";

const JUP_TREE = process.env.JUP_TREE ?? join(process.env.HOME ?? "", "jup");
const KB_NAME = "JUP Strategy KB";
const KB_DESCRIPTION =
  "Generated from ~/jup (kb/, DECISIONS.md, records/) by deploy/gcp/sync-kb.ts. Edit the source, not this.";
const JUNK = /(^|\/)(\.DS_Store|Thumbs\.db|\._[^/]*)$/;

type Entry = { filename: string; path: string; checksum: string; size: number; content: string };
type Result = {
  knowledge_id?: string;
  drift?: boolean;
  reason?: string;
  added?: string[];
  modified?: string[];
  deleted?: string[];
  unmodified?: number;
  failed?: string[];
};

const mode = process.argv[2] === "--check" ? "check" : process.argv[2] ? "usage" : "sync";
if (mode === "usage") {
  console.error("usage: bun deploy/gcp/sync-kb.ts [--check]");
  process.exit(2);
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

function entry(file: string, path: string): Entry {
  const bytes = readFileSync(file);
  return {
    filename: file.split("/").pop() as string,
    path,
    checksum: createHash("sha256").update(bytes).digest("hex"),
    size: bytes.length,
    content: bytes.toString("utf8"),
  };
}

function collect(): Entry[] {
  const kbDir = join(JUP_TREE, "kb");
  const recordsDir = join(JUP_TREE, "records");
  const decisions = join(JUP_TREE, "DECISIONS.md");
  for (const required of [kbDir, recordsDir, decisions]) {
    if (!existsSync(required)) throw new Error(`missing ${required}; set JUP_TREE`);
  }
  const kb = readdirSync(kbDir)
    .filter((f) => f.endsWith(".md") && f !== "CONTEXT.md")
    .map((f) => entry(join(kbDir, f), "kb"));
  const records = walk(recordsDir)
    .filter((f) => f.endsWith(".md") && !JUNK.test(f))
    .map((f) => entry(f, relative(JUP_TREE, f).split("/").slice(0, -1).join("/")));
  return [...kb, entry(decisions, ""), ...records].sort((a, b) =>
    `${a.path}/${a.filename}`.localeCompare(`${b.path}/${b.filename}`),
  );
}

// Runs in the tab with P = { entries, check, name, description }.
const PROGRAM = `
  const list = await call('/api/v1/knowledge/search?query=' + encodeURIComponent(P.name), { headers: h });
  let kb = (list.items || []).find((k) => k.name === P.name);
  if (!kb && P.check) return { drift: true, reason: 'knowledge base does not exist yet' };
  if (!kb) {
    kb = await call('/api/v1/knowledge/create', {
      method: 'POST', headers: json,
      body: JSON.stringify({ name: P.name, description: P.description, access_grants: [] }),
    });
  }
  const manifest = P.entries.map(({ filename, path, checksum, size }) => ({ filename, path, checksum, size }));
  const diff = await call('/api/v1/knowledge/' + kb.id + '/sync/diff', {
    method: 'POST', headers: json, body: JSON.stringify({ manifest }),
  });
  const summary = {
    knowledge_id: kb.id,
    added: diff.added.map((a) => (a.path ? a.path + '/' : '') + a.filename),
    modified: diff.modified.map((m) => (m.path ? m.path + '/' : '') + m.filename),
    deleted: diff.deleted.map((d) => d.filename),
    unmodified: diff.unmodified_count,
  };
  if (P.check) {
    const drift = summary.added.length + summary.modified.length + summary.deleted.length > 0 || diff.rmdir.length > 0;
    return { drift, ...summary };
  }
  const stale = [...diff.deleted.map((d) => d.file_id), ...diff.modified.map((m) => m.stale_file_id)];
  if (stale.length || diff.rmdir.length) {
    await call('/api/v1/knowledge/' + kb.id + '/sync/cleanup', {
      method: 'POST', headers: json, body: JSON.stringify({ file_ids: stale, dir_ids: diff.rmdir }),
    });
  }
  const dirs = { ...diff.directory_map };
  for (const path of diff.mkdir) {
    const segments = path.split('/');
    const parent = segments.slice(0, -1).join('/');
    const body = { name: segments[segments.length - 1] };
    if (parent) body.parent_id = dirs[parent];
    const made = await call('/api/v1/knowledge/' + kb.id + '/dirs/create', {
      method: 'POST', headers: json, body: JSON.stringify(body),
    });
    dirs[path] = made.id;
  }
  const wanted = new Set([...diff.added, ...diff.modified].map((e) => e.path + '/' + e.filename));
  const failed = [];
  for (const e of P.entries.filter((e) => wanted.has(e.path + '/' + e.filename))) {
    const form = new FormData();
    form.append('file', new File([e.content], e.filename, { type: 'text/markdown' }));
    form.append('metadata', JSON.stringify({
      knowledge_id: kb.id, file_hash: e.checksum, directory_id: e.path ? dirs[e.path] : null,
    }));
    try { await call('/api/v1/files/', { method: 'POST', headers: h, body: form }); }
    catch (err) { failed.push(e.path + '/' + e.filename + ': ' + err.message); }
  }
  return { failed, ...summary };
`;

const entries = collect();
const head = Bun.spawnSync(["git", "-C", JUP_TREE, "rev-parse", "--short", "HEAD"]).stdout.toString().trim();
const dirty = Bun.spawnSync(["git", "-C", JUP_TREE, "status", "--porcelain", "kb", "records", "DECISIONS.md"])
  .stdout.toString()
  .trim();
console.log(`${mode}: ${entries.length} files from ${JUP_TREE} @ ${head}${dirty ? " (WORKING TREE DIRTY)" : ""}`);

const result = await runInTab<Result>(
  { entries, check: mode === "check", name: KB_NAME, description: KB_DESCRIPTION },
  PROGRAM,
);
console.log(JSON.stringify(result, null, 2));
if (mode === "check" && result.drift) process.exit(1);
if (result.failed?.length) process.exit(1);
