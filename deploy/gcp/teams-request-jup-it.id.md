# Permohonan ke TI JUP: Bot Asisten JUP di Microsoft Teams

Direksi JUP akan bisa bertanya ke Asisten JUP langsung dari Microsoft Teams, tanpa membuka
`https://non-jupe.jup.co.id`. Untuk itu, kami memerlukan tiga hal di tenant Microsoft JUP:

1. satu **Azure Bot** (single tenant) beserta *app registration*-nya;
2. izin Microsoft Graph **`User.ReadBasic.All`** (*application*) dengan *admin consent*;
3. aplikasi Teams **Asisten JUP** yang dipasang lewat Teams admin center, mula-mula hanya untuk
   `erik@jakarta-utilitas.com`.

Total pengerjaan sekitar 30–45 menit. Paket aplikasi Teams (file `.zip`) kami kirim terpisah
setelah langkah 2 selesai, karena paket itu memuat ID aplikasi dari langkah tersebut.

## Mengapa izin ini diperlukan

Setiap pesan Teams membawa ID objek Entra pengirim dan ID tenant-nya. Server kami hanya menerima
pesan dari tenant JUP (`fc521bfb-40c2-4b87-95a7-65e0e888fdf8`). Server lalu mencocokkan ID objek
pengirim dengan alamat `@jakarta-utilitas.com`-nya melalui Graph `User.ReadBasic.All`. Alamat itu
yang menentukan hak akses di Asisten JUP, persis seperti saat staf login di web. Izin ini hanya
membaca profil dasar (nama, email, foto). Izin ini **tidak** membaca email, file, kalender, atau
chat.

Bot hanya melayani **chat pribadi 1:1**. Bot tidak bisa ditambahkan ke grup atau channel, dan tidak
membaca percakapan lain. Pengirim yang tidak terdaftar di Asisten JUP hanya menerima balasan tetap
"akun ini belum terhubung ke Asisten JUP". Konten berklasifikasi TERBATAS tidak pernah dikirim
sebagai teks di Teams, melainkan sebagai tautan ke `non-jupe.jup.co.id` yang memerlukan login.

## Ringkasan

| Kolom | Nilai |
|-------|-------|
| Resource | **Azure Bot**, nama `asisten-jup-bot` |
| Type of App | **Single Tenant** |
| Creation type | **Create new Microsoft App ID** |
| Pricing tier | **Standard (S1)**. Channel Teams gratis, tanpa biaya per pesan |
| Data residency | **Global** |
| Messaging endpoint | Akan kami kirimkan (alamat server *gateway* JUP). Boleh dikosongkan dulu |
| Channel | **Microsoft Teams** (Commercial) |
| Graph permission | `User.ReadBasic.All`, tipe **Application**, dengan *admin consent* |
| Client secret | 12 atau 24 bulan |

**Peran yang dibutuhkan:**

- *Contributor* pada satu Azure subscription dan resource group, untuk membuat Azure Bot (langkah 1).
- *Application Administrator* atau *Cloud Application Administrator*, untuk *app registration* dan
  *client secret* (langkah 2–3).
- *Privileged Role Administrator* atau *Global Administrator*, untuk *admin consent* izin
  **application** Graph (langkah 4). Peran *Cloud Application Administrator* tidak cukup untuk izin
  jenis ini.
- *Teams Administrator*, untuk memasang aplikasi Teams (langkah 6).

## Langkah demi langkah

Label di bawah mengikuti tampilan Azure portal, Microsoft Entra admin center, dan Teams admin
center berbahasa Inggris.

### 1. Buat Azure Bot

1. Buka `https://portal.azure.com` dan masuk dengan akun administrator.
2. Cari **Azure Bot** di kolom pencarian atas, lalu klik **Create**.
3. Isi:
   - **Bot handle:** `asisten-jup-bot`
   - **Subscription / Resource group:** pakai subscription JUP yang ada. Kami sarankan resource
     group baru `rg-asisten-jup`.
   - **Data residency:** **Global**
   - **Pricing tier:** klik *Change plan* lalu pilih **Standard**. Channel Teams tidak dikenai
     biaya pesan.
   - **Type of App:** **Single Tenant**
   - **Creation type:** **Create new Microsoft App ID**
4. Klik **Review + create → Create**, lalu tunggu sampai *deployment* selesai.

### 2. Catat ID aplikasi

