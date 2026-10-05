# Insiden: Sesi IAP Kedaluwarsa Tiap Jam

Penanganan saat sesi IAP/Identity Platform habis sekitar satu jam setelah login sehingga jawaban terpotong dan skrip gagal.

## Gejala

- Jawaban yang sedang di-stream berhenti di tengah dan tertinggal dalam status belum selesai.
- Pesan berikutnya di chat yang sama **masuk antrean dan tidak pernah terkirim**, walaupun kolom input sudah kosong sehingga terlihat terkirim.
- Request same-origin dijawab IAP, bukan aplikasi: 401 atau `Invalid GCIP ID token: JWT signature is invalid`.
- Skrip yang berjalan lewat tab (mis. `sync-*.ts --check`) gagal dengan pesan yang sama.
- Tab otomatis mendarat di `iap-gcip-hosted-ui-...run.app`.

## Penyebab

Token sesi IAP dalam mode external identities berlaku sekitar 1 jam. Setelah itu IAP menolak request sebelum sampai ke `ent-os`. Ini perilaku platform, bukan bug aplikasi.

## Langkah

1. **Buka tab baru** ke `https://non-jupe.jup.co.id/`. Reload biasanya login ulang secara diam-diam lewat SSO Microsoft.
2. Cek sesi hidup sebelum melakukan apa pun:

   ```js
   (await fetch('/api/v1/auths/')).status; // harus 200
   ```

3. Jika masih gagal, login ulang di `non-jupe.jup.co.id` lewat Microsoft.
4. **Jangan melanjutkan chat yang jawabannya terpotong.** Mulai chat baru; pesan di chat lama tetap tertahan di belakang jawaban yang terpotong.
5. Untuk pekerjaan panjang lewat tab (sinkronisasi, uji live): mulai dari tab yang baru login, dan pecah agar selesai jauh di bawah satu jam.

## Verifikasi

- `fetch('/api/v1/auths/')` = 200 di tab yang dipakai.
- Pesan uji di chat baru terkirim dan dijawab sampai selesai.
- Skrip yang gagal, bila dijalankan ulang dari tab baru, selesai tanpa `Invalid GCIP ID token`.
