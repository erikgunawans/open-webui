# Mengubah model default dan alat Asisten JUP

Langkah untuk mengubah model default, saran pertanyaan, dan alat (tool) yang dipakai Asisten JUP, beserta jebakan yang sering membuat perubahan tampak tidak berlaku.

## Hal pertama yang perlu dipahami

### Konfigurasi produksi tersimpan di database, bukan di env var

Open WebUI menulis setiap pengaturan _PersistentConfig_ ke database pada boot pertama, dan sejak itu **nilai database yang berlaku**. Mengubah env var di [`deploy/gcp/deploy.sh`](../../../deploy/gcp/deploy.sh) **tidak** mengubah model default, model yang disematkan, saran pertanyaan, atau pengaturan sejenis di produksi. Contohnya tertulis di `deploy.sh` sendiri: `ENABLE_OLLAMA_API` "hanya mengisi nilai awal pada database baru".

Pengaturan ini diubah dari **Panel Admin → Pengaturan** (atau API admin yang sama), dan setiap perubahan adalah penulisan produksi. Env var yang dibaca langsung pada setiap boot, seperti `DEFAULT_LOCALE`, `WEBUI_NAME`, dan `ENABLE_ADMIN_CHAT_ACCESS`, tetap diatur lewat `deploy.sh`. Lihat [referensi/pengaturan-penting.md](../referensi/pengaturan-penting.md).

### Grant alat tidak sama dengan alat default model

Di Open WebUI, grant akses pada sebuah alat hanya membuat alat itu **dapat dipilih** pengguna dari menu **Alat** di kolom chat. Alat yang dipakai model secara otomatis berasal dari daftar alat model itu sendiri (`meta.toolIds`). Alat yang sudah diberi grant kepada staf tetapi belum ada di `meta.toolIds` Asisten JUP **tidak akan dipakai** dalam percakapan biasa, dan model akan menjawab dengan jujur bahwa ia tidak memiliki alat tersebut.

Model suara `asisten-jup-suara` memiliki daftar alatnya sendiri, yang diatur oleh `deploy/gcp/sync-voice-model.ts`, bukan oleh langkah di bawah.

## Sebelum mengubah apa pun

1. Simpan salinan konfigurasi saat ini (before-value), misalnya hasil `GET /api/models` untuk model Asisten JUP, agar dapat dikembalikan.
2. Pastikan perubahan sudah disetujui. Perubahan konfigurasi produksi diperlakukan seperti deploy.

## Menambahkan alat ke Asisten JUP

1. Pastikan alatnya sudah ada di aplikasi. Alat JUP berasal dari folder `tools/` dan dimasukkan dengan `bun deploy/gcp/sync-tools.ts` ([`deploy/gcp/sync-tools.ts`](../../../deploy/gcp/sync-tools.ts)). Alat baru dibuat tanpa grant akses, sehingga awalnya hanya admin yang dapat memilihnya. Sinkronisasi ulang tidak mengubah grant yang diberikan lewat UI.
2. Jika staf boleh memakai alat itu, beri grant akses baca pada alatnya di **Ruang Kerja → Alat**.
3. Buka **Panel Admin → Pengaturan → Model**, lalu klik **Edit** pada model **Asisten JUP**.
4. Di bagian **Alat**, centang alat yang ingin dipakai model secara otomatis. Pilihan ini disimpan ke `meta.toolIds`.
5. Jangan mengubah bagian akses model. Asisten JUP harus tetap dapat dibaca semua pengguna.
6. Klik **Simpan & Perbarui**.
7. Uji di **Obrolan Baru**, tanpa menyentuh menu **Alat** di kolom chat. Percakapan lama yang pernah menolak permintaan cenderung tetap menolak, karena model mengikuti jawabannya sendiri di riwayat.
8. Periksa log audit: baris `admitted` tanpa baris `tool_call` berarti model memilih tidak memakai alatnya, bukan alatnya hilang. Lihat [penjelasan/model-tata-kelola.md](../penjelasan/model-tata-kelola.md#log-audit-jupgovernance).

Alat dengan Risk Class `external` akan meminta persetujuan pengguna setiap kali dipanggil, dan selalu ditolak di jalur tanpa pengguna (otomasi, kanal, subagent). Lihat [referensi/alat-jup.md](../referensi/alat-jup.md).

## Melampirkan koleksi pengetahuan

Koleksi **JUP Staff Contributions** dan **JUP Strategy KB** dibaca asisten hanya jika tercantum di bagian **Pengetahuan** model Asisten JUP (`meta.knowledge`). Langkahnya sama dengan menambahkan alat: **Edit** model, centang koleksi di **Pengetahuan**, **Simpan & Perbarui**, lalu uji di **Obrolan Baru** ([ADR-0015](../../adr/0015-staff-contributions-are-a-separate-reviewed-collection.md)).

## Mengubah model default dan model yang disematkan

1. Buka **Panel Admin → Pengaturan → Model**.
2. Pada model yang dipilih, buka menu **Lainnya**, lalu pilih **Set as Selected Model** (model default untuk obrolan baru) atau **Set as Pinned Model** (disematkan di sidebar). Label ini belum diterjemahkan. Model default ditandai **Selected**, model yang disematkan ditandai **Disematkan**.
3. Periksa akses model. Model atau override baru yang **tidak memiliki grant akses** hanya terlihat oleh pemilik atau admin. Agar semua pengguna melihatnya, model perlu grant baca untuk semua pengguna; ini keputusan kebijakan akses, bukan sekadar tampilan.
4. Buka aplikasi dengan akun non-admin dan pastikan model default muncul di **Obrolan Baru**.

## Mengubah saran pertanyaan

Saran pertanyaan di halaman chat juga tersimpan di database. Ubah lewat panel **Model Defaults** di **Panel Admin → Pengaturan → Model** (bagian **Prompt Suggestions**), bukan lewat env var. Setiap model juga dapat memiliki saran pertanyaannya sendiri di editor model.

## Tata kelola tetap berlaku

Perubahan model atau alat tidak dapat melewati kontrol tata kelola. Setiap giliran percakapan tetap harus membawa kontrak operasional JUP di pesan sistemnya, dan alat `external` tetap meminta persetujuan ([ADR-0002](../../adr/0002-fail-closed-attaches-at-generate-chat-completion.md), [ADR-0013](../../adr/0013-risky-tool-calls-need-the-asking-user-to-approve.md)).

Docstring alat hanya menjelaskan apa yang dikerjakan alat. Jangan menulis aturan identitas ("hanya jika admin yang bertanya") di docstring: model akan menolak sendiri karena tidak dapat memverifikasi identitas. Pemeriksaan peran dan grant dilakukan di kode `backend/jup/`.
