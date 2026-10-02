// Dates pass: every drafted card in <run>/cards/ → <run>/dates/<n>.json with tanggal_mulai,
// tanggal_berakhir (YYYY-MM-DD or ""), perpanjangan_otomatis, dasar, keyakinan. The app's contract
// import reads them. Resumable (existing outputs are skipped); logs carry numbers only.
//
//   bun dates.ts <run> [--concurrency 8] [--limit N] [NN ...]
import { MODEL, auth, extractDates, gcsPut, shText } from "./lib";

const args = process.argv.slice(2);
const opt = (name: string, def: number) => {
  const i = args.indexOf(name);
  if (i < 0) return def;
  const v = Number(args[i + 1]);
  args.splice(i, 2);
  return v;
};
const CONCURRENCY = opt("--concurrency", 8);
const LIMIT = opt("--limit", Infinity);
const [run, ...only] = args;
if (!run) throw new Error("usage: bun dates.ts <run> [--concurrency N] [--limit N] [NN ...]");
const BUCKET = `gs://jup-ops-legal-kb/${run}`;

const names = async (dir: string) =>
  (await shText(["gcloud", "storage", "ls", `${BUCKET}/${dir}/`]).catch(() => ""))
    .split("\n").filter(Boolean).map((u) => u.split("/").pop()!.replace(/\.json$/, ""));
const [cardNs, doneNs] = await Promise.all([names("cards"), names("dates")]);
const done = new Set(doneNs);
const todo = cardNs.filter((n) => !done.has(n) && (!only.length || only.includes(n))).slice(0, LIMIT);
console.log(`${new Date().toISOString()} cards=${cardNs.length} dated=${done.size} todo=${todo.length}`);

const read = async (path: string) => {
  const r = await fetch(`https://storage.googleapis.com/storage/v1/b/jup-ops-legal-kb/o/${encodeURIComponent(`${run}/${path}`)}?alt=media`, {
    headers: { Authorization: `Bearer ${await auth()}` },
  });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
};

const ISO = /^\d{4}-\d{2}-\d{2}$/;
let ok = 0, failed = 0, withEnd = 0;
const queue = [...todo];
await Promise.all(Array.from({ length: CONCURRENCY }, async () => {
  for (let n = queue.shift(); n; n = queue.shift()) {
    try {
      const rec = await read(`cards/${n}.json`);
      if (!rec.card) continue; // a scan without text has no card, so no dates
      const d = await extractDates(rec.card);
      const clean = (v: string) => (ISO.test(v ?? "") && !Number.isNaN(Date.parse(v)) ? v : "");
      const out = {
        n,
        tanggal_mulai: clean(d.tanggal_mulai),
        tanggal_berakhir: clean(d.tanggal_berakhir),
        perpanjangan_otomatis: d.perpanjangan_otomatis,
        dasar: d.dasar,
        keyakinan: d.keyakinan,
        model: MODEL,
        at: new Date().toISOString(),
      };
      await gcsPut(`${BUCKET}/dates/${n}.json`, new Blob([JSON.stringify(out)]));
      ok++;
      if (out.tanggal_berakhir) withEnd++;
    } catch (err) {
      failed++;
      console.log(`FAIL ${n} ${String((err as Error)?.message ?? err).slice(0, 120)}`);
    }
  }
}));
console.log(`${new Date().toISOString()} finished ok=${ok} withEnd=${withEnd} failed=${failed}`);
