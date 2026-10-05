# CI

Isi setiap workflow GitHub Actions di `.github/workflows/`, jebakan yang membuatnya merah, dan cara memutarnya ulang di lokal sebelum push.

## Ringkasan

| Workflow (nama di GitHub) | File               | Pemicu                                                                                                                            |
| ------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Python CI                 | `backend.yaml`     | Push/PR ke `main`/`dev` yang mengubah `backend/**`, `tests/**`, `pyproject.toml`, `uv.lock`, atau file workflow-nya; juga manual. |
| Frontend Build            | `frontend.yaml`    | Push/PR ke `main`/`dev`, **kecuali** perubahan yang hanya menyentuh `backend/**`, `pyproject.toml`, `uv.lock`.                    |
| Gateway                   | `gateway.yaml`     | Push/PR ke `main`/`dev` yang mengubah `gateway/**`.                                                                               |
| Drift gates               | `drift-gates.yaml` | Terjadwal setiap hari 05.00 WIB, manual, dan push ke `main` yang mengubah mesin gerbangnya.                                       |
| Tests                     | `regression.yaml`  | PR rilis upstream (judul berawalan versi, dari/ke `dev`). Praktis tidak berjalan di alur JUP.                                     |
| Release                   | `release.yml`      | Push ke `main`. Mesin rilis upstream.                                                                                             |
| Issue Labeler             | `issue-label.yaml` | Issue dibuka atau diubah.                                                                                                         |

Workflow upstream yang tidak berlaku untuk fork ini dimatikan dengan mengganti ekstensinya menjadi `.disabled`: `release-pypi.disabled`, `docker.disabled`, `codespell.disabled`, `lint-backend.disabled`, `lint-frontend.disabled`. Tidak ada yang di-deploy dari image ghcr; deploy berjalan lewat Cloud Build (lihat [alur kerja](alur-kerja.md)). `release.yml` masih aktif dan bisa gagal ketika upstream menaikkan versi di `package.json`; anggap kegagalannya sebagai warisan upstream, tetapi jangan biarkan itu membuat Anda mengabaikan tanda merah lain.

## Python CI

Tiga job:

1. **Ruff Format** (Python 3.11 dan 3.12):
   - `uv run --frozen --only-group dev ruff format --check . --exclude .venv --exclude venv`
   - `uv run --frozen --only-group dev ruff check --select=F --ignore=F401,F403,F405,F541,F811,F841 --output-format=github .`

   Ruff diambil dari lockfile (`--frozen`), jadi versi lokal dan CI sama. Menaikkan versinya adalah langkah sengaja: `uv lock --upgrade-package ruff`.

2. **pytest** (3.11 dan 3.12): `uv run --only-group dev pytest`. Tanpa runtime vendor, sehingga test yang butuh `open_webui` di-skip di sini.

3. **Runtime suite**: `uv sync --frozen` (runtime penuh, ~2 GB) lalu `uv run pytest tests/test_boot.py tests/test_jup_portfolio_endpoint.py -v`. Job ini hanya berjalan bila commit mengubah `migrations/` atau `jup_portfolio`, atau saat dijalankan manual (`workflow_dispatch`). Jalankan manual setelah rebase upstream.

**Python CI tidak memeriksa sumber frontend, padahal sebagian test membacanya.** Beberapa file di `tests/` memindai `.svelte` atau `.ts` sebagai teks (pemindaian aksesibilitas, paritas versi). PR yang hanya mengubah frontend tidak memicu Python CI, sehingga bisa merge dengan hijau lalu membuat `main` merah. Sebelum merge PR frontend, cari test yang membaca file yang Anda ubah dan jalankan di lokal:

```sh
rg -l "src/lib|\.svelte" tests/
uv run --only-group dev pytest -q tests/<file>
```

**Git tidak melacak direktori kosong.** Fixture yang bergantung pada direktori kosong ada di mesin Anda tetapi tidak ada di clone baru, sehingga test lolos di lokal dan gagal di CI dengan pesan yang tidak menyebut penyebabnya. Setelah menambah tree fixture, jalankan:

```sh
find tests/fixtures -type d -empty
```

Setiap direktori yang muncul perlu `.gitkeep`. Pembuktian paling jujur adalah clone ke folder sementara dan menjalankan suite di sana.

