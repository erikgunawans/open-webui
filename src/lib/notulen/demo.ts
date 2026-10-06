import { RAPAT_DEMO as R } from './demo-source';
import { record, freshSession } from './seed';
import { RUMUSAN, ULANG, UNDECIDED } from './keputusan';
import { SYARAT, type DateValue, type Meeting, type NotulenRecord, type PropValue } from './types';

// The demo meeting: rapat-dummy-data.js (fictional) mapped into a Meeting through the schema's own
// property names, so the Layar reads it exactly as it reads real minutes. Only what the schema has
// no field for goes into `plan`.

export const DEMO_ID = 'demo';

const MONTHS: Record<string, string> = {
	Jan: '01',
	Feb: '02',
	Mar: '03',
	Apr: '04',
	Mei: '05',
	Jun: '06',
	Jul: '07',
	Agu: '08',
	Sep: '09',
	Okt: '10',
	Nov: '11',
	Des: '12'
};

/** "30 Okt 2026" or "31 Okt" (year 2026) → ISO date; "—" or anything unreadable → none. */
export const idDate = (s: string, year = 2026): DateValue | undefined => {
	const m = /^(\d{1,2}) (\w{3})(?: (\d{4}))?$/.exec(s.trim());
	if (!m || !MONTHS[m[2]]) return undefined;
	return { start: `${m[3] ?? year}-${MONTHS[m[2]]}-${m[1].padStart(2, '0')}`, end: '' };
};

const date = (start: string, end = ''): DateValue => ({ start, end });
const rp = (miliar: number) => Math.round(miliar * 1e9);
const SOURCE = 'Data dummy';

// The demo's decided Usulan carry what a Keputusan needs (Rumusan, Syarat, the date it comes back),
// so the demo's own Tutup rapat check does not scold it. The generated source has no such fields.
const RUMUSAN_DEMO: Record<string, string> = {
	'D-05':
		'Direksi menyetujui pembentukan task force rekonsiliasi aset ERP lintas direktorat selama 6 minggu, dipimpin Dit. Keuangan.'
};

/** The kolom a demo Keputusan needs, filled when the source leaves them out. */
export const demoKeputusan = (x: { id: string; mohon: string; status: string }) => {
	const out: Record<string, PropValue> = {};
	if (!x.status || x.status === UNDECIDED) return out;
	const mohon = x.mohon.replace(/^Menyetujui /, '').replace(/\.$/, '');
	out[RUMUSAN] =
		RUMUSAN_DEMO[x.id] ??
		(x.status === 'Ditolak'
			? `Direksi menolak usulan: ${mohon}.`
			: x.status === 'Ditunda'
				? `Direksi menunda keputusan atas usulan: ${mohon}.`
				: `Direksi menyetujui ${mohon}.`);
	if (x.status === 'Disetujui bersyarat')
		out[SYARAT] = 'Pelaksanaan menunggu reviu SPI atas metode dan dokumen pendukung.';
	if (x.status === 'Ditunda') out[ULANG] = { start: '2026-11-02', end: '' };
	return out;
};

