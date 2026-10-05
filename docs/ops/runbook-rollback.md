# Runbook Rollback

Cara mengembalikan traffic `ent-os` atau `jup-gateway` ke revision sebelumnya tanpa build ulang, lalu memverifikasinya.

## Kapan dipakai

- Revision baru error, gagal start, atau merusak fitur yang sebelumnya jalan.
- Rollback lewat traffic adalah jalur tercepat (±1 menit). Build ulang dari commit lama memakan puluhan menit.

## Yang perlu dipahami sebelum rollback

- **Revision bersifat immutable.** Rollback mengembalikan image, env, dan konfigurasi revision lama apa adanya.
- **Secret dirujuk sebagai `:latest`.** Revision lama tetap membaca versi secret **terbaru**, bukan versi saat revision itu dibuat.
- **Database tidak ikut mundur.** Migrasi yang dijalankan revision baru saat boot tetap ada. Pastikan kode lama masih kompatibel dengan skema baru sebelum rollback, terutama jika revision baru menambah migrasi.
- **Setting yang disimpan di database (DB-seeded) tidak ikut mundur.**
- Setelah traffic dipatok ke revision tertentu, service tidak lagi otomatis mengikuti revision terbaru. Lihat bagian Kembali ke revision terbaru.

## Langkah

1. **Lihat revision yang ada** dan pilih target (biasanya yang tercatat sebagai "rollback" di PROGRESS.md):

   ```sh
   gcloud run revisions list --service=ent-os --project=jup-ops --region=asia-southeast2 --limit=5
   ```

2. **Catat kondisi sekarang** (before-value):

   ```sh
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='yaml(status.traffic)'
   ```

3. **Pindahkan seluruh traffic ke revision target:**

   ```sh
   gcloud run services update-traffic ent-os --project=jup-ops --region=asia-southeast2 \
     --to-revisions=<NAMA-REVISION>=100
   ```

   Contoh nama revision: `ent-os-00099-vvt`. Untuk gateway, ganti `ent-os` dengan `jup-gateway`.

## Verifikasi

1. Traffic 100% ke revision target:

   ```sh
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='yaml(status.traffic)'
   ```

2. Image revision target sesuai commit yang diharapkan. Revision menyimpan image sebagai digest (`…/ent-os@sha256:…`), bukan tag SHA commit, jadi bandingkan kedua digest:

   ```sh
   gcloud run revisions describe <NAMA-REVISION> --project=jup-ops --region=asia-southeast2 \
     --format='value(spec.containers[0].image)'
   gcloud artifacts docker images describe \
     asia-southeast2-docker.pkg.dev/jup-ops/ent-os/ent-os:<SHA-COMMIT> \
     --format='value(image_summary.digest)'
   ```

3. Tidak ada error baru di log (lihat [observability.md](observability.md)).

4. Di browser sungguhan yang login, paksa muat ulang HTML shell dan buktikan hash `entry/app` sesuai build lama. Lihat [verifikasi-live.md](verifikasi-live.md).

5. Catat rollback, alasannya, dan revision yang ditinggalkan di PROGRESS.md.

## Kembali ke revision terbaru

Setelah perbaikan di-deploy, pastikan traffic benar-benar pindah ke revision baru. Setelah traffic dipatok ke revision tertentu, revision baru belum tentu otomatis menerima traffic. Selalu cek `status.traffic` setelah deploy berikutnya. Jika belum pindah:

```sh
gcloud run services update-traffic ent-os --project=jup-ops --region=asia-southeast2 --to-latest
```

## Yang bukan rollback

- Membangun ulang commit lama dengan `deploy.sh`: itu deploy baru, dan memakai env dari heredoc commit lama.
- Rollback infrastruktur (IAP, load balancer, IAM) tidak tercakup di sini. Untuk IAP lihat [insiden/iap-toggle-cloud-run.md](insiden/iap-toggle-cloud-run.md).
