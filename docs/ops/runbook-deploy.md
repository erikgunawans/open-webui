# Runbook Deploy

Langkah men-deploy `ent-os` dan `jup-gateway` ke Cloud Run di `jup-ops`, termasuk pemulihan dan pemeriksaan sesudahnya.

## Aturan keras

- **JANGAN** deploy tanpa persetujuan eksplisit untuk perubahan itu.
- **JANGAN** pindah branch, `git checkout`, `git pull`, atau mengedit file di repo selama `deploy.sh` berjalan. Skrip meng-upload working tree (`Uploading tarball of [.]`) dan memberi tag image = SHA `HEAD`. Kerjakan hal lain di `git worktree` terpisah.
- **JANGAN** menyimpan log deploy di dalam repo. File yang tidak di-track membuat tree "dirty" dan `deploy.sh` menolak jalan.
- **JANGAN** menambah env var production lewat `gcloud run services update --update-env-vars` saja. `--env-vars-file` di `deploy.sh` **mengganti seluruh env**; nilai yang hanya ada di gcloud hilang pada deploy berikutnya.
- **JANGAN** menaruh credential sebagai env var biasa. Semua secret lewat `--set-secrets`.
- **JANGAN** mengandalkan notifikasi "completed, exit 0". Konfirmasi lewat `gcloud` (lihat Pemeriksaan pasca-deploy).

## Prasyarat

1. **Login ulang gcloud sebelum mulai.** Kebijakan sesi Workspace bisa meminta re-auth di tengah deploy. Shell non-interaktif tidak bisa menjawabnya, `gcloud builds submit` gagal, dan `gcloud run deploy` tidak pernah jalan.

   ```sh
   gcloud auth login
   gcloud builds list --project=jup-ops --limit=1
   ```

   Perintah kedua harus berhasil **tepat sebelum** deploy.

2. **Cek billing account masih terbuka.** Kalau tertutup, deploy pasti gagal. Lihat [insiden/billing-akun-tertutup.md](insiden/billing-akun-tertutup.md).

3. **Cek ruang disk dan swap di Mac.** Swap macOS memakai volume yang sama, jadi ruang kosong bisa turun beberapa GB dalam hitungan menit.

   ```sh
   df -h /
   sysctl vm.swapusage
   ```

   Di bawah ±5 GB kosong: bebaskan ruang dulu. Lihat [insiden/disk-penuh.md](insiden/disk-penuh.md).

4. **Tree bersih, di commit yang benar.** `deploy.sh` menolak tree yang dirty (`refusing to deploy a dirty tree`). Pastikan `HEAD` adalah commit yang memang mau di-deploy (biasanya `main` setelah merge).

   ```sh
   git status --short
   git rev-parse --short HEAD
   ```

5. **Catat revision yang sedang live** sebagai titik rollback:

   ```sh
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
   ```

## Deploy `ent-os`

Jalankan dari **root repo** (Cloud Build meng-upload direktori kerja saat ini sebagai build context):

```sh
bash deploy/gcp/deploy.sh > "${TMPDIR:-/tmp}/deploy-ent-os.log" 2>&1; rc=$?; echo "exit: $rc"; exit $rc
```

Pola `rc=$?; ...; exit $rc` wajib bila dijalankan di background atau lewat pipe. `| tail` atau `; echo` di ujung akan menutupi exit code yang gagal.

Yang dilakukan skrip, berurutan:

1. Menolak tree yang dirty.
2. `gcloud builds submit` ke pool `global` dengan tag `asia-southeast2-docker.pkg.dev/jup-ops/ent-os/ent-os:<sha>` (upload ±159 MB, build bisa puluhan menit).
3. Menulis env ke file sementara dari heredoc di skrip.
4. Memastikan runtime service account punya grant di `gs://jup-ops-legal-kb`. Jika tidak, berhenti (`not deploying`).
5. `gcloud run deploy ent-os ... --set-secrets=... --env-vars-file=...`.

Durasi wajar: upload ±20 menit dari jaringan rumah, lalu build dan deploy.

## Env var dan secret

- **Satu-satunya tempat env production adalah heredoc di `deploy/gcp/deploy.sh`.** Tambah, ubah, atau hapus nilai di sana, commit, lalu deploy.
- Untuk menerapkan nilai **sekarang** tanpa rebuild, `gcloud run services update ent-os --update-env-vars=...` boleh dipakai, **asalkan** nilai yang sama sudah di-commit di heredoc dalam perubahan yang sama.
- Sebagian setting Open WebUI disimpan di database (DB-seeded), bukan dibaca dari env pada setiap boot. Mengubah env-nya tidak mengubah nilai live. Komentar di heredoc menyebutkan mana yang DB-seeded.
- Heredoc memakai delimiter tanpa kutip: **jangan pakai backtick** di dalamnya, termasuk di komentar.
- `--set-secrets` mengganti **seluruh** blok secret. Setiap secret baru harus ditambahkan ke daftar yang sama di `deploy.sh`. Secret yang tidak disebut akan hilang dari service.
- Secret baru butuh `roles/secretmanager.secretAccessor` untuk runtime service account, dan nilainya ditulis tanpa newline. Lihat [insiden/secret-newline.md](insiden/secret-newline.md).

## Pemulihan: `SKIP_BUILD=1`

