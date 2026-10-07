# Permohonan ke TI JUP: Asisten JUP membaca dan mengunggah ke SharePoint atas nama pengguna

Menggantikan permohonan sebelumnya (`qhse-sharepoint-request-jup-it.id.md`, akses *application*
`Sites.Selected` baca saja). **Langkah 2 dan 3 permohonan lama itu tidak perlu dijalankan lagi.**
Jika sudah terlanjur dijalankan, mohon dikabari; akses *application* itu nanti kami minta dicabut.

Asisten JUP di None-JUPe (`https://non-jupe.jup.co.id`) akan dapat **mencari, membaca, dan
mengunggah** dokumen di site SharePoint tertentu, **atas nama pengguna yang sedang masuk**
(*delegated*). Artinya:

- Asisten JUP hanya dapat melihat file yang **memang boleh dibuka pengguna itu** di SharePoint.
  Hak akses pengguna tetap diatur oleh TI JUP seperti biasa.
- Asisten JUP hanya menjangkau **site yang secara eksplisit diberi akses** oleh TI JUP. Site lain
  tidak terlihat, walaupun pengguna dapat membukanya.
- Unggahan hanya ke **satu folder per site**, `Keluaran Asisten JUP`, dan **setiap unggahan harus
  disetujui pengguna** di layar sebelum dikirim. Asisten JUP tidak pernah menimpa, mengganti nama,
  atau menghapus file.
- Tidak ada isi SharePoint yang disimpan di sistem Asisten JUP. Setiap pencarian dan unggahan
  dicatat (siapa, kapan, file mana; tanpa isi file).

Site pertama: **QHSE-JUP**. Dasar keputusan: D26 di register keputusan JUP (2026-10-07).

## Sudah diuji

Pada 2026-10-07 kami menguji seluruh alur ini di tenant JUP memakai aplikasi uji sementara
(**Asisten JUP - SharePoint spike**, `b05e9e7e-8796-489a-8106-e2292250da7f`) dan site uji berisi
data dummy (**Spike Asisten JUP**, `/sites/SpikeAsistenJUP`), dibuat oleh Erik selaku Global
Administrator. Site QHSE-JUP dan dokumen asli tidak disentuh. Hasilnya: masuk, pencarian, unduh,
unggah ke folder yang diizinkan berhasil; unggah di luar folder dan akses ke site lain **ditolak
oleh Microsoft**. Aplikasi dan site uji akan kami hapus setelah tahap pengembangan pertama; TI JUP
boleh menghapusnya lebih dulu bila diinginkan.

## Ringkasan

| Kolom | Nilai |
|-------|-------|
| Aplikasi | None-JUPe, Application (client) ID `095f7f79-2430-4cff-8363-560bb063b3e1` |
| Izin baru (*Delegated*, Microsoft Graph) | `Sites.Selected`, `Files.SelectedOperations.Selected`, `offline_access`, dengan *admin consent* |
| Redirect URI baru (platform **Web**) | `https://non-jupe.jup.co.id/oauth/clients/mcp:jup-sharepoint/callback` |
| Client secret | **Secret baru khusus** untuk fitur ini, masa berlaku 12 bulan, diserahkan langsung ke Erik (bukan lewat email atau chat) |
| Site | `https://jakartautilitas.sharepoint.com/sites/QHSE-JUP` |
| Akses pada site | **`read`** pada site QHSE-JUP |
| Akses pada folder | **`write`** pada folder `Keluaran Asisten JUP` saja |

**Peran yang dibutuhkan:** *Global Administrator*, atau *Application Administrator* (langkah 1)
bersama *SharePoint Administrator* (langkah 3 dan 4).

`Sites.Selected` dan `Files.SelectedOperations.Selected` sendiri **tidak memberi akses ke site
mana pun**. Akses baru ada setelah langkah 3 dan 4, dan hanya untuk site dan folder yang disebutkan.

## Langkah demi langkah

### 1. Izin *delegated* dan redirect URI pada None-JUPe

1. Buka `https://entra.microsoft.com` → **Entra ID → App registrations → None-JUPe**.
2. **Authentication → + Add a platform → Web** (atau tambahkan pada platform Web yang sudah ada):
   `https://non-jupe.jup.co.id/oauth/clients/mcp:jup-sharepoint/callback`. Simpan.
3. **API permissions → + Add a permission → Microsoft Graph → Delegated permissions** → centang
   `Sites.Selected`, `Files.SelectedOperations.Selected`, `offline_access` → **Add permissions**.
4. Klik **Grant admin consent for Jakarta Utilitas Propertindo** → **Yes**. Pastikan ketiganya
   berstatus hijau.
