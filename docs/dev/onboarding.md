# Onboarding Pengembang

Langkah menyiapkan mesin sampai bisa menjalankan server dev dan seluruh test None-JUPe, beserta biaya waktu dan disk yang perlu dianggarkan sejak awal.

## Prasyarat

| Alat             | Versi / catatan                                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Python           | 3.11 atau 3.12 (`requires-python = ">= 3.11, < 3.13.0a1"` di `pyproject.toml`). CI menguji keduanya.                                         |
| uv               | Pengelola environment dan lockfile Python (`uv.lock`).                                                                                       |
| Bun              | Untuk skrip JS/TS, `bunx`, dan gateway. CI gateway memakai Bun 1.3.11.                                                                       |
| Node.js 22 + npm | Vite dan SvelteKit berjalan di Node; npm hanya untuk lockfile frontend (lihat di bawah). CI memakai Node 22.                                 |
| git, `gh`        | `gh` untuk issue dan PR. Jalankan `gh repo set-default erikgunawans/ent-os-new-jup` (detail di [issue tracker](../agents/issue-tracker.md)). |
| Ruang disk       | Minimal beberapa GB kosong: runtime Python penuh beberapa GB, model embedding ~1,1 GB. Cek `df -h /` dulu.                                   |

## 1. Python: dua environment yang berbeda

Proyek ini punya dua cara memasang dependensi Python, dan keduanya sengaja dibedakan.

**Untuk test (cepat, beberapa detik):**

```sh
uv run --only-group dev pytest
```

`--only-group dev` hanya memasang grup `dev` (pytest, ruff, PyYAML, dan beberapa renderer) tanpa proyeknya sendiri. Akibatnya `open_webui` **tidak bisa di-import** di environment ini, sementara `backend/jup/` tetap bisa karena `pythonpath = ["backend"]` di konfigurasi pytest. Inilah environment yang dipakai CI.

**Untuk server dev dan test yang butuh app (lambat):**

```sh
uv sync
```

Ini memasang runtime penuh (torch, chromadb, transformers, onnxruntime, dan lain-lain): beberapa GB dan beberapa menit. Mulai di latar belakang di awal pekerjaan bila tiket Anda nanti perlu diverifikasi di browser, bukan di akhir.

**Mengubah dependensi atau lockfile:** pakai `uv lock --offline`. `uv lock` biasa pernah menggantung lebih dari 10 menit; `--offline` selesai dalam hitungan detik selama versi yang dipin sudah ada di cache lokal. Jalankan edit `pyproject.toml` dan perintah lambat sebagai langkah terpisah, jangan dirangkai dengan `&&`: kalau rangkaian itu dipindah ke latar belakang, kegagalan langkah pertama ikut tersembunyi.

Dependensi yang di-import oleh modul `backend/jup/` yang diuji harus dipin juga di grup `dev`, karena `--only-group dev` tidak mewarisi dependensi proyek.

## 2. JavaScript: Bun untuk tugas, npm hanya untuk lockfile

Untuk menjalankan skrip dan alat JS/TS, pakai `bun run <skrip>` dan `bunx <alat>`. Pengecualiannya satu: **lockfile frontend adalah `package-lock.json`**, karena Dockerfile dan CI memasang dengan `npm ci --force`. Bun tidak bisa menulis lockfile itu.

Pasang `node_modules` dari lockfile yang sama dengan CI:

```sh
npm ci --force
```

Jangan commit `bun.lock` kalau tidak sengaja terbuat.

**Memperbarui `@jup/ui`.** Paket ini tidak punya registry; tarball-nya di-vendor di `vendor/` dan dipasang sebagai dependensi `file:`. Setelah menaruh tarball versi baru:

```sh
npm install --force ./vendor/jup-ui-<versi>.tgz
```

Perintah ini memperbarui `package.json` dan `package-lock.json` sekaligus; commit keduanya bersama tarball. `.gitignore` mengabaikan `*.tgz` kecuali `vendor/*.tgz`, dan Dockerfile menjalankan `COPY vendor` sebelum `npm ci`. Jangan alias-kan `@jup/ui` ke direktori sumbernya: subpath `@jup/ui/styles.css` jadi rusak.

