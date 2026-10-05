# Insiden: Secret dengan Newline di Akhir

Penanganan secret di Secret Manager yang menyimpan newline tersembunyi sehingga gagal di production tetapi lolos semua cek lokal.

## Aturan keras

- **JANGAN mencetak nilai secret** ke terminal, log, atau chat. Periksa panjang byte saja.
- Tulis versi secret selalu dengan `printf '%s'`, tidak pernah dengan `echo`, `cut`, atau hasil `openssl` yang langsung di-pipe.

## Gejala

- Fitur yang memakai secret sebagai header gagal di production, misalnya suara: `Error transcribing chunk: Open WebUI: Server Connection Error`, dengan log server `Newline, carriage return, or null byte detected in headers`.
- Koneksi database gagal dengan error yang menyebut host, bukan newline.
- Uji lokal dengan `KEY=$(gcloud secrets versions access ...)` berhasil. Command substitution di shell membuang newline di akhir, sehingga masalahnya tidak terlihat secara lokal.

## Penyebab

Nilai yang ditempel atau di-pipe membawa `\n` di akhir dan tersimpan di versi secret. Cloud Run menyuntikkan byte mentah sebagai env var, termasuk newline itu.

## Langkah

1. **Periksa jumlah byte tanpa mencetak nilai:**

   ```sh
   f="$(mktemp)"
   gcloud secrets versions access latest --secret=<NAMA-SECRET> --project=jup-ops --out-file="$f"
   echo "total: $(wc -c < "$f")  tanpa-newline: $(tr -d '\r\n' < "$f" | wc -c)"
   rm -f "$f"
   ```

   Dua angka berbeda = ada newline atau carriage return.

2. **Tambahkan versi baru tanpa newline.** Masukkan nilai lewat prompt tersembunyi, bukan argumen command line:

   ```sh
   read -rs V && printf '%s' "$V" | gcloud secrets versions add <NAMA-SECRET> --data-file=- --project=jup-ops; unset V
   ```

   Jalankan di terminal sungguhan (Terminal.app/iTerm). `read -rs` mendapat EOF bila dijalankan dari shell non-interaktif.

3. **Ulangi langkah 1** untuk versi baru.

4. **Paksa instance membaca versi baru.** Secret dirujuk sebagai `:latest` dan dibaca saat instance start, jadi buat revision baru: deploy biasa, atau tanpa rebuild (butuh persetujuan):

   ```sh
   gcloud run services update ent-os --project=jup-ops --region=asia-southeast2 \
     --update-labels=secret-rotated=<YYYY-MM-DD>
   ```

5. **Di kode**, trim secret di titik pemakaian untuk nilai yang dipakai sebagai header atau token. Ini sudah diterapkan untuk `openai-live-key`.

## Verifikasi

- Langkah 1 menunjukkan dua angka yang sama.
- Revision baru `Ready` dan menerima 100% traffic.
- Fitur yang gagal diuji ulang di aplikasi live dan berhasil ([verifikasi-live.md](../verifikasi-live.md)).
- Versi lama yang mengandung newline dinonaktifkan bila tidak dipakai lagi: `gcloud secrets versions disable <VERSI> --secret=<NAMA-SECRET> --project=jup-ops`.
