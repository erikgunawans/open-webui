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
 * The app sits behind IAP, so the calls run inside Erik's signed-in tab through Interceptor, as
 * every other admin write on this deployment has. The target host is checked inside the page
 * before anything is sent, because the driven tab has drifted to another app before.
 *
 *   bun deploy/gcp/sync-kb.ts            # sync
 *   bun deploy/gcp/sync-kb.ts --check    # report drift only, exit 1 if any; writes nothing
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const JUP_TREE = process.env.JUP_TREE ?? join(process.env.HOME ?? "", "jup");
const HOST = process.env.JUP_OPS_HOST ?? "ops.axiara.ai";
const KB_NAME = "JUP Strategy KB";
const KB_DESCRIPTION =
  "Generated from ~/jup (kb/, DECISIONS.md, records/) by deploy/gcp/sync-kb.ts. Edit the source, not this.";
const JUNK = /(^|\/)(\.DS_Store|Thumbs\.db|\._[^/]*)$/;
const POLL_MS = 3000;
// `interceptor eval` stops answering somewhere between 7 and 9 KB of source (measured
// 2026-09-23), so the file contents are staged into the page in chunks well under that and the
// program itself carries no payload.
const CHUNK = 2500;
const TIMEOUT_MS = 10 * 60 * 1000;

type Entry = { filename: string; path: string; checksum: string; size: number; content: string };

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
    .map((f) => {
      const dir = relative(JUP_TREE, f).split("/").slice(0, -1).join("/");
      return entry(f, dir);
    });
  return [...kb, entry(decisions, ""), ...records].sort((a, b) =>
    `${a.path}/${a.filename}`.localeCompare(`${b.path}/${b.filename}`),
  );
}

const guard = `if (location.host !== ${JSON.stringify(HOST)}) return 'WRONG HOST ' + location.host;`;

/** The payload, as evals that append it to `window.__jupKbBuf`. */
function stagingPrograms(entries: Entry[], check: boolean): string[] {
  const payload = JSON.stringify({ entries, check, name: KB_NAME, description: KB_DESCRIPTION });
  const programs = [`(() => { ${guard} window.__jupKbBuf = ''; return 'staged'; })()`];
  for (let i = 0; i < payload.length; i += CHUNK) {
    const chunk = JSON.stringify(payload.slice(i, i + CHUNK));
    programs.push(`(() => { ${guard} window.__jupKbBuf += ${chunk}; return 'staged'; })()`);
  }
  return programs;
}

/** The in-page program. Runs as Erik; leaves its result on `window.__jupKbSync`. */
function pageProgram(): string {
  return `(() => {
  ${guard}
  const P = JSON.parse(window.__jupKbBuf);
  delete window.__jupKbBuf;
  window.__jupKbSync = { state: 'running' };
  const h = { Authorization: 'Bearer ' + localStorage.token };
  const json = { ...h, 'Content-Type': 'application/json' };
  const call = async (url, init) => {
    const r = await fetch(url, init);
    const body = await r.text();
    if (!r.ok) throw new Error(url + ' -> ' + r.status + ' ' + body.slice(0, 200));
    return body ? JSON.parse(body) : null;
  };
  (async () => {
    const list = await call('/api/v1/knowledge/search?query=' + encodeURIComponent(P.name), { headers: h });
    let kb = (list.items || []).find((k) => k.name === P.name);
    if (!kb && P.check) {
      window.__jupKbSync = { state: 'done', drift: true, reason: 'knowledge base does not exist yet' };
      return;
    }
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
      window.__jupKbSync = { state: 'done', drift, ...summary };
      return;
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
    window.__jupKbSync = { state: 'done', failed, ...summary };
  })().catch((err) => { window.__jupKbSync = { state: 'error', error: String(err) }; });
  return 'started';
})()`;
}

async function interceptor(args: string[]): Promise<string> {
  const proc = Bun.spawn(["interceptor", ...args], { stdout: "pipe", stderr: "pipe" });
  const out = (await new Response(proc.stdout).text()).trim();
  const err = (await new Response(proc.stderr).text()).trim();
  const code = await proc.exited;
  if (code !== 0) throw new Error(`interceptor ${args[0]} exited ${code}: ${out} ${err}`.trim());
  return out.split("\n").pop() ?? "";
}

const entries = collect();
const head = Bun.spawnSync(["git", "-C", JUP_TREE, "rev-parse", "--short", "HEAD"]).stdout.toString().trim();
const dirty = Bun.spawnSync(["git", "-C", JUP_TREE, "status", "--porcelain", "kb", "records", "DECISIONS.md"])
  .stdout.toString()
  .trim();
console.log(`${mode}: ${entries.length} files from ${JUP_TREE} @ ${head}${dirty ? " (WORKING TREE DIRTY)" : ""}`);

for (const program of stagingPrograms(entries, mode === "check")) {
  const staged = await interceptor(["eval", "--main", program]);
  if (staged !== "staged") {
    console.error(`refused before sending anything: ${staged}`);
    process.exit(1);
  }
}
const started = await interceptor(["eval", "--main", pageProgram()]);
if (started !== "started") {
  console.error(`refused before sending anything: ${started}`);
  process.exit(1);
}

const deadline = Date.now() + TIMEOUT_MS;
let result: Record<string, unknown> = { state: "running" };
while (result.state === "running") {
  if (Date.now() > deadline) throw new Error("timed out waiting for the in-page sync");
  await Bun.sleep(POLL_MS);
  result = JSON.parse(await interceptor(["eval", "--main", "JSON.stringify(window.__jupKbSync)"]));
}

console.log(JSON.stringify(result, null, 2));
if (result.state === "error") process.exit(1);
if (mode === "check" && result.drift) process.exit(1);
if (Array.isArray(result.failed) && result.failed.length) process.exit(1);
