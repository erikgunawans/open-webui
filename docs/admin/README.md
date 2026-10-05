# Panduan Admin dan TI JUP — None-JUPe

Panduan ini untuk admin None-JUPe (`https://non-jupe.jup.co.id`) dan TI JUP: cara mengelola pengguna, hak akses, Basis Pengetahuan, dan kanal, beserta alasan di balik aturannya.

None-JUPe adalah asisten AI PT JUP yang dibangun di atas fork Open WebUI (repo `ent-os-new-jup`). Aplikasi berjalan di Cloud Run, di belakang load balancer dengan IAP, dan staf masuk dengan akun Microsoft 365 melalui Identity Platform ([ADR-0012](../adr/0012-iap-as-the-login.md), [ADR-0016](../adr/0016-jup-staff-sign-in-with-entra-through-identity-platform.md)).

## Isi panduan

Panduan disusun menurut tiga jenis dokumen: langkah kerja, referensi, dan penjelasan.

### Cara (langkah kerja)

| Tugas                                                   | Dokumen                                                                                          |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Menyetujui pengguna baru (`pending` → `user`)           | [cara/menyetujui-pengguna-baru.md](cara/menyetujui-pengguna-baru.md)                             |
| Mengelola grup dan grant `jup.*`                        | [cara/mengelola-grup-dan-grant.md](cara/mengelola-grup-dan-grant.md)                             |
| Mengatur Jabatan untuk akses Kartu Kontrak              | [cara/mengatur-jabatan-kontrak.md](cara/mengatur-jabatan-kontrak.md)                             |
| Meninjau pengajuan Basis Pengetahuan                    | [cara/meninjau-pengajuan-pengetahuan.md](cara/meninjau-pengajuan-pengetahuan.md)                 |
| Mengubah model default dan alat Asisten JUP             | [cara/mengubah-model-default-dan-alat.md](cara/mengubah-model-default-dan-alat.md)               |
| Memperbarui Basis Pengetahuan strategi                  | [cara/memperbarui-basis-pengetahuan-strategi.md](cara/memperbarui-basis-pengetahuan-strategi.md) |
| Mengaktifkan kanal WhatsApp dan Teams                   | [cara/mengaktifkan-kanal-whatsapp-teams.md](cara/mengaktifkan-kanal-whatsapp-teams.md)           |
| Sign-in Entra melalui Identity Platform (bagian TI JUP) | [cara/sign-in-entra.md](cara/sign-in-entra.md)                                                   |

### Referensi

| Topik                                       | Dokumen                                                            |
| ------------------------------------------- | ------------------------------------------------------------------ |
| Daftar grant dan grup                       | [referensi/grant-dan-grup.md](referensi/grant-dan-grup.md)         |
| Daftar alat (tool) JUP dan Risk Class-nya   | [referensi/alat-jup.md](referensi/alat-jup.md)                     |
| Pengaturan penting (env key di `deploy.sh`) | [referensi/pengaturan-penting.md](referensi/pengaturan-penting.md) |

### Penjelasan

| Topik                                                            | Dokumen                                                                        |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Model tata kelola: fail-closed, persetujuan alat berisiko, audit | [penjelasan/model-tata-kelola.md](penjelasan/model-tata-kelola.md)             |
| Batas 50 pengguna dan lokasi data                                | [penjelasan/lisensi-dan-lokasi-data.md](penjelasan/lisensi-dan-lokasi-data.md) |

Untuk detail teknis kode, lihat [docs/architecture/](../architecture/README.md) (khususnya [13-fe-admin-GOVERNANCE.md](../architecture/13-fe-admin-GOVERNANCE.md)) dan keputusan arsitektur di [docs/adr/](../adr/).

## Dari mana peran admin berasal

Peran `admin` tidak dipilih di layar. Peran ini ditetapkan oleh daftar email di env key `JUP_ADMIN_EMAILS`, yang diisi oleh [`deploy/gcp/deploy.sh`](../../deploy/gcp/deploy.sh) ([ADR-0012](../adr/0012-iap-as-the-login.md)).

