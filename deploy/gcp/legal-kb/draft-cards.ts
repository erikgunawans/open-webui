// Draft one contract card per pilot PDF from its OCR text (gs://jup-ops-legal-kb/pilot/ocr-text/NN.json).
// Cards go back to gs://jup-ops-legal-kb/pilot/cards/NN.json. Nothing persists on local disk.
// Prompt, schema and model live in lib.ts; the full run uses run.ts.
import { MODEL, draftCard, gcsCat, gcsPut } from "./lib";

const BUCKET = "gs://jup-ops-legal-kb/pilot";
const manifest: any[] = JSON.parse(new TextDecoder().decode(await gcsCat(`${BUCKET}/manifest.json`)));
const only = process.argv.slice(2);
for (const m of manifest) {
  if (only.length && !only.includes(m.n)) continue;
  const pages = JSON.parse(new TextDecoder().decode(await gcsCat(`${BUCKET}/ocr-text/${m.n}.json`)));
  const t0 = Date.now();
  const { card, tokens } = await draftCard(pages);
  const rec = {
    ...m,
    pages: pages.length,
    ocrLowConfidencePages: pages.filter((p: any) => p.conf < 0.8).map((p: any) => p.n),
    model: MODEL,
    draftedAt: new Date().toISOString(),
    card,
  };
  await gcsPut(`${BUCKET}/cards/${m.n}.json`, new Blob([JSON.stringify(rec, null, 1)]));
  console.log(`${m.n} ${Math.round((Date.now() - t0) / 1000)}s tokens=${tokens} mitra=${card.mitra?.isi?.slice(0, 60)}`);
}
