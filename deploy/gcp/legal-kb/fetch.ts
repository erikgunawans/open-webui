// Stream contract PDFs from the legal OneDrive (Graph, item-level grant on SCAN PERJANJIAN) straight
// into gs://jup-ops-legal-kb/<run>/src/NN.pdf, and write <run>/manifest.json. Nothing touches local disk.
//
//   bun fetch.ts <run> <picks.json>
//
// picks.json: [["01", "<year folder>", "<partner folder>", "<file name prefix>"], ...]. An exact folder
// name wins over a prefix match; anything else ambiguous is an error, never a guess.
// Token: client-credentials for None-Jupe, secret `none-jupe-graph-secret` (Jakarta). It is read here
// and never printed.
const [run, picksPath] = process.argv.slice(2);
if (!run || !picksPath) throw new Error("usage: bun fetch.ts <run> <picks.json>");
const BUCKET = `gs://jup-ops-legal-kb/${run}`;
const TENANT = "fc521bfb-40c2-4b87-95a7-65e0e888fdf8";
const CLIENT = "095f7f79-2430-4cff-8363-560bb063b3e1";
const FOLDER_URL =
  "https://jakartautilitas-my.sharepoint.com/personal/legal_jup_jakarta-utilitas_com/Documents/Backup data/Dokumen Legal/SCAN PERJANJIAN";
const G = "https://graph.microsoft.com/v1.0";

const sh = async (cmd: string[], stdin?: any) => {
  const p = Bun.spawn(cmd, { stdin: stdin ?? "ignore", stdout: "pipe", stderr: "pipe" });
  const out = await new Response(p.stdout).text();
  if ((await p.exited) !== 0) throw new Error(`${cmd.slice(0, 4).join(" ")}: ${await new Response(p.stderr).text()}`);
  return out;
};

const secret = (await sh(["gcloud", "secrets", "versions", "access", "latest", "--secret", "none-jupe-graph-secret", "--project", "jup-ops"])).trim();
const tr = await fetch(`https://login.microsoftonline.com/${TENANT}/oauth2/v2.0/token`, {
  method: "POST",
  body: new URLSearchParams({ client_id: CLIENT, client_secret: secret, scope: "https://graph.microsoft.com/.default", grant_type: "client_credentials" }),
});
const { access_token: tok } = (await tr.json()) as any;
if (!tok) throw new Error(`token request failed: ${tr.status}`);
const H = { Authorization: `Bearer ${tok}` };

// Under an item-level grant, /users/{upn}/drive 404s; the folder is reachable only through /shares.
const share = "u!" + Buffer.from(FOLDER_URL).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const root: any = await (await fetch(`${G}/shares/${share}/driveItem?$select=id,parentReference`, { headers: H })).json();
const DRIVE = root.parentReference.driveId;

type Item = { id: string; name: string; size: number; folder?: unknown; webUrl: string };
async function children(id: string): Promise<Item[]> {
  let url = `${G}/drives/${DRIVE}/items/${id}/children?$top=200&$select=id,name,size,folder,webUrl`;
  const out: Item[] = [];
  while (url) {
    const r = await fetch(url, { headers: H });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const j: any = await r.json();
    out.push(...j.value);
    url = j["@odata.nextLink"];
  }
  return out;
}
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
  const r = await fetch(`${G}/drives/${DRIVE}/items/${f.id}/content`, { headers: H });
  if (!r.ok || !r.body) throw new Error(`content ${n}: ${r.status}`);
  await sh(["gcloud", "storage", "cp", "--content-type=application/pdf", "-", `${BUCKET}/src/${n}.pdf`], r.body);
  manifest.push({ n, folder: y.name, partner: p.name, file: f.name, bytes: f.size, itemId: f.id, webUrl: f.webUrl, gcs: `${BUCKET}/src/${n}.pdf` });
  console.log(`${n} ${(f.size / 1e6).toFixed(1)} MB  ${y.name} / ${p.name} / ${f.name}`);
}
await sh(["gcloud", "storage", "cp", "-", `${BUCKET}/manifest.json`], new Blob([JSON.stringify(manifest, null, 1)]));
