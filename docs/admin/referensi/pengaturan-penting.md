# Referensi pengaturan penting

Env key di [`deploy/gcp/deploy.sh`](../../../deploy/gcp/deploy.sh) yang perlu diketahui admin dan TI JUP, beserta artinya. Nilai rahasia tidak dicantumkan.

## Sebelum mengubah

- Setiap perubahan di `deploy.sh` baru berlaku setelah deploy, yang membuat revisi Cloud Run baru.
- `deploy.sh` mengganti seluruh env service dengan isi berkasnya (`--env-vars-file`). Nilai yang diubah langsung lewat `gcloud` atau Console akan hilang pada deploy berikutnya. Tambahkan perubahan ke `deploy.sh`.
- **Tidak semua env var dapat mengubah produksi.** Pengaturan _PersistentConfig_ Open WebUI hanya mengisi database baru; setelah itu nilai database yang berlaku. Lihat [cara/mengubah-model-default-dan-alat.md](../cara/mengubah-model-default-dan-alat.md).

## Identitas dan akses

| Key                               | Nilai di `deploy.sh`                | Arti                                                                                                                                    |
| --------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `JUP_ADMIN_EMAILS`                | daftar email (dari env saat deploy) | Satu-satunya sumber peran `admin`. Menghapus alamat tidak menurunkan peran; lihat [README](../README.md#dari-mana-peran-admin-berasal). |
| `DEFAULT_USER_ROLE`               | `pending`                           | Akun baru menunggu persetujuan admin.                                                                                                   |
| `ENABLE_SIGNUP`                   | `False`                             | Tidak ada pendaftaran mandiri; akun dibuat dari login IAP.                                                                              |
| `WEBUI_AUTH_TRUSTED_EMAIL_HEADER` | `X-Goog-Authenticated-User-Email`   | Aplikasi mempercayai email dari IAP. Aman hanya selama ingress Cloud Run dibatasi ke load balancer.                                     |
| `ENABLE_ADMIN_CHAT_ACCESS`        | `false`                             | Admin tidak dapat membuka percakapan pengguna lain. Jika diubah, teks di halaman chat (`Placeholder.svelte`) juga harus diubah.         |

## Tampilan dan bahasa

| Key                | Nilai       | Arti                                                                                                                                  |
| ------------------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `WEBUI_NAME`       | `None-JUPe` | Nama produk. Penggantian branding bergantung pada batas 50 pengguna ([ADR-0001](../../adr/0001-fifty-seats-is-a-license-ceiling.md)). |
| `DEFAULT_LOCALE`   | `id-ID`     | Browser tanpa pilihan bahasa membuka aplikasi dalam Bahasa Indonesia.                                                                 |
| `WHISPER_LANGUAGE` | `id`        | Transkripsi suara diperlakukan sebagai Bahasa Indonesia.                                                                              |

## Fitur JUP (saklar)

| Key                                 | Nilai                               | Arti                                                                                              | Jika dihapus                    |
| ----------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------- |
| `JUP_LEADERSHIP_ENABLED`            | `true`                              | Mengaktifkan Ruang Pimpinan. Akses tetap memerlukan grant.                                        | Ruang Pimpinan nonaktif         |
| `JUP_LEADERSHIP_SAMPLE_FILE`        | path di `/srv/jup/leadership/`      | Dataset contoh ilustratif tahap P1                                                                | –                               |
| `JUP_LEADERSHIP_ACTIONS_SOURCE`     | `records`                           | Register tindak lanjut dibaca dari penyimpanan catatan                                            | –                               |
| `JUP_LEADERSHIP_BOD_POLICY`         | **tidak dipasang**                  | Kebijakan penutupan BOD. Sengaja kosong sampai perusahaan memutuskan; penutupan BOD menjawab 503. | –                               |
| `JUP_LEADERSHIP_PUBLICATION_POLICY` | **tidak dipasang**                  | Kewenangan publikasi snapshot. Sengaja kosong; setiap snapshot tetap draf.                        | –                               |
| `JUP_VOICE_ENABLED`                 | `true`                              | Mengaktifkan panggilan suara. Tetap memerlukan grant `jup.voice.call`.                            | Suara nonaktif                  |
| `JUP_CHANNELS_ENABLED`              | `true`                              | Mengizinkan gateway WhatsApp/Teams. Tetap memerlukan grant `jup.channel.use`.                     | Gateway ditolak 403 untuk semua |
| `JUP_GATEWAY_PRINCIPAL`             | email service account `jup-gateway` | Satu-satunya identitas yang boleh bertindak atas nama pengguna, hanya di `/api/jup/channel/`      | –                               |

## Data dan penyimpanan

| Key                                                          | Nilai                          | Arti                                                                                                                                                               |
| ------------------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `STORAGE_PROVIDER`, `GCS_BUCKET_NAME`                        | `gcs`, `jup-ops-data`          | Berkas aplikasi disimpan di Cloud Storage                                                                                                                          |
| `VECTOR_DB`                                                  | `pgvector`                     | Indeks vektor di Postgres                                                                                                                                          |
| `JUP_RECORDS_DIR`, `JUP_ARTEFACT_ROOT`                       | `/srv/jup/records`, `/srv/jup` | Mount baca-saja dari bucket `jup-ops-records`                                                                                                                      |
| `JUP_CONTRACTS_DIR`                                          | `/srv/legal-kb`                | Mount baca-saja dari bucket kontrak `jup-ops-legal-kb` (Jakarta). `deploy.sh` menolak deploy jika service account runtime tidak memiliki akses baca ke bucket ini. |
| `RAG_EMBEDDING_QUERY_PREFIX`, `RAG_EMBEDDING_CONTENT_PREFIX` | `query: `, `passage: `         | Prefiks wajib model embedding multilingual-e5. Hanya benar selama model embedding di database adalah model e5.                                                     |
| `RAG_EMBEDDING_MODEL_AUTO_UPDATE`                            | `False`                        | Model embedding dibawa di image; tidak mengunduh saat boot                                                                                                         |

## Pengamanan lain

| Key                                           | Nilai   | Arti                                                                                                                                                  |
| --------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ENABLE_OLLAMA_API`                           | `False` | Tidak ada backend Ollama. Rute passthrough tetap ditolak oleh tata kelola.                                                                            |
| `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` | `False` | Menyimpan alat tidak boleh memasang paket ke image                                                                                                    |
| `ENABLE_VERSION_UPDATE_CHECK`                 | `False` | Tidak ada notifikasi versi upstream; pembaruan upstream mengikuti rebase triwulanan ([ADR-0007](../../adr/0007-track-upstream-rebasing-quarterly.md)) |

## Secret (Secret Manager)

Nilai ini tidak pernah ditulis di `deploy.sh`; layanan menerima referensi ke secret.

| Env key                    | Nama secret                | Untuk                                                                                                   |
| -------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------- |
| `WEBUI_SECRET_KEY`         | `webui-secret-key`         | Kunci sesi dan tanda tangan aplikasi                                                                    |
| `DATABASE_URL`             | `database-url`             | Koneksi Cloud SQL. Jika instance database dibuat ulang dengan IP baru, tambahkan versi baru secret ini. |
| `JUP_VOICE_OPENAI_API_KEY` | `openai-live-key`          | Suara (OpenAI)                                                                                          |
| `JUP_NOTION_TOKEN`         | `notion-integration-token` | Alat `notion`                                                                                           |

Gateway kanal memakai secret-nya sendiri ([`deploy/gcp/deploy-gateway.sh`](../../../deploy/gcp/deploy-gateway.sh)): `gateway-hmac-key`, `identity-platform-browser-key`, `bot-app-secret` (Teams), serta `whatsapp-app-secret`, `whatsapp-access-token`, `whatsapp-verify-token` (WhatsApp).

Nilai secret dapat membawa baris baru di akhir yang tidak terlihat di shell. Saat menambah versi secret, pastikan tidak ada baris baru tambahan.

## Infrastruktur Cloud Run

| Pengaturan            | Nilai                                   | Arti                                                                               |
| --------------------- | --------------------------------------- | ---------------------------------------------------------------------------------- |
| Project / region      | `jup-ops` / `asia-southeast2` (Jakarta) |                                                                                    |
| Ingress               | `internal-and-cloud-load-balancing`     | Satu-satunya jalan masuk adalah load balancer dengan IAP. **Jangan dilonggarkan.** |
| Autentikasi Cloud Run | `--no-allow-unauthenticated`            | URL `run.app` menolak semua orang                                                  |
| Instance              | min 1, maks 4                           | Selalu ada satu instance aktif; Cloud Run menambah hingga empat saat beban naik    |
| Timeout               | 3600 detik                              | Panggilan GPT-Live dibatasi satu jam                                               |
