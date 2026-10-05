# Aturan Repo

Aturan khusus fork None-JUPe. Sebagian besar lahir dari kegagalan nyata; alasannya ditulis agar tidak ada yang "merapikannya" kembali.

## Bahasa dan alat

- **Python dipakai di fork ini.** Backend adalah FastAPI, dan frontend memakai `adapter-static` sehingga tidak ada server route SvelteKit. Semua yang membaca file atau mencegat request saat runtime harus ditulis dalam Python. Persetujuan ini hanya berlaku untuk repo ini.
- **Selain itu, pakai Bun**: `bun run`, `bunx`, `bun test`. npm hanya dipakai untuk `package-lock.json` (memasang dari lockfile dan memperbarui `@jup/ui`), karena Dockerfile memasang dengan `npm ci`. Lihat [onboarding](onboarding.md#2-javascript-bun-untuk-tugas-npm-hanya-untuk-lockfile).
- **Format Python mengikuti ruff dari lockfile**: quote tunggal, lebar baris 120. Kode dengan quote ganda akan gagal di CI.

## Frontend

### Jangan restyle komponen vendor

Route dan komponen di `src/` adalah file vendor yang ikut rebase setiap kuartal ([ADR-0007](../adr/0007-track-upstream-rebasing-quarterly.md)). Komponen yang diubah tampilannya menjadi konflik yang harus dibawa selamanya. Sebagai gantinya:

- Nilai visual berasal dari token JUP Design System di `src/jup-tokens.css` (`--jup-*`). Referensinya ada di `design/jup-design-system/` dan [`docs/design-system/`](../design-system/).
- Restyle dilakukan di `src/jup-skin.css`. Aturannya sengaja **tanpa layer**, sehingga menang atas utility Tailwind (yang ada di `@layer utilities`) tanpa `!important`.
- Kaitkan aturan lewat selektor pada markup vendor yang sudah ada, atau paling banyak **satu class** yang ditambahkan ke file vendor (contoh yang sudah ada: `jup-seg` pada bar tab, `jup-primary` pada `SplitCreateButton.svelte`).
- Ukur kontras setiap pasangan warna baru sebelum commit.
- **Ramp `--color-gray-*` di `src/tailwind.css` sebagian besar dipakai untuk teks**, bukan permukaan. Bila perlu retheme, ubah hue dan chroma saja dengan mempertahankan lightness OKLCH tiap step. Jangan arahkan step abu-abu ke token permukaan; itu menggeser lightness dan merusak kontras di ratusan komponen. Warna permukaan dipasang pada elemen tertentu lewat token `--jup-*`.

Untuk UI baru di pulau React Rapat Direksi, pakai komponen `@jup/ui` saja.

### i18n

- **`bun run i18n:parse` hanya mengekstrak panggilan literal** `$i18n.t('…')`. Bentuk seperti `$i18n.t(MAP[x])` tidak terlihat oleh parser: string-nya tidak pernah mendapat key, tampil dalam bahasa Inggris di id-ID, dan terjemahan yang ditambahkan manual **dihapus** pada parse berikutnya. Tulis peta label sebagai objek reaktif berisi panggilan literal, lalu indeks objek itu:

  ```svelte
  $: STATE = { in_progress: $i18n.t('In progress'), done: $i18n.t('Done') } as Record<string, string>;
  ```

- Parser bisa melewatkan panggilan literal di markup, misalnya tepat di bawah komentar HTML, tanpa peringatan. Bila key baru tidak muncul, pindahkan panggilannya ke `<script>`. Setelah parse, pastikan setiap key baru benar-benar ada di file locale.
- **Key vendor bisa sudah ada dengan nilai id-ID kosong** ("History", "Open", "Select", "Status", dan lain-lain). Parse tidak menandainya sebagai key baru, sehingga label tampil dalam bahasa Inggris. Setelah parse, periksa setiap `$i18n.t('…')` di komponen baru terhadap file locale id-ID dan isi nilai yang kosong.

## Backend

### Revisi alembic yang bertabrakan menghentikan boot

Migrasi Open WebUI berjalan **saat `open_webui/config.py` di-import**, bukan dari CLI. Bila revisi fork dan revisi upstream sama-sama menunjuk `down_revision` yang sama, alembic melihat dua head, upgrade gagal, dan **aplikasi tidak bisa start sama sekali**. Pegangan:

- Percayai `down_revision`, bukan docstring `Revises:` (salah satu file vendor sudah saling bertentangan).
- Setelah setiap rebase upstream, jalankan `uv run --only-group dev pytest tests/test_boot.py`.
- Detail: [`docs/architecture/08-backend-tools-migrations.md`](../architecture/08-backend-tools-migrations.md).

### Data fork di pesan chat disimpan di `message.meta`

Pesan ditulis ganda ke blob JSON `chat` dan tabel `chat_message`, tetapi tabel hanya menyimpan kolom yang dikenalnya (role, content, output, meta, done, dan seterusnya), dan pembacaan mengutamakan tabel. Key tingkat atas yang ditambahkan fork **hilang saat dibaca, tanpa error**. Simpan data fork di bawah `message['meta']`, digabung di atas hasil baca terbaru, karena `meta` di payload menggantikan `meta` yang tersimpan secara utuh.

### Tidak ada `app.state.config` di versi vendor ini

Pengaturan disimpan di store berbasis database:

```python
from open_webui.models.config import Config

defaults = await Config.get('ui.default_models')
```

Key bertitik diambil dari peta `*_CONFIG_KEYS` di `routers/configs.py` dan `routers/auths.py`. Membaca `request.app.state.config` menghasilkan 500 di produksi, dan unit test tidak bisa menangkapnya karena router fork tidak bisa di-import di bawah `--only-group dev`. Sebelum router baru membaca pengaturan vendor, cari bagaimana router vendor membaca pengaturan yang sama dan tiru caranya.

### Docstring tool tidak boleh menyaring identitas

Model membaca docstring tool sebagai instruksi. Kalimat seperti "panggil hanya bila admin yang meminta" membuat model menolak sendiri, sehingga pemeriksaan di server dan gerbang approval tidak pernah tercapai. Docstring di `tools/*.py` menjelaskan **apa yang dilakukan tool dan kapan berguna**, bukan siapa yang boleh memanggilnya. Pemeriksaan peran ada di kode modul `jup.*`; docstring cukup menyebut bahwa tool memeriksa peran pemanggil sendiri (contoh: `tools/gate_probe.py`).

### Jangan import app di luar pytest tanpa `STATIC_DIR`

Saat di-import, `open_webui/config.py` menghapus **semua file** di `STATIC_DIR` lalu mengisinya ulang dari build frontend. Tanpa `build/static`, tidak ada yang dikembalikan, dan kegagalannya ditelan `except` kosong. Akibatnya favicon, logo, `loader.js`, `splash.png`, dan manifest yang dilacak git ikut terhapus.

- Di dalam pytest sudah aman: `tests/conftest.py` mengarahkan `STATIC_DIR` ke salinan sementara sebelum test apa pun di-import, dan `tests/test_boot.py` memastikan penjaga itu tetap ada.
- Di luar pytest (server dev, `python -c 'import open_webui…'`, skrip ad hoc), set `STATIC_DIR` ke salinan direktori itu dan cek `git status` setelahnya. Jangan pernah `git add -u` sebelum memeriksa.

## File hasil generate dan handoff

- **Schema Rapat Direksi hanya diregenerasi dengan** `bun scripts/gen-schema.ts`. Skrip ini membaca `design_handoff_notulen_rapat_direksi/` dan menulis `src/lib/notulen/schema.ts` serta `src/lib/notulen/demo-source.ts`. Jangan mengedit kedua file hasil itu dengan tangan; jalankan `bun run format` setelahnya.
- **Folder handoff disimpan apa adanya.** `design_handoff_notulen_rapat_direksi/` dan `skills/` dikecualikan dari prettier dan tidak boleh "dirapikan": handoff dibaca oleh generator, dan sumber skill disinkronkan ke app byte demi byte.
- **Fixture test adalah byte-nya.** `tests/fixtures/` dikecualikan dari prettier karena fixture yang sengaja rusak tidak boleh diperbaiki formatter.

## Dokumentasi

- `README.md` di root milik upstream; jangan diubah.
- Prosa di `docs/` ikut diformat prettier oleh CI kecuali foldernya tercantum di `.prettierignore` (`docs/adr/`, `docs/agents/`, `docs/architecture/`, `docs/design-system/`). Folder lain, termasuk `docs/dev/`, harus bersih menurut prettier. Lihat [ci.md](ci.md#frontend-build).
- Keputusan desain baru dicatat sebagai ADR di [`docs/adr/`](../adr/).
