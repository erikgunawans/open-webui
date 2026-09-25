# Permohonan ke TI JUP: App Registration Entra untuk login None-JUPe

None-JUPe (`https://non-jupe.jup.co.id`), asisten AI JUP, akan memungkinkan staf JUP masuk dengan
akun Microsoft 365 yang sudah mereka pakai sehari-hari. Google Cloud Identity Platform terhubung ke
Entra ID melalui OpenID Connect. Untuk itu, kami memerlukan satu *app registration* di tenant Entra
JUP. Pengerjaannya sekitar 15 menit.

## Ringkasan

| Kolom | Nilai |
|-------|-------|
| Name | `None-JUPe` |
| Supported account types | **Accounts in this organizational directory only** (single tenant) |
| Redirect URI | Platform **Web**: `https://jup-ops.firebaseapp.com/__/auth/handler` |
| API permissions | Microsoft Graph, *delegated*: `openid`, `email`, `profile`, dengan *admin consent* |
| Optional claim | `email` di ID token |
| Client secret | 12 atau 24 bulan |

**Peran yang dibutuhkan:** *Application Administrator* atau *Cloud Application Administrator*
(atau *Global Administrator*). Peran ini juga cukup untuk memberikan *admin consent* pada langkah 4.

## Langkah demi langkah

Label di bawah mengikuti tampilan Microsoft Entra admin center berbahasa Inggris.

### 1. Buat app registration

1. Buka `https://entra.microsoft.com` dan masuk dengan akun administrator.
2. Di menu kiri: **Entra ID → App registrations** (pada tampilan lama: **Identity → Applications →
   App registrations**).
3. Klik **+ New registration**.
4. Isi:
   - **Name:** `None-JUPe`. Nama ini yang dilihat staf di halaman login Microsoft.
   - **Supported account types:** pilih **Accounts in this organizational directory only
     (single tenant)**.
   - **Redirect URI:** pada daftar *Select a platform* pilih **Web**, lalu isi
     `https://jup-ops.firebaseapp.com/__/auth/handler`. Salin persis, termasuk `/__/`.
5. Klik **Register**.

### 2. Catat dua ID

Setelah terdaftar, halaman **Overview** aplikasi terbuka. Salin:

- **Application (client) ID**
- **Directory (tenant) ID**

### 3. Buat client secret

1. Di menu aplikasi: **Certificates & secrets → Client secrets → + New client secret**.
2. **Description:** `None-JUPe IAP`. **Expires:** 365 hari (12 bulan) atau 730 hari (24 bulan).
3. Klik **Add**.
4. **Segera salin kolom `Value`**, bukan `Secret ID`. Nilai ini hanya tampil sekali. Jika halaman
   sudah ditutup sebelum disalin, hapus *secret* tersebut dan buat yang baru.
5. Catat tanggal di kolom **Expires**. Login akan berhenti berfungsi begitu *secret* kedaluwarsa,
   jadi mohon pasang pengingat sekitar sebulan sebelumnya.

### 4. Izin API dan admin consent

1. Di menu aplikasi: **API permissions**. Biasanya sudah ada `User.Read`; biarkan saja.
2. Klik **+ Add a permission → Microsoft Graph → Delegated permissions**.
3. Pada bagian **OpenId permissions**, centang `email`, `openid`, dan `profile`, lalu klik
   **Add permissions**.
4. Klik **Grant admin consent for \<nama tenant JUP\>** → **Yes**.
5. Pastikan kolom **Status** untuk keempat izin berisi tanda centang hijau *Granted for …*.
   Dengan begitu staf tidak akan diminta persetujuan satu per satu.

### 5. Klaim email di ID token

1. Di menu aplikasi: **Token configuration → + Add optional claim**.
2. **Token type:** **ID**. Centang `email`, lalu klik **Add**.
3. Jika muncul pertanyaan untuk mengaktifkan izin Microsoft Graph `email`, centang lalu klik **Add**.
4. Periksa atribut email staf: **Entra ID → Users →** pilih seorang staf **→ Properties →
   Contact information → Email**. Isinya harus alamat `@jakarta-utilitas.com` staf tersebut,
   karena akun di aplikasi dibuat dengan alamat itu. Untuk pengguna yang memiliki kotak surat
   Exchange Online, kolom ini biasanya sudah terisi otomatis. Mohon periksa minimal akun
   `erik@jakarta-utilitas.com`.

Menu **Authentication** tidak perlu diubah. Aplikasi memakai *authorization code flow*, sehingga
*implicit grant* (*Access tokens* dan *ID tokens*) tetap tidak dicentang.

### 6. Batasi siapa yang boleh login (opsional, kami sarankan)

1. Buka **Entra ID → Enterprise applications → All applications**, lalu cari `None-JUPe`. Jika
   tidak muncul, hapus filter *Application type*.
2. **Properties → Assignment required? = Yes → Save**.
3. **Users and groups → + Add user/group → Users → None Selected**, pilih
   `erik@jakarta-utilitas.com` lebih dulu, lalu klik **Select → Assign**. Akun itu yang pertama
   login untuk menguji pengaturan ini sebelum staf lain.
4. Staf lain (atau satu grup keamanan) dapat di-*assign* dengan cara yang sama setelah uji login
   Erik berhasil.

Tanpa langkah ini, semua akun di tenant bisa sampai ke tahap login. Walaupun begitu, aplikasi tetap
menahan akun baru dalam status menunggu (*pending*) sampai disetujui administrator JUP.

## Mohon dikirimkan kembali

- **Directory (tenant) ID** (langkah 2)
- **Application (client) ID** (langkah 2)
- **Client secret value** (langkah 3), melalui kanal yang aman: disampaikan langsung atau lewat
  telepon, atau tautan sekali-lihat. **Jangan** lewat email atau chat biasa.
- Tanggal kedaluwarsa *secret* (langkah 3)

Kedua ID tersebut bukan rahasia dan boleh dikirim lewat email.

## Dampak bagi staf

Tidak ada yang perlu dipasang. Staf cukup membuka `https://non-jupe.jup.co.id`, memilih Microsoft,
lalu masuk dengan akun kerja seperti biasa. Pada login pertama, akun akan menunggu persetujuan
administrator JUP.
