import { describe, expect, it } from 'vitest';

import { meetingRepoContract } from './repo.contract';
import { LocalStorageMeetingRepo, parseMeeting } from './repo';
import { seedMeeting } from './seed';

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

// One browser: every tab shares the storage, and another tab's write arrives as a storage event.
meetingRepoContract('LocalStorageMeetingRepo', () => {
	const storage = new MemoryStorage();
	const ev = events();
	const open = (user: string) => new LocalStorageMeetingRepo(storage, ev, user);
	return {
		open,
		writeElsewhere: (user, id, raw) => {
			const key = open(user).key(id);
			storage.setItem(key, raw);
			ev.fire(key, raw);
		},
		settle: async () => {}
	};
});

describe('LocalStorageMeetingRepo', () => {
	it('parses only a whole meeting', () => {
		const m = seedMeeting('r');
		expect(parseMeeting(JSON.stringify(m))).toEqual(m);
		expect(parseMeeting('{"id":"x"}')).toBeNull();
		expect(parseMeeting('not json')).toBeNull();
		expect(parseMeeting(null)).toBeNull();
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

	it('names the ids it cannot read, which list() skips', () => {
		const storage = new MemoryStorage();
		const repo = new LocalStorageMeetingRepo(storage, events(), 'user-1');
		repo.save(seedMeeting('rapat-1'));
		storage.setItem(repo.key('rapat-2'), 'not json');
		expect(repo.list().map((m) => m.id)).toEqual(['rapat-1']);
		expect(repo.unreadableIds()).toEqual(['rapat-2']);
	});
});
