# Insiden: Batch Document AI Macet

Penanganan OCR kontrak (knowledge base kontrak) ketika `batchProcess` Document AI tidak bergerak.

## Gejala

- Operasi `batchProcess` pada processor `legal-kb-ocr` berstatus `RUNNING` selama lebih dari satu jam.
- `updateTime` operasi tidak pernah berubah dan tidak ada output di bucket.
- Polling operasi mendapat 403 tentang "quota project" (terlihat seperti masalah autentikasi, padahal bukan).

## Penyebab

Antrean batch Document AI tidak memberi sinyal progres, sehingga batch yang macet tidak bisa dibedakan dari batch yang lambat. Pada 2026-10-01 batch macet 1,5 jam; panggilan sinkron ke processor yang sama langsung berhasil. 403 saat polling terjadi karena header quota project tidak dikirim.

## Langkah

1. **Batalkan batch yang macet** dan jangan menunggu lebih lama.
2. **Gunakan OCR sinkron** (`:process`) dalam potongan **maksimal 15 halaman** (batas online). Skrip yang sudah melakukannya ada di `deploy/gcp/legal-kb/`:

   ```sh
   cd deploy/gcp/legal-kb
   bun install
   bun ocr.ts            # pilot: semua PDF
   bun ocr.ts 03 07      # hanya nomor tertentu
   bun run.ts full       # run penuh, resumable
   ```

   PDF diproses di memori. Output ditulis ke `gs://jup-ops-legal-kb/<run>/ocr-text/NN.json`.

3. Jika tetap perlu mem-polling operasi Document AI secara langsung, kirim header `x-goog-user-project: jup-ops`.
4. Patuhi aturan lokasi data: penyimpanan di Jakarta (`gs://jup-ops-legal-kb`), OCR di `asia-southeast1`. Jangan menulis PDF atau teks OCR ke disk lokal atau ke repo.

## Verifikasi

- Setiap dokumen menghasilkan `ocr-text/NN.json`, dan log skrip menampilkan jumlah halaman serta karakter (`ocr=… chars=…`).
- Untuk run penuh: `full/errors/` kosong atau hanya berisi dokumen yang memang rusak; ulangi `bun run.ts full` untuk mencoba ulang.
