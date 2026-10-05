# Insiden: Cloud Run Mencadangkan `/healthz`

Penjelasan 404 di path yang berakhiran `z` pada Cloud Run, dan path health check yang benar.

## Gejala

- `GET /healthz` ke `jup-gateway` mendapat halaman HTML Google "Error 404 (Not Found)!!1", padahal server menjawabnya dengan benar saat dijalankan lokal.
- Tidak ada log request di container untuk panggilan itu.

## Penyebab

Cloud Run mencadangkan path URL yang berakhiran `z` (`/healthz`, `/readyz`, dan sejenisnya) dan menjawabnya sendiri. Request tidak pernah sampai ke container.

## Langkah

1. Gunakan **`/health`**. Itu path health check `jup-gateway` (`gateway/src/server.ts`).
2. Jangan menambahkan endpoint baru berakhiran `z` di service Cloud Run mana pun.
3. Bila 404 berbentuk HTML Google muncul di path seperti itu, anggap itu platform, bukan aplikasi. Jangan men-debug kode.

## Verifikasi

```sh
URL=$(gcloud run services describe jup-gateway --project=jup-ops --region=asia-southeast2 --format='value(status.url)')
curl -s -o /dev/null -w '%{http_code}\n' "$URL/health"     # 200
```

`ent-os` tidak bisa dicek dengan cara ini: ingress-nya hanya lewat load balancer dan IAP. Gunakan [verifikasi-live.md](../verifikasi-live.md).
