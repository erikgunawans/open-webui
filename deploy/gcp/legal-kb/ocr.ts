// Synchronous OCR of the pilot PDFs in 15-page chunks (the batch queue stalled 10-01).
// Source and output live in gs://jup-ops-legal-kb (Jakarta); OCR runs in asia-southeast1.
// PDFs are held in memory only; nothing is written to local disk. The full run uses run.ts.
import { gcsCat, gcsPut, ocrPdf } from "./lib";

const BUCKET = "gs://jup-ops-legal-kb/pilot";
const only = process.argv.slice(2);
const ns = only.length ? only : ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"];
for (const n of ns) {
  const t0 = Date.now();
  const pages = await ocrPdf(await gcsCat(`${BUCKET}/src/${n}.pdf`));
  await gcsPut(`${BUCKET}/ocr-text/${n}.json`, new Blob([JSON.stringify(pages)]));
  const low = pages.filter((p) => p.conf < 0.8).length;
  const chars = pages.reduce((a, p) => a + p.text.length, 0);
  console.log(`${n} ocr=${pages.length} lowconf=${low} chars=${chars} ${Math.round((Date.now() - t0) / 1000)}s`);
}
