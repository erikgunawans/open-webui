import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { LocalStorageMeetingRepo } from '../repo';
import { seedMeeting } from '../seed';
import type { Meeting } from '../types';
import { useMeeting, type SaveState, type Unreadable } from './useMeeting';

// Opening a meeting must never destroy what is stored under its id. These run the hook's opening
// (its state initialisers) through a server render, against an in-memory storage.

class MemoryStorage implements Storage {
	m = new Map<string, string>();
	/** Keys whose writes are refused, as a full or blocked browser storage would. */
	refuse: (k: string) => boolean = () => false;
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
		if (this.refuse(k)) throw new DOMException('quota', 'QuotaExceededError');
		this.m.set(k, v);
	}
}

const noEvents = { addEventListener: () => {}, removeEventListener: () => {} };

const openWith = (storage: MemoryStorage) => {
	const repo = new LocalStorageMeetingRepo(storage, noEvents, 'u');
	let out: { meeting: Meeting; saved: SaveState; unreadable: Unreadable } | null = null;
	const Probe = () => {
		const [meeting, , saved, unreadable] = useMeeting(repo, 'rapat-1', () =>
			seedMeeting('rapat-1')
		);
		out = { meeting, saved, unreadable };
		return null;
	};
	renderToStaticMarkup(<Probe />);
	return { repo, out: out! };
};

const OLD = '{"id":"rapat-1","records":[[],[]],"from":"an older version"}';

describe('opening a meeting', () => {
	it('reads a stored meeting as it is', () => {
		const storage = new MemoryStorage();
		const repo = new LocalStorageMeetingRepo(storage, noEvents, 'u');
		repo.save({
			...seedMeeting('rapat-1'),
			session: { ...seedMeeting('x').session, currentAgenda: 4 }
		});
		const { out } = openWith(storage);
		expect(out.unreadable).toBeNull();
		expect(out.meeting.session.currentAgenda).toBe(4);
	});

	it('copies unreadable data aside before the template is saved over it', () => {
		const storage = new MemoryStorage();
		const before = new LocalStorageMeetingRepo(storage, noEvents, 'u');
		storage.setItem(before.key('rapat-1'), OLD);
		// The list names it for recovery instead of silently dropping it.
		expect(before.list()).toEqual([]);
		expect(before.unreadableIds()).toEqual(['rapat-1']);
		const { repo, out } = openWith(storage);
		expect(repo.unreadableIds()).toEqual([]);
		expect(out.unreadable).toEqual({ raw: OLD, kept: true });
		expect(out.saved.ok).toBe(true);
		expect(repo.get('rapat-1')).not.toBeNull();
		const copies = [...storage.m].filter(([k]) => k.startsWith('jup-rapat-direksi-tidak-terbaca:'));
		expect(copies.map(([, v]) => v)).toEqual([OLD]);
		// The copy is never listed as a meeting.
		expect(repo.list().map((m) => m.id)).toEqual(['rapat-1']);
	});

	it('leaves the original untouched when the copy cannot be made', () => {
		const storage = new MemoryStorage();
		const key = new LocalStorageMeetingRepo(storage, noEvents, 'u').key('rapat-1');
		storage.setItem(key, OLD);
		storage.refuse = () => true;
		const { out } = openWith(storage);
		expect(out.unreadable).toEqual({ raw: OLD, kept: false });
		expect(out.saved.ok).toBe(false);
		expect(storage.getItem(key)).toBe(OLD);
	});
});