export const demoMeeting = (now = Date.now()): Meeting => {
	const m = R.meta;
	const s = R.ringkasan;
	const c = R.kinerjaCatatan;

	const info: NotulenRecord = {
		...record(
			{
				'Nama rapat': m.nama,
				'Tanggal & waktu': date('2026-10-05T09:00', '2026-10-05T12:00'),
				'Ruang / lokasi': m.lokasi,
				'Periode pelaporan': date('2026-01-01', '2026-09-30'),
				'Klasifikasi dokumen': m.klasifikasi,
				'Status validasi': m.status,
				'Pimpinan rapat': m.pimpinan,
				Notulis: m.notulis,
				Peserta: m.peserta.map(([n, j]) => `${n} — ${j}`).join('\n'),
				'Peserta berhalangan': m.berhalangan.join('\n'),
				'Peserta eksternal & jabatan': m.eksternal.join('\n'),
				'Kondisi perusahaan': s.kondisi,
				'Isu perhatian Direksi': s.isu.join('\n'),
				'Tindak lanjut mendesak': s.mendesak.join('\n')
			},
			'',
			SOURCE
		),
		time: { 'Tanggal & waktu': true }
	};

	const strategi = R.strategi.map((x) =>
		record(
			{
				'Sasaran strategis': x.sasaran,
				Pemapar: x.pemapar,
				'Target & indikator': x.target,
				'Posisi terkini / pencapaian': x.posisi,
				'Evaluasi strategi': x.evaluasi,
				'Deviasi & hambatan': x.deviasi
			},
			'',
			SOURCE
		)
	);

	const kinerja = R.kinerja.map((x, i) =>
		record(
			{
				Indikator: x.ind,
				Satuan: x.sat,
				'Basis pelaporan': 'YTD',
				'Periode laporan': date('2026-01-01', '2026-09-30'),
				'Target / anggaran': String(x.target),
				Realisasi: String(x.real),
				'Deviasi persen': (((x.real - x.target) / x.target) * 100).toFixed(1),
				...(i === 0
					? {
							'Penyebab & langkah koreksi': `Penyebab: ${c.penyebab}\nKoreksi: ${c.koreksi}`,
							'Likuiditas & pendanaan': c.likuiditas
						}
					: {})
			},
			'',
			SOURCE
		)
	);

	const isu = R.isu.map((x) =>
		record(
			{
				Isu: x.isu,
				'Direktorat / divisi terkait': x.unit,
				'Dampak perusahaan': x.dampak,
				'Keputusan yang diperlukan': x.perlu,
				'PIC koordinasi': x.pic,
				...(idDate(x.target) ? { 'Target penyelesaian': idDate(x.target)! } : {}),
				'Referensi keputusan / tindak lanjut': x.ref
			},
			'',
			SOURCE
		)
	);

	const program = R.program.map((x) =>
		record(
			{
				'Program / proyek': x.nama,
				Kategori: x.kat,
				'PIC utama': x.pic,
				'Progres persen': String(x.pct),
				'Status progres': x.status,
				'Anggaran Rp': String(rp(x.ang)),
				'Realisasi Rp': String(rp(x.real)),
				'Target milestone': x.milestone
			},
			'',
			SOURCE
		)
	);

	const risiko = R.risiko.map((x) =>
		record(
			{
				'Risiko / isu kepatuhan': x.r,
				'Kategori dampak': [...x.kat],
				'Tingkat risiko': x.lvl,
				'Status mitigasi': x.status,
				'Risk owner / PIC': x.owner,
				...(idDate(x.tenggat) ? { Tenggat: idDate(x.tenggat)! } : {}),
				'Mitigasi / kontrol': x.mitigasi
			},
			'',
			SOURCE
		)
	);

	const stakeholder = R.stakeholder.map((x) =>
		record(
			{
				'Stakeholder / organisasi': x.org,
				'Jenis stakeholder': x.jenis,
				'Isu / permintaan utama': x.isu,
				Urgensi: x.urg,
				'PIC komunikasi': x.pic,
				...(idDate(x.target) ? { 'Target tindak lanjut': idDate(x.target)! } : {})
			},
			'',
			SOURCE
		)
	);

	const keputusan = R.keputusan.map((x) =>
		record(
			{
				'ID keputusan': x.id,
				'Topik keputusan': x.topik,
				Agenda: x.agenda,
				'Keputusan yang dimohonkan': x.mohon,
				'Opsi & rekomendasi': x.rekom,
				'Kewenangan / persetujuan lanjutan': [...x.kewenangan],
				'PIC pelaksanaan': x.pic,
				'Status keputusan': x.status,
				...demoKeputusan(x)
			},
			'',
			SOURCE
		)
	);

	const aksi = R.aksi.map((x) =>
		record(
			{
				'ID tindakan': x.id,
				'Tindakan / deliverable': x.t,
				'Asal tindak lanjut': x.asal,
				'PIC utama': x.pic,
				'Target waktu': date(x.target),
				Status: x.status,
				'Indikator penyelesaian': x.ind
			},
			'',
			SOURCE
		)
	);

	return {
		id: DEMO_ID,
		records: [[info], strategi, kinerja, isu, program, risiko, stakeholder, keputusan, aksi],
		session: freshSession(now),
		plan: {
			nomor: m.nomor,
			agendas: R.agendas.map((a) => ({ menit: a.menit, pemapar: a.pemapar })),
			strategicProgress: Object.fromEntries(strategi.map((r, i) => [r.id, R.strategi[i].pct])),
			revenueMonthly: R.kinerjaBulan.map(([b, real, t]) => [b, real, t])
		}
	};
};