5. **Certificates & secrets → + New client secret**: deskripsi `Asisten JUP SharePoint`, 12 bulan.
   Serahkan nilainya langsung ke Erik.

Izin *application* `Files.SelectedOperations.Selected` yang sudah ada (untuk folder Legal) **tetap
dipertahankan**.

### 2. Folder unggahan di QHSE-JUP (oleh Pak Ikhsan sebagai pemilik site)

Di pustaka **Documents** site QHSE-JUP, buat folder **`Keluaran Asisten JUP`** di tingkat teratas.
Biarkan kosong. Asisten JUP tidak membuat folder sendiri.

### 3. Akses baca pada site QHSE-JUP

Graph Explorer (`https://developer.microsoft.com/graph/graph-explorer`), masuk dengan akun admin
yang telah menyetujui `Sites.FullControl.All` untuk dirinya sendiri.

1. **GET**
   `https://graph.microsoft.com/v1.0/sites/jakartautilitas.sharepoint.com:/sites/QHSE-JUP?$select=id`
   → catat `id` (bentuknya `jakartautilitas.sharepoint.com,<guid>,<guid>`).
2. **POST** `https://graph.microsoft.com/v1.0/sites/<id>/permissions`

```json
{"roles":["read"],"grantedToIdentities":[{"application":{"id":"095f7f79-2430-4cff-8363-560bb063b3e1","displayName":"None-JUPe"}}]}
```

Hasil yang benar: **201 Created**, `"roles": ["read"]`.

Alternatif PnP PowerShell:

```powershell
Grant-PnPAzureADAppSitePermission -AppId 095f7f79-2430-4cff-8363-560bb063b3e1 -DisplayName "None-JUPe" -Permissions Read -Site https://jakartautilitas.sharepoint.com/sites/QHSE-JUP
```

### 4. Akses tulis pada folder `Keluaran Asisten JUP` saja

**Penting:** gunakan endpoint *list item* di bawah ini. Endpoint *drive item*
(`/drives/.../root:/Keluaran Asisten JUP:/permissions`) memang menjawab **201 Created**, tetapi pada
uji kami **tidak berlaku sama sekali**: unggahan tetap ditolak.

1. **GET** `https://graph.microsoft.com/v1.0/sites/<id>/drive/list?$select=id` → catat `id` pustaka
   (`<list-id>`).
2. **GET**
   `https://graph.microsoft.com/v1.0/sites/<id>/drive/root:/Keluaran Asisten JUP?$expand=listItem($select=id)&$select=id`
   → catat `listItem.id` (sebuah angka, `<item-id>`).
3. **POST** `https://graph.microsoft.com/v1.0/sites/<id>/lists/<list-id>/items/<item-id>/permissions`

```json
{"roles":["write"],"grantedToV2":{"application":{"id":"095f7f79-2430-4cff-8363-560bb063b3e1","displayName":"None-JUPe"}}}
```

Hasil yang benar: **201 Created**, `"roles": ["write"]`. Folder itu kemudian tidak lagi mewarisi
izin dari pustaka; itu memang akibat pemberian izin ini dan tidak mengubah akses pengguna.

### 5. Folder Legal "SCAN PERJANJIAN" (terpisah dari fitur ini)

Sejak 2026-10-07 Microsoft Graph menjawab **403 "sharing link no longer exists"** untuk tautan
berbagi folder **SCAN PERJANJIAN** yang dipakai Kartu Kontrak. Kartu yang sudah ada tidak terdampak,
tetapi sinkronisasi kontrak baru gagal. Mohon tautan berbagi folder itu dibuat ulang (atau akses
None-JUPe pada folder itu diberikan ulang) dan tautan barunya dikirim ke Erik.

## Yang kami perlukan kembali

1. Konfirmasi langkah 1 selesai, dan client secret diserahkan langsung ke Erik.
2. Hasil langkah 3 dan 4 (status 201 dan `roles`; tidak ada rahasia di dalamnya).
3. Konfirmasi Pak Ikhsan telah membuat folder `Keluaran Asisten JUP`.
4. Tautan baru SCAN PERJANJIAN (langkah 5).

Setelah itu fitur diuji dulu oleh kelompok kecil (tim QHSE termasuk Pak Ikhsan, satu anggota
Direksi, dan Erik) selama dua minggu sebelum dibuka untuk seluruh staf. Menambah site lain cukup
dengan langkah 3 dan 4 untuk site tersebut, atas permintaan tertulis Erik.

## Mencabut

Hapus izin pada site dan folder (`DELETE /sites/<id>/permissions/<permission-id>`), lalu hapus
ketiga izin *delegated* dan redirect URI di None-JUPe. Token pengguna yang tersisa ikut tidak berlaku.
