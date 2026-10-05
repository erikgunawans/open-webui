# Mengapa Asisten Bisa Menolak

Halaman ini menjelaskan mengapa Asisten JUP kadang menjawab "itu bukan sesuatu yang saya miliki" dan mengapa penolakan itu disengaja.

## Prinsip fail-closed

JUP meminta mitranya memercayai keputusan yang didasarkan pada bukti. None-JUPe memegang disiplin yang sama: kendali yang tidak dapat menghitung atau membuktikan jawabannya harus berhenti, bukan melanjutkan dengan dugaan. Gate proyek yang tidak dapat diverifikasi berarti "tidak". Asisten yang tidak dapat mendasarkan jawabannya pada sumber yang diizinkan menolak menjawab.

Bagi pembaca laporan Direksi, angka yang dikarang lebih berbahaya daripada jawaban "data itu tidak tersedia". Karena itu penolakan adalah jaminannya, bukan kegagalannya.

## Aturan yang mengikat setiap jawaban

Setiap percakapan dengan Asisten JUP membawa kontrak operasional JUP. Percakapan yang tidak membawa kontrak ini ditolak sebelum mencapai model AI. Isi kontraknya:

1. Jangan pernah mengarang angka, nama, tanggal, atau klaim. Jika tidak ada, katakan terus terang.
2. Jangan mencampur tingkat kepastian. Angka rupiah gas adalah potensi **pendapatan**, bukan margin, laba, atau NPV, karena tarif B-to-G ditetapkan pemerintah.
3. Setiap kali pilar gas dibahas, sebutkan bahwa alokasi 5 mmscfd **belum diamankan** (Gate G1). Setiap kali WTP dibahas, sebutkan bahwa _fold-out_-nya masih tertunda.
4. Jangan berspekulasi apakah mitra (SKK Migas, PGN, PLN, Pelindo) akan setuju.
5. Jawab dalam bahasa pengguna, dengan istilah teknis dan bisnis tetap dalam bahasa Inggris.
6. Penolakan adalah fitur, bukan kegagalan.

## Tingkat kepastian angka

Setiap angka tentang JUP berdiri di atas satu dasar:

| Tingkat                    | Dasar                                                          | Cara menyatakannya                                                                 |
| -------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Tingkat 1 · FAKTA**      | Ekonomi kelayakan dari rencana bisnis: NPV, IRR, _payback_.    | Dinyatakan apa adanya dengan dokumen sumbernya.                                    |
| **Tingkat 2 · POTENSI**    | Potensi pendapatan kotor, misalnya angka rupiah gas.           | Selalu disertai "pendapatan, bukan margin".                                        |
| **Tingkat 3 · ILUSTRATIF** | Perkiraan orde besaran dari target kapasitas dan biaya satuan. | Hanya sebagai gambaran skala, selalu berlabel ilustratif, dan memerlukan studi G1. |

Angka dari tingkat berbeda tidak pernah dijumlahkan, dibandingkan, atau diperingkat bersama. Tingkat juga tidak naik hanya karena sebuah dokumen mengulang angka yang sama. Jika asisten tidak yakin tingkat sebuah angka, angka itu tidak dipakai. Menghilangkan angka itu aman; salah memberi label menyesatkan Direksi.

## Bentuk penolakan yang mungkin Anda temui

| Yang Anda lihat                                            | Artinya                                                                                                                      |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Asisten menyatakan tidak memiliki informasinya.            | Jawabannya tidak ada di basis pengetahuan yang boleh dipakai.                                                                |
| "Ditahan: …" pada jawaban kontrak                          | Jabatan kontrak Anda tidak mencakup isian itu.                                                                               |
| "Akses kartu kontrak belum diberikan untuk akun ini."      | Akun Anda belum memiliki jabatan kontrak.                                                                                    |
| Asisten menyampaikan bahwa suatu langkah tidak dijalankan. | Panggilan Eksternal ditolak, tidak disetujui dalam 10 menit, atau diminta di tempat tanpa kartu persetujuan.                 |
| "Refused by JUP governance: …"                             | Percakapan tidak dapat diatur sesuai kontrak, sehingga tidak diteruskan ke model. Laporkan ke admin None-JUPe jika berulang. |

## Yang sebaiknya Anda lakukan

- Jika jawaban yang Anda harapkan ternyata ditolak, perjelas pertanyaannya atau sebutkan dokumen yang Anda maksud.
- Jika dokumen yang dibutuhkan memang belum ada di basis pengetahuan, ajukan lewat [Mengajukan Dokumen ke Basis Pengetahuan](../cara/mengajukan-dokumen-kb.md) bila Anda memiliki akses, atau sampaikan ke admin None-JUPe.
- Setelah sebuah masalah diperbaiki, tanyakan ulang di **obrolan baru**. Di obrolan lama, asisten cenderung mengulang penolakannya sendiri.
- Jangan memaksa asisten menebak. Jawaban tebakan tidak dapat dipertanggungjawabkan.
