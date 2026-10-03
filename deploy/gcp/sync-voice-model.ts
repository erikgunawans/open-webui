#!/usr/bin/env bun
/**
 * Create "Asisten JUP — Suara" and keep it in step (#27, ADR-0006, ADR-0017, ADR-0018).
 *
 * The voice model is Asisten JUP with a voice scope: the same base model and params (the operating
 * contract rides in the system prompt and is attached again at the funnel), `meta.knowledge` = the
 * JUP knowledge bases below as `{type:'collection'}` items (Erik 2026-10-02: voice reads every JUP
 * knowledge base, replacing the eight named documents of 2026-09-27), tools = `portfolio_status`,
 * `jup_contracts` and `jup_leadership` plus the knowledge builtins, every other builtin category off and the web,
 * image and code capabilities off. `jup.voice_turn` enforces the same scope in code on every voice
 * turn, for both call modes (GPT-Live delegates to this model); this script makes the stored model
 * say what the code enforces.
 *
 * Each knowledge base is resolved by exact name and must be unique; a missing or ambiguous name
 * stops the script before it writes.
 *
 * A new model is created with empty access grants, so it is admin-only; an update never sends
 * `access_grants`, so grants given later (widening voice, ADR-0017) survive a re-sync.
 *
 * The app sits behind IAP, so the calls run inside Erik's signed-in tab (`lib/in-tab.ts`).
 * Running it without `--dry-run` is a DB write and needs Erik's OK.
 *
 *   bun deploy/gcp/sync-voice-model.ts --dry-run   # resolve and print; writes nothing
 *   bun deploy/gcp/sync-voice-model.ts             # create or update the model
 */
import { runInTab } from "./lib/in-tab";

/** Asisten JUP is an override of its base model, so it carries the base model's id. */
const ASISTEN_JUP_ID = "xiaomi/mimo-v2.6-pro-ultraspeed";
const VOICE_MODEL_ID = "asisten-jup-suara"; // jup.voice.VOICE_MODEL_ID
const VOICE_MODEL_NAME = "Asisten JUP — Suara";
const VOICE_TOOL_IDS = ["portfolio_status", "jup_contracts", "jup_leadership"]; // jup.voice_turn.VOICE_TOOL_IDS

/**
 * The JUP knowledge bases voice answers from (Erik, 2026-10-02: "all of the knowledge base").
 * The same two Asisten JUP has; contracts come through `jup_contracts`, per caller.
 * `tests/test_jup_voice_model_sync.py` holds this list to Asisten JUP's.
 */
const VOICE_COLLECTIONS = ["JUP Strategy KB", "JUP Staff Contributions"];

/** Every builtin category the vendor knows (`utils/tools.py`); only `knowledge` stays on. */
const BUILTIN_CATEGORIES = [
  "time",
  "user_input",
  "files",
  "knowledge",
  "chats",
  "subagents",
  "memory",
  "web_search",
  "image_generation",
  "code_interpreter",
  "notes",
  "channels",
  "tasks",
  "automations",
  "calendar",
  "notifications",
];

/**
 * Added after Asisten JUP's own system prompt (Erik, 2026-09-28). The opening line is the call
 * UI's `CALL_OPENING` (`src/lib/voice/call.ts`); `tests/test_jup_voice_model_sync.py` holds the
 * two to the same text. `{{USER_NAME}}` is filled in by the vendor for each caller.
 */
const CALL_OPENING = "Halo, saya memulai panggilan.";
const VOICE_INSTRUCTIONS = [
  "## Panggilan suara",
  "Selalu jawab dalam Bahasa Indonesia, apa pun bahasa pesan pengguna. Istilah teknis bahasa Inggris seperti capex, NPV atau stage-gate boleh tetap dipakai.",
  "Pesan pengguna berasal dari transkripsi suara dan bisa salah dengar. Jika pesan tidak jelas, tidak nyambung, atau muncul dalam bahasa selain Indonesia atau Inggris, jangan menebak: minta pengguna mengulang pertanyaannya dengan singkat.",
  "Jawab seperti orang berbicara: kalimat pendek dan mengalir, tanpa daftar, tabel, judul, atau format markdown. Sebut angka dengan jelas beserta satuannya.",
  "",
  `Jika pesan pengguna persis "${CALL_OPENING}", itu tanda panggilan baru dimulai. Balas hanya dengan:`,
  "1. Sapaan hangat dengan nama pengguna: {{USER_NAME}}.",
  "2. Satu pantun Betawi yang baru, empat baris dengan rima a-b-a-b: dua baris sampiran bernuansa Betawi atau Jakarta, dua baris isi yang menyambut dan mencairkan suasana. Sopan dan ringan, tanpa angka dan tanpa klaim tentang JUP.",
  "3. Satu kalimat yang mengajak pengguna menyampaikan pertanyaannya.",
  "Untuk pesan pembuka ini, jangan mencari dokumen dan jangan memanggil tool.",
].join("\n");

