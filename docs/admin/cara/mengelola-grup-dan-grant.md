# Mengelola grup dan grant

Langkah untuk membuat grup, mengatur anggotanya, dan memberikan grant `jup.*` yang membuka fitur JUP.

## Cara kerja grant

- Semua fitur JUP **ditolak secara default**. Akses dibuka hanya oleh grant di grup tempat pengguna menjadi anggota.
- Grant dari beberapa grup digabung dengan "atau": cukup satu grup yang memberi grant.
- Grant hanya berlaku jika nilainya boolean `true` persis. Nilai `"true"` (teks) atau `1` **tidak dihitung** dan dianggap penolakan. Ini disengaja: salah ketik di editor grup tidak boleh membuka materi Direksi ([`backend/jup/leadership/policy.py`](../../../backend/jup/leadership/policy.py)).
- Peran `admin` tidak menggantikan grant mana pun.

Daftar lengkap grant ada di [referensi/grant-dan-grup.md](../referensi/grant-dan-grup.md).

## Penting: editor grup tidak menampilkan grant `jup.*`

Tab **Permissions** di editor grup hanya menampilkan izin bawaan Open WebUI (workspace, sharing, chat, features, settings). Grant `jup.*` **tidak muncul di sana**, tetapi tetap tersimpan: editor grup sudah ditambal agar tidak menghapus kunci yang tidak dikelolanya saat Anda menekan **Simpan** atau **Reset to Defaults** ([`deploy/gcp/VENDOR-PATCHES.md`](../../../deploy/gcp/VENDOR-PATCHES.md), bagian "The group editor keeps permission keys it doesn't manage").

Akibatnya:

- Mengatur **anggota** grup dilakukan di layar.
- Menulis **grant `jup.*`** ke grup dilakukan melalui API grup (lihat di bawah), kecuali grant kontrak `jup.contracts.*`, yang diatur otomatis lewat kolom **Jabatan** ([mengatur-jabatan-kontrak.md](mengatur-jabatan-kontrak.md)).

## Membuat grup dan mengatur anggota

1. Buka **Panel Admin → Pengguna**, lalu tab **Groups**.
2. Klik **New Group** (atau tombol **Edit** pada grup yang sudah ada).
3. Di tab **Umum**, isi **Group Name** dan **Deskripsi**. Tulis di deskripsi grant apa yang dipegang grup ini, karena grant `jup.*` tidak terlihat di layar.
4. Di tab **Pengguna**, centang anggota grup.
5. Klik **Simpan**.

## Menulis grant `jup.*` ke grup

Grant ditulis dengan endpoint admin Open WebUI ([`backend/open_webui/routers/groups.py`](../../../backend/open_webui/routers/groups.py)):

| Langkah                      | Endpoint                             |
| ---------------------------- | ------------------------------------ |
| Baca grup saat ini           | `GET /api/v1/groups/id/{id}`         |
| Simpan grup dengan izin baru | `POST /api/v1/groups/id/{id}/update` |

1. Baca grup dan **simpan salinannya** sebagai nilai sebelum perubahan (before-value) untuk rollback.
2. Ambil objek `permissions` dari hasil bacaan, lalu tambahkan subtree `jup` yang diperlukan tanpa menghapus kunci lain. Contoh untuk grup panggilan suara:

   ```json
   { "jup": { "voice": { "call": true, "live": false } } }
   ```

3. Kirim `name`, `description`, dan objek `permissions` yang sudah digabung ke endpoint update. Endpoint ini hanya untuk admin.
4. Baca grup lagi dan pastikan subtree `jup` tersimpan persis, dengan nilai boolean `true`, bukan teks.
5. Minta anggota grup memuat ulang halaman dan memulai **Obrolan Baru**.

Aplikasi berada di belakang IAP, sehingga permintaan API harus dikirim dari sesi browser admin yang sudah login. Perlakukan setiap penulisan grant sebagai perubahan produksi: catat nilai sebelumnya dan siapa yang menyetujui.

## Grant yang memerlukan langkah tambahan

| Grant                                                | Langkah tambahan                                                                                                                                                                                                       | Sumber                                                                                                                              |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `jup.ruang_pimpinan.board.view` / `rka.view`         | Harus disertai `jup.ruang_pimpinan.scopes.jup_consolidated: true`. Tampilan tanpa cakupan tetap tertutup.                                                                                                              | [`policy.py`](../../../backend/jup/leadership/policy.py)                                                                            |
| `jup.ruang_pimpinan.bod.review`, `snapshots.publish` | Juga memerlukan kebijakan `JUP_LEADERSHIP_BOD_POLICY` / `JUP_LEADERSHIP_PUBLICATION_POLICY`, yang sengaja **belum** dipasang di `deploy.sh`. Sampai perusahaan memutuskan, penutupan BOD dan publikasi tetap nonaktif. | [`deploy.sh`](../../../deploy/gcp/deploy.sh)                                                                                        |
| `jup.voice.call`                                     | `JUP_VOICE_ENABLED` harus `true`, dan grup juga perlu akses baca ke model suara `asisten-jup-suara`.                                                                                                                   | [`voice.py`](../../../backend/jup/voice.py), [ADR-0017](../../adr/0017-voice-is-a-chained-pipeline-that-speaks-our-exact-answer.md) |
| `jup.voice.live`                                     | Hanya berlaku bersama `jup.voice.call` ([ADR-0018](../../adr/0018-gpt-live-is-an-opt-in-second-call-mode.md)).                                                                                                         | [`voice.py`](../../../backend/jup/voice.py)                                                                                         |
| `jup.channel.use`                                    | `JUP_CHANNELS_ENABLED` harus `true`. Lihat [mengaktifkan-kanal-whatsapp-teams.md](mengaktifkan-kanal-whatsapp-teams.md).                                                                                               | [`channel.py`](../../../backend/jup/channel.py)                                                                                     |
| `jup.kb.submit`                                      | Tidak ada. Peninjauan tetap dilakukan admin.                                                                                                                                                                           | [`kb_review.py`](../../../backend/jup/kb_review.py)                                                                                 |

## Mencabut grant

Keluarkan pengguna dari grup (tab **Pengguna** di editor grup), atau tulis nilai `false` pada grant di grup itu melalui endpoint update. Pengguna yang masih menjadi anggota grup lain dengan grant yang sama tetap memiliki akses.
