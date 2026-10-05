# Panduan Pengembang None-JUPe

Titik masuk bagi pengembang yang baru bergabung: apa fork ini, bagian repo mana yang milik JUP, dan dokumen mana yang dibaca berikutnya.

## Apa ini

None-JUPe adalah Operating Layer PT Jakarta Utilitas Propertindo (JUP): ruang kerja AI internal yang tertata (governed), dibangun di atas fork [Open WebUI](https://github.com/open-webui/open-webui) v0.11.3 (commit `0a7c158`). Repo kerjanya `erikgunawans/ent-os-new-jup` (privat). Upstream dipasang sebagai remote `upstream` dan hanya ditarik, tidak pernah didorong. Fork ini di-rebase ke upstream setiap kuartal ([ADR-0007](../adr/0007-track-upstream-rebasing-quarterly.md)), sehingga setiap baris yang kita ubah di kode vendor adalah konflik yang harus dibawa terus. Karena itu kode JUP sebisa mungkin hidup di direktori sendiri.

Komponen utamanya:

- **Frontend**: SvelteKit (`adapter-static`) di `src/`. Hasil build disajikan oleh backend; tidak ada server route SvelteKit.
- **Backend**: Python FastAPI di `backend/open_webui/` (vendor) ditambah paket JUP `backend/jup/`.
- **Pulau React Rapat Direksi**: layar Notulen dan Layar di `src/lib/notulen/react/`, memakai `@jup/ui` (React 18), dipasang dari Svelte lewat `src/lib/notulen/react/entry.tsx`.
- **Gateway**: layanan Bun + TypeScript di `gateway/` yang menerima pesan Teams dan WhatsApp lalu meneruskannya ke ent-os atas nama satu pengguna JUP.

Kosakata domain (Operating Layer, Gate, Engagement, dan seterusnya) ada di [`CONTEXT.md`](../../CONTEXT.md). Pedoman untuk agen AI ada di [`AGENTS.md`](../../AGENTS.md). `README.md` di root repo adalah milik upstream; jangan diubah.

## Peta repo

Prinsipnya: tambahkan, jangan ubah. Direktori di kolom "JUP" bebas diubah; direktori vendor hanya disentuh bila tidak ada jalan lain, dan setiap tambalan dicatat di [`deploy/gcp/VENDOR-PATCHES.md`](../../deploy/gcp/VENDOR-PATCHES.md).

| Path                                                                                  | Pemilik       | Isi                                                                                                                                          |
| ------------------------------------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/jup/`                                                                        | JUP           | Logika domain JUP: portfolio, gate, approval, kontrak, leadership (Ruang Pimpinan), voice, office, channel. Bisa diuji tanpa runtime vendor. |
| `backend/jup_mcp/`                                                                    | JUP           | Server MCP keputusan (`decisions.py`).                                                                                                       |
| `backend/open_webui/routers/jup_*.py`                                                 | JUP di vendor | Router FastAPI JUP. Harus hidup di dalam `open_webui/` karena dipasang ke app vendor.                                                        |
| `backend/open_webui/` (selain di atas)                                                | Vendor        | Kode Open WebUI. Tambalan JUP tercatat di `VENDOR-PATCHES.md`.                                                                               |
| `tools/`                                                                              | JUP           | Sumber tool Open WebUI (`*.py`); disinkronkan ke app oleh `deploy/gcp/sync-tools.ts`.                                                        |
| `tests/`                                                                              | JUP           | Seluruh suite pytest fork. `test/` (tunggal) milik upstream.                                                                                 |
| `src/lib/{contracts,gate,iap,leadership,notulen,office,voice}/`                       | JUP           | Logika frontend JUP.                                                                                                                         |
| `src/lib/components/{contracts,jup,kb-review,leadership}/`                            | JUP           | Komponen Svelte JUP.                                                                                                                         |
| `src/lib/apis/{contracts,kb-review,leadership,portfolio,voice,whatsapp-link}/`        | JUP           | Klien API JUP.                                                                                                                               |
| `src/routes/(app)/{portfolio,kb-review,ruang-pimpinan}/`                              | JUP           | Halaman JUP.                                                                                                                                 |
| `src/jup-tokens.css`, `src/jup-skin.css`                                              | JUP           | Token JUP Design System dan lapisan restyle untuk komponen vendor.                                                                           |
| `src/` (selain di atas)                                                               | Vendor        | Frontend Open WebUI.                                                                                                                         |
| `gateway/`                                                                            | JUP           | jup-gateway (Bun, TypeScript). Lihat [`gateway/README.md`](../../gateway/README.md).                                                         |
| `deploy/gcp/`                                                                         | JUP           | Skrip deploy Cloud Run, sinkronisasi tool/skill/KB, catatan tambalan vendor.                                                                 |
| `design/jup-design-system/`                                                           | JUP           | Salinan referensi JUP Design System.                                                                                                         |
| `design_handoff_notulen_rapat_direksi/`                                               | JUP (handoff) | Handoff desain Rapat Direksi. Disimpan apa adanya; dibaca oleh `scripts/gen-schema.ts`.                                                      |
| `skills/`                                                                             | JUP           | Sumber skill yang disinkronkan ke app apa adanya.                                                                                            |
| `vendor/jup-ui-<versi>.tgz`                                                           | JUP           | Paket `@jup/ui` yang di-vendor (repo privat, tanpa registry).                                                                                |
| `scripts/gen-schema.ts`, `scripts/agent-depth.ts`, `scripts/wizard-jup-repo-token.sh` | JUP           | Skrip JUP. Sisanya di `scripts/` milik upstream.                                                                                             |
| `.planning/`, `PROGRESS.md`                                                           | JUP           | Catatan kerja dan checkpoint sesi. Lihat [alur kerja](alur-kerja.md).                                                                        |

Untuk memahami kode vendor, jangan membaca ulang dari nol: [`docs/architecture/README.md`](../architecture/README.md) memetakan seluruh basis kode Open WebUI per area (backend core, model, router, pipeline chat, RAG, migrasi, frontend). Untuk keputusan JUP, baca [`docs/adr/`](../adr/); keputusan baru dicatat sebagai ADR berikutnya di sana.

## Peta dokumentasi

| Folder                                     | Pembaca                    | Isi                                                                                    |
| ------------------------------------------ | -------------------------- | -------------------------------------------------------------------------------------- |
| [`docs/panduan/`](../panduan/)             | Staf JUP                   | Cara memakai None-JUPe sehari-hari.                                                    |
| [`docs/admin/`](../admin/)                 | Admin aplikasi             | Pengguna, grup, izin, model, tool.                                                     |
| [`docs/ops/`](../ops/)                     | Operator                   | Deploy, rollback, runbook. Mulai dari [`runbook-deploy.md`](../ops/runbook-deploy.md). |
| `docs/dev/` (folder ini)                   | Pengembang                 | Onboarding, aturan repo, CI, alur kerja.                                               |
| [`docs/adr/`](../adr/)                     | Semua yang mengubah desain | Keputusan arsitektur yang sudah diambil.                                               |
| [`docs/architecture/`](../architecture/)   | Pengembang                 | Peta kode vendor Open WebUI.                                                           |
| [`docs/design-system/`](../design-system/) | Pengembang frontend        | Token dan penerapan brand.                                                             |
| [`docs/agents/`](../agents/)               | Agen AI dan pengembang     | Issue tracker, label triase, dokumen domain.                                           |

## Dokumen di folder ini

1. [`onboarding.md`](onboarding.md): menyiapkan mesin, menjalankan server dev, dan menjalankan semua test.
2. [`aturan-repo.md`](aturan-repo.md): aturan khusus fork ini dan jebakan yang sudah pernah memakan korban.
3. [`ci.md`](ci.md): isi setiap workflow GitHub Actions dan cara memutarnya ulang di lokal.
4. [`alur-kerja.md`](alur-kerja.md): dari branch sampai verifikasi di produksi, termasuk checkpoint sesi.
