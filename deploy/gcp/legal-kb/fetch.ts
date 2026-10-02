// Stream contract PDFs from the legal OneDrive (Graph, item-level grant on SCAN PERJANJIAN) straight
// into gs://jup-ops-legal-kb/<run>/src/NN.pdf, and write <run>/manifest.json. Nothing touches local disk.
//
//   bun fetch.ts <run> <picks.json>
//
// picks.json: [["01", "<year folder>", "<partner folder>", "<file name prefix>"], ...]. An exact folder
// name wins over a prefix match; anything else ambiguous is an error, never a guess.
// Graph access and the token live in graph.ts.
import { graph } from "./graph";

const [run, picksPath] = process.argv.slice(2);
if (!run || !picksPath) throw new Error("usage: bun fetch.ts <run> <picks.json>");
const BUCKET = `gs://jup-ops-legal-kb/${run}`;
const { root, children, content, sh } = await graph();
type Item = Awaited<ReturnType<typeof children>>[number];
const pick = (xs: Item[], prefix: string, folder: boolean) => {
  const kind = xs.filter((x) => !!x.folder === folder);
  const exact = kind.filter((x) => x.name.toLowerCase() === prefix.toLowerCase());
  const m = exact.length ? exact : kind.filter((x) => x.name.toLowerCase().startsWith(prefix.toLowerCase()));
  if (m.length !== 1) throw new Error(`"${prefix}": ${m.length} matches (${m.map((x) => x.name).join(" | ")})`);
  return m[0];
};

const picks: [string, string, string, string][] = JSON.parse(await Bun.file(picksPath).text());
const top = await children(root.id);
const manifest: any[] = [];
for (const [n, year, partner, file] of picks) {
  const y = pick(top, year, true);
  const p = pick(await children(y.id), partner, true);
  const f = pick((await children(p.id)).filter((x) => x.name.toLowerCase().endsWith(".pdf")), file, false);
  const r = await content(f.id);
  if (!r.body) throw new Error(`content ${n}: empty body`);
  await sh(["gcloud", "storage", "cp", "--content-type=application/pdf", "-", `${BUCKET}/src/${n}.pdf`], r.body);
  manifest.push({ n, folder: y.name, partner: p.name, file: f.name, bytes: f.size, itemId: f.id, webUrl: f.webUrl, gcs: `${BUCKET}/src/${n}.pdf` });
  console.log(`${n} ${(f.size / 1e6).toFixed(1)} MB  ${y.name} / ${p.name} / ${f.name}`);
}
await sh(["gcloud", "storage", "cp", "-", `${BUCKET}/manifest.json`], new Blob([JSON.stringify(manifest, null, 1)]));
