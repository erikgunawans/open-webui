# Insiden: Billing Account Tertutup

Penanganan saat billing account yang tertaut ke `jup-ops` tertutup (delinquent), padahal proyek masih melaporkan billing aktif.

## Gejala

- Halaman login `iap-gcip-hosted-ui-ent-os-backend-jup` menjawab 503 "not available yet" (di log HTTP tercatat 500). Pengguna yang sesinya habis tidak bisa login.
- Log halaman login berisi `The request failed because billing is disabled for this project`.
- GCS menolak dengan `403 The billing account for the owning project is disabled in state delinquent`.
- Deploy, revision baru, dan sinkronisasi records ke GCS gagal.
- `ent-os` terlihat setengah hidup: instance minimum yang sudah hangat masih melayani sesi yang ada.
- `gcloud billing projects describe jup-ops` tetap menunjukkan `billingEnabled: true`. **Nilai ini menyesatkan.**

## Penyebab

Billing account yang tertaut berstatus `open: false` karena ada tagihan belum dibayar. Proyek tetap tertaut ke akun itu, jadi `billingEnabled` tetap `true`, tetapi layanan berbayar dihentikan.

## Langkah

1. **Cek status akun, bukan status proyek:**

   ```sh
   gcloud billing projects describe jup-ops --format='value(billingAccountName)'
   gcloud billing accounts describe <ID-BILLING-ACCOUNT> --format='value(open)'
   ```

   `False` = akun tertutup. Itu penyebabnya.

2. **Eskalasi ke pemegang billing account** (pemilik proyek). Hanya pemegang ini yang bisa membayar dan membuka kembali akun lewat Cloud Console, bagian Billing.

3. **Sementara akun tertutup:**
   - **JANGAN** deploy, restart, atau "memulihkan" halaman login dengan revision baru. Tidak akan berhasil dan menambah perubahan yang harus dilacak.
   - **JANGAN** mengubah IAP, load balancer, atau IAM untuk "memperbaiki" login. Penyebabnya bukan di sana.
   - Kerjakan hanya pekerjaan lokal.

4. **Setelah akun dibuka kembali**, cek layanan pulih sendiri sebelum mengubah apa pun. Jika halaman login tetap 503, revision baru tanpa perubahan konfigurasi (hanya label) adalah opsi terakhir dan butuh persetujuan:

   ```sh
   gcloud run services update iap-gcip-hosted-ui-ent-os-backend-jup --project=jup-ops --region=asia-southeast2 \
     --update-labels=restarted=<YYYY-MM-DD>
   ```

## Verifikasi

- `gcloud billing accounts describe <ID-BILLING-ACCOUNT> --format='value(open)'` menghasilkan `True`.
- Log halaman login tidak lagi berisi `billing is disabled`.
- `gcloud builds list --project=jup-ops --limit=1` berhasil.
- Login dari tab baru sampai ke aplikasi dan `fetch('/api/v1/auths/')` = 200 ([verifikasi-live.md](../verifikasi-live.md)).
- Pemegang billing account mengetahui penyebab penutupan dan mencegahnya terulang (metode pembayaran, notifikasi tagihan).
