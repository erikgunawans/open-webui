# Meninjau pengajuan Basis Pengetahuan

Langkah untuk menyetujui atau menolak dokumen yang diajukan staf ke Basis Pengetahuan Asisten JUP.

## Cara kerja

Staf tidak menambahkan dokumen langsung ke pengetahuan asisten. Dokumen diajukan, ditinjau admin, lalu masuk ke koleksi tersendiri ([ADR-0015](../../adr/0015-staff-contributions-are-a-separate-reviewed-collection.md), [`backend/jup/kb_review.py`](../../../backend/jup/kb_review.py)):

| Peran      | Siapa | Syarat                                                                               |
| ---------- | ----- | ------------------------------------------------------------------------------------ |
| Mengajukan | Staf  | Grant `jup.kb.submit` (ditolak secara default; admin pun tidak memilikinya otomatis) |
| Meninjau   | Admin | Peran `admin`. Akun lain menerima 403.                                               |

- Dokumen yang disetujui masuk ke koleksi **JUP Staff Contributions**, **bukan** ke **JUP Strategy KB**. Strategy KB dibuat ulang dari repo `jup` dan setiap berkas yang ditambahkan dengan tangan akan terhapus pada sinkronisasi berikutnya ([memperbarui-basis-pengetahuan-strategi.md](memperbarui-basis-pengetahuan-strategi.md)).
- Jenis berkas yang diterima: `md`, `txt`, `pdf`, `docx`, `pptx`, `xlsx`, `csv`. Gambar dan media tidak diterima.
- Setiap pengajuan, persetujuan, dan penolakan menulis satu baris audit `jup.governance` berisi ID dan hasil, tanpa isi dokumen, catatan, atau alasan.
- Asisten baru membaca koleksi ini setelah koleksi dilampirkan ke model Asisten JUP (`meta.knowledge`). Ini perubahan produksi tersendiri; lihat [mengubah-model-default-dan-alat.md](mengubah-model-default-dan-alat.md).

Format dokumen yang disarankan untuk staf ada di [`docs/kb-document-template.md`](../../kb-document-template.md); alur lengkap kedua jalur masuk pengetahuan ada di [`docs/kb-update-process.md`](../../kb-update-process.md).

## Memberi staf hak mengajukan

1. Buat atau pilih grup pengaju pengetahuan dan tambahkan stafnya ([mengelola-grup-dan-grant.md](mengelola-grup-dan-grant.md)).
2. Tulis grant berikut ke grup itu:

   ```json
   { "jup": { "kb": { "submit": true } } }
   ```

3. Staf akan melihat menu **Tinjauan Pengetahuan** di sidebar dengan bagian **Ajukan dokumen** dan **Pengajuan saya**.

## Meninjau pengajuan

1. Buka **Tinjauan Pengetahuan** dari sidebar (alamat `/kb-review`).
2. Di **Antrean tinjauan**, saring dengan status **Menunggu peninjauan**.
3. Klik pengajuan untuk membukanya. Anda akan melihat **Diajukan oleh**, **Catatan pengaju**, dan pratinjau teks yang diekstrak (sampai 20.000 karakter).
4. Baca isinya. Anda menyetujui teks yang terlihat di pratinjau ini.
5. Pilih salah satu:
   - **Setujui dan tambahkan ke basis pengetahuan**. Berkas ditambahkan ke **JUP Staff Contributions**. Jika penambahan atau embedding gagal, pengajuan tetap menunggu dan galatnya ditampilkan.
   - **Tolak pengajuan**. Isi **Alasan penolakan (dapat dilihat oleh pengaju)**. Alasan wajib diisi, maksimal 1.000 karakter.

## Jika muncul pesan perubahan teks

- Persetujuan membawa sidik (SHA-256) teks yang Anda buka. Jika pemilik berkas mengubah teksnya setelah Anda membuka pratinjau, persetujuan ditolak dengan kode 409. Buka pengajuan lagi, baca ulang, lalu putuskan.
- Setelah disetujui, pemilik berkas masih dapat mengubah teks yang diekstrak melalui fitur bawaan Open WebUI, dan perubahan itu ikut diproses ke koleksi. Antrean tidak dapat mencegahnya, tetapi menampilkan **Teks berubah setelah diajukan.** bila sidiknya tidak lagi cocok. Jika Anda melihat tanda ini, periksa isinya dan keluarkan berkas dari koleksi bila perlu.

## Pengajuan yang ditolak

Pengajuan yang ditolak tidak dapat diajukan ulang. Staf mengunggah dokumen yang sudah diperbaiki sebagai berkas baru. Keputusan dan alasan lama tetap tercatat di berkas lama.

## Kartu Kontrak di halaman yang sama

Halaman **Tinjauan Pengetahuan** juga memuat antrean **Kartu Kontrak** untuk Tim Legal. Bagian itu memerlukan grant `jup.contracts.review`, yang diberikan oleh Jabatan **Legal**, bukan oleh peran admin. Lihat [mengatur-jabatan-kontrak.md](mengatur-jabatan-kontrak.md).
