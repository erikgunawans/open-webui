# Alur Kerja

Jalur sebuah perubahan dari branch sampai terbukti berjalan di produksi, serta cara mencatat checkpoint agar sesi berikutnya bisa melanjutkan tanpa merekonstruksi apa pun.

## Ringkasan

```text
issue → branch → commit → PR → CI hijau → merge ke main → deploy → verifikasi live → checkpoint
```

## 1. Issue

Pekerjaan berawal dari issue GitHub di `erikgunawans/ent-os-new-jup`. Pastikan `gh` menunjuk repo ini, bukan `upstream`; lihat [issue tracker](../agents/issue-tracker.md) dan [label triase](../agents/triage-labels.md).

## 2. Branch dan commit

- Buat branch dari `origin/main` terbaru, dengan nama berawalan jenis perubahan: `feat/…`, `fix/…`, `docs/…`.
- Pesan commit mengikuti pola yang sudah dipakai di riwayat: `feat(ruang-pimpinan): …`, `fix(rapat-direksi): …`, `style(…): …`, `chore(session): checkpoint — …`.
- Satu commit, satu langkah logis. Sertakan file hasil generate (locale dari `i18n:parse`, output `gen-schema.ts`) di commit yang sama dengan perubahan sumbernya.
- Bila mengubah kode vendor, catat tambalannya di [`deploy/gcp/VENDOR-PATCHES.md`](../../deploy/gcp/VENDOR-PATCHES.md): apa, mengapa, apa yang rusak bila tambalan hilang, dan risiko konfliknya.
- Keputusan desain baru dicatat sebagai ADR di [`docs/adr/`](../adr/).

## 3. Sebelum push

Putar ulang **kedua** workflow CI di lokal (Python CI dan Frontend Build), ditambah Gateway bila `gateway/` berubah. Daftar perintahnya ada di [ci.md](ci.md#memutar-ulang-ci-di-lokal). Untuk PR yang hanya menyentuh frontend, jalankan juga test pytest yang membaca sumber frontend.

## 4. Pull request

- Buka PR ke `main` dengan `gh pr create`. PR yang belum siap dibuka sebagai draft.
- Deskripsi PR memuat apa yang berubah, bukti verifikasi (test, pemeriksaan di browser), dan apa yang **belum** diverifikasi.
- PR siap di-merge bila semua check hijau. Python CI hanya berjalan bila path backend berubah, jadi check yang tidak muncul bukan berarti lulus.
- PR di-merge dengan merge commit ("Merge pull request #…").

## 5. Deploy

Merge ke `main` **tidak** otomatis men-deploy. Deploy dijalankan manual oleh orang yang berwenang, mengikuti [`docs/ops/runbook-deploy.md`](../ops/runbook-deploy.md). Hal yang perlu diketahui pengembang:

- `deploy/gcp/deploy.sh` menolak working tree yang kotor dan menandai image dengan SHA `HEAD`.
- Skrip itu mengunggah working tree ke Cloud Build. Jangan pindah branch atau mengedit file selama unggahan berlangsung; kerjakan hal lain di `git worktree` terpisah.
- Bila skrip mati setelah Cloud Build selesai tetapi sebelum langkah Cloud Run, `SKIP_BUILD=1` men-deploy image yang sudah ada untuk commit yang sama. Checkout commit yang dibangun terlebih dahulu.
- Cek ruang disk (`df -h /`) sebelum deploy.

## 6. Verifikasi live

Pekerjaan belum selesai sebelum terbukti di aplikasi yang berjalan, bukan di mock atau server lokal. Langkah lengkapnya ada di [`docs/ops/verifikasi-live.md`](../ops/verifikasi-live.md); intinya:

- Buka aplikasi live di Chrome sungguhan dan jalankan alur yang Anda ubah dengan akun yang memang punya akses ke fitur itu.
- Pastikan browser memuat bundle baru. Shell HTML lama bisa tetap tersaji setelah deploy dan menjalankan alur lama; muat ulang halaman sebelum menilai.
- Untuk perubahan tool, uji di **chat baru**. Model cenderung berpegang pada penolakan yang sudah diucapkannya di chat lama.
- Catat apa yang terverifikasi dan apa yang belum di PR atau issue, lalu tutup issue-nya.

## 7. Checkpoint sesi dan handoff

Pekerjaan di repo ini berlangsung dalam sesi yang sering terputus. Dua file menjaga kesinambungannya:

- **`PROGRESS.md`**: log checkpoint, terbaru di atas. Setiap checkpoint (`## Checkpoint <tanggal>-v<n> — <ringkasan>`) mencatat apa yang dikerjakan di sesi itu, revisi yang sedang live beserta revisi rollback-nya, PR yang masih terbuka, bukti verifikasi, apa yang belum diverifikasi, dan langkah berikutnya.
- **`.planning/next-session-prompt.md`**: prompt pembuka untuk sesi berikutnya. Isinya anchor commit `origin/main` (cara memeriksa apakah ada push paralel), keadaan terkini, daftar "kerjakan berikutnya" yang berurutan, dan batasan yang masih berlaku. Blok baru ditambahkan di atas dan menyatakan blok mana yang digantikannya.

Keduanya ditulis ulang di setiap akhir sesi dan di-commit sebagai `chore(session): checkpoint — <tanggal>-v<n>: …`. Keduanya ada di `.prettierignore`, jadi tidak memerahkan Frontend Build.

Sesi baru dimulai dengan membaca checkpoint teratas di `PROGRESS.md` dan blok teratas `.planning/next-session-prompt.md`, lalu mencocokkan anchor dengan `git log --oneline <anchor>..origin/main`.

Rencana kerja jangka panjang dan catatan sebelum/sesudah (nilai konfigurasi sebelum diubah, hasil uji manual) juga disimpan di `.planning/`.
