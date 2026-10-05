# Insiden: IAP Diaktifkan Langsung di Cloud Run

Penanganan outage ketika IAP bawaan Cloud Run diaktifkan pada service `ent-os` (atau halaman login), di samping IAP load balancer yang memang dipakai.

## Aturan keras

- **JANGAN pernah mencentang baris Cloud Run di halaman IAP Cloud Console.** Halaman IAP menampilkan beberapa baris: backend service `ent-os-backend` dan `ent-os-backend-jup` (boleh disentuh bila memang ada tugasnya), serta service Cloud Run `ent-os` dan `iap-gcip-hosted-ui-ent-os-backend-jup` (**jangan disentuh**).
- **Tutup setiap tab Cloud Console segera setelah satu langkah selesai.** Outage ketiga terjadi dari tab Console yang dibiarkan terbuka; pemicunya belum terungkap.
- Setelah menyentuh salah satu service, **cek anotasi `iap-enabled` di kedua service Cloud Run.**

## Gejala

- Pengguna yang login mendapat **500 kosong** dari "Google Frontend". Request tidak pernah sampai ke Cloud Run (tidak ada log request).
- Atau, setelah perbaikan yang tidak lengkap: **403 "Your client does not have permission"** bagi pengguna yang login.
- curl anonim tetap menunjukkan 302 ke halaman login, jadi dari luar terlihat sehat.
- Untuk halaman login: halaman login me-redirect ke login Google, bukan Microsoft.

## Penyebab

Aksi di halaman IAP Console menulis anotasi `run.googleapis.com/iap-enabled: true` pada service Cloud Run. Itu IAP _langsung_ milik Cloud Run, lapisan kedua tanpa accessor, terpisah dari IAP di backend load balancer. Perbaikannya (`--no-iap`) juga menulis **IAM policy kosong** ke service, sehingga binding `roles/run.invoker` untuk service agent IAP hilang. Akibatnya 403.

## Langkah

1. **Pastikan penyebabnya** dari audit log admin Cloud Run (perubahan `ReplaceService` atau `SetIamPolicy`):

   ```sh
   gcloud logging read 'logName="projects/jup-ops/logs/cloudaudit.googleapis.com%2Factivity" AND protoPayload.serviceName="run.googleapis.com"' \
     --project=jup-ops --freshness=1d --limit=20
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='value(metadata.annotations."run.googleapis.com/iap-enabled")'
   ```

   Nilai `true` = insiden ini.

2. **Catat before-value IAM:**

   ```sh
   gcloud run services get-iam-policy ent-os --project=jup-ops --region=asia-southeast2
   ```

3. **Matikan IAP Cloud Run di `ent-os`:**

   ```sh
   gcloud run services update ent-os --region=asia-southeast2 --project=jup-ops --no-iap
   ```

4. **Segera pasang kembali invoker untuk service agent IAP** (langkah 3 mengosongkan IAM):

   ```sh
   PN=$(gcloud projects describe jup-ops --format='value(projectNumber)')
   gcloud run services add-iam-policy-binding ent-os \
     --region=asia-southeast2 --project=jup-ops \
     --member="serviceAccount:service-$PN@gcp-sa-iap.iam.gserviceaccount.com" \
     --role=roles/run.invoker
   ```

   Butuh ±1 menit sampai berlaku.

5. **Jika halaman login juga terkena** (`iap-gcip-hosted-ui-ent-os-backend-jup`): matikan IAP-nya dan kembalikan ke tanpa pemeriksaan invoker, lalu hapus binding service agent IAP yang ditambahkan Console.

   ```sh
   gcloud run services update iap-gcip-hosted-ui-ent-os-backend-jup --region=asia-southeast2 --project=jup-ops \
     --no-iap --no-invoker-iam-check
   gcloud run services remove-iam-policy-binding iap-gcip-hosted-ui-ent-os-backend-jup \
     --region=asia-southeast2 --project=jup-ops \
     --member="serviceAccount:service-$PN@gcp-sa-iap.iam.gserviceaccount.com" \
     --role=roles/run.invoker
   ```

6. Tutup semua tab Cloud Console.

## Verifikasi

- Anotasi `iap-enabled` **kosong** di kedua service:

  ```sh
  for s in ent-os iap-gcip-hosted-ui-ent-os-backend-jup; do
    gcloud run services describe "$s" --project=jup-ops --region=asia-southeast2 \
      --format='value(metadata.annotations."run.googleapis.com/iap-enabled")'
  done
  ```

- `gcloud run services get-iam-policy ent-os ...` memuat `service-<PN>@gcp-sa-iap.iam.gserviceaccount.com` dengan `roles/run.invoker`.
- **Jalur login dibuktikan dari browser**, bukan curl: dari tab baru, `fetch('/api/config')` dan `fetch('/api/v1/auths/')` = 200 ([verifikasi-live.md](../verifikasi-live.md)).
- Log request Cloud Run kembali menerima request pengguna.
