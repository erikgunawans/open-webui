# Model tata kelola None-JUPe

Penjelasan mengapa None-JUPe menolak secara default, siapa yang menyetujui panggilan alat berisiko, dan apa yang dicatat di log audit.

## Prinsip: menolak bila ragu (fail-closed)

Setiap fitur JUP tertutup sampai dibuka dengan sengaja: grant bernilai `false` secara default, alat tanpa class dianggap `external`, dan permintaan model yang tidak membawa kontrak operasional ditolak. Kesalahan konfigurasi menghasilkan akses yang **kurang**, bukan berlebih. Contohnya, grant yang salah ketik sebagai teks `"true"` dibaca sebagai penolakan, bukan sebagai izin.

## Setiap giliran model membawa kontrak operasional JUP

Keputusan: [ADR-0002](../../adr/0002-fail-closed-attaches-at-generate-chat-completion.md). Implementasi: [`backend/jup/governance.py`](../../../backend/jup/governance.py).

- **Kebijakannya:** giliran percakapan yang diatur harus membawa kontrak operasional JUP di pesan sistemnya, atau ditolak.
- **Tempatnya:** di `generate_chat_completion`, satu-satunya jalur di dalam aplikasi menuju setiap penyedia model, termasuk setiap putaran dalam loop alat. Kontrak dipasang ulang pada setiap putaran, sehingga kontrak yang terhapus di tengah loop dipulihkan pada putaran berikutnya.
- **Mengapa tidak memakai filter atau pipeline Open WebUI:** semua titik ekstensi bawaan dapat dimatikan admin, gagal terbuka saat error, atau berjalan setelah jawaban terkirim. Kontrol yang harus mencegah keluaran harus menolak permintaan, bukan memperbaiki jawaban.
- **Rute langsung ke penyedia** (passthrough OpenAI/Ollama) yang tidak melewati jalur itu ditolak seluruhnya.
- **Batasnya:** kontrol ini hanya memeriksa permintaan. Jawaban yang sudah mengalir ke layar tidak dapat dihentikan.

Pembuatan internal seperti judul, tag, dan saran lanjutan dikecualikan melalui daftar yang diuji, dan pengecualian itu hanya berlaku untuk giliran yang ditandai oleh aplikasi sendiri.

## Panggilan alat berisiko disetujui oleh pengguna yang bertanya

Keputusan: [ADR-0013](../../adr/0013-risky-tool-calls-need-the-asking-user-to-approve.md). Implementasi: [`backend/jup/tool_policy.py`](../../../backend/jup/tool_policy.py), [`backend/jup/approval.py`](../../../backend/jup/approval.py).

Mode persetujuan bawaan Open WebUI (`ask`) adalah preferensi pengguna: dapat dimatikan pengguna sendiri, dilewati di otomasi dan kanal, dan catatannya ada di chat yang dapat dihapus. None-JUPe menambahkan gerbang di server yang tidak dapat dimatikan:

1. **Setiap alat memiliki Risk Class**: `read`, `write_own`, atau `external`. Daftarnya ada di [referensi/alat-jup.md](../referensi/alat-jup.md).
2. **Panggilan `external` selalu berhenti** untuk persetujuan, apa pun mode persetujuan chat-nya.
3. **Yang menyetujui adalah pengguna yang bertanya**, satu panggilan setiap kali. Tidak ada "izinkan untuk chat ini" atau "selalu izinkan". Kartu persetujuan menampilkan argumen lengkap panggilan, dengan nilai yang tampak rahasia disamarkan.
4. **Tanpa jawaban dalam 10 menit**, panggilan ditolak sebagai `timed_out`, dan model diberi tahu.
5. **Di jalur tanpa pengguna** (otomasi, kanal, subagent) panggilan `external` ditolak sebagai `rejected_unattended`.

Admin tidak menyetujui atas nama staf. Peran admin dalam hal ini adalah menetapkan Risk Class untuk server MCP dan tidak mengubah class alat tanpa peninjauan.

## Akses diperiksa di kode, sebelum model membaca apa pun

Alat JUP memeriksa peran dan grant pemanggil di modul `backend/jup/`, lalu menyaring dan menyamarkan data **sebelum** data dikirim ke model. Model tidak pernah diminta "menjaga rahasia". Contoh:

