import { describe, expect, it } from 'vitest';

import { SCHEMA } from './schema';
import { seedMeeting, KINERJA_STARTERS } from './seed';
import { LocalStorageMeetingRepo, parseMeeting } from './repo';
import { demoMeeting, idDate } from './demo';
import { DBS, titleField, filled } from './types';

class MemoryStorage implements Storage {
	private m = new Map<string, string>();
	get length() {
		return this.m.size;
	}
	clear() {
		this.m.clear();
	}
	getItem(k: string) {
		return this.m.get(k) ?? null;
	}
	key(i: number) {
		return [...this.m.keys()][i] ?? null;
	}
	removeItem(k: string) {
		this.m.delete(k);
	}
	setItem(k: string, v: string) {
		this.m.set(k, v);
	}
}

const events = () => {
	const target = new EventTarget();
	return {
		addEventListener: target.addEventListener.bind(target),
		removeEventListener: target.removeEventListener.bind(target),
		fire: (key: string, newValue: string) =>
			target.dispatchEvent(Object.assign(new Event('storage'), { key, newValue }))
	};
};

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

describe('repository', () => {
	it('round-trips a meeting and refuses malformed data', () => {
		const ev = events();
		const repo = new LocalStorageMeetingRepo(new MemoryStorage(), ev, 'user-1');
		const m = seedMeeting('rapat-1');
		repo.save(m);
		expect(repo.get('rapat-1')).toEqual(m);
		expect(repo.get('other')).toBeNull();
		expect(parseMeeting('{"id":"x"}')).toBeNull();
		expect(parseMeeting('not json')).toBeNull();
	});

	it('reports a refused write instead of swallowing it, and still tells this tab', () => {
		class FullStorage extends MemoryStorage {
			setItem(): void {
				throw new DOMException('quota', 'QuotaExceededError');
			}
		}
		const repo = new LocalStorageMeetingRepo(new FullStorage(), events(), 'user-1');
		const seen: string[] = [];
		repo.subscribe('rapat-1', (x) => seen.push(x.id));
		expect(repo.save(seedMeeting('rapat-1'))).toBe(false);
		expect(seen).toEqual(['rapat-1']);
		expect(new LocalStorageMeetingRepo(new MemoryStorage(), events()).save(seedMeeting('r'))).toBe(
			true
		);
	});

	it('tells subscribers about local saves and other tabs’ writes, and stops after unsubscribe', () => {
		const ev = events();
		const repo = new LocalStorageMeetingRepo(new MemoryStorage(), ev, 'user-1');
		const seen: number[] = [];
		const off = repo.subscribe('rapat-1', (x) => seen.push(x.session.currentAgenda));
		const m = seedMeeting('rapat-1');
		repo.save({ ...m, session: { ...m.session, currentAgenda: 3 } });
		ev.fire(
			repo.key('rapat-1'),
			JSON.stringify({ ...m, session: { ...m.session, currentAgenda: 7 } })
		);
		ev.fire(repo.key('someone-else'), JSON.stringify(m));
		off();
		ev.fire(repo.key('rapat-1'), JSON.stringify(m));
		expect(seen).toEqual([3, 7]);
	});

	it('keeps two users’ meetings apart on one browser', () => {
		const storage = new MemoryStorage();
		const a = new LocalStorageMeetingRepo(storage, events(), 'user-a');
		const b = new LocalStorageMeetingRepo(storage, events(), 'user-b');
		a.save(seedMeeting('rapat-1'));
		expect(b.get('rapat-1')).toBeNull();
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
