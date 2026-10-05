# Insiden: `$BUILDPLATFORM` Kosong di Cloud Build

Penanganan build `ent-os` yang gagal dengan `failed to parse platform`, yang menyalahkan Dockerfile padahal penyebabnya builder.

## Gejala

- Cloud Build berhenti di tahap frontend dengan:

  ```
  failed to parse platform : "" is an invalid component of ""
  ```

- Log build memuat peringatan `the legacy builder is deprecated ... install the buildx component`.
- Terjadi sama persis di pool `global` maupun `asia-southeast2`.

## Penyebab

`gcloud builds submit --tag` (yang dipakai `deploy.sh`) kini menjalankan **legacy docker builder**, bukan BuildKit. `BUILDPLATFORM` adalah argumen yang hanya disediakan BuildKit, sehingga `FROM --platform=$BUILDPLATFORM ...` di Dockerfile menjadi kosong. Pesannya menuduh Dockerfile, padahal perubahannya ada di sisi platform.

## Langkah

1. Pastikan Dockerfile masih memuat default ini tepat di atas stage frontend:

   ```dockerfile
   ARG BUILDPLATFORM=linux/amd64
   FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build
   ```

   Patch ini tercatat di `deploy/gcp/VENDOR-PATCHES.md`. **Jangan dihapus walaupun terlihat berlebihan**; ia hanya terlihat berlebihan saat BuildKit aktif. Saat rebase upstream, pastikan baris ini tetap ada.

2. Jika baris itu hilang (mis. tertimpa rebase), kembalikan, commit, lalu deploy ulang.

3. **Jangan** mengganti pool build atau ukuran mesin untuk mengatasi error ini. Pool `global` di `deploy.sh` adalah pilihan kuota, bukan perbaikan.

4. Untuk trigger Cloud Build berbasis `deploy/gcp/cloudbuild.yaml`: file itu sudah menyetel `DOCKER_BUILDKIT=1`.

## Hal terkait yang sering tertukar

- **OOM vite** (`JavaScript heap out of memory`) adalah batas heap node, bukan ukuran mesin. Gagal sama di 8 GB maupun 32 GB. Perbaikannya `NODE_OPTIONS` di Dockerfile.

## Verifikasi

- Build melewati stage frontend dan `gcloud builds list --project=jup-ops --limit=1` menunjukkan `SUCCESS`.
- Image `asia-southeast2-docker.pkg.dev/jup-ops/ent-os/ent-os:<sha>` ada:

  ```sh
  gcloud artifacts docker images describe asia-southeast2-docker.pkg.dev/jup-ops/ent-os/ent-os:<sha> \
    --project=jup-ops --format='value(image_summary.digest)'
  ```
