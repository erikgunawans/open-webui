// Graph access to SCAN PERJANJIAN (item-level grant). Token: client-credentials for None-Jupe, secret
// `none-jupe-graph-secret` (Jakarta); read here, refreshed every 45 min, never printed.
const TENANT = "fc521bfb-40c2-4b87-95a7-65e0e888fdf8";
const CLIENT = "095f7f79-2430-4cff-8363-560bb063b3e1";
const FOLDER_URL =
  "https://jakartautilitas-my.sharepoint.com/personal/legal_jup_jakarta-utilitas_com/Documents/Backup data/Dokumen Legal/SCAN PERJANJIAN";
export const G = "https://graph.microsoft.com/v1.0";

export const sh = async (cmd: string[], stdin?: any) => {
  const p = Bun.spawn(cmd, { stdin: stdin ?? "ignore", stdout: "pipe", stderr: "pipe" });
  const out = await new Response(p.stdout).text();
  if ((await p.exited) !== 0) throw new Error(`${cmd.slice(0, 4).join(" ")}: ${await new Response(p.stderr).text()}`);
  return out;
};

export type Item = { id: string; name: string; size: number; folder?: unknown; webUrl: string };

export async function graph() {
  const secret = (await sh(["gcloud", "secrets", "versions", "access", "latest", "--secret", "none-jupe-graph-secret", "--project", "jup-ops"])).trim();
  let tok = "";
  let tokAt = 0;
  const headers = async () => {
    if (Date.now() - tokAt > 45 * 60_000) {
      const tr = await fetch(`https://login.microsoftonline.com/${TENANT}/oauth2/v2.0/token`, {
        method: "POST",
        body: new URLSearchParams({ client_id: CLIENT, client_secret: secret, scope: "https://graph.microsoft.com/.default", grant_type: "client_credentials" }),
      });
      const j = (await tr.json()) as any;
      if (!j.access_token) throw new Error(`token request failed: ${tr.status}`);
      tok = j.access_token;
      tokAt = Date.now();
    }
    return { Authorization: `Bearer ${tok}` };
  };
  // Graph throttles with 429/503 + Retry-After; retry those, fail on anything else.
  const get = async (url: string) => {
    for (let attempt = 1; ; attempt++) {
      const r = await fetch(url, { headers: await headers() });
      if (r.ok) return r;
      if (attempt >= 5 || ![429, 500, 502, 503, 504].includes(r.status)) throw new Error(`${r.status} ${await r.text()}`);
      await Bun.sleep(1000 * Number(r.headers.get("retry-after") ?? 5 * attempt));
    }
  };

  // Under an item-level grant, /users/{upn}/drive 404s; the folder is reachable only through /shares.
  const share = "u!" + Buffer.from(FOLDER_URL).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const root: any = await (await get(`${G}/shares/${share}/driveItem?$select=id,parentReference`)).json();
  const DRIVE = root.parentReference.driveId;

  async function children(id: string): Promise<Item[]> {
    let url = `${G}/drives/${DRIVE}/items/${id}/children?$top=200&$select=id,name,size,folder,webUrl`;
    const out: Item[] = [];
    while (url) {
      const j: any = await (await get(url)).json();
      out.push(...j.value);
      url = j["@odata.nextLink"];
    }
    return out;
  }
  const content = (itemId: string) => get(`${G}/drives/${DRIVE}/items/${itemId}/content`);
  return { root, children, content, sh };
}
