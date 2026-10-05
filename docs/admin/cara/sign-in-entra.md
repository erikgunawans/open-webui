# Sign-in Entra melalui Identity Platform

Penjelasan alur login staf JUP dengan akun Microsoft 365, pembagian tanggung jawab antara TI JUP dan pengelola aplikasi, serta langkah rutin yang menjadi bagian TI JUP.

## Alur login

1. Staf membuka `https://non-jupe.jup.co.id`.
2. Load balancer meneruskan permintaan ke backend `ent-os-backend-jup`, yang dilindungi IAP dalam mode **identitas eksternal** (Google Cloud Identity Platform).
3. IAP menampilkan halaman login. Staf memilih Microsoft dan masuk dengan akun kerja `@jakarta-utilitas.com`.
4. Identity Platform memverifikasi login ke Microsoft Entra ID melalui OpenID Connect (provider `oidc.entra-jup`).
5. IAP meneruskan alamat email terverifikasi ke aplikasi dalam header `X-Goog-Authenticated-User-Email`. Aplikasi membuang prefiks penyedia dan memakai alamat polosnya ([`backend/jup/iap_identity.py`](../../../backend/jup/iap_identity.py)).
6. Login pertama membuat akun `pending`. Admin JUP menyetujuinya ([menyetujui-pengguna-baru.md](menyetujui-pengguna-baru.md)).

Keputusan dan riwayat lengkapnya ada di [ADR-0012](../../adr/0012-iap-as-the-login.md) dan [ADR-0016](../../adr/0016-jup-staff-sign-in-with-entra-through-identity-platform.md). Penyiapan IAP ada di [`deploy/gcp/iap.md`](../../../deploy/gcp/iap.md).

## Hal penting tentang keamanan

- **Dengan identitas eksternal, IAP tidak memakai IAM untuk otorisasi.** Siapa pun yang berhasil login dengan provider yang diaktifkan akan lolos IAP. Karena itu hanya tenant JUP yang diizinkan (app registration _single tenant_), provider Google sengaja tidak diaktifkan, dan persetujuan admin di aplikasi menjadi gerbang yang sebenarnya.
- Cloud Run hanya menerima lalu lintas dari load balancer (`--ingress=internal-and-cloud-load-balancing` di [`deploy/gcp/deploy.sh`](../../../deploy/gcp/deploy.sh)). Inilah yang membuat header email tidak dapat dipalsukan. **Melonggarkan ingress itu menjadikan header tersebut celah login.**
- Alamat akun diambil dari klaim `email` di token Entra. Klaim ini harus sama dengan alamat `@jakarta-utilitas.com` staf.

## Yang menjadi tanggung jawab TI JUP

Rincian langkah ada di [`deploy/gcp/entra-request-jup-it.id.md`](../../../deploy/gcp/entra-request-jup-it.id.md). Ringkasnya:

| Hal                           | Rincian                                                                                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| App registration              | Nama `None-JUPe`, **Accounts in this organizational directory only** (single tenant)                                                      |
| Redirect URI                  | Platform **Web**, alamat `/__/auth/handler` Identity Platform yang tercantum di dokumen permohonan                                        |
| Izin API                      | Microsoft Graph _delegated_: `openid`, `email`, `profile`, dengan _admin consent_                                                         |
| Klaim opsional                | `email` di ID token                                                                                                                       |
| Atribut email staf            | **Entra ID → Users → Properties → Contact information → Email** harus berisi alamat `@jakarta-utilitas.com` staf                          |
| Client secret                 | Berlaku 12 atau 24 bulan; dikirim melalui kanal yang aman                                                                                 |
| Pembatasan login (disarankan) | **Enterprise applications → None-JUPe → Properties → Assignment required? = Yes**, lalu _assign_ staf atau grup keamanan yang boleh masuk |

Peran Microsoft yang dibutuhkan: _Application Administrator_ atau _Cloud Application Administrator_ (atau _Global Administrator_).

## Tugas rutin TI JUP

### Memperpanjang client secret sebelum kedaluwarsa

Login semua staf berhenti begitu _client secret_ kedaluwarsa. Tanggal kedaluwarsanya belum tercatat di [`entra-request-jup-it.id.md`](../../../deploy/gcp/entra-request-jup-it.id.md); mohon dicatat dan dipasang pengingat sekitar sebulan sebelumnya.

1. Buat _client secret_ baru di app registration `None-JUPe` (**Certificates & secrets → Client secrets → + New client secret**).
2. Salin kolom `Value` (bukan `Secret ID`) dan kirim ke pengelola aplikasi melalui kanal yang aman.
3. Pengelola aplikasi mengganti _secret_ pada provider dengan [`deploy/gcp/entra-provider.sh`](../../../deploy/gcp/entra-provider.sh), yang menerima _secret_ dari terminal dan hanya mengganti _secret_-nya.
4. Setelah login berhasil diuji, TI JUP menghapus _secret_ lama.

### Membuka atau menutup akses untuk staf

Jika _assignment_ diwajibkan, tambahkan atau hapus staf di **Enterprise applications → None-JUPe → Users and groups**. Menghapus _assignment_ mencegah login di sisi Microsoft. Untuk menutup akses di sisi aplikasi, admin JUP mengubah peran akun menjadi **Pending**.

## Gangguan yang sering terjadi

| Gejala                                                                              | Kemungkinan penyebab                                                        |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Semua staf tidak dapat login sejak tanggal tertentu                                 | _Client secret_ Entra kedaluwarsa                                           |
| Login berhasil tetapi akun baru terbentuk dengan alamat lain, atau akun tidak cocok | Klaim `email` tidak terisi atau berbeda dari alamat `@jakarta-utilitas.com` |
| Staf diminta persetujuan izin satu per satu                                         | _Admin consent_ belum diberikan                                             |
| Staf yang sudah login melihat halaman menunggu persetujuan                          | Akun masih `pending`; admin JUP perlu menyetujuinya                         |
