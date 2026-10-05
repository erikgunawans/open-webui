# Verifikasi Live

Cara membuktikan bahwa perubahan benar-benar berjalan di aplikasi live, sebagai pengguna yang login, bukan di mock atau lewat curl.

## Aturan keras

- **Verifikasi di aplikasi live `https://non-jupe.jup.co.id/`, di Chrome sungguhan.** Jangan membuat mock HTML untuk "mewakili" aplikasi. Mock hanya menguji kontrak class, bukan perilaku konten sungguhan.
- **Jangan verifikasi di `ops.axiara.ai`.** Host itu sudah pensiun dan hanya me-redirect (302) ke `non-jupe`.
- **curl hanya membuktikan jalur anonim** (302 ke halaman login). Outage IAP sebelumnya terlihat sehat dari curl tetapi 500/403 bagi pengguna yang login.
- **`fetch` same-origin dari tab berjalan sebagai pengguna itu.** Panggilan `POST`/`PUT`/`DELETE` adalah tulisan sungguhan ke production. Hanya lakukan bila memang dimaksudkan dan disetujui.
- **Cek host sebelum setiap eval atau aksi tulis.** Tab yang dikendalikan otomatis pernah berpindah ke aplikasi lain.

## Mengapa browser sungguhan bisa masuk

IAP di depan `ent-os` memakai external identities (Entra). Browser yang sudah login dengan akun Microsoft JUP membawa sesi itu, sehingga IAP meloloskannya sebagai pengguna tersebut. Service account atau akun gcloud **tidak** bisa membuka aplikasi. Untuk maintainer, alat yang dipakai adalah Interceptor, yang mengendalikan Chrome milik pengguna:

```sh
interceptor open https://non-jupe.jup.co.id/
```

Bukti diambil dengan `interceptor eval --main` (computed style, ukuran elemen, `fetch` same-origin).

## Langkah

### 1. Tab baru dan sesi yang hidup

Sesi IAP habis sekitar 1 jam setelah login. Buka **tab baru**, lalu jalankan di konsol tab (atau lewat `interceptor eval --main`):

```js
location.host === 'non-jupe.jup.co.id'
	? (await fetch('/api/v1/auths/')).status
	: 'WRONG HOST ' + location.host;
```

- `200`: sesi hidup, lanjut.
- `401`, atau tab mendarat di `iap-gcip-hosted-ui-...run.app`: sesi habis. Muat ulang halaman atau login lagi di `non-jupe.jup.co.id` lewat Microsoft, lalu ulangi.

Jangan melanjutkan chat yang jawabannya terpotong; mulai chat baru. Lihat [insiden/sesi-iap-kedaluwarsa.md](insiden/sesi-iap-kedaluwarsa.md).

### 2. Buktikan build yang dimuat sama dengan yang disajikan server

Setelah deploy, browser bisa tetap memakai HTML shell lama dari cache yang menunjuk ke aset build sebelumnya. Bandingkan hash `entry/app`:

```js
const html = await (await fetch('/', { cache: 'no-store' })).text();
const served = html.match(/entry\/app\.[^"']+\.js/)?.[0];
const loaded = performance
	.getEntriesByType('resource')
	.map((e) => e.name)
	.find((n) => n.includes('entry/app.'));
({ served, loaded });
```

- Sama: tab menjalankan build baru.
- Berbeda: shell lama. Perbaiki dalam **satu** eval:

  ```js
  fetch('/', { cache: 'reload' }).then(() => location.reload());
  ```

  Lalu ulangi perbandingan. Tombol keyboard hard-reload lewat otomasi tidak selalu melewati cache.

Catatan:

- Hash `start.*.js` tidak berguna untuk ini (sering tidak berubah antar build).
- Hash tidak akan sama dengan build lokal dari commit yang sama, karena `BUILD_HASH` disuntikkan saat build image.

### 3. Uji perubahan itu sendiri

- Tampilan: ukur dengan `getComputedStyle` dan `getBoundingClientRect` pada elemen yang berubah.
- API: `fetch` same-origin ke endpoint terkait, cek status dan bentuk respons.
- Fitur chat atau tool: **chat baru**. Model bisa "berpegang" pada penolakannya sendiri di chat lama.
- Cek mode gelap bila perubahan menyentuh warna.

### 4. Bukti dari sisi server

Cocokkan dengan log, misalnya baris `jup.governance` untuk giliran yang baru dijalankan. Lihat [observability.md](observability.md).

### 5. Selesai

- Tutup tab yang dibuka untuk verifikasi, terutama tab Cloud Console.
- Catat bukti (nilai terukur, status HTTP, baris log) di PR atau PROGRESS.md. "Kelihatannya jalan" bukan bukti.

## Jika screenshot gagal

Screenshot lewat ekstensi bisa timeout. Gunakan pengukuran DOM sebagai bukti. **Jangan** beralih ke screenshot layar sistem operasi saat pengguna sedang memakai Chrome; itu menangkap jendela lain (pernah menangkap aplikasi chat pribadi).
