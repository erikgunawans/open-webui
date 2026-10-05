# Insiden: Disk Mac Penuh

Penanganan saat ruang disk mesin deploy habis karena `docker pull`, build, atau swap.

## Gejala

- `docker pull` atau build lokal menghabiskan ruang kosong (pernah 3,2 GB menjadi 137 MB oleh satu image 663 MB).
- Docker Desktop menjawab API dengan 500, lalu "Docker Desktop is unable to start".
- Ruang kosong naik turun beberapa GB dalam hitungan menit tanpa ada proses yang menulis.
- Error `ENOSPC` di tengah edit atau build.

## Penyebab

- Disk image Docker Desktop membesar di host dan **tidak menyusut** walaupun image dihapus.
- Swap macOS berada di volume APFS yang sama. Tekanan memori langsung memakan ruang disk.

## Langkah

1. **Sebelum pull atau build besar, selalu cek:**

   ```sh
   df -h /
   sysctl vm.swapusage
   ```

2. **Di bawah ±5 GB kosong: jangan lanjut.** Minta pemilik mesin membebaskan ruang dulu (cache besar, aplikasi yang tidak dipakai, sesi idle yang memakan memori).
3. Bila ruang turun mendadak, cek `sysctl vm.swapusage` lebih dulu sebelum mencari "file yang bocor". Swap yang tinggi menjelaskan sebagian besar kasus.
4. **Jangan memperbaiki atau me-restart Docker Desktop sendiri.** Laporkan ke pemilik mesin.
5. Untuk uji Postgres lokal, hindari Docker: gunakan Postgres sekali pakai dari biner `pgserver` (port TCP 55432), sesuai catatan pengujian repo.
6. Deploy tidak butuh Docker lokal: `deploy.sh` mem-build di Cloud Build. Yang perlu ruang hanya tarball upload (±159 MB).

## Verifikasi

- `df -h /` menunjukkan ruang kosong yang cukup (minimal ±5 GB plus kebutuhan pekerjaan).
- `sysctl vm.swapusage` tidak mendekati penuh.
- Bila Docker dipakai: Docker Desktop start normal dan `docker info` berhasil.
