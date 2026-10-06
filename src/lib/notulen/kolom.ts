import {
	DBS,
	DECISION_STATUS,
	SYARAT,
	filled,
	text,
	type NotulenRecord,
	type PropDef
} from './types';

// Kolom inti: the few kolom of each agenda the Corsec fills while the meeting runs, in working
// order (Erik, 2026-10-06). Every other kolom sits behind "Tampilkan semua kolom" unless it already
// holds something. Informasi Rapat (0) keeps INFO_GROUPS and is not listed here. Names are the
// stored field names (storage keys), not display labels.

const CORE: Record<number, string[]> = {
	1: [
		'Pemapar',
		'Posisi terkini / pencapaian',
		'Deviasi & hambatan',
		'Evaluasi strategi',
		'Kesimpulan / arahan'
	],
	2: [
		'Satuan',
		'Target / anggaran',
		'Realisasi',
		'Penyebab & langkah koreksi',
		'Kesimpulan / arahan'
	],
	3: [
		'Direktorat / divisi terkait',
		'Opsi solusi & rekomendasi',
		'PIC koordinasi',
		'Target penyelesaian',
		'Kesimpulan / arahan'
	],
	4: [
		'PIC utama',
		'Status progres',
		'Progres persen',
		'Hambatan & dukungan',
		'Kesimpulan / arahan'
	],
	5: ['Tingkat risiko', 'Risk owner / PIC', 'Mitigasi / kontrol', 'Tenggat', 'Kesimpulan / arahan'],
	6: [
		'Urgensi',
		'Isu / permintaan utama',
		'Posisi / respons perusahaan',
		'PIC komunikasi',
		// Stakeholder has no "Kesimpulan / arahan"; its outcome kolom is this one.
		'Output tindak lanjut'
	],
	7: [
		'Agenda',
		'Keputusan yang dimohonkan',
		'Status keputusan',
		'Rumusan keputusan',
		'PIC pelaksanaan'
	],
	8: ['PIC utama', 'Target waktu', 'Status', 'Agenda', 'Asal tindak lanjut']
};

/** Kolom a Keputusan brings into the kolom inti, right after Status keputusan. */
const BY_DECISION: Record<string, string[]> = {
	'Disetujui bersyarat': [SYARAT],
	Ditunda: [
		'Tanggal pembahasan ulang',
		'Data tambahan untuk keputusan ditunda',
		'PIC data tambahan'
	]
};

const byName = (db: number, names: string[]): PropDef[] =>
	names.map((n) => {
		const f = DBS[db].fields.find((x) => x.name === n);
		if (!f) throw new Error(`Kolom "${n}" tidak ada di database ${db}`);
		return f;
	});

/**
 * The kolom inti of one entry, in working order, without its title kolom. `status` stands in for
 * a Keputusan chosen but not yet recorded, so its kolom show while they are being filled.
 */
export const coreFields = (
	db: number,
	r: NotulenRecord,
	status = text(r.values[DECISION_STATUS])
): PropDef[] => {
	const names = [...(CORE[db] ?? [])];
	if (db === 7) {
		const extra = BY_DECISION[status] ?? [];
		names.splice(names.indexOf(DECISION_STATUS) + 1, 0, ...extra);
	}
	return byName(db, names);
};

/**
 * Every other kolom, in schema order: `filled` ones always show (nothing typed is ever hidden),
 * `empty` ones only behind "Tampilkan semua kolom".
 */
export const otherFields = (
	db: number,
	r: NotulenRecord,
	status?: string
): { filled: PropDef[]; empty: PropDef[] } => {
	const core = new Set(coreFields(db, r, status).map((f) => f.name));
	const rest = DBS[db].fields.filter((f) => f.type !== 'title' && !core.has(f.name));
	return {
		filled: rest.filter((f) => filled(r.values[f.name])),
		empty: rest.filter((f) => !filled(r.values[f.name]))
	};
};
