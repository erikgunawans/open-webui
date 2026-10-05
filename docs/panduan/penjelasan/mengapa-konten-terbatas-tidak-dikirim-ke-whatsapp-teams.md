# Mengapa Konten Terbatas Tidak Dikirim ke WhatsApp

Halaman ini menjelaskan mengapa sebagian jawaban di WhatsApp hanya berupa tautan ke aplikasi, bukan teks jawabannya.

Aturan yang sama dirancang untuk Microsoft Teams. Saat panduan ini ditulis, kanal Teams belum aktif.

## Apa yang terjadi

Saat Anda bertanya lewat WhatsApp, Asisten JUP memeriksa apakah jawaban untuk pertanyaan itu memakai materi berklasifikasi **TERBATAS**. Saat ini materi tersebut adalah nilai uang kontrak (nilai, pembayaran, denda, batas ganti rugi) dan teks lengkap kontrak.

- Jika jawaban **memakai** materi terbatas, WhatsApp hanya menerima tautan ke obrolan di None-JUPe. Anda membaca jawabannya di aplikasi, setelah masuk dengan akun Microsoft 365 Anda.
- Jika pemeriksaan itu sendiri gagal, hasilnya sama: hanya tautan.
- Jika jawaban berikutnya di obrolan yang sama tidak memakai materi terbatas, jawaban itu kembali dikirim sebagai teks.

## Mengapa

**Isi WhatsApp keluar dari kendali JUP.** Pesan WhatsApp melewati server Meta, termasuk di Amerika Serikat, lalu tersimpan di ponsel Anda, di cadangan ponsel, dan dapat diteruskan dengan satu ketukan. Materi TERBATAS tidak boleh berakhir di tempat seperti itu.

**Tautan tetap berada di balik pintu masuk JUP.** Tautan hanya dapat dibuka oleh akun yang berhak, setelah masuk dengan akun Microsoft 365 JUP. Jika tautan diteruskan ke orang lain, orang itu tidak dapat membukanya.

**Ragu berarti tidak dikirim.** Ini penerapan prinsip _fail-closed_: jika aplikasi tidak dapat memastikan sebuah jawaban bersih dari materi terbatas, jawaban itu diperlakukan sebagai terbatas. Lihat [Mengapa Asisten Bisa Menolak](mengapa-asisten-bisa-menolak.md).

## Aturan lain di kanal

- **Panggilan Eksternal selalu ditolak** di WhatsApp. Kartu persetujuan hanya ada di aplikasi web, sehingga di kanal tidak ada orang yang dapat menyetujuinya.
- **Lampiran belum dibaca.** Asisten membalas bahwa lampiran belum didukung dan mengarahkan Anda ke aplikasi web.

Panduan menghubungkan nomor ada di [Menghubungkan WhatsApp](../cara/menghubungkan-whatsapp.md).