- Kartu kontrak tanpa grant `money` dikirim tanpa kolom nilai.
- Nama pihak perorangan selalu diganti kode ("Perorangan A") untuk model, bahkan bagi pembaca Legal; nama asli hanya ditampilkan di layar untuk pembaca yang berhak.
- Docstring alat sengaja tidak memuat aturan identitas. Aturan seperti "hanya untuk admin" di docstring membuat model menolak sendiri dan tidak dapat diuji atau diaudit.

## Admin bukan Direksi

Peran `admin` adalah _operating layer_: mengelola aplikasi, menyetujui akun, meninjau pengajuan, dan membaca status gate. Peran ini tidak mewakili keanggotaan BOD atau BOC, sehingga tidak membuka Ruang Pimpinan, Kartu Kontrak, atau percakapan staf ([README](../README.md#yang-dapat-dan-tidak-dapat-dilakukan-admin)). Penolakan untuk akun yang sudah login selalu 403.

## Log audit `jup.governance`

Setiap keputusan tata kelola menulis satu baris audit, baik yang diizinkan, dikecualikan, maupun ditolak. Penolakan yang tidak meninggalkan jejak tidak dapat dibedakan dari permintaan yang tidak pernah terjadi.

**Lokasi:** baris audit dikirim ke logger aplikasi dengan awalan `jup.governance` dan dapat dicari di Cloud Logging untuk service `ent-os`. Jejak berkas JSONL hanya ditulis jika `JUP_GOVERNANCE_AUDIT` atau `DATA_DIR` dipasang; `deploy.sh` tidak memasang keduanya ([`governance.py`](../../../backend/jup/governance.py), fungsi `audit_path`).

Jenis baris yang umum:

| Event                             | Kapan                                         | Isi penting                                                                                                                                                                                                                         |
| --------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `admitted` / `exempt` / `refused` | Setiap giliran model                          | Pengguna, chat, hasil                                                                                                                                                                                                               |
| `tool_call`                       | Setiap panggilan alat                         | Nama alat, **ukuran** argumen (bukan isinya), hasil (`ok`, `error`, `refused`, `not_found`, `unparsed`), `approval` (`approved`, `rejected`, `timed_out`, `rejected_unattended`, `not_required`), `approved_by`, `approval_wait_ms` |
| `contract_title`                  | Jabatan diubah                                | Admin, pengguna sasaran, nilai sebelum dan sesudah                                                                                                                                                                                  |
| `kb_review`                       | Ajukan, setujui, tolak                        | ID dan hasil, tanpa isi dokumen, catatan, atau alasan                                                                                                                                                                               |
| `leadership_read`                 | Ruang Pimpinan dibaca, termasuk lewat asisten | ID saja                                                                                                                                                                                                                             |
| `channel_turn`                    | Giliran dari WhatsApp/Teams                   | Hash identitas dan percakapan, chat; tanpa email atau nomor telepon                                                                                                                                                                 |

Prinsip isi audit: **ID dan hasil, bukan konten.** Argumen alat, isi dokumen, dan alasan penolakan tidak disalin ke log, karena log dibaca lebih luas daripada chat asalnya.

**Membaca audit untuk diagnosis:** baris `admitted` tanpa baris `tool_call` pada giliran yang sama berarti model memilih tidak memanggil alat, bukan alatnya hilang.

## Bacaan lanjutan

- [ADR-0002](../../adr/0002-fail-closed-attaches-at-generate-chat-completion.md) — tempat kontrol fail-closed dipasang
- [ADR-0012](../../adr/0012-iap-as-the-login.md) — IAP sebagai login, admin dari daftar email
- [ADR-0013](../../adr/0013-risky-tool-calls-need-the-asking-user-to-approve.md) — persetujuan alat berisiko
- [ADR-0015](../../adr/0015-staff-contributions-are-a-separate-reviewed-collection.md) — kontribusi staf yang ditinjau
- [`deploy/gcp/VENDOR-PATCHES.md`](../../../deploy/gcp/VENDOR-PATCHES.md) — setiap tambalan pada kode Open WebUI dan alasannya
- [docs/architecture/13-fe-admin-GOVERNANCE.md](../../architecture/13-fe-admin-GOVERNANCE.md) — peta kode panel admin
