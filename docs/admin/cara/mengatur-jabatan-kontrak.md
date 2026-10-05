# Mengatur Jabatan untuk akses Kartu Kontrak

Langkah untuk menentukan siapa yang dapat membaca Kartu Kontrak, nilai kontrak, teks lengkap, dan nama pihak perorangan.

## Cara kerja

Akses kontrak hanya berasal dari satu sumber: kolom **Jabatan** di **Panel Admin → Pengguna** ([`backend/jup/contracts/titles.py`](../../../backend/jup/contracts/titles.py)). Setiap pengguna memegang paling banyak satu Jabatan. Setiap Jabatan adalah grup terkelola dengan nama `Kontrak — <Jabatan>`, dan grant `jup.contracts.*`-nya ditetapkan di kode, bukan di editor grup.

| Jabatan | `cards` | `money` | `fulltext` | `names` | `review` |
| ------- | :-----: | :-----: | :--------: | :-----: | :------: |
| Staff   |   ya    |    –    |     –      |    –    |    –     |
| Manager |   ya    |   ya    |     –      |    –    |    –     |
| Legal   |   ya    |   ya    |     ya     |   ya    |    ya    |
| Direksi |   ya    |   ya    |     ya     |   ya    |    –     |

Arti setiap grant:

- `cards`: membaca kartu kontrak, tanpa kolom nilai.
- `money`: nilai, pembayaran, denda, dan batas ganti rugi.
- `fulltext`: teks OCR semua halaman dan PDF kontrak.
- `names`: nama asli pihak perorangan ditampilkan di layar setelah jawaban. Model **tidak pernah** membaca nama perorangan; setiap kartu dan halaman yang dikirim ke model sudah disamarkan untuk semua pembaca, termasuk Legal ([`backend/jup/contracts/access.py`](../../../backend/jup/contracts/access.py)).
- `review`: antrean tinjauan Kartu Kontrak (Tim Legal).

Asisten menjawab dari kartu mana pun, baik yang sudah disetujui Tim Legal maupun yang masih draf, dan setiap jawaban menyebutkan status kartunya (keputusan D1, dicatat di [`access.py`](../../../backend/jup/contracts/access.py)).

**Admin bukan Jabatan.** Admin tanpa Jabatan tidak melihat kartu kontrak. Admin dapat diberi Jabatan seperti pengguna lain bila memang perlu.

## Langkah

1. Buka **Panel Admin → Pengguna**, tab **Overview**.
2. Cari pengguna. Kolom **Jabatan** berada di sebelah kolom **Peran**.
3. Pilih salah satu: **Direksi**, **Legal**, **Manager**, **Staff**, atau **Tanpa jabatan**.
4. Tunggu notifikasi **Jabatan diperbarui**. Jika muncul pesan gagal, pilihan dikembalikan ke nilai sebelumnya; ulangi atau periksa log.
5. Minta pengguna memulai **Obrolan Baru** agar asisten membaca akses yang baru.

Memilih Jabatan memindahkan pengguna antara keempat grup sehingga ia tersisa di satu grup saja. Setiap perubahan dicatat sebagai baris audit `contract_title` dengan nilai sebelum dan sesudah ([`backend/open_webui/routers/jup_contracts.py`](../../../backend/open_webui/routers/jup_contracts.py)).

## Hal yang perlu diperhatikan

- **Jangan mengubah grup `Kontrak — …` dengan tangan.** Grup terkelola dikenali dari penanda `jup_contract_title` di datanya, bukan dari namanya. Subtree `jup.contracts` dipulihkan ke nilai kode setiap kali Jabatan berpindah. Grant lain yang Anda tambahkan ke grup itu tidak disentuh.
- Jika kolom **Jabatan** menampilkan tanda `+1` (atau angka lain), pengguna tercatat di lebih dari satu grup Jabatan karena grup diubah dengan tangan. Pilih Jabatan yang benar sekali lagi; pengguna akan tersisa di satu grup.
- Tanpa Jabatan, asisten menjawab bahwa akses kartu kontrak belum diberikan dan bahwa admin menetapkannya lewat kolom Jabatan.
- Akses per unit untuk Manager (teks lengkap kontrak unitnya sendiri) belum tersedia karena aplikasi belum memiliki data unit (keputusan D4, disebut di [`access.py`](../../../backend/jup/contracts/access.py)).
