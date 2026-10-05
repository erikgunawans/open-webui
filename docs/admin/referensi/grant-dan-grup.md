# Referensi grant dan grup

Daftar semua grant `jup.*`, artinya, dan cara memberikannya.

## Aturan umum

- Semua grant bernilai `false` secara default (`DEFAULT_PERMISSIONS` di setiap modul).
- Grant hanya berlaku jika bernilai boolean `true` persis. Teks `"true"` atau angka `1` dianggap penolakan.
- Grant dari beberapa grup digabung dengan "atau".
- Peran `admin` tidak memberi grant apa pun.
- Grant `jup.*` tidak tampil di editor grup, tetapi tidak terhapus saat grup disimpan. Cara menulisnya ada di [cara/mengelola-grup-dan-grant.md](../cara/mengelola-grup-dan-grant.md).

## Ruang Pimpinan — `jup.ruang_pimpinan`

Sumber: [`backend/jup/leadership/policy.py`](../../../backend/jup/leadership/policy.py).

| Grant                                        | Membuka                                                                    | Syarat tambahan                                                                  |
| -------------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `jup.ruang_pimpinan.board.view`              | Tampilan Board (Direksi & Komisaris)                                       | `scopes.jup_consolidated`                                                        |
| `jup.ruang_pimpinan.rka.view`                | Tampilan RKA (RKA & Realisasi), termasuk tab KPI 2026                      | `scopes.jup_consolidated`                                                        |
| `jup.ruang_pimpinan.scopes.jup_consolidated` | Cakupan pelaporan JUP konsolidasi (satu-satunya cakupan saat ini)          | harus dipasangkan dengan salah satu `view`                                       |
| `jup.ruang_pimpinan.actions.submit`          | Mengirim progres dan bukti untuk tindak lanjut yang PIC-nya pengguna itu   | grant baca tampilan                                                              |
| `jup.ruang_pimpinan.actions.assign`          | Menetapkan PIC tindak lanjut                                               | grant baca tampilan                                                              |
| `jup.ruang_pimpinan.bod.review`              | Ikut memutuskan penutupan, pengembalian, dan pembukaan ulang tindak lanjut | grant baca tampilan **dan** `JUP_LEADERSHIP_BOD_POLICY` (belum dipasang)         |
| `jup.ruang_pimpinan.snapshots.publish`       | Membekukan tampilan menjadi draf rapat dan menerbitkannya                  | grant baca tampilan **dan** `JUP_LEADERSHIP_PUBLICATION_POLICY` (belum dipasang) |
| `jup.ruang_pimpinan.imports.review`          | Mengunggah berkas kandidat dari deck dan memproses antrean impor           | grant baca tampilan                                                              |

Contoh grup pembaca Board saja:

```json
{
	"jup": { "ruang_pimpinan": { "board": { "view": true }, "scopes": { "jup_consolidated": true } } }
}
```

Tanpa grant, admin pun mendapat **403**. Setiap kemampuan tambahan tidak pernah membuka tampilan yang tidak dapat dibaca pengguna. Asisten JUP (alat `jup_leadership`) memeriksa grant yang sama pada setiap panggilan.

## Kartu Kontrak — `jup.contracts`

Sumber: [`backend/jup/contracts/titles.py`](../../../backend/jup/contracts/titles.py), [`access.py`](../../../backend/jup/contracts/access.py). **Jangan diberikan dengan tangan**; pilih **Jabatan** di **Panel Admin → Pengguna** ([cara/mengatur-jabatan-kontrak.md](../cara/mengatur-jabatan-kontrak.md)).

| Grant                    | Membuka                                    | Jabatan yang memegang          |
| ------------------------ | ------------------------------------------ | ------------------------------ |
| `jup.contracts.cards`    | Kartu kontrak tanpa kolom nilai            | Staff, Manager, Legal, Direksi |
| `jup.contracts.money`    | Nilai, pembayaran, denda, batas ganti rugi | Manager, Legal, Direksi        |
| `jup.contracts.fulltext` | Teks OCR dan PDF kontrak                   | Legal, Direksi                 |
| `jup.contracts.names`    | Nama asli pihak perorangan, hanya di layar | Legal, Direksi                 |
| `jup.contracts.review`   | Antrean tinjauan Kartu Kontrak             | Legal                          |

