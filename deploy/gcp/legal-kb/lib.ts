// Shared OCR + card drafting for the pilot scripts and the full run. OCR runs in asia-southeast1
// (Document AI has no Jakarta endpoint); drafting with gemini-2.5-flash in asia-southeast1 (Erik
// 2026-09-29: in-region drafting). Callers keep PDFs and text in memory and store results only in
// gs://jup-ops-legal-kb (Jakarta).
import { PDFDocument } from "pdf-lib";

// Ask only for what ocrPdf reads; by default the response carries page images and layout tokens
// (tens of MB per 15-page chunk), which timed out under load on 2026-10-02.
const OCR_FIELDS = "text,pages.pageNumber,pages.layout"; // only top-level page fields are allowed
const OCR_URL =
  "https://asia-southeast1-documentai.googleapis.com/v1/projects/1001937491646/locations/asia-southeast1/processors/c764ec7c50cd9021/processorVersions/pretrained-ocr-v2.1.1-2025-01-31:process";
const MODEL_URL =
  "https://asia-southeast1-aiplatform.googleapis.com/v1/projects/jup-ops/locations/asia-southeast1/publishers/google/models/gemini-2.5-flash:generateContent";
export const MODEL = "gemini-2.5-flash (asia-southeast1)";
const CHUNK = 15; // synchronous Document AI OCR takes at most 15 pages per request

export const sh = async (cmd: string[], stdin?: any): Promise<Uint8Array> => {
  const p = Bun.spawn(cmd, { stdin: stdin ?? "ignore", stdout: "pipe", stderr: "pipe" });
  const out = new Uint8Array(await new Response(p.stdout).arrayBuffer());
  if ((await p.exited) !== 0) throw new Error(`${cmd.slice(0, 4).join(" ")}: ${await new Response(p.stderr).text()}`);
  return out;
};
export const shText = async (cmd: string[], stdin?: any) => new TextDecoder().decode(await sh(cmd, stdin));
export const gcsCat = (uri: string) => sh(["gcloud", "storage", "cat", uri]);
export const gcsPut = (uri: string, body: Blob | ReadableStream, contentType = "application/json") =>
  sh(["gcloud", "storage", "cp", `--content-type=${contentType}`, "-", uri], body);

let token = "";
let tokenAt = 0;
let pending: Promise<string> | null = null;
export const auth = async () => {
  if (Date.now() - tokenAt > 30 * 60_000) {
    pending ??= shText(["gcloud", "auth", "print-access-token", "--quiet"]).then((t) => {
      token = t.trim();
      tokenAt = Date.now();
      pending = null;
      return token;
    });
    return pending;
  }
  return token;
};

