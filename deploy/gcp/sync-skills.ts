#!/usr/bin/env bun
/**
 * Upsert the skills under `skills/` into the live app's Skills system.
 *
 * `skills/` is the source of truth; the DB rows are a copy. Two kinds live there:
 *
 * - `skills/jup/*.md`: JUP's own skills, with `id`, `name`, `description` and `tags` frontmatter.
 * - `skills/holaos/`: prompt-only skills copied from holaOS (Holaboss, modified Apache-2.0) and
 *   one MIT skill it bundles (stop-slop, Hardik Pandya). See `skills/holaos/NOTICE.md` for what
 *   was taken, what was left out and why. Each gets an attribution footer in its content.
 *
 * New skills are created with empty access grants, so they are admin-only. An update never
 * sends `access_grants`, which the route treats as "leave unchanged", so grants given to staff
 * in the UI survive a re-sync.
 *
 *   bun deploy/gcp/sync-skills.ts            # upsert
 *   bun deploy/gcp/sync-skills.ts --check    # report drift only, exit 1 if any; writes nothing
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { runInTab } from "./lib/in-tab";

const ROOT = join(import.meta.dir, "..", "..", "skills");
const HOLAOS_COMMIT = "a6b58be";

type Skill = { id: string; name: string; description: string; content: string; tags: string[] };
type Result = { created: string[]; updated: string[]; unmodified: string[]; drift?: boolean; failed: string[] };

const mode = process.argv[2] === "--check" ? "check" : process.argv[2] ? "usage" : "sync";
if (mode === "usage") {
  console.error("usage: bun deploy/gcp/sync-skills.ts [--check]");
  process.exit(2);
}

function parse(file: string): { fm: Record<string, string>; body: string } {
  const text = readFileSync(file, "utf8");
  const match = text.match(/^---\n([\s\S]*?)\n---\n\n?([\s\S]*)$/);
  if (!match) throw new Error(`${file}: no frontmatter`);
  const fm: Record<string, string> = {};
  for (const line of match[1].split("\n")) {
    const i = line.indexOf(":");
    // Nested YAML (stop-slop's `metadata:` block) is indented; only top-level keys matter here.
    if (i > 0 && !line.startsWith(" ")) fm[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return { fm, body: match[2].trim() };
}

function title(body: string, fallback: string): string {
  return body.match(/^# (.+)$/m)?.[1].trim() ?? fallback;
}

function attribution(origin: string, licence: string): string {
  return `\n\n---\n*Ported from ${origin} (${licence}) at holaOS commit ${HOLAOS_COMMIT}; text unmodified except as noted in skills/holaos/NOTICE.md in ent-os-new-jup.*`;
}

function jupSkills(): Skill[] {
  const dir = join(ROOT, "jup");
  return readdirSync(dir)
    .filter((f) => f.endsWith(".md"))
    .map((f) => {
      const { fm, body } = parse(join(dir, f));
      const tags = (fm.tags ?? "").replace(/[[\]]/g, "").split(",").map((t) => t.trim()).filter(Boolean);
      return { id: fm.id, name: fm.name, description: fm.description, content: body, tags };
    });
}

function holaosSkills(): Skill[] {
  const dir = join(ROOT, "holaos");
  const flat = readdirSync(dir)
    .filter((f) => f.endsWith(".md") && f !== "NOTICE.md")
    .map((f) => {
      const { fm, body } = parse(join(dir, f));
      return {
        id: fm.name,
        name: title(body, fm.name),
        description: fm.description,
        content: body + attribution("holaOS by Holaboss", "modified Apache-2.0"),
        tags: ["holaos"],
      };
    });

  // stop-slop points at three reference files. A DB skill is one text field, so the references
  // are inlined in place of the links, in the order the skill cites them.
  const slop = join(dir, "stop-slop");
  const { fm, body } = parse(join(slop, "SKILL.md"));
  const refs = ["phrases.md", "structures.md", "examples.md"]
    .filter((r) => existsSync(join(slop, "references", r)))
    .map((r) => `## Reference: ${r}\n\n${readFileSync(join(slop, "references", r), "utf8").trim()}`);
  const inlined = body.replace(/See \[references\/([a-z]+\.md)\]\(references\/[a-z]+\.md\)\./g, "See Reference: $1 below.");
  return [
    ...flat,
    {
      id: fm.name,
      name: title(body, fm.name),
      description: fm.description,
      content: [inlined, ...refs].join("\n\n") + attribution("stop-slop by Hardik Pandya, bundled in holaOS", "MIT"),
      tags: ["holaos", "writing"],
    },
  ];
}

const skills = [...jupSkills(), ...holaosSkills()].sort((a, b) => a.id.localeCompare(b.id));
for (const s of skills) {
  if (!/^[a-z0-9_-]+$/.test(s.id) || !s.name || !s.content) throw new Error(`bad skill ${JSON.stringify(s.id)}`);
}
console.log(`${mode}: ${skills.length} skills from ${ROOT}`);

// Runs in the tab with P = { skills, check }.
const PROGRAM = `
  const existing = await call('/api/v1/skills/export', { headers: h });
  const byId = Object.fromEntries(existing.map((s) => [s.id, s]));
  const out = { created: [], updated: [], unmodified: [], failed: [] };
  for (const s of P.skills) {
    const cur = byId[s.id];
    const same = cur && cur.name === s.name && (cur.description || '') === s.description && cur.content === s.content
      && JSON.stringify((cur.meta && cur.meta.tags) || []) === JSON.stringify(s.tags);
    if (same) { out.unmodified.push(s.id); continue; }
    const bucket = cur ? out.updated : out.created;
    if (P.check) { bucket.push(s.id); continue; }
    const form = { id: s.id, name: s.name, description: s.description, content: s.content, meta: { tags: s.tags }, is_active: true };
    if (!cur) form.access_grants = [];
    try {
      await call(cur ? '/api/v1/skills/id/' + s.id + '/update' : '/api/v1/skills/create', {
        method: 'POST', headers: json, body: JSON.stringify(form),
      });
      bucket.push(s.id);
    } catch (err) { out.failed.push(s.id + ': ' + err.message); }
  }
  if (P.check) out.drift = out.created.length + out.updated.length > 0;
  return out;
`;

const result = await runInTab<Result>({ skills, check: mode === "check" }, PROGRAM);
console.log(JSON.stringify(result, null, 2));
if (mode === "check" && result.drift) process.exit(1);
if (result.failed.length) process.exit(1);
