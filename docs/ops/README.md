# Runbook Operasional None-JUPe

Titik masuk untuk siapa pun yang men-deploy, memantau, atau memulihkan None-JUPe (`non-jupe.jup.co.id`) di proyek GCP `jup-ops`.

## Daftar dokumen

| Dokumen                                                                      | Isi                                                                                              |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| [runbook-deploy.md](runbook-deploy.md)                                       | Prasyarat, deploy `ent-os` dan `jup-gateway`, pemulihan `SKIP_BUILD=1`, pemeriksaan pasca-deploy |
| [runbook-rollback.md](runbook-rollback.md)                                   | Mengembalikan traffic ke revision sebelumnya dan memverifikasinya                                |
| [observability.md](observability.md)                                         | Lokasi log, filter Cloud Logging, scaling dan konsekuensinya                                     |
| [verifikasi-live.md](verifikasi-live.md)                                     | Cara memverifikasi aplikasi live sebagai pengguna yang benar-benar login                         |
| [insiden/billing-akun-tertutup.md](insiden/billing-akun-tertutup.md)         | Billing account tertutup (delinquent)                                                            |
| [insiden/iap-toggle-cloud-run.md](insiden/iap-toggle-cloud-run.md)           | Outage karena IAP diaktifkan langsung di Cloud Run                                               |
| [insiden/sesi-iap-kedaluwarsa.md](insiden/sesi-iap-kedaluwarsa.md)           | Sesi IAP habis tiap ±1 jam, jawaban terpotong                                                    |
| [insiden/secret-newline.md](insiden/secret-newline.md)                       | Secret dengan newline di akhir                                                                   |
| [insiden/healthz-dicadangkan.md](insiden/healthz-dicadangkan.md)             | Cloud Run mencadangkan `/healthz`                                                                |
| [insiden/cloud-build-buildplatform.md](insiden/cloud-build-buildplatform.md) | `$BUILDPLATFORM` kosong di Cloud Build                                                           |
| [insiden/document-ai-batch-macet.md](insiden/document-ai-batch-macet.md)     | Batch Document AI macet                                                                          |
| [insiden/embedding-perlu-restart.md](insiden/embedding-perlu-restart.md)     | Ganti model embedding butuh revision baru                                                        |
| [insiden/disk-penuh.md](insiden/disk-penuh.md)                               | Disk Mac penuh saat `docker pull` atau build                                                     |

Dokumen sumber yang lebih rinci ada di `deploy/gcp/`: `README.md` (provisioning dan jebakan gcloud), `iap.md` (load balancer dan IAP), `VENDOR-PATCHES.md`, `drift-gates.md`. Jika runbook ini berbeda dengan skrip, **skrip yang benar**.

## Arsitektur singkat

```
Pengguna (browser, akun Microsoft JUP)
   │  HTTPS 443
   ▼
Global external load balancer  (IP statis ent-os-ip, forwarding rule ent-os-fr, URL map ent-os-lb)
   │  host rule non-jupe.jup.co.id ──► backend service ent-os-backend-jup  (IAP, external identities)
   │                                        │  login via halaman iap-gcip-hosted-ui-ent-os-backend-jup
   │                                        │  (Identity Platform, provider oidc.entra-jup = Entra JUP)
   │  ops.axiara.ai ──► 302 ke non-jupe     ▼
   │  (sudah pensiun)                   Serverless NEG ent-os-neg-jup
   ▼                                        ▼
                                  Cloud Run ent-os  (asia-southeast2)
                                    ├─ Cloud SQL jup-ops-db (Postgres 16 + pgvector, private IP saja)
                                    ├─ gs://jup-ops-records   → /srv/jup        (read-only)
                                    ├─ gs://jup-ops-legal-kb  → /srv/legal-kb   (read-only)
                                    └─ gs://jup-ops-data      (upload, STORAGE_PROVIDER=gcs)

Teams / WhatsApp (Meta) ──► Cloud Run jup-gateway (ingress publik, verifikasi request sendiri)
                                    └─► ent-os lewat load balancer + IAP, dengan token Identity Platform
```

