# Ke Mana Data Anda Pergi

Halaman ini menjelaskan di mana pertanyaan, dokumen, suara, dan pesan Anda disimpan dan diproses saat memakai None-JUPe.

Ringkasnya: aplikasi dan data tersimpan di Jakarta, tetapi menyusun jawaban selalu melibatkan penyedia model AI di luar Indonesia. Apa pun yang Anda ketik, lampirkan, atau ucapkan ikut terkirim ke penyedia itu. Jangan memasukkan informasi yang belum boleh keluar dari JUP.

## Peta singkat

| Bagian                                            | Tempat                                                                                          | Keterangan                                                                        |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Aplikasi None-JUPe                                | Google Cloud, Jakarta (`asia-southeast2`)                                                       | Tempat aplikasi berjalan.                                                         |
| Basis data (akun, riwayat obrolan, memori)        | Google Cloud, Jakarta                                                                           | Disimpan di basis data JUP sendiri.                                               |
| Berkas yang Anda unggah dan berkas buatan asisten | Google Cloud Storage, Jakarta                                                                   |                                                                                   |
| Penyusunan jawaban obrolan tertulis               | Model AI melalui OpenRouter, di luar Indonesia                                                  | Pertanyaan Anda, isi dokumen yang relevan, dan memori yang dipakai ikut terkirim. |
| Panggilan suara: suara menjadi teks               | OpenAI, Amerika Serikat                                                                         | Dapat disimpan OpenAI hingga 30 hari.                                             |
| Panggilan suara: jawaban dibacakan                | Google Text-to-Speech                                                                           | Google menyatakan tidak mencatat teks maupun audio jawaban.                       |
| GPT-Live                                          | OpenAI, Amerika Serikat                                                                         | Seluruh sesi, termasuk suara Anda, diproses dan dapat disimpan hingga 30 hari.    |
| WhatsApp                                          | Server Meta, termasuk di Amerika Serikat                                                        | Pesan melewati Meta sebelum sampai ke Asisten JUP.                                |
| Pindaian kontrak dan teks hasil OCR               | Disimpan di Jakarta; OCR dan penyusunan kartu kontrak diproses di Singapura (`asia-southeast1`) | Proses ini dijalankan admin, bukan oleh Anda saat bertanya.                       |

## Obrolan tertulis

Setiap pertanyaan tertulis dijawab oleh model AI yang diakses melalui OpenRouter, sebuah perantara layanan model. Pemrosesannya berada di luar Indonesia, dan JUP menerima hal itu secara sadar. Yang ikut terkirim: pertanyaan Anda, potongan dokumen basis pengetahuan yang relevan, isi lampiran yang dipakai, dan memori Anda bila dipakai dalam percakapan.

Nama orang perorangan dalam kontrak tidak ikut terkirim: nama itu sudah diganti kode sebelum sampai ke model. Lihat [Mengapa Nama Disamarkan](mengapa-nama-disamarkan.md).

Fitur bacakan jawaban di luar panggilan suara memakai suara bawaan peramban Anda, sehingga jawaban tertulis tidak dikirim ke OpenAI.

## Panggilan suara

Sebelum panggilan pertama, Anda menyetujui pernyataan yang menjelaskan alurnya: OpenAI mengubah suara Anda menjadi teks di Amerika Serikat dan dapat menyimpannya hingga 30 hari; jawaban dibacakan oleh Google Text-to-Speech; kata-kata Anda juga melewati OpenRouter dan Xiaomi, penyedia model yang menyusun jawaban. Apa pun yang Anda ucapkan tetap terkirim, termasuk hal di luar topik. Lihat [Memulai Panggilan Suara](../cara/panggilan-suara.md).

Catatan sumber: rancangan awal suara mensyaratkan OpenAI tidak menyimpan data (_zero data retention_) dan memakai OpenAI untuk membacakan jawaban. Keputusan yang lebih baru mencabut syarat itu, sehingga data suara dapat disimpan hingga 30 hari, dan memindahkan pembacaan jawaban ke Google. Panduan ini mengikuti sumber yang paling baru, yaitu teks pernyataan yang Anda setujui di aplikasi (versi 3 Oktober 2026).

## WhatsApp

Pesan WhatsApp melewati server Meta, termasuk di Amerika Serikat, sebelum sampai ke Asisten JUP. Setelah itu, jawabannya disusun dengan alur yang sama seperti obrolan tertulis. Jawaban yang memuat materi terbatas hanya dikirim sebagai tautan ke aplikasi. Lihat [Mengapa Konten Terbatas Tidak Dikirim ke WhatsApp](mengapa-konten-terbatas-tidak-dikirim-ke-whatsapp-teams.md).

## Siapa yang dapat membaca obrolan Anda

- Admin None-JUPe tidak dapat membuka obrolan staf dari aplikasi.
- Pengelola sistem yang memiliki akses langsung ke basis data secara teknis dapat membaca isinya.
- Pengguna lain tidak dapat melihat obrolan, memori, atau berkas buatan asisten milik Anda, kecuali Anda membagikan obrolan itu sendiri.
- Setiap percakapan dicatat dalam log audit (diterima, dikecualikan, atau ditolak). Untuk panggilan suara, log audit mencatat ukuran dan hasil, bukan isi.
