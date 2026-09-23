# Asisten JUP — catatan untuk staf: Memori

> Keputusan Erik, 2026-09-23: fitur Memori **tetap aktif** untuk staf, **tanpa tinjauan latar
> belakang**. Catatan ini menjelaskan apa artinya bagi Anda.

## Apa itu Memori

Memori adalah catatan pendek tentang Anda (misalnya "saya menangani proyek SPBG" atau "jawab dalam
bahasa Indonesia") yang disimpan agar Asisten JUP tidak perlu diberi tahu ulang di setiap
percakapan. Memori milik Anda hanya dipakai dalam percakapan Anda sendiri.

## Cara kerjanya

- **Aktif secara bawaan.** Anda bisa mematikannya kapan saja di **Pengaturan → Personalisasi →
  Memori**. Di sana juga Anda bisa melihat, menambah, mengubah, dan menghapus semua memori Anda.
- **Asisten bisa menulis memori sendiri** selama percakapan: menyimpan hal baru, memperbarui, atau
  menghapus memori, jika menurutnya itu relevan. Periksa daftar memori Anda sesekali.
- **Tidak ada tinjauan latar belakang.** Tidak ada proses otomatis yang membaca ulang percakapan
  Anda setelah selesai untuk mengekstrak memori. Memori hanya tercipta saat Anda sedang
  bercakap dengan asisten, atau saat Anda menambahkannya sendiri.
- **Asisten juga bisa mencari riwayat percakapan Anda sendiri** jika relevan. Riwayat percakapan
  staf lain tidak bisa diakses.

## Di mana datanya disimpan

Memori disimpan di database JUP sendiri (Cloud SQL, region Jakarta `asia-southeast2`) dan tidak
dikirim ke layanan pihak ketiga mana pun untuk disimpan. Saat memori dipakai dalam percakapan,
isinya ikut terkirim ke model AI bersama pesan Anda, sama seperti isi percakapan itu sendiri.
Administrator sistem yang memiliki akses database secara teknis dapat membacanya.

## Yang jangan disimpan sebagai memori

- Kata sandi, token, atau kredensial apa pun.
- Syarat komersial yang belum dirilis, angka negosiasi, atau informasi rahasia pihak mitra.
- Data pribadi orang lain.

Jika asisten menyimpan hal seperti ini, hapus memori itu di **Personalisasi → Memori**.
