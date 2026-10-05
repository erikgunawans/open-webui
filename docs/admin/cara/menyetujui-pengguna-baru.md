# Menyetujui pengguna baru

Langkah untuk mengubah akun baru dari `pending` menjadi `user`, lalu memberinya akses yang sesuai.

## Latar belakang

Staf JUP masuk melalui Microsoft Entra ([sign-in-entra.md](sign-in-entra.md)). Login pertama membuat akun dengan peran `pending` (`DEFAULT_USER_ROLE: "pending"` di [`deploy/gcp/deploy.sh`](../../../deploy/gcp/deploy.sh)). Akun `pending` belum dapat memakai asisten. Dengan identitas eksternal, IAP tidak lagi memeriksa daftar IAM, sehingga persetujuan admin inilah gerbang yang sebenarnya ([ADR-0016](../../adr/0016-jup-staff-sign-in-with-entra-through-identity-platform.md), keputusan 3).

## Sebelum menyetujui

1. Pastikan alamat akun berakhiran `@jakarta-utilitas.com` dan memang milik staf yang dimaksud.
2. Periksa jumlah pengguna aktif. Lisensi Open WebUI membatasi branding putih (white-label) pada **maksimal 50 pengguna dalam 30 hari bergulir** ([ADR-0001](../../adr/0001-fifty-seats-is-a-license-ceiling.md)). Menambah pengguna di atas batas itu adalah keputusan lisensi, bukan keputusan teknis. Lihat [penjelasan/lisensi-dan-lokasi-data.md](../penjelasan/lisensi-dan-lokasi-data.md).

## Langkah

1. Buka menu akun di sidebar, lalu pilih **Panel Admin**.
2. Pilih **Pengguna**. Tab daftar pengguna berlabel **Overview** (label ini belum diterjemahkan).
3. Cari akun baru. Kolom peran menampilkan **tertunda**.
4. Klik label peran **tertunda** pada baris itu. Jendela **Edit Pengguna** terbuka.
5. Pada **Peran**, pilih **User**. Jangan memilih **Admin**: peran admin ditetapkan oleh `JUP_ADMIN_EMAILS`, bukan dari layar ini (lihat [README](../README.md#dari-mana-peran-admin-berasal)).
6. Klik **Simpan**.
7. Pada baris yang sama, isi kolom **Jabatan** jika staf perlu membaca Kartu Kontrak. Lihat [mengatur-jabatan-kontrak.md](mengatur-jabatan-kontrak.md).
8. Tambahkan akun ke grup yang sesuai (misalnya grup pengaju pengetahuan atau grup Ruang Pimpinan). Lihat [mengelola-grup-dan-grant.md](mengelola-grup-dan-grant.md).

## Setelah disetujui

- Akun `user` tanpa grant tambahan dapat bertanya ke Asisten JUP, tetapi tidak dapat membuka Ruang Pimpinan, Kartu Kontrak, panggilan suara, kanal, atau pengajuan pengetahuan. Setiap fitur itu ditolak secara default sampai grant diberikan.
- Minta staf memulai **Obrolan Baru** setelah aksesnya berubah. Model cenderung mempertahankan jawaban penolakan yang sudah ada dalam riwayat percakapan yang sama.

## Menolak atau mencabut akun

- Untuk menolak akun, biarkan perannya **Pending**. Akun itu tetap tidak dapat memakai asisten.
- Untuk mencabut akses staf yang keluar, ubah perannya menjadi **Pending** di **Edit Pengguna** dan keluarkan dari semua grup. TI JUP juga dapat menghapus _assignment_ aplikasi `None-JUPe` di Entra (langkah 6 di [`entra-request-jup-it.id.md`](../../../deploy/gcp/entra-request-jup-it.id.md)).
