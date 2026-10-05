# Observability

Lokasi log `ent-os` dan `jup-gateway`, filter Cloud Logging yang dipakai, dan perilaku scaling yang memengaruhi cara membaca log.

## Prinsip

- **Cloud Logging adalah jejak audit yang tahan lama.** `DATA_DIR` tidak di-set di `deploy.sh` dan `/srv/jup` read-only, jadi file JSONL audit di dalam container hilang bersama instance. Setiap entri audit juga ditulis ke logger, dan itulah yang tersimpan.
- **Log tertunda sekitar 1 menit.** Jangan menyimpulkan "tidak ada log" sebelum menunggu.
- **`gcloud logging read` tidak mengirim traffic ke aplikasi**, sehingga aman dipakai saat menguji perilaku yang bergantung pada ada atau tidaknya request.
- Jangan mencetak isi secret atau nomor telepon pengguna. Gateway hanya mencatat `identity_hash`, bukan nomor.

## Filter yang dipakai

Semua perintah memakai `--project=jup-ops`. Tambahkan `--freshness=1h` (atau lainnya) dan `--limit=50` sesuai kebutuhan.

### `jup-gateway` (Teams dan WhatsApp)

Gateway menulis satu baris JSON per kejadian, sehingga field-nya muncul di `jsonPayload`.

```sh
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="jup-gateway" AND jsonPayload.event:*' \
  --project=jup-ops --freshness=1h --limit=50
```

Nilai `jsonPayload.event` yang penting:

| Event                                       | Arti                                                        |
| ------------------------------------------- | ----------------------------------------------------------- |
| `gateway_started`                           | Instance baru start                                         |
| `selfcheck`                                 | Hasil `SELFCHECK=1` setelah deploy                          |
| `turn_answered` / `turn_refused`            | Satu giliran percakapan dijawab atau ditolak ent-os         |
| `entos_failed`                              | Panggilan ke ent-os gagal                                   |
| `teams_rejected` / `whatsapp_rejected`      | Request ditolak (tanda tangan atau konfigurasi tidak valid) |
| `whatsapp_duplicate`                        | Webhook yang dikirim ulang Meta dibuang                     |
| `whatsapp_send_failed`, `teams_send_failed` | Balasan gagal dikirim ke kanal                              |

Contoh filter satu event:

```sh
gcloud logging read 'resource.labels.service_name="jup-gateway" AND jsonPayload.event="entos_failed"' \
  --project=jup-ops --freshness=1d
```

### `ent-os`: audit kanal

```sh
gcloud logging read 'resource.labels.service_name="ent-os" AND textPayload=~"channel_turn|channel_link"' \
  --project=jup-ops --freshness=1h --limit=50
```

`channel_turn` mencatat setiap giliran dari gateway (dengan `outcome` dan `reason`). `channel_link` mencatat menghubungkan dan memutus nomor WhatsApp.

### `ent-os`: audit tata kelola

```sh
gcloud logging read 'resource.labels.service_name="ent-os" AND textPayload:"jup.governance"' \
  --project=jup-ops --freshness=1d --limit=50
```

Setiap giliran chat, panggilan tool, penolakan, dan akses Ruang Pimpinan menghasilkan satu baris `jup.governance {...}`.

### `ent-os`: error aplikasi

```sh
gcloud logging read 'resource.labels.service_name="ent-os" AND severity>=ERROR' \
  --project=jup-ops --freshness=1h --limit=50
```

### Request HTTP ke Cloud Run

```sh
gcloud logging read 'resource.labels.service_name="ent-os" AND logName="projects/jup-ops/logs/run.googleapis.com%2Frequests"' \
  --project=jup-ops --freshness=30m --limit=50
```

Catatan: request yang ditolak IAP atau load balancer **tidak** sampai ke log ini. Signed-in 500 tanpa log request di Cloud Run hampir selalu masalah di depan Cloud Run (lihat [insiden/iap-toggle-cloud-run.md](insiden/iap-toggle-cloud-run.md)).

### Perubahan admin pada Cloud Run (siapa mengubah apa)

```sh
gcloud logging read 'logName="projects/jup-ops/logs/cloudaudit.googleapis.com%2Factivity" AND protoPayload.serviceName="run.googleapis.com"' \
  --project=jup-ops --freshness=1d --limit=20
```

Ini yang pertama dibaca bila aplikasi tiba-tiba 500/403 bagi pengguna yang login.

### Halaman login (Identity Platform)

```sh
gcloud logging read 'resource.labels.service_name="iap-gcip-hosted-ui-ent-os-backend-jup"' \
  --project=jup-ops --freshness=1h --limit=20
```

`billing is disabled for this project` di sini berarti [insiden/billing-akun-tertutup.md](insiden/billing-akun-tertutup.md).

## Scaling

| Service       | Min / max | CPU                                                         | Konsekuensi                                                                                                               |
| ------------- | --------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `ent-os`      | 1 / 4     | Dialokasikan per request (throttled)                        | Satu instance selalu hangat. Pekerjaan latar (otomasi, timer, scheduler) hanya pasti dapat CPU saat ada request berjalan. |
| `jup-gateway` | 0 / 2     | Selalu dialokasikan (`--no-cpu-throttling`), concurrency 20 | Bisa cold start dari nol.                                                                                                 |

Cek nilai live, jangan percaya dokumen:

```sh
gcloud run services describe ent-os --project=jup-ops --region=asia-southeast2 \
  --format='value(spec.template.metadata.annotations)'
```

### State di dalam proses bersifat per instance

- **Lock per percakapan** di `ent-os` (urutan giliran kanal) ada di memori proses. Dua giliran dari percakapan yang sama yang mendarat di dua instance tidak diurutkan satu sama lain.
- **Dedup WhatsApp** di gateway (`RecentIds`, 5.000 ID pesan terakhir) juga per instance. Dengan max 2 instance, redelivery dari Meta yang mendarat di instance lain bisa dijawab dua kali.
- Cache, rate limit, atau state lain di memori: anggap per instance kecuali terbukti sebaliknya.

### Menguji pekerjaan terjadwal

Tab aplikasi yang terbuka (websocket dan polling `_app/version.json` tiap menit) membuat CPU `ent-os` tetap aktif, sehingga uji ketepatan waktu otomasi bisa lulus palsu.

- Jadwalkan uji pada jam ketika tidak ada yang membuka aplikasi.
- Tutup tab segera setelah membuat jadwal.
- Pantau hanya lewat `gcloud logging read`.
- Baca log request untuk jendela waktu itu. Ada request = hasil uji tidak sah.
