import { describe, expect, it } from 'vitest';

import { agendaNo, agendaOption, captureRecord, CAPTURED, kindsFor } from './capture';
import { coreFields, otherFields } from './kolom';
import { record } from './seed';
import { DBS, titleField } from './types';

describe('kolom inti', () => {
	it('names only kolom that exist, for every agenda', () => {
		for (let db = 1; db <= 8; db++) expect(coreFields(db, record()).length).toBeGreaterThan(3);
	});

	it('keeps working order, not the alphabetical schema order', () => {
		expect(coreFields(5, record()).map((f) => f.name)).toEqual([
			'Tingkat risiko',
			'Risk owner / PIC',
			'Mitigasi / kontrol',
			'Tenggat',
			'Kesimpulan / arahan'
		]);
	});

	it('brings the Ditunda kolom in right after Status keputusan', () => {
		const names = coreFields(7, record({ 'Status keputusan': 'Ditunda' })).map((f) => f.name);
		expect(
			names.slice(names.indexOf('Status keputusan') + 1, names.indexOf('Status keputusan') + 4)
		).toEqual([
			'Tanggal pembahasan ulang',
			'Data tambahan untuk keputusan ditunda',
			'PIC data tambahan'
		]);
		expect(coreFields(7, record()).map((f) => f.name)).not.toContain('Tanggal pembahasan ulang');
	});

	it('splits every other kolom into filled and empty, none lost and none twice', () => {
		const r = record({ 'Unit pendukung': 'Legal' });
		const core = coreFields(8, r).map((f) => f.name);
		const { filled, empty } = otherFields(8, r);
		expect(filled.map((f) => f.name)).toEqual(['Unit pendukung']);
		const all = [
			titleField(8).name,
			...core,
			...filled.map((f) => f.name),
			...empty.map((f) => f.name)
		];
		expect(new Set(all).size).toBe(DBS[8].fields.length);
	});
});

describe('catat cepat', () => {
	it('offers a Butir only on agendas with their own entries', () => {
		expect(kindsFor(0)).toEqual([]);
		expect(kindsFor(4)).toEqual(['butir', 'usulan', 'tindakan']);
		expect(kindsFor(7)).toEqual(['usulan', 'tindakan']);
		expect(kindsFor(8)).toEqual(['tindakan']);
	});

	it('maps an agenda to its stored option and back', () => {
		expect(agendaOption(4)).toMatch(/^4\. /);
		expect(agendaNo(agendaOption(4))).toBe('04');
		expect(agendaNo('')).toBe('');
	});

	it('puts a Butir in its own agenda', () => {
		const { db, record: r } = captureRecord({ kind: 'butir', from: 3, title: '  Sengketa lahan ' });
		expect(db).toBe(3);
		expect(r.values[titleField(3).name]).toBe('Sengketa lahan');
		expect(r.origin).toBe(CAPTURED);
	});

	it('puts an Usulan in 07, undecided, remembering where it came from', () => {
		const { db, record: r } = captureRecord({ kind: 'usulan', from: 4, title: 'Kemitraan X' });
		expect(db).toBe(7);
		expect(r.values['Status keputusan']).toBe('Belum diputuskan');
		expect(agendaNo(r.values.Agenda as string)).toBe('04');
	});

	it('puts a Tindakan in 08 with its PIC and tenggat', () => {
		const { db, record: r } = captureRecord({
			kind: 'tindakan',
			from: 5,
			title: 'Review kontrak',
			pic: ' Legal ',
			due: '2026-10-20'
		});
		expect(db).toBe(8);
		expect(r.values['PIC utama']).toBe('Legal');
		expect(r.values['Target waktu']).toEqual({ start: '2026-10-20', end: '' });
		expect(r.values['Asal tindak lanjut']).toBe('Rapat ini');
		expect(DBS[8].fields.find((f) => f.name === 'Status')!.options).toContain(r.values.Status);
	});
});
