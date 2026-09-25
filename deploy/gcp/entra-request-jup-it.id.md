# Permohonan ke TI JUP: App Registration Entra untuk login Asisten JUP

Asisten JUP (`https://non-jupe.jup.co.id`) akan memungkinkan staf JUP masuk dengan akun Microsoft 365
yang sudah mereka pakai sehari-hari. Google Cloud Identity Platform terhubung ke Entra ID melalui
OpenID Connect. Untuk itu, kami memerlukan satu *app registration* di tenant Entra JUP.

## Mohon dibuatkan

**Microsoft Entra admin center → App registrations → New registration**

| Kolom | Nilai |
|-------|-------|
| Name | `Asisten JUP` |
| Supported account types | **Accounts in this organizational directory only** (single tenant) |
| Redirect URI | Platform **Web**: `https://jup-ops.firebaseapp.com/__/auth/handler` |

Setelah itu:

1. **Certificates & secrets → New client secret.** Masa berlaku 12 atau 24 bulan. Mohon catat
   tanggal kedaluwarsanya, karena login akan berhenti berfungsi begitu *secret* kedaluwarsa.
2. **API permissions:** Microsoft Graph *delegated* `openid`, `email`, `profile` (biasanya sudah ada
   secara bawaan). Mohon berikan *admin consent* agar staf tidak diminta persetujuan satu per satu.
3. **Token configuration:** pastikan ID token memuat klaim `email`. Atribut `mail` setiap pengguna
   di Entra harus berisi alamat `@jakarta-utilitas.com` mereka, karena akun di aplikasi dibuat
   dengan alamat tersebut.
4. Opsional, tetapi kami sarankan: **Enterprise applications → Asisten JUP → Properties →
   Assignment required = Yes**, lalu *assign* hanya staf yang memang perlu akses. Tanpa pengaturan
   ini, semua akun di tenant bisa sampai ke tahap login. Walaupun begitu, aplikasi tetap menahan
   akun baru dalam status menunggu (*pending*) sampai disetujui administrator. Jika pengaturan ini
   diaktifkan, mohon *assign* `erik@jakarta-utilitas.com` lebih dulu. Akun itu yang pertama
   login untuk menguji pengaturan ini sebelum staf lain.

## Mohon dikirimkan kembali

- **Directory (tenant) ID**
- **Application (client) ID**
- **Client secret value**, melalui kanal yang aman, bukan lewat email atau chat biasa
- Tanggal kedaluwarsa *secret*

## Dampak bagi staf

Tidak ada yang perlu dipasang. Staf cukup membuka `https://non-jupe.jup.co.id`, memilih Microsoft,
lalu masuk dengan akun kerja seperti biasa. Pada login pertama, akun akan menunggu persetujuan
administrator JUP.
