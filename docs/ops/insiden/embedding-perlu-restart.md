# Insiden: Ganti Model Embedding Butuh Revision Baru

Langkah wajib saat mengganti model embedding agar semua instance `ent-os` memakai model yang sama.

## Gejala

- Setelah model embedding diganti, hasil pencarian knowledge base menjadi buruk atau acak, **tanpa error**.
- Kualitas berbeda-beda antar percobaan, tergantung instance yang melayani request.

## Penyebab

`POST /api/v1/retrieval/embedding/update` hanya mengganti model di memori **instance yang menerima request itu**. Instance lain (max 4) tetap memakai model lama sampai restart. Dimensi vektor bisa sama (mis. 384), sehingga tidak ada error, hanya ranking yang salah. Konfigurasi yang tersimpan di database baru dibaca saat instance boot.

## Langkah

1. Ganti model lewat panel admin atau `POST /api/v1/retrieval/embedding/update` (dari tab yang login sebagai admin).
2. **Reindex** knowledge base: `POST /api/v1/knowledge/reindex`. Tunggu sampai selesai (pernah ±2 menit untuk 59 file).
3. **Paksa revision baru tanpa mengubah env** agar semua instance boot ulang dengan model baru (butuh persetujuan):

   ```sh
   gcloud run services update ent-os --project=jup-ops --region=asia-southeast2 \
     --update-labels=embedding-switch=<YYYY-MM-DD>
   ```

4. Cek prefix e5 di heredoc `deploy/gcp/deploy.sh`: `RAG_EMBEDDING_QUERY_PREFIX: "query: "` dan `RAG_EMBEDDING_CONTENT_PREFIX: "passage: "` **hanya benar untuk model e5**. Jika model baru bukan e5, ubah atau hapus keduanya di heredoc, commit, dan deploy.
5. Model harus sudah ada di image (`RAG_EMBEDDING_MODEL_AUTO_UPDATE: "False"`); model baru butuh perubahan image.

Catatan: file yang diunggah langsung di chat dengan model lama tidak ikut di-reindex oleh route itu.

## Verifikasi

- Revision baru `Ready` dengan 100% traffic ([runbook-deploy.md](../runbook-deploy.md), Pemeriksaan pasca-deploy).
- Uji beberapa pertanyaan knowledge base di **chat baru** dan cek sumber yang dikutip relevan.