## Frontend Build

Job **Format & Build** (Node 22) menjalankan, berurutan:

1. `npm install --force`
2. `npm run format` (prettier `--write` atas `**/*.{js,ts,svelte,css,md,html,json}`)
3. `npm run i18n:parse` (regenerasi semua file locale)
4. `git diff --exit-code`
5. `NODE_OPTIONS=--max-old-space-size=8192 npm run build`

Langkah 4 membuat gerbang ini merah bila langkah 2 atau 3 **mengubah satu file saja**. Akibatnya:

- **Prosa juga bisa memerahkannya.** Glob prettier mencakup `md`, `json`, dan `html` di seluruh repo, termasuk perubahan "backend saja" seperti file `manifest.json` baru. Folder prosa fork yang tidak diformat tercantum di `.prettierignore` (`.planning/`, `PROGRESS.md`, `docs/adr/`, `docs/architecture/`, `deploy/`, `tests/fixtures/`, `skills/`, folder handoff, dan lain-lain). File markdown di luar daftar itu, termasuk `docs/dev/`, harus bersih menurut prettier.
- **Locale yang basi juga memerahkannya.** String `$i18n.t('…')` baru tanpa regenerasi locale membuat langkah 3 mengubah file. Commit hasil `i18n:parse` bersama perubahan komponennya.
- Selama langkah 4 merah, build di langkah 5 tidak pernah berjalan. Gerbang yang merah karena format sebenarnya tidak menguji build sama sekali.

Job **Unit Tests** menjalankan `npm ci --force` lalu `npm run test:frontend` (Vitest, sekali jalan di CI).

`.tsx` di `src/lib/notulen/` tidak diperiksa oleh langkah mana pun di atas: bukan oleh prettier, bukan oleh `svelte-check`. Jalankan `bun run check:notulen` dan prettier untuk `.tsx` sendiri (lihat [onboarding](onboarding.md#pulau-react-rapat-direksi-tsx)).

## Gateway

Di `gateway/`, dengan Bun 1.3.11: `bun install --frozen-lockfile`, `bunx tsc --noEmit`, `bun test`.

## Drift gates

Membandingkan apa yang tertulis dengan apa yang disajikan: `kb/partners.md` terhadap `records/` di repo JUP, dan bucket `gs://jup-ops-records` terhadap tree JUP. Keduanya butuh kredensial di luar repo ini. Bila secret-nya belum ada, job **di-skip (abu-abu), bukan lulus**, dan ringkasan run menyebut secret yang kurang. Job ini hanya membaca; penulisan ke bucket tetap tindakan manusia. Detail: [`deploy/gcp/drift-gates.md`](../../deploy/gcp/drift-gates.md).

## Memutar ulang CI di lokal

Putar ulang **kedua** workflow sebelum push, bukan hanya yang terasa relevan. pytest yang hijau tidak mengatakan apa pun tentang format, dan perubahan backend pun bisa memerahkan Frontend Build.

**Python CI:**

```sh
uv run --frozen --only-group dev ruff format --check . --exclude .venv --exclude venv
uv run --frozen --only-group dev ruff check --select=F --ignore=F401,F403,F405,F541,F811,F841 .
uv run --only-group dev pytest
find tests/fixtures -type d -empty
```

Untuk meniru environment CI yang bersih tanpa memakai `.venv` penuh: `UV_PROJECT_ENVIRONMENT=<folder-scratch>/devenv uv run --frozen --only-group dev pytest`.

**Frontend Build** (seluruh urutan, lalu pastikan tidak ada file yang berubah):

```sh
bun run format
bun run i18n:parse
git status --porcelain
bunx vitest run
bun run check:notulen
```

`git status --porcelain` harus kosong selain perubahan yang memang akan Anda commit. Untuk build, andalkan CI; build lokal biasanya OOM (lihat [onboarding](onboarding.md#6-build-produksi)).

**Gateway** (bila `gateway/` berubah): `cd gateway && bunx tsc --noEmit && bun test`.

Bila gerbangnya berbentuk "jalankan alat, lalu pastikan tree bersih", putar ulang **seluruh urutannya**, bukan hanya langkah yang Anda sentuh.
