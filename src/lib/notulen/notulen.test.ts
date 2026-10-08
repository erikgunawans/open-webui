import { describe, expect, it } from 'vitest';

import { SCHEMA } from './schema';
import { seedMeeting, KINERJA_STARTERS } from './seed';
import { demoMeeting, idDate } from './demo';
import { DBS, titleField, filled } from './types';

describe('schema', () => {
	it('has 9 databases and 151 kolom (150 from the template + Syarat), each with exactly one title', () => {
		expect(SCHEMA).toHaveLength(9);
		expect(DBS.reduce((n, db) => n + db.fields.length, 0)).toBe(151);
		DBS.forEach((_, i) => expect(titleField(i)).toBeDefined());
	});
});

describe('seed', () => {
	const m = seedMeeting('rapat-1', 1000);

	it('is one Informasi entry, Strategic, Kinerja’s nine, and one empty form for each of agendas 3–8', () => {
		expect(m.records).toHaveLength(9);
		expect(m.records.map((r) => r.length)).toEqual([1, 1, 9, 1, 1, 1, 1, 1, 1]);
		const empty = m.records.flat().filter((r) => r.origin.startsWith('Formulir kosong'));
		expect(m.records.flat().length - empty.length).toBe(11);
		expect(empty).toHaveLength(6);
	});

	it('names the eight Kinerja starters and marks the Informasi entry Draft', () => {
		expect(m.records[2].slice(0, 8).map((r) => r.values.Indikator)).toEqual(KINERJA_STARTERS);
		expect(m.records[0][0].values['Status validasi']).toBe('Draft');
		expect(m.records[0][0].values['Nama rapat']).toBe('Isi nama rapat');
	});

	it('starts the session at agenda 00 with nothing done', () => {
		expect(m.session).toEqual({ currentAgenda: 0, doneAgendas: [], agendaEnteredAt: 1000 });
	});

	it('gives every record a unique id', () => {
		const ids = m.records.flat().map((r) => r.id);
		expect(new Set(ids).size).toBe(ids.length);
	});
});

describe('demo meeting', () => {
	const d = demoMeeting(0);

	it('maps the dummy data into the schema collections', () => {
		expect(d.records.map((r) => r.length)).toEqual([1, 4, 8, 3, 6, 5, 5, 5, 8]);
		expect(d.plan?.agendas.reduce((n, a) => n + a.menit, 0)).toBe(175);
	});

	it('uses only property names the schema defines', () => {
		d.records.forEach((coll, db) => {
			const names = new Set(DBS[db].fields.map((f) => f.name));
			coll.forEach((r) => Object.keys(r.values).forEach((k) => expect(names).toContain(k)));
		});
	});

	it('only uses options the schema allows', () => {
		d.records.forEach((coll, db) =>
			coll.forEach((r) =>
				Object.entries(r.values).forEach(([k, v]) => {
					const f = DBS[db].fields.find((x) => x.name === k)!;
					if (f.type === 'select' || f.type === 'status') expect(f.options).toContain(v);
					if (f.type === 'multi_select')
						(v as string[]).forEach((o) => expect(f.options).toContain(o));
				})
			)
		);
	});

	it('reads Indonesian short dates and skips a dash', () => {
		expect(idDate('31 Okt')).toEqual({ start: '2026-10-31', end: '' });
		expect(idDate('6 Nov 2026')).toEqual({ start: '2026-11-06', end: '' });
		expect(idDate('—')).toBeUndefined();
		expect(filled(idDate('—'))).toBe(false);
	});
});
