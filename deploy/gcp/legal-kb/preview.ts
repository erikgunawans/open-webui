// Build the side-by-side review page (card | OCR pages) and store it in the Jakarta bucket only.
const BUCKET = "gs://jup-ops-legal-kb/pilot";
const run = async (cmd: string[], stdin?: Blob) => {
  const p = Bun.spawn(cmd, { stdin: stdin ?? "ignore", stdout: "pipe", stderr: "pipe" });
  const out = await new Response(p.stdout).text();
  if ((await p.exited) !== 0) throw new Error(await new Response(p.stderr).text());
  return out;
};
const esc = (s: string) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

const LABELS: Record<string, string> = {
  mitra: "Mitra", nomor_pks: "Nomor", judul: "Judul", tanggal_tanda_tangan: "Tanggal tanda tangan",
  jenis_dokumen: "Jenis dokumen", hak_kewajiban_lingkup: "1. Hak, kewajiban, ruang lingkup",
  nilai_dan_pembayaran: "2. Nilai dan pembayaran 💰", jangka_waktu_perpanjangan: "3. Jangka waktu dan perpanjangan",
  pengakhiran: "4. Pengakhiran", wanprestasi_ganti_rugi: "5. Wanprestasi dan ganti rugi 💰",
  kerahasiaan_hki: "6. Kerahasiaan dan HKI", keadaan_kahar: "7. Keadaan kahar",
  penyelesaian_sengketa: "8. Penyelesaian sengketa", keabsahan: "9. Keabsahan", hubungan_dokumen: "Hubungan dokumen",
};

const ids = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"];
const sections: string[] = [];
const nav: string[] = [];
for (const n of ids) {
  const rec = JSON.parse(await run(["gcloud", "storage", "cat", `${BUCKET}/cards/${n}.json`]));
  const pages: { n: number; text: string; conf: number }[] = JSON.parse(await run(["gcloud", "storage", "cat", `${BUCKET}/ocr-text/${n}.json`]));
  const c = rec.card;
  nav.push(`<a href="#k${n}">${n} · ${esc(rec.folder)} · ${esc(rec.partner)}</a>`);
  const rows = Object.entries(LABELS).map(([k, label]) => {
    const f = c[k] ?? { isi: "", halaman: [] };
    const miss = /tidak tercantum/i.test(f.isi);
    const manual = /perlu diperiksa manual/i.test(f.isi);
    const pg = (f.halaman ?? []).map((p: number) => `<a class="pg" href="#k${n}p${p}" onclick="show('${n}',${p})">h.${p}</a>`).join(" ");
    return `<tr class="${miss ? "miss" : manual ? "manual" : ""}"><th>${esc(label)}</th><td>${esc(f.isi)}<div class="pgs">${pg}</div></td></tr>`;
  });
  const flags = [
    c.halaman_perlu_diperiksa_manual?.length ? `Periksa manual: h.${c.halaman_perlu_diperiksa_manual.join(", ")}` : "",
    c.perorangan_non_penandatangan?.length ? `⚠ Perorangan (perlu disamarkan): ${esc(c.perorangan_non_penandatangan.join(", "))}` : "",
  ].filter(Boolean);
  const ocr = pages
    .map((p) => `<div class="page" id="k${n}p${p.n}"><div class="ph">Halaman ${p.n} · OCR ${(p.conf * 100).toFixed(0)}%</div><pre>${esc(p.text)}</pre></div>`)
    .join("");
  sections.push(`<section id="k${n}"><h2>${n}. ${esc(c.judul?.isi?.slice(0, 140))}</h2>
<p class="meta">${esc(rec.folder)} / ${esc(rec.partner)} / <a href="${esc(rec.webUrl)}" target="_blank">${esc(rec.file)}</a> · ${rec.pages} halaman · draf ${esc(rec.model)}</p>
${flags.map((f) => `<p class="flag">${f}</p>`).join("")}
<div class="grid"><table>${rows.join("")}</table><div class="ocr" id="o${n}">${ocr}</div></div></section>`);
}

const html = `<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pratinjau kartu kontrak — pilot 10</title><style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--miss:#f4f4f4;--man:#fff4d6;--acc:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#eee;--mut:#aaa;--line:#333;--miss:#1e1e1e;--man:#3a3010;--acc:#6ab0ff}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
h1{font-size:20px}h2{font-size:16px;margin:32px 0 4px}nav a{display:block;color:var(--acc)}a{color:var(--acc)}
.meta{color:var(--mut);margin:0 0 8px}.flag{background:var(--man);padding:4px 8px;border-radius:4px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%}th,td{border-top:1px solid var(--line);padding:6px;vertical-align:top;text-align:left}
th{width:32%;font-weight:600}tr.miss td{color:var(--mut);background:var(--miss)}tr.manual td{background:var(--man)}
.pgs{margin-top:2px}.pg{font-size:12px;margin-right:6px}
.ocr{max-height:80vh;overflow:auto;border:1px solid var(--line);border-radius:6px;padding:8px}
.page{border-bottom:1px dashed var(--line);padding-bottom:8px}.page.hit{outline:2px solid var(--acc)}
.ph{font-weight:600;color:var(--mut)}pre{white-space:pre-wrap;font:12px/1.45 ui-monospace,monospace;margin:4px 0}
</style></head><body>
<h1>Pratinjau kartu kontrak — pilot 10 (DRAF, belum ditinjau Tim Legal)</h1>
<p>Kiri: draf kartu per topik FAQ Kontrak, dengan halaman sumber. Kanan: teks OCR per halaman. Klik "h.N" untuk melompat ke halamannya. Baris abu-abu = "tidak tercantum"; kuning = perlu diperiksa manual. 💰 = isian nilai uang (hanya Manajer ke atas).</p>
<nav>${nav.join("")}</nav>${sections.join("")}
<script>function show(n,p){document.querySelectorAll('#o'+n+' .page').forEach(e=>e.classList.remove('hit'));const e=document.getElementById('k'+n+'p'+p);if(e){e.classList.add('hit');e.scrollIntoView({block:'start'});}event.preventDefault();}</script>
</body></html>`;
await run(["gcloud", "storage", "cp", "--content-type=text/html; charset=utf-8", "-", `${BUCKET}/preview/kartu-kontrak-pilot.html`], new Blob([html]));
console.log("bytes", html.length);