| Komponen             | Detail                                                                                                                                                                                                    | Sumber                 |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| Proyek / region      | `jup-ops`, `asia-southeast2` (Jakarta)                                                                                                                                                                    | `deploy/gcp/deploy.sh` |
| `ent-os`             | Cloud Run, 2 CPU, 4 GiB, `--timeout=3600`, min 1 / max 4, `--ingress=internal-and-cloud-load-balancing`, `--no-allow-unauthenticated`, direct VPC egress `private-ranges-only`                            | `deploy.sh`            |
| `jup-gateway`        | Cloud Run, 1 CPU, 512 MiB, min 0 / max 2, `--no-cpu-throttling`, `--ingress=all --no-invoker-iam-check`, berjalan sebagai service account `jup-gateway@`                                                  | `deploy-gateway.sh`    |
| Image                | `asia-southeast2-docker.pkg.dev/jup-ops/ent-os/ent-os:<sha>` dan `.../ent-os/jup-gateway:<sha>`; `<sha>` = `git rev-parse --short HEAD`                                                                   | kedua skrip            |
| Build                | Cloud Build pool `global`, mesin `e2-highcpu-32` (kuota di Jakarta terblokir)                                                                                                                             | `deploy.sh`            |
| Database             | Cloud SQL `jup-ops-db`, Postgres 16, ENTERPRISE `db-g1-small`, private IP, backup harian 18:00 UTC (01:00 WIB)                                                                                            | `provision.sh`         |
| Login                | IAP mode external identities → Identity Platform → Entra ID tenant JUP. Di mode ini IAP **tidak** memakai IAM; gerbang akses ada di aplikasi (`DEFAULT_USER_ROLE=pending`, admin dari `JUP_ADMIN_EMAILS`) | `iap.md`, `deploy.sh`  |
| Secret `ent-os`      | `webui-secret-key`, `database-url`, `openai-live-key`, `notion-integration-token` (semuanya via `--set-secrets`)                                                                                          | `deploy.sh`            |
| Secret `jup-gateway` | `gateway-hmac-key`, `identity-platform-browser-key`, `whatsapp-app-secret`, `whatsapp-access-token`, `whatsapp-verify-token`; `bot-app-secret` nanti untuk Teams                                          | `deploy-gateway.sh`    |
| Biaya tetap          | Forwarding rule load balancer ±USD 18/bulan, ditambah instance minimum `ent-os`                                                                                                                           | `iap.md`               |

Hal yang sengaja **tidak** ada: tidak ada jalur tanpa autentikasi ke `ent-os`, signup mati (`ENABLE_SIGNUP=False`), dan tidak ada port 80.

## Pembagian tanggung jawab

| Area                                                                         | Pemilik                                                                               | Catatan                                                                                                                                                   |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Kode, image, deploy, rollback, Cloud Run, load balancer, IAP, Secret Manager | Maintainer (Axiara)                                                                   | Perubahan production butuh persetujuan per perubahan dari Direktur JUP yang berwenang; role Owner di proyek **bukan** izin deploy.                        |
| Billing account proyek `jup-ops`                                             | Pemegang billing account (pemilik proyek, role Owner + Billing Account Administrator) | Hanya pemegang ini yang bisa membayar dan membuka kembali akun yang tertutup. Lihat [insiden/billing-akun-tertutup.md](insiden/billing-akun-tertutup.md). |
| DNS `jup.co.id` (record `non-jupe A`)                                        | JUP IT                                                                                | DNS dikelola di penyedia hosting `jup.co.id`.                                                                                                             |
| Aplikasi Entra (client ID, client secret, redirect URI, admin consent)       | JUP IT                                                                                | Rotasi secret dijalankan maintainer lewat `deploy/gcp/entra-provider.sh` di terminal sungguhan.                                                           |
| Akun Microsoft staf JUP                                                      | JUP IT                                                                                | Akun di aplikasi dibuat dan disetujui oleh admin aplikasi.                                                                                                |
| Bot Teams (`BOT_APP_ID`, `bot-app-secret`, `JUP_TENANT_ID`)                  | JUP IT menyediakan, maintainer memasang                                               | Selama belum ada, Teams tertutup (setiap request 401).                                                                                                    |
| Nomor WhatsApp produksi dan Meta Business                                    | JUP (bisnis)                                                                          | Saat ini memakai nomor uji Meta di aplikasi developer Axiara.                                                                                             |
| Role admin dan grant grup di aplikasi                                        | Admin aplikasi JUP                                                                    | Mengangkat seseorang menjadi `admin` = memberi akses ke seluruh lapisan operasional. Perlakukan sebagai grant.                                            |