1. Buka resource `asisten-jup-bot` → **Settings → Configuration**.
2. Salin **Microsoft App ID** dan **App Tenant ID**. App Tenant ID seharusnya
   `fc521bfb-40c2-4b87-95a7-65e0e888fdf8`.
3. Kolom **Messaging endpoint** boleh dibiarkan kosong. Kami akan mengirimkan alamatnya, atau
   mengisinya bersama TI JUP saat server *gateway* siap.

### 3. Buat client secret

1. Di halaman **Configuration** yang sama, klik **Manage Password** di samping Microsoft App ID.
   Halaman *app registration* bot akan terbuka di Entra.
2. **Certificates & secrets → Client secrets → + New client secret**.
3. **Description:** `Asisten JUP gateway`. **Expires:** 365 hari atau 730 hari.
4. Klik **Add**, lalu **segera salin kolom `Value`**, bukan `Secret ID`. Nilai ini hanya tampil
   sekali. Jika halaman sudah tertutup sebelum disalin, hapus *secret* tersebut dan buat yang baru.
5. Catat tanggal **Expires**. Bot akan berhenti menjawab begitu *secret* kedaluwarsa, jadi mohon
   pasang pengingat sekitar sebulan sebelumnya.

### 4. Izin Graph dan admin consent

1. Masih di *app registration* bot: **API permissions → + Add a permission → Microsoft Graph →
   Application permissions**. Pastikan yang dipilih **Application**, bukan *Delegated*.
2. Cari dan centang **`User.ReadBasic.All`**, lalu klik **Add permissions**.
3. Klik **Grant admin consent for \<nama tenant JUP\>** → **Yes**.
4. Pastikan kolom **Status** untuk `User.ReadBasic.All` berisi tanda centang hijau
   *Granted for …*.

### 5. Aktifkan channel Microsoft Teams

1. Kembali ke resource `asisten-jup-bot` di Azure portal → **Settings → Channels**.
2. Klik **Microsoft Teams**, pilih **Microsoft Teams Commercial**, centang persetujuan *Terms of
   Service*, lalu klik **Apply**.
3. Pastikan Microsoft Teams tercantum dengan status **Healthy**.

### 6. Pasang aplikasi Teams (setelah kami kirim file `.zip`)

1. Buka `https://admin.teams.microsoft.com` → **Teams apps → Manage apps → Actions → Upload new
   app**, lalu unggah `asisten-jup.zip` dari kami.
2. Buka aplikasi **Asisten JUP**. Pada **Users and groups** (atau *Available to*), batasi aplikasi
   hanya untuk `erik@jakarta-utilitas.com` dulu. Jika tenant memakai *App permission policies*,
   izinkan aplikasi ini untuk akun tersebut saja.
3. Pastikan status aplikasi **Allowed**.

Staf lain dibuka bertahap setelah Erik selesai menguji, atas permintaan tertulis dari kami.

## Mohon dikirimkan kembali

- **Microsoft App ID** (langkah 2)
- **App Tenant ID** (langkah 2)
- **Client secret value** (langkah 3) melalui kanal yang aman: disampaikan langsung, lewat telepon,
  atau tautan sekali-lihat. **Jangan** lewat email atau chat biasa.
- Tanggal kedaluwarsa *secret* (langkah 3)
- Konfirmasi bahwa *admin consent* `User.ReadBasic.All` berstatus *Granted* (langkah 4) dan channel
  Teams berstatus *Healthy* (langkah 5)

Kedua ID tersebut bukan rahasia dan boleh dikirim lewat email.

## Catatan untuk TI JUP

- **Lalu lintas pesan.** Teks pesan diteruskan oleh Microsoft Bot Service (layanan Microsoft, di
  bawah kontrak Microsoft 365 JUP) ke server *gateway* JUP di Google Cloud Jakarta
  (`asia-southeast2`). Server *gateway* hanya menerima permintaan yang tanda tangan Bot
  Framework-nya valid dan berasal dari tenant JUP.
- **Mematikan bot.** Kami memiliki saklar untuk mematikan seluruh jalur Teams dari sisi server. Dari
  sisi TI JUP, cukup ubah aplikasi menjadi **Blocked** di Teams admin center, atau nonaktifkan
  channel Teams di Azure Bot.
- **Biaya Azure.** Azure Bot Standard tidak dikenai biaya untuk channel Teams. Tidak ada resource
  Azure lain yang dibuat.
