// Full run: every PDF in <run>/inventory.json (from inventory.ts) goes fetch → OCR → card, with a
// small worker pool. Resumable: a stage whose output already exists in the bucket is skipped, so a
// crash or a Mac restart costs only the documents in flight. Failures are written to
// <run>/errors/NN.json and retried on the next invocation. Logs carry numbers only, never names.
//
//   bun run.ts <run> [--concurrency 6] [--limit N] [NN ...]
import { graph } from "./graph";
import { MODEL, draftCard, gcsCat, gcsPut, ocrPdf, shText, type Page } from "./lib";

const args = process.argv.slice(2);
const opt = (name: string, def: number) => {
  const i = args.indexOf(name);
  if (i < 0) return def;
  const v = Number(args[i + 1]);
  args.splice(i, 2);
  return v;
};
const CONCURRENCY = opt("--concurrency", 6);
const LIMIT = opt("--limit", Infinity);
const [run, ...only] = args;
if (!run) throw new Error("usage: bun run.ts <run> [--concurrency N] [--limit N] [NN ...]");
const BUCKET = `gs://jup-ops-legal-kb/${run}`;
const MIN_CHARS = 200; // below this the scan has no usable text; the card says so instead of guessing

const dec = new TextDecoder();
const inventory: any[] = JSON.parse(dec.decode(await gcsCat(`${BUCKET}/inventory.json`)));
const existing = async (dir: string) => {
  const out = await shText(["gcloud", "storage", "ls", `${BUCKET}/${dir}/`]).catch(() => "");
  return new Set(out.split("\n").filter(Boolean).map((u) => u.split("/").pop()!.replace(/\.(pdf|json)$/, "")));
};
const [haveSrc, haveOcr, haveCard] = await Promise.all([existing("src"), existing("ocr-text"), existing("cards")]);
const todo = inventory.filter((e) => !haveCard.has(e.n) && (!only.length || only.includes(e.n))).slice(0, LIMIT);
console.log(`${new Date().toISOString()} inventory=${inventory.length} cards=${haveCard.size} todo=${todo.length} concurrency=${CONCURRENCY}`);

const g = await graph();
let done = 0;
let failed = 0;
const t0 = Date.now();

async function one(e: any) {
  const t = Date.now();
  let stage = "fetch";
  try {
    let pages: Page[];
    if (haveOcr.has(e.n)) {
      stage = "read-ocr";
      pages = JSON.parse(dec.decode(await gcsCat(`${BUCKET}/ocr-text/${e.n}.json`)));
    } else {
      let bytes: Uint8Array;
      if (haveSrc.has(e.n)) bytes = await gcsCat(`${BUCKET}/src/${e.n}.pdf`);
      else {
        bytes = new Uint8Array(await (await g.content(e.itemId)).arrayBuffer());
        await gcsPut(`${BUCKET}/src/${e.n}.pdf`, new Blob([bytes]), "application/pdf");
      }
      stage = "ocr";
      pages = await ocrPdf(bytes);
      await gcsPut(`${BUCKET}/ocr-text/${e.n}.json`, new Blob([JSON.stringify(pages)]));
    }
    stage = "draft";
    const chars = pages.reduce((a, p) => a + p.text.length, 0);
    const drafted = chars < MIN_CHARS ? null : await draftCard(pages);
    const rec = {
      n: e.n,
      path: e.path,
      file: e.file,
      bytes: e.bytes,
      itemId: e.itemId,
      webUrl: e.webUrl,
      gcs: `${BUCKET}/src/${e.n}.pdf`,
      pages: pages.length,
      ocrChars: chars,
      ocrLowConfidencePages: pages.filter((p) => p.conf < 0.8).map((p) => p.n),
      model: drafted ? MODEL : null,
      skipped: drafted ? undefined : "no-ocr-text",
      draftedAt: new Date().toISOString(),
      card: drafted?.card ?? null,
    };
    await gcsPut(`${BUCKET}/cards/${e.n}.json`, new Blob([JSON.stringify(rec, null, 1)]));
    done++;
    console.log(`ok ${e.n} pages=${pages.length} chars=${chars}${drafted ? ` tokens=${drafted.tokens}` : " skipped=no-text"} ${Math.round((Date.now() - t) / 1000)}s [${done + failed}/${todo.length}]`);
  } catch (err) {
    failed++;
    const message = String((err as Error)?.message ?? err).slice(0, 500);
    await gcsPut(`${BUCKET}/errors/${e.n}.json`, new Blob([JSON.stringify({ n: e.n, stage, message, at: new Date().toISOString() })])).catch(() => {});
    console.log(`FAIL ${e.n} stage=${stage} ${message.slice(0, 160)} [${done + failed}/${todo.length}]`);
  }
}

const queue = [...todo];
await Promise.all(Array.from({ length: CONCURRENCY }, async () => {
  for (let e = queue.shift(); e; e = queue.shift()) await one(e);
}));
console.log(`${new Date().toISOString()} finished ok=${done} failed=${failed} in ${Math.round((Date.now() - t0) / 60_000)} min`);