**Gateway** punya lockfile Bun sendiri:

```sh
cd gateway
bun install --frozen-lockfile
```

## 3. Menjalankan server dev

Server dev terdiri dari **dua proses**. `vite dev` di port 5173 meneruskan `/api`, `/ws`, dan jalur backend lain ke `http://localhost:8080` (atau `WEBUI_BACKEND_URL`), jadi frontend saja tidak menampilkan apa-apa yang berguna.

**Backend** (setelah `uv sync`), dijalankan dari `backend/` agar `open_webui` dan `jup` sama-sama ada di `sys.path`:

```sh
cd backend
DATA_DIR=<folder-scratch>/data \
STATIC_DIR=<folder-scratch>/static \
ENABLE_SIGNUP=True \
uv run bash dev.sh
```

- `dev.sh` menjalankan uvicorn di port 8080 dengan `--reload`.
- `DATA_DIR` di luar repo agar `webui.db` tidak tertinggal di working tree.
- `STATIC_DIR` wajib diarahkan ke salinan `backend/open_webui/static` (salin dulu dengan `cp -R`). Saat `open_webui.config` di-import, semua file di `STATIC_DIR` dihapus lalu diisi ulang dari build frontend; tanpa build, file branding tidak kembali. Detail di [aturan repo](aturan-repo.md#jangan-import-app-di-luar-pytest-tanpa-static_dir). Periksa `git status` setelahnya.
- Untuk data JUP, arahkan `JUP_RECORDS_DIR` ke tree record (misalnya fixture di `tests/fixtures/`).
- Akun pertama yang dibuat lewat signup otomatis menjadi `admin`.

**Biaya boot pertama:** sebelum uvicorn mau menerima koneksi, backend mengunduh model embedding bawaan Open WebUI (`sentence-transformers/all-MiniLM-L6-v2`, ~1,1 GB ke `~/.cache/huggingface`). Selama beberapa menit itu `/health` tidak menjawab dan _connection refused_ adalah hal normal, bukan kegagalan.

**Frontend:**

```sh
bun run dev
```

Skrip `dev` mengambil paket Pyodide dulu (`pyodide:fetch`), lalu menjalankan `vite dev --host`. Buka `http://localhost:5173`.

## 4. Postgres sementara (pgserver, TCP 55432)

Produksi memakai Postgres 16. Test default memakai SQLite di direktori sementara; beberapa suite (lock percakapan, channel link, repository leadership) juga berjalan di Postgres bila `JUP_TEST_POSTGRES_URL` diisi. Tanpa Docker atau brew, binary Postgres 16 bisa diambil dari paket `pgserver`:

```sh
uv run --no-project --with pgserver python -c 'import pgserver'
BIN=$(dirname "$(find ~/.cache/uv -path '*pgserver/pginstall/bin/initdb' | head -1)")
$BIN/initdb -D <folder-scratch>/pgdata -U postgres -A trust
$BIN/pg_ctl -D <folder-scratch>/pgdata -o "-k '' -h 127.0.0.1 -p 55432" -l <folder-scratch>/pg.log -w start
```

Jalankan binary-nya langsung lewat TCP; `pgserver.get_server()` gagal bila path folder terlalu panjang untuk Unix socket. Lalu:

```sh
JUP_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/postgres \
uv run --group dev pytest tests/test_jup_conversation_lock.py tests/test_channel_links.py
```

Test ini butuh SQLAlchemy, jadi pakai `--group dev` (runtime penuh), bukan `--only-group dev`. Hentikan server dengan `$BIN/pg_ctl -D <folder-scratch>/pgdata stop -m fast`.

## 5. Test

### pytest (backend dan pemindaian sumber)

```sh
uv run --only-group dev pytest                   # seluruh suite, seperti CI
uv run --only-group dev pytest -q tests/<file>   # satu file
uv run --group dev pytest                        # dengan runtime penuh (butuh uv sync)
```

Konvensi harness:

- **Test ada di `tests/` (jamak) di root repo**, di luar `backend/`, agar rebase upstream kuartalan tidak perlu menggabungkannya. `test/` (tunggal) milik upstream; jangan menambah apa pun di sana.
- **Fixture** ada di `tests/fixtures/`, diakses lewat fixture `fixtures_dir` / `fixture_path` di `tests/conftest.py`.
- **Kode fork yang perlu diuji cepat ditaruh di `backend/jup/`**, bukan di `backend/open_webui/`. Di bawah `--only-group dev`, apa pun di `open_webui` tidak bisa di-import.
- **Muat modul lewat path** bila modulnya harus tinggal di `open_webui/` (misalnya router) atau paketnya menarik dependensi runtime: `importlib.util.spec_from_file_location(...)`, dengan import vendor diletakkan di dalam fungsi yang memerlukannya. Contoh: `tests/test_jup_voice_live_relay.py`, `tests/test_leadership_kpi.py`.
- **Lewati test yang butuh runtime dengan `pytest.importorskip`** pada dependensinya (`sqlalchemy`, `alembic`, `fastapi`), bukan pada `open_webui`. `pythonpath` membuat paket `open_webui` _terlihat_ ada padahal import-nya gagal. Mark `skipif` di level modul tidak mencegah import di bagian atas file; import level atas yang gagal tetap menggagalkan pengumpulan test satu file.
- **`asyncio_mode = "auto"` disengaja**: test `async def` tidak perlu marker. Jangan diubah ke `strict`.
- **`--only-group dev` diam-diam memakai `.venv` penuh bila ada.** Test yang lolos lokal bisa gagal di CI. Untuk meniru CI tanpa merusak `.venv`: `UV_PROJECT_ENVIRONMENT=<folder-scratch>/devenv uv run --frozen --only-group dev pytest`.

Setelah rebase upstream, jalankan `uv run --only-group dev pytest tests/test_boot.py` untuk memastikan alembic hanya punya satu head.

### Vitest (frontend)

```sh
bunx vitest run           # seluruh suite, sekali jalan
bunx vitest run <file>    # satu file
```

Jangan pakai `bun run test:frontend` di lokal: skrip itu `vitest --passWithNoTests`, yang di luar CI masuk mode watch dan tidak pernah selesai. Hentikan watcher yang tertinggal dengan `pkill -f vitest`.

### Pulau React Rapat Direksi (`.tsx`)

```sh
bun run check:notulen
bunx prettier --write "src/lib/notulen/**/*.tsx"
```

`check:notulen` menjalankan `tsc` dengan `tsconfig.notulen.json`. Ini satu-satunya pemeriksaan tipe untuk `.tsx`: `svelte-check` hanya melihat `.ts` dan `.svelte`, Vite membuang tipe tanpa memeriksanya, dan glob prettier di CI (`{js,ts,svelte,css,md,html,json}`) tidak mencakup `.tsx`. Format `.tsx` sendiri sebelum commit.

### Svelte

```sh
bun run check
```

### Gateway

```sh
cd gateway
bun run typecheck
bun test
```

Test gateway bernama `*_test.ts` supaya Vitest frontend tidak ikut mengumpulkannya.

### Format dan lint

```sh
uv run --frozen --only-group dev ruff format .   # memformat Python (quote tunggal, lebar 120)
bun run format                                   # prettier --write, sama dengan langkah CI
bun run i18n:parse                               # regenerasi locale, sama dengan langkah CI
```

Sebelum push, putar ulang kedua workflow CI; daftar perintahnya di [ci.md](ci.md#memutar-ulang-ci-di-lokal).

## 6. Build produksi

`bun run build` di laptop biasanya kehabisan heap Node (OOM). Dockerfile dan CI menaikkan batasnya, jadi andalkan job **Frontend Build** di CI sebagai gerbang build. Bila tetap perlu build lokal:

```sh
NODE_OPTIONS=--max-old-space-size=8192 bun run build
```

Jangan mengedit `package.json` selama build berjalan: build membacanya di tengah proses dan gagal pada file yang setengah tertulis.
