# Permohonan ke TI JUP: Site SharePoint QHSE dan akses baca untuk None-JUPe

Dokumen Sistem Manajemen QHSE JUP (SOP, prosedur, formulir, template) saat ini tersimpan di OneDrive
pribadi Pak Ikhsan (`1. JUP/Sistem Manajemen QHSE JUP`). Kami mengusulkan dua hal:

1. Dokumen dipindahkan ke **site SharePoint QHSE** milik perusahaan, agar tidak bergantung pada satu
   akun pribadi (jika akun berubah atau dinonaktifkan, OneDrive-nya ikut hilang).
2. Asisten JUP di None-JUPe (`https://non-jupe.jup.co.id`) mendapat **akses baca saja** ke site
   tersebut, sehingga staf dapat bertanya tentang SOP dan meminta template, dengan jawaban yang
   menyebut nomor dokumen, revisi, dan tautan ke file aslinya.

Pak Ikhsan sudah kami minta memindahkan dokumennya setelah site tersedia.

## Ringkasan

| Kolom | Nilai |
|-------|-------|
| Site | Team site (tanpa Microsoft 365 Group pun tidak masalah), nama usulan **QHSE JUP**, URL `https://jakartautilitas.sharepoint.com/sites/QHSE-JUP` |
| Pemilik site | Pak Ikhsan (`ikhsan@jakarta-utilitas.com`), ditambah TI JUP |
| Aplikasi | None-JUPe, Application (client) ID `095f7f79-2430-4cff-8363-560bb063b3e1` |
| Izin aplikasi | Microsoft Graph *application* `Sites.Selected`, dengan *admin consent* |
| Akses pada site | **`read`** pada site QHSE JUP saja, bukan seluruh tenant |

**Peran yang dibutuhkan:** *SharePoint Administrator* (membuat site) dan *Application Administrator*
atau *Global Administrator* (admin consent dan pemberian akses ke site).

## Langkah demi langkah

### 1. Buat site SharePoint

1. Buka **SharePoint admin center → Sites → Active sites → + Create** (atau dari beranda SharePoint
   **+ Create site**, jika pengguna diizinkan membuat site).
2. Pilih **Team site**. Nama: `QHSE JUP`. Alamat: `QHSE-JUP`.
3. Tambahkan Pak Ikhsan sebagai **Owner**.
4. Kabari Pak Ikhsan dan kami setelah site siap. Pak Ikhsan lalu memindahkan folder dari OneDrive
   ke pustaka **Documents** site ini (fitur **Move to** di OneDrive mempertahankan riwayat versi).

### 2. Pastikan izin `Sites.Selected` aktif

1. Buka `https://entra.microsoft.com` → **Entra ID → App registrations → None-JUPe → API permissions**.
2. Jika belum ada: **+ Add a permission → Microsoft Graph → Application permissions →
   `Sites.Selected`** → **Add permissions**.
3. Klik **Grant admin consent for \<nama tenant JUP\>** → **Yes**, dan pastikan statusnya hijau.

`Sites.Selected` sendiri **tidak memberi akses ke site mana pun**. Akses baru ada setelah langkah 3,
dan hanya untuk site yang disebutkan di sana.

### 3. Beri akses baca pada site QHSE JUP saja

Pilih salah satu cara.

**PnP PowerShell:**

```powershell
Connect-PnPOnline -Url https://jakartautilitas.sharepoint.com/sites/QHSE-JUP -Interactive -ClientId <ID aplikasi PnP milik TI>
Grant-PnPAzureADAppSitePermission -AppId 095f7f79-2430-4cff-8363-560bb063b3e1 -DisplayName "None-JUPe" -Permissions Read -Site https://jakartautilitas.sharepoint.com/sites/QHSE-JUP
```

**Microsoft Graph** (Graph Explorer, dengan akun admin yang memiliki `Sites.FullControl.All`):

```http
GET https://graph.microsoft.com/v1.0/sites/jakartautilitas.sharepoint.com:/sites/QHSE-JUP
```

Salin `id` dari hasilnya, lalu:

```http
POST https://graph.microsoft.com/v1.0/sites/{id}/permissions
Content-Type: application/json

{
  "roles": ["read"],
  "grantedToIdentities": [
    { "application": { "id": "095f7f79-2430-4cff-8363-560bb063b3e1", "displayName": "None-JUPe" } }
  ]
}
```

### 4. Kabari kami

Cukup balas bahwa langkah 3 sudah dilakukan. Kami akan menguji dari sisi aplikasi bahwa site QHSE
JUP terbaca dan site lain tetap tertolak.

## Yang tidak berubah

- Akses yang sudah ada ke folder `SCAN PERJANJIAN` tetap seperti sekarang.
- None-JUPe hanya **membaca**. Aplikasi tidak menulis, mengubah, atau menghapus dokumen di site.
- Salinan teks dokumen untuk pencarian disimpan di Google Cloud wilayah Jakarta.
