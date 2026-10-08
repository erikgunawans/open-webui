import { describe, expect, it } from 'vitest';

import { reopenMeeting } from './keputusan';
import { closeMeeting } from './layar-model';
import { seedMeeting } from './seed';
import type { MeetingRepo } from './repo';
import type { Meeting } from './types';

// What every MeetingRepo must do, whatever it stores to. Each implementation's test file runs this
// suite with its own harness; a case that only one storage can have (a full localStorage, a server
// conflict) belongs in that implementation's own file, next to its run of the contract.
//
// Who sees whose meetings is not in here, because the two stores answer it differently: the
// browser keeps each account's meetings apart on a shared browser (its own file), while the server
// shows every meeting to every board reader and refuses everyone else (its HTTP tests).

export interface RepoHarness {
	/**
	 * A repository for `user`, ready to read. Repositories opened from one harness share one store.
	 * A server-backed one loads what the server holds first, so opening may be asynchronous.
	 */
	open(user: string): MeetingRepo | Promise<MeetingRepo>;
	/**
	 * Store `raw` (JSON, possibly malformed) as meeting `id` of `user`, the way another tab or
	 * machine would, so the repositories of that user can see it.
	 */
	writeElsewhere(user: string, id: string, raw: string): void;
	/** Let pending deliveries (polls, timers) run; the browser repository has none. */
	settle(): Promise<void>;
}

const at = (m: Meeting, currentAgenda: number): Meeting => ({
	...m,
	session: { ...m.session, currentAgenda }
});

export const meetingRepoContract = (name: string, harness: () => RepoHarness) =>
	describe(`${name} — MeetingRepo contract`, () => {
		it('round-trips a meeting and has nothing under an unknown id', async () => {
			const h = harness();
			const repo = await h.open('user-1');
			const m = seedMeeting('rapat-1');
			repo.save(m);
			await h.settle();
			expect(repo.get('rapat-1')).toEqual(m);
			expect((await h.open('user-1')).get('rapat-1')).toEqual(m);
			expect(repo.get('other')).toBeNull();
		});

		it('refuses malformed data: it never reads as a meeting nor reaches subscribers', async () => {
			const h = harness();
			const repo = await h.open('user-1');
			const seen: string[] = [];
			repo.subscribe('rapat-1', (x) => seen.push(x.id));
			h.writeElsewhere('user-1', 'rapat-1', '{"id":"rapat-1"}');
			h.writeElsewhere('user-1', 'rapat-1', 'not json');
			await h.settle();
			expect(repo.get('rapat-1')).toBeNull();
			expect(repo.list()).toEqual([]);
			expect(seen).toEqual([]);
		});

		it('tells subscribers about local saves and writes from elsewhere, and stops after unsubscribe', async () => {
			const h = harness();
			const repo = await h.open('user-1');
			const seen: number[] = [];
			const off = repo.subscribe('rapat-1', (x) => seen.push(x.session.currentAgenda));
			const m = seedMeeting('rapat-1');
			repo.save(at(m, 3));
			await h.settle();
			h.writeElsewhere('user-1', 'rapat-1', JSON.stringify(at(m, 7)));
			h.writeElsewhere('user-1', 'someone-else', JSON.stringify(seedMeeting('someone-else')));
			await h.settle();
			off();
			h.writeElsewhere('user-1', 'rapat-1', JSON.stringify(at(m, 5)));
			await h.settle();
			expect(seen).toEqual([3, 7]);
		});

		it('a closed meeting refuses changes until it is reopened with a reason', async () => {
			const h = harness();
			const repo = await h.open('user-1');
			const m = seedMeeting('rapat-1');
			repo.save(m);
			await h.settle();
			const closed = closeMeeting(m, 1_000);
			expect(repo.save(closed)).toBe(true);
			await h.settle();

			const seen: Meeting[] = [];
			repo.subscribe('rapat-1', (x) => seen.push(x));
			const session = { ...closed.session };
			delete session.closedAt;
			const blankReason = {
				...closed,
				session: { ...session, reopenings: [{ at: 2_000, reason: '   ' }] }
			};
			expect(repo.save(at(closed, 3))).toBe(false);
			expect(repo.save({ ...closed, notes: { 1: { text: 'diubah', risalah: false } } })).toBe(
				false
			);
			expect(repo.save(blankReason)).toBe(false);
			await h.settle();
			expect(seen).toEqual([]);
			expect(repo.get('rapat-1')).toEqual(closed);
			expect((await h.open('user-1')).get('rapat-1')).toEqual(closed);

			const reopened = reopenMeeting(closed, 'Koreksi agenda 07', 2_000);
			expect(repo.save(reopened)).toBe(true);
			expect(repo.save(at(reopened, 3))).toBe(true);
			await h.settle();
			expect((await h.open('user-1')).get('rapat-1')).toEqual(at(reopened, 3));

			// Closing again freezes it again.
			const again = closeMeeting(at(reopened, 3), 3_000);
			expect(repo.save(again)).toBe(true);
			expect(repo.save(at(again, 5))).toBe(false);
			await h.settle();
			expect((await h.open('user-1')).get('rapat-1')).toEqual(again);
		});

		it('lists every meeting', async () => {
			const h = harness();
			const repo = await h.open('user-1');
			repo.save(seedMeeting('rapat-1'));
			repo.save(seedMeeting('rapat-2'));
			await h.settle();
			expect(
				repo
					.list()
					.map((m) => m.id)
					.sort()
			).toEqual(['rapat-1', 'rapat-2']);
		});
	});
