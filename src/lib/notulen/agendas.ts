// Presentation constants shared by Notulen and Layar: agenda copy, groupings and status tones,
// verbatim from the design handoff (Bahasa Indonesia).

export interface AgendaCopy {
	eyebrow: string;
	nav: string;
	title: string;
	focus: string;
	unit?: string;
	/** The Layar's short name and two-digit number. */
	layar: string;
	no: string;
}

export const AGENDAS: AgendaCopy[] = [
	{
		eyebrow: 'Informasi rapat',
		nav: 'Informasi Rapat',
		title: 'Informasi & Ringkasan Rapat',
		focus:
			'Informasi rapat, peserta, dokumen, ringkasan eksekutif, serta penutupan dan validasi notulen.',
		layar: 'Pembukaan & Ringkasan',
		no: '00'
	},
	{
		eyebrow: 'Agenda 01',
		nav: '1. Strategic Update',
		title: '1. Strategic Update',
		focus: 'Perkembangan target dan strategi perusahaan.',
		unit: 'satu baris untuk setiap sasaran strategis',
		layar: 'Strategic Update',
		no: '01'
	},
	{
		eyebrow: 'Agenda 02',
		nav: '2. Kinerja Perusahaan',
		title: '2. Kinerja Perusahaan',
		focus: 'Revenue, EBITDA/laba, cash flow, CAPEX–OPEX, dan KPI.',
		unit: 'satu baris untuk setiap indikator',
		layar: 'Kinerja Perusahaan',
		no: '02'
	},
	{
		eyebrow: 'Agenda 03',
		nav: '3. Isu Lintas Direktorat',
		title: '3. Isu Lintas Direktorat / Divisi',
		focus: 'Masalah yang membutuhkan keputusan bersama.',
		unit: 'satu baris untuk setiap isu',
		layar: 'Isu Lintas Direktorat',
		no: '03'
	},
	{
		eyebrow: 'Agenda 04',
		nav: '4. Program Prioritas',
		title: '4. Program Prioritas',
		focus: 'Proyek strategis, investasi, business development, dan transformasi.',
		unit: 'satu baris untuk setiap program / proyek',
		layar: 'Program Prioritas',
		no: '04'
	},
	{
		eyebrow: 'Agenda 05',
		nav: '5. Risk & Compliance',
		title: '5. Risk & Compliance',
		focus: 'Risiko utama dan mitigasinya.',
		unit: 'satu baris untuk setiap risiko / isu kepatuhan',
		layar: 'Risk & Compliance',
		no: '05'
	},
	{
		eyebrow: 'Agenda 06',
		nav: '6. Stakeholder Issues',
		title: '6. Stakeholder Issues',
		focus: 'Pemegang Saham, regulator, pemerintah, mitra, dan pelanggan.',
		unit: 'satu baris untuk setiap stakeholder / isu',
		layar: 'Stakeholder Issues',
		no: '06'
	},
	{
		eyebrow: 'Agenda 07',
		nav: '7. Decision Making',
		title: '7. Decision Making',
		focus: 'Keputusan yang harus disepakati Direksi.',
		unit: 'satu baris untuk setiap usulan / keputusan',
		layar: 'Decision Making',
		no: '07'
	},
	{
		eyebrow: 'Agenda 08',
		nav: '8. Action Plan',
		title: '8. Action Plan',
		focus: 'PIC, target waktu, dan indikator penyelesaian.',
		unit: 'satu baris untuk setiap tindakan / deliverable',
		layar: 'Action Plan',
		no: '08'
	}
];

/** The standard BOD agenda plan (175 minutes), used when a meeting has none of its own. */
export const STANDARD_MINUTES = [10, 20, 25, 20, 25, 15, 15, 30, 15];

export const INFO_GROUPS: [string, string[]][] = [
	['Informasi rapat', ['Tanggal & waktu', 'Ruang / lokasi', 'Tautan meeting', 'Periode pelaporan']],
	[
		'Peserta',
		['Pimpinan rapat', 'Peserta', 'Peserta berhalangan', 'Peserta eksternal & jabatan', 'Notulis']
	],
	['Dokumen', ['Dokumen pendukung', 'Tautan bahan rapat', 'Klasifikasi dokumen']],
	[
		'Ringkasan eksekutif',
		[
			'Kondisi perusahaan',
			'Pencapaian & deviasi utama',
			'Isu perhatian Direksi',
			'Ringkasan keputusan utama',
			'Tindak lanjut mendesak'
		]
	],
	[
		'Penutupan & validasi',
		[
			'Topik rapat berikutnya',
			'Rapat berikutnya',
			'Waktu rapat ditutup',
			'Disusun oleh',
			'Tanggal penyusunan',
			'Diperiksa / disetujui oleh',
			'Tanggal validasi',
			'Status validasi'
		]
	],
	[
		'Checklist finalisasi',
		[
			'Delapan agenda dicatat',
			'Keputusan jelas',
			'PIC & tenggat lengkap',
			'Basis angka lengkap',
			'Bukti ditautkan',
			'Siap didistribusikan'
		]
	]
];

export const CHECKLIST = INFO_GROUPS[5][1];

export const SUMMARY_KEYS = [
	'Status validasi',
	'Status',
	'Status keputusan',
	'Status progres',
	'Status mitigasi',
	'Tingkat risiko',
	'Urgensi',
	'Evaluasi strategi',
	'Basis pelaporan',
	'Kategori',
	'Jenis stakeholder'
];

export type Tone = 'success' | 'info' | 'warning' | 'danger' | 'neutral';

const TONES: Record<string, Tone> = {
	Selesai: 'success',
	Disetujui: 'success',
	'On track': 'success',
	Dilanjutkan: 'success',
	Berjalan: 'info',
	'Dalam review': 'info',
	Disesuaikan: 'info',
	'Disetujui bersyarat': 'warning',
	'At risk': 'warning',
	Sedang: 'warning',
	Ditunda: 'warning',
	'Perlu evaluasi': 'warning',
	'Belum diputuskan': 'warning',
	Terhambat: 'danger',
	Delayed: 'danger',
	Ditolak: 'danger',
	'Perlu revisi': 'danger',
	Tinggi: 'danger',
	Mendesak: 'danger',
	Dihentikan: 'danger',
	Draft: 'neutral',
	'Belum mulai': 'neutral',
	Rendah: 'neutral'
};

/** Status word → badge tone. The Layar shows "Belum diputuskan" as neutral, Notulen as warning. */
export const toneOf = (s: string | undefined, surface: 'notulen' | 'layar' = 'notulen'): Tone =>
	surface === 'layar' && s === 'Belum diputuskan' ? 'neutral' : (TONES[s ?? ''] ?? 'neutral');

export const DECISION_STATUSES = [
	'Belum diputuskan',
	'Disetujui',
	'Disetujui bersyarat',
	'Ditunda',
	'Ditolak'
];
export const ACTION_COLUMNS = ['Belum mulai', 'Berjalan', 'Terhambat', 'Selesai'];
