# Referensi alat (tool) JUP

Daftar alat yang dapat dipanggil Asisten JUP, siapa yang dapat memakainya, dan Risk Class-nya menurut kebijakan alat.

## Risk Class

Setiap alat memiliki satu Risk Class ([ADR-0013](../../adr/0013-risky-tool-calls-need-the-asking-user-to-approve.md), [`backend/jup/tool_policy.py`](../../../backend/jup/tool_policy.py)):

| Class       | Arti                                                                                                                                              | Perlakuan                                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `read`      | Hanya membaca                                                                                                                                     | Langsung berjalan; dicatat di audit                                                                                |
| `write_own` | Menulis di dalam JUP, terbatas pada data milik pengguna sendiri                                                                                   | Langsung berjalan; dicatat di audit                                                                                |
| `external`  | Berdampak di luar ruang pengguna: jaringan keluar, mengirim, mengisi formulir, perintah terminal, menulis ke data bersama atau data pengguna lain | **Berhenti untuk persetujuan pengguna yang bertanya**, satu panggilan setiap kali; ditolak di jalur tanpa pengguna |

Aturan penentuan class:

1. Alat JUP menyatakan class-nya sendiri di frontmatter berkasnya (`risk_class: read`). `deploy/gcp/sync-tools.ts` menolak memasukkan alat tanpa class yang sah.
2. Alat bawaan Open WebUI diklasifikasikan di tabel `BUILTIN_CLASSES` di `tool_policy.py`.
3. Alat lain yang tidak diklasifikasikan (alat bawaan baru, server alat, terminal) diperlakukan sebagai `external`.
4. Untuk server MCP, admin menetapkan class pada koneksi server alat: `config.jup_risk_class` untuk semua alatnya, dan `config.jup_tool_risk_classes` untuk mengecualikan satu alat. Server yang tidak diklasifikasikan bernilai `external`. Hanya admin yang dapat mengubah class.

## Alat JUP

Sumber alat ada di folder `tools/` dan logikanya di `backend/jup/`. Berkas di `tools/` hanya pembungkus tipis; pemeriksaan akses dilakukan di modul `backend/jup/`, sebelum data apa pun sampai ke model.

| Alat (id)          | Fungsi                                                                                                                            | Risk Class  | Siapa yang dapat memakai                                                                                                        | Sumber logika                                                   |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `portfolio_status` | Gate saat ini, hambatan, engagement, dan angka berlabel tier untuk proyek JUP, dihitung dari catatan penilaian gate               | `read`      | Peran `admin` saja; pengguna lain menerima penolakan yang harus disampaikan apa adanya                                          | [`portfolio_tool.py`](../../../backend/jup/portfolio_tool.py)   |
| `jup_contracts`    | Mencari dan membaca Kartu Kontrak, dan halaman OCR bila diizinkan (`search_contracts`, `get_contract`, `read_contract_pages`)     | `read`      | Pengguna dengan Jabatan; isi yang dikembalikan mengikuti grant `jup.contracts.*`; nama perorangan selalu disamarkan untuk model | [`contracts/tool.py`](../../../backend/jup/contracts/tool.py)   |
| `jup_leadership`   | Membaca tampilan Ruang Pimpinan (Board, RKA) beserta sumber slide (`read_ruang_pimpinan`)                                         | `read`      | Pengguna dengan grant `jup.ruang_pimpinan.*` untuk tampilan dan cakupan; admin tanpa grant ditolak                              | [`leadership/tool.py`](../../../backend/jup/leadership/tool.py) |
| `jup_documents`    | Membuat draf Word pada templat JUP, workbook Excel, dan presentasi PowerPoint pada templat JUP                                    | `write_own` | Pengguna yang ditawari alat ini; berkas dimiliki pengguna yang bertanya dan hanya dapat diunduh olehnya atau admin              | [`office_tool.py`](../../../backend/jup/office_tool.py)         |
| `notion`           | Mencari dan membaca halaman Notion yang dibagikan ke integrasi JUP (`search_notion`, `read_notion_page`); tidak menyimpan apa pun | `read`      | Peran `admin` saja                                                                                                              | [`notion.py`](../../../backend/jup/notion.py)                   |
| `gate_probe`       | Alat uji yang hanya mengembalikan argumennya, untuk membuktikan gerbang persetujuan masih bekerja                                 | `external`  | Peran `admin` saja                                                                                                              | [`gate_probe.py`](../../../backend/jup/gate_probe.py)           |

Catatan:

- **Batas klasifikasi berkas.** Percakapan yang sudah membaca nilai kontrak atau teks lengkap kontrak membuat setiap berkas yang dibuat `jup_documents` di percakapan itu minimal berlabel TERBATAS ([`office_floor.py`](../../../backend/jup/office_floor.py)). Jika label tidak dapat dibaca, berkas tidak dibuat.
- **Grant alat bukan alat default.** Alat yang dapat dipilih pengguna belum tentu dipakai model secara otomatis. Lihat [cara/mengubah-model-default-dan-alat.md](../cara/mengubah-model-default-dan-alat.md).
- Riwayat penambahan alat ke model Asisten JUP dan model suara dicatat di `PROGRESS.md`; konfigurasi yang berlaku ada di database produksi, bukan di repo.

## Alat bawaan Open WebUI yang berclass `external`

Alat bawaan berikut meminta persetujuan pengguna setiap kali dipanggil ([`tool_policy.py`](../../../backend/jup/tool_policy.py), `BUILTIN_CLASSES`):

| Alat                                                                      | Alasan                                                            |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `fetch_url`                                                               | Mengambil URL apa pun yang dipilih model                          |
| `generate_image`, `edit_image`                                            | Prompt dikirim ke penyedia gambar di luar jalur model yang diatur |
| `write_note`, `replace_note_content`                                      | Dapat mengubah catatan yang dibagikan pengguna lain               |
| `create_calendar_event`, `update_calendar_event`, `delete_calendar_event` | Dapat mengubah kalender yang dibagikan pengguna lain              |

`search_web` adalah pengecualian bernama dan berclass `read`. `execute_code` berclass `read` karena kode berjalan di browser pengguna (Pyodide). `kb_exec` sengaja tidak diklasifikasikan karena dinonaktifkan di deployment ini.

## Jalur tanpa pengguna

Di otomasi, chat `channel:`, giliran kanal WhatsApp/Teams, dan subagent, tidak ada orang yang dapat menyetujui. Panggilan `external` di jalur ini selalu ditolak dengan alasan `rejected_unattended`, dan subagent bahkan tidak ditawari alat `external`.