- Daftar berisi alamat email yang dipisahkan koma, dibaca tanpa membedakan huruf besar dan kecil ([`backend/jup/admin_allowlist.py`](../../backend/jup/admin_allowlist.py)).
- Peran ditetapkan saat permintaan masuk, bukan saat aplikasi mulai. Akibatnya, orang yang baru ditambahkan ke daftar dan belum pernah login tetap menjadi `admin` pada login pertamanya.
- Mengubah daftar berarti deploy ulang (revisi Cloud Run baru).
- **Menghapus alamat dari daftar tidak menurunkan peran.** Aplikasi tidak pernah menurunkan admin secara otomatis. Penurunan peran dilakukan dengan sengaja di **Panel Admin → Pengguna**, lalu alamatnya dihapus dari `JUP_ADMIN_EMAILS` agar tidak dipromosikan lagi.

Pengguna baru selalu dibuat dengan peran `pending` (`DEFAULT_USER_ROLE: "pending"` di `deploy.sh`). Lolos IAP dan memegang peran admin sengaja dipisahkan.

## Yang dapat dan tidak dapat dilakukan admin

Peran `admin` adalah _operating layer_ aplikasi, bukan Direksi atau BOD. Admin mengelola aplikasi, tetapi tidak otomatis membaca materi pimpinan, kontrak, atau percakapan staf.

### Admin dapat

- Menyetujui akun baru dan mengubah peran pengguna.
- Membuat grup, mengatur anggota, dan memberikan grant `jup.*` kepada grup.
- Memilih **Jabatan** setiap pengguna, yang menentukan akses Kartu Kontrak.
- Meninjau pengajuan dokumen staf di **Tinjauan Pengetahuan** (`/kb-review`). Meninjau adalah hak peran `admin` ([ADR-0015](../adr/0015-staff-contributions-are-a-separate-reviewed-collection.md)).
- Membaca status gate portofolio (`portfolio_status`, halaman Portfolio) dan memakai alat khusus admin (`notion`, `gate_probe`).
- Mengubah konfigurasi model, alat, dan Risk Class server MCP.

### Admin tidak dapat (tanpa grant tambahan)

| Hal                                                    | Alasan                                                                                                                                                                                                           | Sumber                                                                                                                                                  |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Membuka Ruang Pimpinan                                 | Perlu grant eksplisit `jup.ruang_pimpinan.*` untuk tampilan dan cakupan. Peran admin tidak memberi akses apa pun; penolakan berupa **403**.                                                                      | [`backend/jup/leadership/policy.py`](../../backend/jup/leadership/policy.py), [`jup_leadership.py`](../../backend/open_webui/routers/jup_leadership.py) |
| Melihat Kartu Kontrak                                  | Admin bukan Jabatan. Admin tanpa Jabatan tidak melihat kartu kontrak.                                                                                                                                            | [`backend/jup/contracts/titles.py`](../../backend/jup/contracts/titles.py)                                                                              |
| Membuka percakapan staf                                | `ENABLE_ADMIN_CHAT_ACCESS: "false"` di `deploy.sh`. Halaman chat memberi tahu pengguna bahwa percakapan tersimpan di riwayat mereka sendiri; mengaktifkan kembali pengaturan ini membuat teks itu tidak lengkap. | [`deploy/gcp/deploy.sh`](../../deploy/gcp/deploy.sh)                                                                                                    |
| Mengajukan dokumen ke Basis Pengetahuan                | Mengajukan memerlukan grant `jup.kb.submit`; peran admin tidak mencakupnya.                                                                                                                                      | [ADR-0015](../adr/0015-staff-contributions-are-a-separate-reviewed-collection.md)                                                                       |
| Memakai panggilan suara atau kanal WhatsApp/Teams      | Memerlukan grant `jup.voice.call` / `jup.voice.live` / `jup.channel.use`.                                                                                                                                        | [`backend/jup/voice.py`](../../backend/jup/voice.py), [`backend/jup/channel.py`](../../backend/jup/channel.py)                                          |
| Menyetujui panggilan alat berisiko milik pengguna lain | Yang menyetujui adalah pengguna yang mengajukan pertanyaan.                                                                                                                                                      | [ADR-0013](../adr/0013-risky-tool-calls-need-the-asking-user-to-approve.md)                                                                             |

Catatan: berkas dokumen yang dibuat alat `jup_documents` hanya dapat diunduh oleh pemiliknya atau oleh admin ([`backend/jup/office_tool.py`](../../backend/jup/office_tool.py)).

### Mengapa 403, bukan 401

Penolakan untuk akun yang sudah login tetapi tidak berhak selalu **403**. Kode 401 berarti "kami tidak tahu siapa Anda" dan akan mengarahkan pengguna ke halaman login yang tidak dapat membantu. Jika Anda melihat 403, akun sudah dikenali; yang kurang adalah peran atau grant.
