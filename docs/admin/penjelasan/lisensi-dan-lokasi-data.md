# Batas 50 pengguna dan lokasi data

Penjelasan dua batas yang memengaruhi keputusan admin: batas lisensi jumlah pengguna, dan tempat data JUP disimpan serta diproses.

## Batas 50 pengguna adalah batas lisensi

Keputusan: [ADR-0001](../../adr/0001-fifty-seats-is-a-license-ceiling.md).

Lisensi Open WebUI (klausul 4) mengizinkan penggantian branding Open WebUI hanya jika total pengguna akhir **tidak lebih dari 50 dalam periode 30 hari bergulir**, kecuali ada perjanjian enterprise tertulis. None-JUPe memakai branding JUP, sehingga jumlah pengguna sengaja dijaga di bawah 50.

Yang perlu dipahami admin:

- Melewati angka 50 **tidak merusak apa pun secara teknis**. Akibatnya bersifat komersial: keputusan branding yang tadinya gratis berubah menjadi negosiasi lisensi per pengguna dengan harga yang tidak dipublikasikan.
- Karena itu, setiap usulan memperluas akses adalah **keputusan lisensi lebih dulu**, baru keputusan kapasitas. Periksa jumlah pengguna aktif sebelum menyetujui akun baru ([cara/menyetujui-pengguna-baru.md](../cara/menyetujui-pengguna-baru.md)).
- Anggota Direksi dan Komisaris dapat menerima hasil (ringkasan, tautan dashboard) tanpa memegang akun.

## Lokasi data

### Aplikasi dan penyimpanan utama: Jakarta

Aplikasi (Cloud Run `ent-os`) dan gateway kanal berjalan di project `jup-ops`, region `asia-southeast2` (Jakarta) ([`deploy/gcp/deploy.sh`](../../../deploy/gcp/deploy.sh), [`deploy/gcp/deploy-gateway.sh`](../../../deploy/gcp/deploy-gateway.sh)). Aplikasi memakai bucket berkas `jup-ops-data`, bucket catatan `jup-ops-records`, dan bucket kontrak `jup-ops-legal-kb` (Jakarta, privat).

### Basis pengetahuan kontrak: disimpan di Jakarta, diproses di Singapura

Sumber: [`deploy/gcp/legal-kb/README.md`](../../../deploy/gcp/legal-kb/README.md).

| Tahap                                      | Lokasi                                               | Catatan                                                                                       |
| ------------------------------------------ | ---------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Penyimpanan PDF, teks OCR, dan kartu       | Jakarta (`gs://jup-ops-legal-kb`, `asia-southeast2`) | Bucket privat, di-mount baca-saja ke aplikasi                                                 |
| OCR (Document AI)                          | Singapura (`asia-southeast1`)                        | Document AI tidak tersedia di region Jakarta                                                  |
| Penyusunan draf kartu (`gemini-2.5-flash`) | Singapura (`asia-southeast1`)                        | Teks OCR mentah masih memuat nama asli, sehingga penyusunan memakai model di region yang sama |

PDF dan teks OCR dialirkan melalui memori dan tidak ditulis ke disk lokal atau ke repo.

**Nama perorangan disamarkan.** Pihak perorangan di kontrak (bukan perusahaan atau instansi) diganti kode tetap, misalnya "Perorangan A". Model penjawab hanya melihat kode. Nama asli ditampilkan kembali di layar, setelah jawaban, hanya bagi pembaca dengan grant `jup.contracts.names` (Jabatan Legal dan Direksi). Penanda tangan yang bertindak untuk perusahaan tidak disamarkan. Nama yang diketik pengguna sendiri di pertanyaan tetap sampai ke model ([`backend/jup/contracts/access.py`](../../../backend/jup/contracts/access.py)).

### Model penjawab

Asisten JUP adalah satu asisten untuk semua topik, termasuk kontrak. Akses dikendalikan oleh alat di kode sebelum data dikirim ke model, bukan oleh pemisahan asisten. Penyedia model untuk chat yang diketik dapat berbeda dari penyedia suara dan memiliki ketentuannya sendiri ([ADR-0006](../../adr/0006-voice-material-crosses-to-the-us-under-zdr.md), bagian _Named non-coverage_).

### Suara: diproses di Amerika Serikat, dibatasi daftar dokumen

Keputusan: [ADR-0006](../../adr/0006-voice-material-crosses-to-the-us-under-zdr.md), [ADR-0017](../../adr/0017-voice-is-a-chained-pipeline-that-speaks-our-exact-answer.md).

- Panggilan suara mengirim audio dan teks ke OpenAI, yang hanya menawarkan pemrosesan regional di Amerika Serikat, Eropa, dan UEA. Materi JUP yang diucapkan ke sistem ini diproses di Amerika Serikat.
- Batasnya dibuat **secara konstruksi**: sesi suara hanya dapat mengambil dari sekumpulan dokumen Strategy KB yang disebut namanya. Dokumen di luar daftar itu tidak dapat dijangkau sama sekali. Daftar saat ini berisi delapan berkas ([`docs/kb-update-process.md`](../../kb-update-process.md), Step 5).
- Menambahkan dokumen ke daftar itu membuat dokumen tersebut masuk cakupan pemrosesan di Amerika Serikat sejak saat itu, tanpa peninjauan lanjutan. Karena itu penambahan memerlukan keputusan tata kelola yang bertanggal dan bernama.
- Amandemen 2026-09-26: _zero data retention_ (ZDR) tidak lagi menjadi prasyarat. Sampai ZDR disetujui pada organisasi OpenAI, materi suara dapat disimpan OpenAI hingga 30 hari.
- Grant suara (`jup.voice.call`) tidak diberikan secara default, dan pengguna harus menyetujui pemberitahuan suara sebelum panggilan pertama.

### WhatsApp dan Teams

- **WhatsApp:** teks pesan melewati server Meta, termasuk di Amerika Serikat, sebelum sampai ke Asisten JUP. Pengguna diberi tahu sekali saat menautkan nomornya. Nomor telepon tidak dikirim ke aplikasi; gateway hanya mengirim hash-nya.
- **Teams:** teks pesan diteruskan oleh Microsoft Bot Service, di bawah kontrak Microsoft 365 JUP, ke gateway JUP di Jakarta ([`deploy/gcp/teams-request-jup-it.id.md`](../../../deploy/gcp/teams-request-jup-it.id.md)).
- Di kedua kanal, jawaban yang membaca materi TERBATAS hanya dikirim sebagai tautan yang memerlukan login.

## Yang perlu diperhatikan admin

| Keputusan                                       | Mengapa perlu persetujuan                                                                                                   |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Menyetujui akun baru di atas batas 50 pengguna  | Keputusan lisensi ([ADR-0001](../../adr/0001-fifty-seats-is-a-license-ceiling.md))                                          |
| Menambah dokumen ke daftar suara                | Memperluas cakupan pemrosesan di Amerika Serikat ([ADR-0006](../../adr/0006-voice-material-crosses-to-the-us-under-zdr.md)) |
| Memberi grant suara atau kanal ke pengguna baru | Materi pengguna itu akan melewati penyedia di luar Indonesia                                                                |
| Memberi Jabatan Legal atau Direksi              | Membuka nama asli pihak perorangan di layar                                                                                 |