// POST with retries on throttling and transient errors; anything else fails the document.
async function post(url: string, body: unknown): Promise<any> {
  for (let attempt = 1; ; attempt++) {
    let r: Response;
    let j: any;
    try {
      r = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${await auth()}`, "x-goog-user-project": "jup-ops", "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(600_000),
      });
      j = await r.json();
    } catch (err) {
      // dropped socket, timeout or a truncated body: transient, retry with backoff
      if (attempt >= 6) throw err;
      await Bun.sleep(5000 * attempt);
      continue;
    }
    if (r.ok) return j;
    // gcloud hands back its cached token, which can expire mid-run: force a fresh one and retry.
    if (r.status === 401 && attempt < 3) {
      tokenAt = 0;
      continue;
    }
    if (attempt >= 6 || ![429, 500, 502, 503, 504].includes(r.status)) throw new Error(`${r.status} ${JSON.stringify(j.error ?? j).slice(0, 300)}`);
    await Bun.sleep(5000 * attempt);
  }
}

export type Page = { n: number; text: string; conf: number };

export async function ocrPdf(bytes: Uint8Array): Promise<Page[]> {
  const src = await PDFDocument.load(bytes, { ignoreEncryption: true });
  const total = src.getPageCount();
  const pages: Page[] = [];
  for (let start = 0; start < total; start += CHUNK) {
    const part = await PDFDocument.create();
    const idx = Array.from({ length: Math.min(CHUNK, total - start) }, (_, i) => start + i);
    for (const p of await part.copyPages(src, idx)) part.addPage(p);
    const { document: doc } = await post(OCR_URL, {
      fieldMask: OCR_FIELDS,
      rawDocument: { content: Buffer.from(await part.save()).toString("base64"), mimeType: "application/pdf" },
      processOptions: { ocrConfig: { hints: { languageHints: ["id", "en"] } } },
    });
    if (!doc) throw new Error(`OCR returned no document for pages ${start + 1}-${start + idx.length}`);
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
  return pages;
}

const field = {
  type: "OBJECT",
  properties: { isi: { type: "STRING" }, halaman: { type: "ARRAY", items: { type: "INTEGER" } } },
  required: ["isi", "halaman"],
};
export const FIELDS = [
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
- "perorangan_non_penandatangan": HANYA orang perseorangan yang menjadi PIHAK dalam perjanjian atas nama dirinya sendiri (misalnya penjual tanah pribadi, peminjam perorangan). BUKAN: notaris, saksi, pejabat/direksi/kuasa yang bertindak untuk perusahaan atau instansi, penghadap yang mewakili badan hukum, atau orang yang hanya disebut dalam akta. Bila ragu, jangan dimasukkan. Kosongkan bila tidak ada.`;

export async function draftCard(pages: Page[]) {
  const body = pages.map((p) => `=== HALAMAN ${p.n} ===\n${p.text}`).join("\n\n");
  const j = await post(MODEL_URL, {
    systemInstruction: { parts: [{ text: PROMPT }] },
    contents: [{ role: "user", parts: [{ text: body }] }],
    generationConfig: { temperature: 0, responseMimeType: "application/json", responseSchema: SCHEMA },
  });
  const part = j.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!part) throw new Error(`no card: finishReason=${j.candidates?.[0]?.finishReason} block=${j.promptFeedback?.blockReason}`);
  return { card: JSON.parse(part), tokens: j.usageMetadata?.promptTokenCount as number };
}

// Dates pass (contract KB phase 1): structured start / end / auto-renewal from a drafted card's own
// fields, so "which contracts end within 6 months" is a query. Same model and region as drafting.
const DATES_SCHEMA = {
  type: "OBJECT",
  properties: {
    tanggal_mulai: { type: "STRING" },
    tanggal_berakhir: { type: "STRING" },
    perpanjangan_otomatis: { type: "STRING", enum: ["ya", "tidak", "tidak jelas"] },
    dasar: { type: "STRING" },
    keyakinan: { type: "STRING", enum: ["tinggi", "rendah"] },
  },
  required: ["tanggal_mulai", "tanggal_berakhir", "perpanjangan_otomatis", "dasar", "keyakinan"],
};

const DATES_PROMPT = `Dari isian kartu kontrak berikut, tentukan tanggal mulai dan tanggal berakhir kontrak.
Aturan:
- Format tanggal YYYY-MM-DD. Kosongkan ("") bila tidak dapat ditentukan dari teks.
- Tanggal berakhir boleh dihitung dari tanggal mulai dan jangka waktu yang tertulis (misalnya "5 tahun sejak ditandatangani"), dengan tanggal mulai = tanggal tanda tangan bila teks menyatakan demikian. Jangan menebak di luar teks.
- Bila hanya bulan/tahun yang diketahui, kosongkan tanggal tersebut.
- "perpanjangan_otomatis": "ya" hanya bila teks menyatakan kontrak diperpanjang otomatis; "tidak" bila perpanjangan memerlukan kesepakatan/adendum; selain itu "tidak jelas".
- "dasar": satu kalimat singkat, kutip frasa sumbernya.
- "keyakinan": "rendah" bila ada perhitungan, ketidakjelasan, atau teks bertentangan.`;

export const DATE_FIELDS = ["judul", "jenis_dokumen", "tanggal_tanda_tangan", "jangka_waktu_perpanjangan", "pengakhiran", "hubungan_dokumen"];

export async function extractDates(card: any) {
  const body = DATE_FIELDS.map((f) => `${f}: ${card?.[f]?.isi ?? "tidak tercantum"}`).join("\n");
  const j = await post(MODEL_URL, {
    systemInstruction: { parts: [{ text: DATES_PROMPT }] },
    contents: [{ role: "user", parts: [{ text: body }] }],
    generationConfig: { temperature: 0, responseMimeType: "application/json", responseSchema: DATES_SCHEMA },
  });
  const part = j.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!part) throw new Error(`no dates: finishReason=${j.candidates?.[0]?.finishReason}`);
  return JSON.parse(part);
}
