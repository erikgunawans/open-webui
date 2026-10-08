import { describe, expect, it } from 'vitest';

import { seedMeeting } from './seed';
import type { MeetingRepo } from './repo';
import type { Meeting } from './types';

// What every MeetingRepo must do, whatever it stores to. Each implementation's test file runs this
// suite with its own harness; a case that only one storage can have (a full localStorage, a server
// conflict) belongs in that implementation's own file, next to its run of the contract.

export interface RepoHarness {
	/** A repository for `user`. Repositories opened from one harness share one store. */
	open(user: string): MeetingRepo;
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
			const repo = h.open('user-1');
			const m = seedMeeting('rapat-1');
			repo.save(m);
			await h.settle();
			expect(repo.get('rapat-1')).toEqual(m);
			expect(h.open('user-1').get('rapat-1')).toEqual(m);
			expect(repo.get('other')).toBeNull();
		});

		it('refuses malformed data: it never reads as a meeting nor reaches subscribers', async () => {
			const h = harness();
			const repo = h.open('user-1');
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
			const repo = h.open('user-1');
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

		it('lists every meeting of this user', async () => {
			const h = harness();
			const repo = h.open('user-1');
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

		it('keeps two users’ meetings apart', async () => {
			const h = harness();
			const a = h.open('user-a');
			const b = h.open('user-b');
			a.save(seedMeeting('rapat-1'));
			await h.settle();
			expect(b.get('rapat-1')).toBeNull();
			expect(b.list()).toEqual([]);
		});
	});