// Staff read this on the voice chat's home screen, so it speaks to them, in Indonesian. This model
// is generated from Asisten JUP by this script (ADR-0006): edit here, never in the admin UI.
const DESCRIPTION =
  "Khusus panggilan suara. Jawaban diambil dari basis pengetahuan JUP dan kartu kontrak sesuai akses Anda.";

const mode = process.argv[2] === "--dry-run" ? "dry-run" : process.argv[2] ? "usage" : "sync";
if (mode === "usage") {
  console.error("usage: bun deploy/gcp/sync-voice-model.ts [--dry-run]");
  process.exit(2);
}

type Result = {
  refused?: string;
  collections?: { name: string; id: string }[];
  tools?: string[];
  builtinTools?: Record<string, boolean>;
  action?: "create" | "update" | "unmodified";
  changed?: string[];
};

// Runs in the tab with P = { collections, check, ... }. Nothing is written before every named
// knowledge base has resolved to exactly one, and nothing at all when P.check.
const PROGRAM = `
  const collections = [];
  for (const name of P.collections) {
    const list = await call('/api/v1/knowledge/search?query=' + encodeURIComponent(name), { headers: h });
    const hits = (list.items || []).filter((k) => k.name === name);
    if (hits.length !== 1) return { refused: 'knowledge base "' + name + '" matched ' + hits.length + ', not 1' };
    collections.push({ name, id: hits[0].id });
  }

  const base = await call('/api/v1/models/model?id=' + encodeURIComponent(P.baseId), { headers: h });
  if (!base || !base.id) return { refused: 'Asisten JUP (' + P.baseId + ') not found' };
  const r = await fetch('/api/v1/models/model?id=' + encodeURIComponent(P.voiceId), { headers: h });
  const current = r.ok ? await r.json() : null;

  const meta = { ...(base.meta || {}) };
  delete meta.suggestion_prompts;
  meta.description = P.description;
  meta.knowledge = collections.map((c) => ({ type: 'collection', id: c.id, name: c.name }));
  meta.toolIds = P.toolIds;
  meta.skillIds = [];
  meta.builtinTools = Object.fromEntries(P.categories.map((c) => [c, c === 'knowledge']));
  meta.capabilities = {
    ...(meta.capabilities || {}),
    web_search: false, image_generation: false, code_interpreter: false, file_upload: false,
  };
  const form = {
    id: P.voiceId,
    name: P.name,
    base_model_id: base.base_model_id || base.id,
    meta,
    params: {
      ...(base.params || {}),
      system: [(base.params || {}).system, P.voiceInstructions].filter(Boolean).join('\\n\\n'),
    },
    is_active: true,
  };

  const fields = ['name', 'base_model_id', 'meta', 'params', 'is_active'];
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const changed = current ? fields.filter((f) => !same(current[f], form[f])) : fields;
  const action = !current ? 'create' : changed.length ? 'update' : 'unmodified';
  const out = { collections, tools: P.toolIds, builtinTools: meta.builtinTools, action, changed };
  if (P.check || action === 'unmodified') return out;

  if (action === 'create') {
    await call('/api/v1/models/create', {
      method: 'POST', headers: json, body: JSON.stringify({ ...form, access_grants: [] }),
    });
  } else {
    await call('/api/v1/models/model/update', { method: 'POST', headers: json, body: JSON.stringify(form) });
  }
  return out;
`;

console.log(`${mode}: ${VOICE_COLLECTIONS.length} knowledge bases`);
const result = await runInTab<Result>(
  {
    collections: VOICE_COLLECTIONS,
    check: mode === "dry-run",
    baseId: ASISTEN_JUP_ID,
    voiceId: VOICE_MODEL_ID,
    name: VOICE_MODEL_NAME,
    description: DESCRIPTION,
    voiceInstructions: VOICE_INSTRUCTIONS,
    toolIds: VOICE_TOOL_IDS,
    categories: BUILTIN_CATEGORIES,
  },
  PROGRAM,
);

if (result.refused) {
  console.error(`refused: ${result.refused}`);
  process.exit(1);
}
console.log("knowledge bases:");
for (const c of result.collections ?? []) console.log(`  ${c.name}  ${c.id}`);
console.log(`tools: ${(result.tools ?? []).join(", ")}`);
const on = Object.entries(result.builtinTools ?? {}).filter(([, v]) => v).map(([k]) => k);
console.log(`builtin categories on: ${on.join(", ")}`);
console.log(`${mode === "dry-run" ? "would " : ""}${result.action}${result.changed?.length ? `: ${result.changed.join(", ")}` : ""}`);
