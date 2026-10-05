# Mengaktifkan kanal WhatsApp dan Teams

Langkah untuk membuka Asisten JUP bagi pengguna tertentu melalui WhatsApp atau Microsoft Teams, dan apa yang masih menunggu TI JUP.

## Cara kerja

Pesan dari WhatsApp atau Teams tidak masuk langsung ke aplikasi. Pesan diterima oleh layanan **jup-gateway** (Cloud Run terpisah, [`gateway/README.md`](../../../gateway/README.md)) yang:

1. memverifikasi asal pesan (tanda tangan Bot Framework untuk Teams, `X-Hub-Signature-256` dari Meta untuk WhatsApp);
2. memetakan pengirim ke satu akun JUP;
3. meminta jawaban dari aplikasi **atas nama** akun itu melalui `POST /api/jup/channel/turn`.

Aplikasi hanya melayani permintaan gateway untuk akun yang memenuhi **semua** syarat berikut ([`backend/jup/channel.py`](../../../backend/jup/channel.py), [`backend/jup/iap_identity.py`](../../../backend/jup/iap_identity.py)):

- `JUP_CHANNELS_ENABLED` bernilai `true` di [`deploy/gcp/deploy.sh`](../../../deploy/gcp/deploy.sh);
- akun sudah ada dan bukan `pending`;
- akun memegang grant `jup.channel.use`.

Jika salah satu tidak terpenuhi, gateway menerima 403 dan pengirim hanya mendapat balasan tetap: "Akun ini belum terhubung ke Asisten JUP. Hubungi admin JUP." Alasan sebenarnya hanya dicatat di log.

Percakapan kanal diperlakukan sama dengan percakapan yang diketik di web: kontrak operasional, kebijakan alat, dan audit tetap berlaku. Karena tidak ada pengguna yang dapat menyetujui di kanal, alat `external` selalu ditolak di sana ([ADR-0013](../../adr/0013-risky-tool-calls-need-the-asking-user-to-approve.md)). Jawaban yang membaca materi TERBATAS (misalnya nilai atau teks lengkap kontrak) dikirim hanya sebagai tautan ke `non-jupe.jup.co.id`, yang memerlukan login.

## Memberi pengguna akses kanal

1. Pastikan akun pengguna sudah disetujui ([menyetujui-pengguna-baru.md](menyetujui-pengguna-baru.md)).
2. Tambahkan pengguna ke grup kanal, atau buat grup baru, lalu tulis grant berikut ([mengelola-grup-dan-grant.md](mengelola-grup-dan-grant.md)):

   ```json
   { "jup": { "channel": { "use": true } } }
   ```

3. Minta pengguna memuat ulang aplikasi.

## WhatsApp: pengguna menautkan nomornya sendiri

Admin tidak memasukkan nomor telepon. Pengguna yang memegang `jup.channel.use` menautkan nomornya sendiri:

1. Pengguna membuka **Pengaturan → Akun**, bagian **WhatsApp**.
2. Pengguna membaca pemberitahuan bahwa pesan WhatsApp melewati server Meta, termasuk di Amerika Serikat, lalu memilih **Hubungkan WhatsApp**.
3. Aplikasi menampilkan kode enam digit. Pengguna mengirim `hubungkan <kode>` ke nomor Asisten JUP dari WhatsApp (atau memilih **Buka WhatsApp**) sebelum waktunya habis. Kode berlaku 10 menit.
4. Setelah berhasil, WhatsApp membalas "Nomor ini sudah terhubung ke Asisten JUP." dan halaman **Akun** menampilkan empat digit terakhir nomor.
5. Untuk melepas tautan, pengguna memilih **Putuskan**.

Pengguna tanpa grant tidak melihat bagian **WhatsApp**. Nomor telepon tidak pernah dikirim ke aplikasi; gateway hanya mengirim hash HMAC-nya.

**Status saat ini:** jalur WhatsApp berjalan dengan nomor uji dari aplikasi pengembang Meta. Peluncuran untuk staf memerlukan nomor WhatsApp milik JUP dan akun Meta Business JUP, dan dijadwalkan setelah Teams (PROGRESS.md, checkpoint v53).

## Teams: menunggu TI JUP

Jalur Teams sudah dibangun dan gateway sudah berjalan, tetapi **tertutup** sampai TI JUP menyelesaikan permohonan di [`deploy/gcp/teams-request-jup-it.id.md`](../../../deploy/gcp/teams-request-jup-it.id.md). Tanpa nilai-nilai itu, setiap permintaan Teams ditolak dengan 401 ([`deploy/gcp/deploy-gateway.sh`](../../../deploy/gcp/deploy-gateway.sh)).

### Bagian TI JUP

| Tugas                                                                      | Peran Microsoft yang dibutuhkan                                    |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Membuat **Azure Bot** `asisten-jup-bot` (single tenant)                    | _Contributor_ pada subscription dan resource group                 |
| _App registration_ bot dan _client secret_                                 | _Application Administrator_ atau _Cloud Application Administrator_ |
| Izin Graph `User.ReadBasic.All` (_application_) dengan _admin consent_     | _Privileged Role Administrator_ atau _Global Administrator_        |
| Mengaktifkan channel Microsoft Teams di Azure Bot                          | sama dengan pembuat bot                                            |
| Memasang aplikasi Teams **Asisten JUP**, mula-mula untuk satu akun penguji | _Teams Administrator_                                              |

TI JUP mengirim kembali **Microsoft App ID**, **App Tenant ID**, tanggal kedaluwarsa _secret_, dan _client secret_ **melalui kanal yang aman** (tidak lewat email atau chat biasa). Kedua ID bukan rahasia.

### Bagian pengelola aplikasi setelah itu

1. Menyimpan _client secret_ ke Secret Manager sebagai `bot-app-secret`.
2. Deploy ulang gateway dengan `BOT_APP_ID` dan `JUP_TENANT_ID` diisi ([`deploy-gateway.sh`](../../../deploy/gcp/deploy-gateway.sh)).
3. Mengisi **Messaging endpoint** bot dengan alamat gateway, bersama TI JUP.
4. Mengirim paket aplikasi Teams (`.zip`) ke TI JUP untuk dipasang.
5. Menguji dengan satu akun, lalu membuka bertahap atas permintaan tertulis.

Bot hanya melayani chat pribadi 1:1, hanya dari tenant JUP. Pengirim dipetakan ke alamat `@jakarta-utilitas.com`-nya melalui Graph, dan alamat itu harus cocok dengan akun yang memegang `jup.channel.use`.

## Mematikan kanal

| Cara                                                                                             | Efek                                      |
| ------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| `JUP_CHANNELS_ENABLED` dihapus atau diubah menjadi `"false"` di `deploy.sh`, lalu deploy         | Gateway menerima 403 untuk semua pengguna |
| Mencabut `jup.channel.use` dari grup                                                             | Hanya pengguna itu yang ditolak           |
| TI JUP mengubah aplikasi Teams menjadi **Blocked** atau menonaktifkan channel Teams di Azure Bot | Teams berhenti dari sisi Microsoft        |
| Deploy gateway dengan `WHATSAPP_PHONE_NUMBER_ID=` kosong                                         | WhatsApp ditutup (401)                    |