## Basis Pengetahuan — `jup.kb`

Sumber: [`backend/jup/kb_review.py`](../../../backend/jup/kb_review.py).

| Grant           | Membuka                                                                           |
| --------------- | --------------------------------------------------------------------------------- |
| `jup.kb.submit` | Mengajukan dokumen di **Tinjauan Pengetahuan**. Meninjau tetap hak peran `admin`. |

## Suara — `jup.voice`

Sumber: [`backend/jup/voice.py`](../../../backend/jup/voice.py), [ADR-0017](../../adr/0017-voice-is-a-chained-pipeline-that-speaks-our-exact-answer.md), [ADR-0018](../../adr/0018-gpt-live-is-an-opt-in-second-call-mode.md).

| Grant            | Membuka                        | Syarat tambahan                                                                                                                   |
| ---------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `jup.voice.call` | Panggilan suara (mode default) | `JUP_VOICE_ENABLED=true`; akses baca ke model `asisten-jup-suara`; pengguna menyetujui pemberitahuan suara saat panggilan pertama |
| `jup.voice.live` | Mode GPT-Live (pilihan kedua)  | `jup.voice.call` juga harus `true`; pemberitahuan GPT-Live terpisah                                                               |

Izin bawaan Open WebUI `chat.call` tidak dihitung sebagai gerbang suara.

## Kanal — `jup.channel`

Sumber: [`backend/jup/channel.py`](../../../backend/jup/channel.py).

| Grant             | Membuka                                                                             | Syarat tambahan                                   |
| ----------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------- |
| `jup.channel.use` | Bertanya dari WhatsApp atau Teams, dan bagian **WhatsApp** di **Pengaturan → Akun** | `JUP_CHANNELS_ENABLED=true`; akun bukan `pending` |

## Hak yang berasal dari peran, bukan grant

| Hak                                                                 | Syarat                            | Sumber                                                                                                                       |
| ------------------------------------------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Status gate portofolio (halaman Portfolio, alat `portfolio_status`) | Peran `admin` (_operating layer_) | [`backend/jup/portfolio_tool.py`](../../../backend/jup/portfolio_tool.py)                                                    |
| Meninjau pengajuan pengetahuan                                      | Peran `admin`                     | [`backend/jup/kb_review.py`](../../../backend/jup/kb_review.py)                                                              |
| Mengatur Jabatan dan impor kontrak                                  | Peran `admin`                     | [`backend/open_webui/routers/jup_contracts.py`](../../../backend/open_webui/routers/jup_contracts.py)                        |
| Alat `notion` dan `gate_probe`                                      | Peran `admin`                     | [`backend/jup/notion.py`](../../../backend/jup/notion.py), [`backend/jup/gate_probe.py`](../../../backend/jup/gate_probe.py) |

## Grup yang dikelola aplikasi

| Grup                                                                           | Dikenali dari                                            | Catatan                                                                                                                  |
| ------------------------------------------------------------------------------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `Kontrak — Direksi`, `Kontrak — Legal`, `Kontrak — Manager`, `Kontrak — Staff` | Penanda `jup_contract_title` di data grup, bukan namanya | Dibuat dan diisi oleh kolom **Jabatan**. Subtree `jup.contracts` dipulihkan ke nilai kode setiap kali Jabatan berpindah. |

Grup lain (misalnya pembaca Ruang Pimpinan, pengaju pengetahuan, penguji suara, penguji kanal) dibuat oleh admin. Tuliskan grant yang dipegang setiap grup di kolom **Deskripsi**, karena grant `jup.*` tidak terlihat di editor grup.
