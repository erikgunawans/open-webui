// Draft one contract card per pilot PDF from its OCR text (gs://jup-ops-legal-kb/pilot/ocr-text/NN.json),
// with gemini-2.5-flash in asia-southeast1 (Erik 2026-09-29: in-region drafting). Cards go back to
// gs://jup-ops-legal-kb/pilot/cards/NN.json. Nothing persists on local disk.
const BUCKET = "gs://jup-ops-legal-kb/pilot";
const MODEL =
  "https://asia-southeast1-aiplatform.googleapis.com/v1/projects/jup-ops/locations/asia-southeast1/publishers/google/models/gemini-2.5-flash:generateContent";

const run = async (cmd: string[], stdin?: Blob) => {
  const p = Bun.spawn(cmd, { stdin: stdin ?? "ignore", stdout: "pipe", stderr: "pipe" });
  const out = await new Response(p.stdout).text();
  if ((await p.exited) !== 0) throw new Error(`${cmd.slice(0, 4).join(" ")}: ${await new Response(p.stderr).text()}`);
  return out;
};
const token = (await run(["gcloud", "auth", "print-access-token"])).trim();
const manifest: any[] = JSON.parse(await run(["gcloud", "storage", "cat", `${BUCKET}/manifest.json`]));

const field = {
  type: "OBJECT",
  properties: { isi: { type: "STRING" }, halaman: { type: "ARRAY", items: { type: "INTEGER" } } },
  required: ["isi", "halaman"],
};
const FIELDS = [
  "mitra", "nomor_pks", "judul", "tanggal_tanda_tangan", "jenis_dokumen", "hak_kewajiban_lingkup",
  "nilai_dan_pembayaran", "jangka_waktu_perpanjangan", "pengakhiran", "wanprestasi_ganti_rugi",
  "kerahasiaan_hki", "keadaan_kahar", "penyelesaian_sengketa", "keabsahan", "hubungan_dokumen",
];
const SCHEMA = {
  type: "OBJECT",
  properties: {
    ...Object.fromEntries(FIELDS.map((f) => [f, field])),
    halaman_perlu_diperiksa_manual: { type: "ARRAY", items: { type: "INTEGER" } },
    perorangan_non_penandatangan: { type: "ARRAY", items: { type: "STRING" } },
  },
  required: [...FIELDS, "halaman_perlu_diperiksa_manual", "perorangan_non_penandatangan"],
};

const PROMPT = `Anda menyusun DRAF kartu kontrak untuk ditinjau Tim Legal PT Jakarta Utilitas Propertindo (JUP).
Sumber: teks OCR dari pindaian PDF, ditandai per halaman dengan "=== HALAMAN n ===".
Aturan:
- Isi setiap isian HANYA dari teks sumber. Jangan menebak, jangan melengkapi dari pengetahuan umum.
- Setiap isian wajib mencantumkan nomor halaman sumbernya di "halaman".
- Bila kontrak tidak mengatur suatu hal, isi "tidak tercantum" dan "halaman" kosong.
- Bila teks pada bagian terkait rusak atau tidak terbaca, isi "perlu diperiksa manual", cantumkan halamannya, dan masukkan juga ke "halaman_perlu_diperiksa_manual".
- Ringkas dan faktual, Bahasa Indonesia. Kutip angka, tanggal, dan nomor pasal persis seperti di teks.
- "jenis_dokumen": misalnya PKS, adendum, perjanjian jual beli gas, perjanjian pinjaman, novasi, KSO.
- "keabsahan": penandatangan dan jabatannya, dasar kewenangan, e-Meterai/meterai, legalisasi notaris.
- "hubungan_dokumen": perjanjian induk/adendum yang dirujuk dan ketentuan mana yang diubah atau digantikan.
- "perorangan_non_penandatangan": nama orang yang menjadi PIHAK atas nama pribadi (bukan yang menandatangani atas nama perusahaan/instansi). Kosongkan bila tidak ada.`;

const only = process.argv.slice(2);
for (const m of manifest) {
  if (only.length && !only.includes(m.n)) continue;
  const pages: { n: number; text: string; conf: number }[] = JSON.parse(
    await run(["gcloud", "storage", "cat", `${BUCKET}/ocr-text/${m.n}.json`]),
  );
  const body = pages.map((p) => `=== HALAMAN ${p.n} ===\n${p.text}`).join("\n\n");
  const t0 = Date.now();
  const r = await fetch(MODEL, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "x-goog-user-project": "jup-ops" },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: PROMPT }] },
      contents: [{ role: "user", parts: [{ text: body }] }],
      generationConfig: { temperature: 0, responseMimeType: "application/json", responseSchema: SCHEMA },
    }),
  });
  const j: any = await r.json();
  if (!r.ok) throw new Error(`${m.n}: ${JSON.stringify(j.error ?? j)}`);
  const card = JSON.parse(j.candidates[0].content.parts[0].text);
  const rec = {
    ...m,
    pages: pages.length,
    ocrLowConfidencePages: pages.filter((p) => p.conf < 0.8).map((p) => p.n),
    model: "gemini-2.5-flash (asia-southeast1)",
    draftedAt: new Date().toISOString(),
    card,
  };
  await run(["gcloud", "storage", "cp", "-", `${BUCKET}/cards/${m.n}.json`], new Blob([JSON.stringify(rec, null, 1)]));
  console.log(`${m.n} ${Math.round((Date.now() - t0) / 1000)}s tokens=${j.usageMetadata?.promptTokenCount} mitra=${card.mitra?.isi?.slice(0, 60)}`);
}
