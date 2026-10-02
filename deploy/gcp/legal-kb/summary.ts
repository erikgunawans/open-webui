// Totals for a run, from its cards: written to <run>/summary.json, counts printed. Names stay in the bucket.
//
//   bun summary.ts <run>
import { auth, gcsCat, gcsPut, shText } from "./lib";

const [run] = process.argv.slice(2);
if (!run) throw new Error("usage: bun summary.ts <run>");
const BUCKET = `gs://jup-ops-legal-kb/${run}`;
const dec = new TextDecoder();
const inventory: any[] = JSON.parse(dec.decode(await gcsCat(`${BUCKET}/inventory.json`)));
const uris = (await shText(["gcloud", "storage", "ls", `${BUCKET}/cards/`])).split("\n").filter(Boolean);
const cards: any[] = [];
const queue = [...uris];
await Promise.all(Array.from({ length: 16 }, async () => {
  // The JSON API, not one gcloud process per card: 16 parallel gcloud processes drove the load to 26.
  for (let u = queue.shift(); u; u = queue.shift()) {
    const [bucket, ...path] = u.replace("gs://", "").split("/");
    const r = await fetch(`https://storage.googleapis.com/storage/v1/b/${bucket}/o/${encodeURIComponent(path.join("/"))}?alt=media`, {
      headers: { Authorization: `Bearer ${await auth()}` },
    });
    if (!r.ok) throw new Error(`${u}: ${r.status}`);
    cards.push(await r.json());
  }
}));
const have = new Set(cards.map((c) => c.n));
const errors = (await shText(["gcloud", "storage", "ls", `${BUCKET}/errors/`]).catch(() => ""))
  .split("\n").filter(Boolean).map((u) => u.split("/").pop()!.replace(".json", "")).filter((n) => !have.has(n));
const summary = {
  run,
  at: new Date().toISOString(),
  inventory: inventory.length,
  cards: cards.length,
  drafted: cards.filter((c) => c.card).length,
  skippedNoText: cards.filter((c) => c.skipped).map((c) => c.n),
  missing: inventory.filter((e) => !have.has(e.n)).map((e) => e.n),
  openErrors: errors,
  pages: cards.reduce((a, c) => a + c.pages, 0),
  withLowConfidencePages: cards.filter((c) => c.ocrLowConfidencePages?.length).length,
  withManualCheckPages: cards.filter((c) => c.card?.halaman_perlu_diperiksa_manual?.length).length,
  withPeroranganParties: cards.filter((c) => c.card?.perorangan_non_penandatangan?.length).map((c) => c.n),
};
await gcsPut(`${BUCKET}/summary.json`, new Blob([JSON.stringify(summary, null, 1)]));
console.log(JSON.stringify({ ...summary, skippedNoText: summary.skippedNoText.length, withPeroranganParties: summary.withPeroranganParties.length }));
