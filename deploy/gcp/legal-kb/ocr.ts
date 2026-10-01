// Synchronous OCR of the pilot PDFs in 15-page chunks (the batch queue stalled 10-01).
// Source and output live in gs://jup-ops-legal-kb (Jakarta); OCR runs in asia-southeast1.
// PDFs are held in memory only; nothing is written to local disk.
import { PDFDocument } from "pdf-lib";

const BUCKET = "gs://jup-ops-legal-kb/pilot";
const PROC =
  "https://asia-southeast1-documentai.googleapis.com/v1/projects/1001937491646/locations/asia-southeast1/processors/c764ec7c50cd9021/processorVersions/pretrained-ocr-v2.1.1-2025-01-31:process";
const CHUNK = 15;

const run = async (cmd: string[], stdin?: Blob) => {
  const p = Bun.spawn(cmd, { stdin: stdin ?? "ignore", stdout: "pipe", stderr: "pipe" });
  const out = new Uint8Array(await new Response(p.stdout).arrayBuffer());
  if ((await p.exited) !== 0) throw new Error(`${cmd.slice(0, 4).join(" ")}: ${await new Response(p.stderr).text()}`);
  return out;
};
let token = "";
let tokenAt = 0;
const auth = async () => {
  if (Date.now() - tokenAt > 30 * 60_000) {
    token = new TextDecoder().decode(await run(["gcloud", "auth", "print-access-token"])).trim();
    tokenAt = Date.now();
  }
  return token;
};

async function ocr(pdf: Uint8Array) {
  for (let attempt = 1; ; attempt++) {
    const r = await fetch(PROC, {
      method: "POST",
      headers: { Authorization: `Bearer ${await auth()}`, "x-goog-user-project": "jup-ops", "Content-Type": "application/json" },
      body: JSON.stringify({
        rawDocument: { content: Buffer.from(pdf).toString("base64"), mimeType: "application/pdf" },
        processOptions: { ocrConfig: { hints: { languageHints: ["id", "en"] } } },
      }),
    });
    const j: any = await r.json();
    if (r.ok) return j.document;
    if (attempt >= 3 || ![429, 500, 503, 504].includes(r.status)) throw new Error(`${r.status} ${JSON.stringify(j.error)}`);
    await Bun.sleep(5000 * attempt);
  }
}

const only = process.argv.slice(2);
const ns = only.length ? only : ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"];
for (const n of ns) {
  const t0 = Date.now();
  const src = await PDFDocument.load(await run(["gcloud", "storage", "cat", `${BUCKET}/src/${n}.pdf`]), { ignoreEncryption: true });
  const total = src.getPageCount();
  const pages: { n: number; text: string; conf: number }[] = [];
  for (let start = 0; start < total; start += CHUNK) {
    const part = await PDFDocument.create();
    const idx = Array.from({ length: Math.min(CHUNK, total - start) }, (_, i) => start + i);
    for (const p of await part.copyPages(src, idx)) part.addPage(p);
    const doc = await ocr(await part.save());
    const text: string = doc.text ?? "";
    for (const pg of doc.pages ?? []) {
      const segs = pg.layout?.textAnchor?.textSegments ?? [];
      pages.push({
        n: start + pg.pageNumber,
        text: segs.map((g: any) => text.slice(Number(g.startIndex ?? 0), Number(g.endIndex))).join(""),
        conf: pg.layout?.confidence ?? 0,
      });
    }
  }
  await run(["gcloud", "storage", "cp", "-", `${BUCKET}/ocr-text/${n}.json`], new Blob([JSON.stringify(pages)]));
  const low = pages.filter((p) => p.conf < 0.8).length;
  const chars = pages.reduce((a, p) => a + p.text.length, 0);
  console.log(`${n} pages=${total} ocr=${pages.length} lowconf=${low} chars=${chars} ${Math.round((Date.now() - t0) / 1000)}s`);
}
