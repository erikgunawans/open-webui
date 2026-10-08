import { describe, expect, it } from 'vitest';

import { DEMO_ID, demoMeeting } from './demo';
import { meetingsToMove, moveToServer } from './migrate';
import { LocalStorageMeetingRepo } from './repo';
import { seedMeeting } from './seed';
import { MeetingApiError, type MoveResult } from './server-repo';
import type { Meeting } from './types';

// Pindahkan ke server, against a stand-in for `ServerMeetingRepo.move`: what the browser keeps and
// removes for every answer the server can give.

class MemoryStorage implements Storage {
	m = new Map<string, string>();
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

const noEvents = { addEventListener: () => {}, removeEventListener: () => {} };

const browser = (...meetings: Meeting[]) => {
	const storage = new MemoryStorage();
	const local = new LocalStorageMeetingRepo(storage, noEvents, 'erik');
	meetings.forEach((m) => local.save(m));
	return { storage, local };
};

const answering =
	(answer: (m: Meeting) => Omit<MoveResult, 'id'>) =>
	(seen: Meeting[][] = []) => ({
		move: async (meetings: Meeting[]) => {
			seen.push(meetings);
			return meetings.map((m) => ({ id: m.id, ...answer(m) }));
		}
	});

const moved = answering(() => ({ result: 'moved', revision: 1, confirmed: true, reason: null }));

describe('moveToServer', () => {
	it('sends every meeting this browser holds for the user, never the demo meeting', async () => {
		const { local } = browser(seedMeeting('rd-a'), seedMeeting('rd-b'), demoMeeting());
		const seen: Meeting[][] = [];
		const report = await moveToServer(local, moved(seen));
		expect(seen[0].map((m) => m.id)).toEqual(['rd-a', 'rd-b']);
		expect(report).toEqual({
			ok: true,
			outcomes: [
				{ id: 'rd-a', result: 'moved' },
				{ id: 'rd-b', result: 'moved' }
			]
		});
		// Moved: the browser's copies are gone; the demo meeting stays where it lives.
		expect(local.list().map((m) => m.id)).toEqual([DEMO_ID]);
		expect(meetingsToMove(local)).toEqual([]);
	});

	it('keeps the copy of a meeting the server holds differently, and of a refused one', async () => {
		const { local } = browser(seedMeeting('rd-a'), seedMeeting('rd-b'), seedMeeting('rd-c'));
		const server = answering((m) =>
			m.id === 'rd-a'
				? { result: 'on_server', revision: 4, confirmed: false, reason: null }
				: m.id === 'rd-b'
					? { result: 'refused', revision: null, confirmed: false, reason: 'malformed' }
					: { result: 'on_server', revision: 1, confirmed: true, reason: null }
		)();
		const report = await moveToServer(local, server);
		expect(report.ok && report.outcomes).toEqual([
			{ id: 'rd-a', result: 'kept' },
			{ id: 'rd-b', result: 'refused' },
			{ id: 'rd-c', result: 'on_server' }
		]);
		expect(meetingsToMove(local).map((m) => m.id)).toEqual(['rd-a', 'rd-b']);
	});

	it('keeps a copy that changed while it was moving', async () => {
		const { local } = browser(seedMeeting('rd-a'));
		const server = {
			move: async (meetings: Meeting[]) => {
				// Another tab edits the meeting before the server answers.
				local.save({ ...meetings[0], session: { ...meetings[0].session, currentAgenda: 5 } });
				return [
					{ id: 'rd-a', result: 'moved' as const, revision: 1, confirmed: true, reason: null }
				];
			}
		};
		const report = await moveToServer(local, server);
		expect(report.ok && report.outcomes).toEqual([{ id: 'rd-a', result: 'kept' }]);
		expect(local.get('rd-a')!.session.currentAgenda).toBe(5);
	});

	it('keeps everything when the whole request is refused or not answered', async () => {
		for (const error of [new MeetingApiError(403, 'restricted'), new TypeError('offline')]) {
			const { local } = browser(seedMeeting('rd-a'));
			const report = await moveToServer(local, {
				move: async () => {
					throw error;
				}
			});
			expect(report).toMatchObject({
				ok: false,
				status: error instanceof MeetingApiError ? 403 : 0
			});
			expect(meetingsToMove(local).map((m) => m.id)).toEqual(['rd-a']);
		}
	});

	it('never moves or touches unreadable data and its quarantined copy', async () => {
		const { storage, local } = browser(seedMeeting('rd-a'));
		storage.setItem(local.key('rd-rusak'), '{not json');
		expect(local.quarantine('rd-rusak')?.kept).toBe(true);
		const before = new Map(storage.m);
		const seen: Meeting[][] = [];
		await moveToServer(local, moved(seen));
		expect(seen[0].map((m) => m.id)).toEqual(['rd-a']);
		expect(storage.getItem(local.key('rd-rusak'))).toBe('{not json');
		const left = [...storage.m.keys()];
		expect(left).toEqual([...before.keys()].filter((k) => k !== local.key('rd-a')));
		expect(local.unreadableIds()).toEqual(['rd-rusak']);
	});

	it('sends nothing when there is nothing to move', async () => {
		const { local } = browser(demoMeeting());
		const seen: Meeting[][] = [];
		expect(await moveToServer(local, moved(seen))).toEqual({ ok: true, outcomes: [] });
		expect(seen).toEqual([]);
	});
});