Gunakan ini bila `deploy.sh` mati **setelah** Cloud Build selesai tetapi **sebelum** Cloud Run menerima image: terminal tertutup, sesi restart, atau re-auth gagal saat streaming log. Cloud Build tetap jalan di server walaupun skrip lokal mati.

1. Cek build terakhir dan revision live:

   ```sh
   gcloud builds list --project=jup-ops --limit=2
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
   ```

2. Jika build `SUCCESS` tetapi image live masih SHA lama: **checkout dulu commit yang di-build.** Tag image = SHA `HEAD`; kalau `HEAD` sudah bergeser (mis. ada commit baru), skrip berhenti dengan `no image ... in the registry`.

   ```sh
   git checkout <sha-yang-di-build>
   git status --short          # harus kosong
   SKIP_BUILD=1 bash deploy/gcp/deploy.sh
   git checkout main
   ```

3. Jika build **gagal** atau tidak ada: login ulang, lalu jalankan `deploy.sh` biasa dari tree bersih. Production tidak tersentuh oleh build yang gagal.

## Deploy `jup-gateway`

```sh
bash deploy/gcp/deploy-gateway.sh > "${TMPDIR:-/tmp}/deploy-gateway.log" 2>&1; rc=$?; echo "exit: $rc"; exit $rc
```

- Skrip menolak jika `gateway/` atau skrip itu sendiri dirty.
- Memakai `--set-env-vars` dan `--set-secrets`: **seluruh env dan secret gateway diganti** setiap deploy. Yang tidak disusun skrip akan hilang.
- **WhatsApp terbuka secara default.** `WHATSAPP_PHONE_NUMBER_ID` default ke nomor uji Meta. Untuk deploy dengan WhatsApp tertutup:

  ```sh
  WHATSAPP_PHONE_NUMBER_ID= bash deploy/gcp/deploy-gateway.sh
  ```

- **Teams tertutup** sampai `BOT_APP_ID` dan `JUP_TENANT_ID` diisi **dan** secret `bot-app-secret` ada:

  ```sh
  BOT_APP_ID=<dari JUP IT> JUP_TENANT_ID=<dari JUP IT> bash deploy/gcp/deploy-gateway.sh
  ```

- `SELFCHECK=1` membuat revision baru membuktikan identitasnya lewat IAP sekali saat start. Hasil yang benar: `422` di endpoint Channel, `403` di tempat lain, lihat baris log `selfcheck`. Deploy biasa berikutnya menghapusnya.
- Health check gateway ada di `/health`, **bukan** `/healthz`. Lihat [insiden/healthz-dicadangkan.md](insiden/healthz-dicadangkan.md).

## Pemeriksaan pasca-deploy

Lakukan **semua** langkah sebelum menyatakan deploy selesai.

1. **Proses lokal sudah selesai.** Notifikasi "completed (exit 0)" pernah datang saat skrip masih upload.

   ```sh
   pgrep -fl deploy/gcp/deploy.sh      # harus kosong
   ```

   Lalu baca baris `exit:` di log.

2. **Revision dan image live sesuai SHA:**

   ```sh
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='yaml(status.traffic)'
   ```

   Image harus berakhir `:<sha>` yang di-deploy, dan traffic 100% ke revision baru. Untuk gateway, ganti `ent-os` dengan `jup-gateway`.

3. **Scaling tidak berubah** (min 1 / max 4 untuk `ent-os`):

   ```sh
   gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
     --format='value(spec.template.metadata.annotations)'
   ```

4. **Log start tanpa error** (migrasi database berjalan saat boot). Lihat [observability.md](observability.md).

5. **Verifikasi di browser sungguhan sebagai pengguna yang login**, termasuk membuktikan hash `entry/app` yang dimuat sama dengan yang disajikan server. HTML shell lama di cache browser bisa tetap menjalankan build lama. Lihat [verifikasi-live.md](verifikasi-live.md).

6. **Catat** revision baru dan revision rollback-nya di PROGRESS.md.

## Masalah umum saat deploy

| Gejala                                                                    | Penyebab                                                                      | Tindakan                                                                                                |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `Reauthentication failed. cannot prompt during non-interactive execution` | Sesi gcloud kedaluwarsa                                                       | `gcloud auth login`, lalu cek apakah build tetap selesai; jika ya, `SKIP_BUILD=1` dari commit yang sama |
| `refusing to deploy a dirty tree`                                         | Ada perubahan atau file baru di repo (termasuk file log)                      | Commit, stash, atau pindahkan file; jangan menulis log ke dalam repo                                    |
| `no image ... in the registry; run without SKIP_BUILD`                    | `HEAD` bukan commit yang di-build                                             | Checkout SHA yang di-build                                                                              |
| `has no grant on gs://jup-ops-legal-kb`                                   | Runtime service account kehilangan `roles/storage.objectViewer` di bucket itu | Pulihkan grant (butuh persetujuan), lalu deploy ulang                                                   |
| `failed to parse platform`                                                | Builder legacy Cloud Build                                                    | [insiden/cloud-build-buildplatform.md](insiden/cloud-build-buildplatform.md)                            |
| Build/upload ditolak, GCS 403 `billing ... delinquent`                    | Billing account tertutup                                                      | [insiden/billing-akun-tertutup.md](insiden/billing-akun-tertutup.md)                                    |
| UI tidak berubah setelah deploy                                           | HTML shell lama di cache                                                      | [verifikasi-live.md](verifikasi-live.md)                                                                |
