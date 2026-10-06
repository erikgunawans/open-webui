import { Card } from '@jup/ui';

import { CHECKLIST } from '../../agendas';

// Panduan: how this Notulen and its Layar are used, before, during and after a Rapat Direksi.
// Written for this screen (Erik, 2026-10-06) in the words of CONTEXT.md — it replaced the Notion
// template's guide, which taught Notion buttons. Keep it in step with the screen it describes.

export const Guide = () => (
	<section className="nt-agenda" aria-labelledby="nt-h-guide">
		<header className="nt-ahead">
			<div className="nt-eyebrow">Panduan</div>
			<h2 className="nt-h2" id="nt-h-guide">
				Panduan & checklist
			</h2>
			<p className="nt-focus">
				Notulen diisi Sekretaris Perusahaan di laptop; Layar menayangkan rapat yang sama ke
				proyektor. Keduanya berjalan di satu laptop dan selalu sama isinya.
			</p>
		</header>
		<Card padding="lg">
			<div className="nt-guide">
				<h2>Sebelum rapat</h2>
				<ol>
					<li>
						Lengkapi <strong>Informasi Rapat</strong>: nama rapat, tanggal dan waktu, tempat,
						pimpinan, notulis, dan peserta.
					</li>
					<li>
						Masukkan bahan yang sudah diketahui ke agenda masing-masing: sasaran strategis (01),
						angka kinerja (02 sudah berisi indikator awal), isu, program, risiko, pemangku
						kepentingan, usulan yang akan dimohonkan keputusan (07), dan tindakan dari rapat
						sebelumnya (08, dengan <em>Asal tindak lanjut: Rapat sebelumnya</em>).
					</li>
					<li>
						Buka <strong>Buka layar</strong>, pindahkan jendelanya ke proyektor, lalu tekan{' '}
						<strong>Layar penuh</strong> atau tombol <kbd>F</kbd>. Notulen tetap di layar laptop.
					</li>
				</ol>

				<h2>Saat rapat</h2>
				<h3>Mengikuti Layar</h3>
				<p>
					Tanda <strong>● Di layar</strong> di daftar agenda menunjukkan agenda yang sedang
					ditayangkan. Selama <strong>Ikuti layar</strong> menyala, Notulen pindah agenda bersama
					Layar. Membuka agenda lain secara manual mematikannya; nyalakan lagi untuk kembali ke
					agenda yang ditayangkan.
				</p>
				<h3>Catat cepat</h3>
				<p>
					Di atas setiap agenda: pilih <strong>Butir</strong>, <strong>Usulan</strong>, atau{' '}
					<strong>Tindakan</strong>, ketik satu kalimat, tekan <kbd>Enter</kbd>.
				</p>
				<ul>
					<li>
						<strong>Butir pembahasan</strong> masuk ke agenda yang sedang dibuka.
					</li>
					<li>
						<strong>Usulan</strong> masuk ke 07 untuk diputuskan, dengan keterangan agenda asalnya.
					</li>
					<li>
						<strong>Tindakan</strong> masuk ke 08 bersama PIC dan tenggatnya.
					</li>
				</ul>
				<h3>Catatan pembahasan</h3>
				<p>
					Tulis jalannya diskusi apa adanya di kotak <strong>Catatan pembahasan</strong> setiap
					agenda. Catatan ini tidak ikut ke Risalah kecuali <strong>Sertakan di Risalah</strong>{' '}
					dicentang.
				</p>
				<h3>Kolom</h3>
				<p>
					Kartu menampilkan <strong>kolom inti</strong> agenda itu, sesuai urutan kerja rapat. Kolom
					lain yang sudah terisi selalu tampil; yang masih kosong ada di balik{' '}
					<strong>Tampilkan semua kolom</strong>.
				</p>
				<h3>Arahan</h3>
				<p>
					Tulis arahan Direksi di <strong>Kesimpulan / arahan</strong> butir yang dibahas. Bila
					arahan menyebut siapa dan kapan, catat juga sebagai <strong>Tindakan</strong>: hanya
					tindakan di 08 yang dipantau.
				</p>
				<h3>Keputusan</h3>
				<p>
					Keputusan diambil di agenda 07, di Layar atau di Notulen. Keputusan baru tercatat setelah
					kolomnya terisi:
				</p>
				<ul>
					<li>
						setiap keputusan: <strong>Rumusan keputusan</strong>;
					</li>
					<li>
						<strong>Disetujui bersyarat</strong>: juga <strong>Syarat</strong>;
					</li>
					<li>
						<strong>Ditunda</strong>: juga <strong>Tanggal pembahasan ulang</strong>.
					</li>
				</ul>
				<p>
					Di Layar, rumusan dan syarat diketik di tempat sehingga peserta membaca kalimatnya saat
					ditulis. Pertimbangan (alasan keputusan) diisi terpisah dari Syarat.
				</p>
				<h3>Tutup rapat</h3>
				<p>
					Tekan <strong>Tutup rapat</strong> di agenda 08 Layar atau di kepala Notulen. Bila masih
					ada usulan belum diputuskan, tindakan tanpa PIC, atau keputusan tanpa rumusan, jumlahnya
					ditampilkan lebih dulu: pilih <strong>Tutup tetap</strong> atau{' '}
					<strong>Kembali ke 07</strong>. Setelah ditutup, Notulen hanya-baca.{' '}
					<strong>Buka kembali</strong> meminta alasan, dan alasan itu dicetak di Risalah.
				</p>

				<h2>Setelah rapat</h2>
				<ol>
					<li>
						Lengkapi <strong>Ringkasan eksekutif</strong> dan <strong>Penutupan & validasi</strong>{' '}
						di Informasi Rapat (perlu Buka kembali bila rapat sudah ditutup).
					</li>
					<li>
						<strong>Cetak / PDF</strong> menghasilkan Risalah formal.{' '}
						<strong>Simpan HTML terisi</strong> membuat salinan baca-saja untuk arsip.
					</li>
					<li>
						Isian tersimpan di peramban dan perangkat ini saja. Simpan salinan HTML sebelum
						membersihkan peramban atau berganti perangkat.
					</li>
				</ol>
				<p className="note">
					<strong>Catatan angka.</strong> Deviasi dan progres diisi manual, bukan dihitung otomatis:
					10 berarti 10%. Anggaran dan realisasi program dalam rupiah penuh; angka kinerja memakai
					satuan yang dipilih di kolom Satuan.
				</p>

				<h2>Checklist finalisasi</h2>
				<p>Centang di Informasi Rapat › Checklist finalisasi sebelum Risalah didistribusikan:</p>
				<ul>
					{CHECKLIST.map((c) => (
						<li key={c}>{c}</li>
					))}
				</ul>
			</div>
		</Card>
	</section>
);
