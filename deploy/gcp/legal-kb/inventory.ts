// Walk the whole SCAN PERJANJIAN tree (Graph, item-level grant) and write every PDF to
// gs://jup-ops-legal-kb/<run>/inventory.json. Prints only counts; names stay in the bucket.
//
//   bun inventory.ts <run>
import { graph } from "./graph";

const [run] = process.argv.slice(2);
if (!run) throw new Error("usage: bun inventory.ts <run>");
const { root, children, sh } = await graph();

type Entry = { path: string[]; file: string; bytes: number; itemId: string; webUrl: string };
const pdfs: Entry[] = [];
let other = 0;
let folders = 0;
async function walk(id: string, path: string[]) {
  for (const x of await children(id)) {
    if (x.folder) {
      folders++;
      await walk(x.id, [...path, x.name]);
    } else if (x.name.toLowerCase().endsWith(".pdf")) {
      pdfs.push({ path, file: x.name, bytes: x.size, itemId: x.id, webUrl: x.webUrl });
    } else other++;
  }
  if (folders % 50 === 0) console.log(`folders=${folders} pdfs=${pdfs.length}`);
}
await walk(root.id, []);
pdfs.sort((a, b) => [...a.path, a.file].join("/").localeCompare([...b.path, b.file].join("/")));
const width = String(pdfs.length).length;
const inv = pdfs.map((p, i) => ({ n: String(i + 1).padStart(Math.max(width, 2), "0"), ...p }));
await sh(["gcloud", "storage", "cp", "-", `gs://jup-ops-legal-kb/${run}/inventory.json`], new Blob([JSON.stringify(inv, null, 1)]));
const mb = pdfs.reduce((a, p) => a + p.bytes, 0) / 1e6;
console.log(`done folders=${folders} pdfs=${pdfs.length} nonpdf=${other} total=${mb.toFixed(0)} MB`);
