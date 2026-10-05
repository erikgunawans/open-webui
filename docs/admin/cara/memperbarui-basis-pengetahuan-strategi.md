# Memperbarui Basis Pengetahuan strategi

Ringkasan cara isi **JUP Strategy KB** diperbarui, dan apa yang boleh serta tidak boleh dilakukan admin di aplikasi.

## Aturan utama

**JUP Strategy KB dibuat dari repo `jup` yang terpisah, bukan diedit di aplikasi.** Sinkronisasi menghapus setiap berkas di koleksi itu yang tidak ditambahkannya sendiri. Berkas yang Anda tambahkan dengan tangan melalui **Ruang Kerja → Pengetahuan** akan hilang pada sinkronisasi berikutnya, tanpa peringatan.

Dokumen dari staf masuk lewat jalur lain, yaitu antrean **Tinjauan Pengetahuan**, ke koleksi **JUP Staff Contributions**. Lihat [meninjau-pengajuan-pengetahuan.md](meninjau-pengajuan-pengetahuan.md).

|                     | Jalur A: Strategy KB                                                    | Jalur B: kontribusi staf                                                             |
| ------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Koleksi di aplikasi | **JUP Strategy KB**                                                     | **JUP Staff Contributions**                                                          |
| Sumber kebenaran    | repo `jup`                                                              | berkas yang diunggah staf                                                            |
| Cara masuk          | skrip sinkronisasi dari repo `jup`                                      | disetujui admin di `/kb-review`                                                      |
| Keputusan           | [ADR-0011](../../adr/0011-the-strategy-kb-is-generated-from-records.md) | [ADR-0015](../../adr/0015-staff-contributions-are-a-separate-reviewed-collection.md) |

## Mengapa dibuat dari `records/`

Status mitra dan gate hanya dicatat di satu tempat, yaitu folder `records/` di repo `jup`. Tabel status mitra di `kb/partners.md` **dihasilkan** dari `records/engagements/` oleh `jup.kb_sync`, dan mode `--check` gagal jika keduanya berbeda ([ADR-0011](../../adr/0011-the-strategy-kb-is-generated-from-records.md)). Tujuannya: apa yang dikatakan asisten kepada komisaris tentang posisi suatu mitra tidak boleh berbeda dari catatan resmi.

## Alur singkat

Langkah lengkap, termasuk perintahnya, ada di [`docs/kb-update-process.md`](../../kb-update-process.md) (Route A). Ringkasnya:

1. Ubah sumber di repo `jup`: catatan di `records/`, prosa di `kb/*.md`, atau `DECISIONS.md`. Jangan mengedit di dalam blok `<!-- BEGIN generated:... -->`.
2. Jalankan ulang pembuatan dan pemeriksaan dengan `python -m jup.kb_sync` (exit `0` bersih, `1` ada drift, `2` struktur rusak).
3. Commit dan push repo `jup`. Hook pre-commit di repo itu menolak commit yang membuat drift.
4. Sinkronkan ke aplikasi dengan `bun deploy/gcp/sync-kb.ts` (jalankan `--check` dulu).
5. Jika salah satu dari delapan berkas suara berubah, jalankan `bun deploy/gcp/sync-voice-model.ts`.
6. Jika dashboard Portfolio perlu data baru, jalankan `deploy/gcp/sync-records.sh`.
7. Verifikasi: ajukan pertanyaan yang hanya dapat dijawab oleh isi baru, di **Obrolan Baru**.

Langkah 4–6 adalah penulisan produksi dan masing-masing memerlukan persetujuan setiap kali dijalankan. Skrip sinkronisasi berjalan di dalam tab browser admin yang sudah login karena aplikasi berada di belakang IAP.

## Batas suara

Asisten suara hanya menjawab dari **delapan berkas bernama** yang tercantum di [`docs/kb-update-process.md`](../../kb-update-process.md) (Step 5). Menambahkan berkas kesembilan adalah perubahan tata kelola, bukan perubahan teknis, karena materi suara diproses di Amerika Serikat ([ADR-0006](../../adr/0006-voice-material-crosses-to-the-us-under-zdr.md)). Lihat [penjelasan/lisensi-dan-lokasi-data.md](../penjelasan/lisensi-dan-lokasi-data.md).

## Yang perlu dihindari admin

- Menambah, mengganti, atau menghapus berkas di **JUP Strategy KB** dari aplikasi.
- Memasukkan dokumen staf ke **JUP Strategy KB**. Gunakan jalur B.
- Mengubah tabel status mitra di `kb/partners.md` secara langsung. Ubah catatannya di `records/engagements/`, lalu buat ulang.
