import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { meetingRepoContract } from './repo.contract';
import { seedMeeting } from './seed';
import {
	MeetingApiError,
	ServerMeetingRepo,
	type MeetingApi,
	type StoredMeeting
} from './server-repo';
import type { Meeting } from './types';

// The server repository against a fake HTTP layer that answers the way the leadership API does:
// a create of a stored id and a save on a stale revision are 409s carrying the stored revision, a
// save of an unknown meeting is 404. Time is fake, so `settle` runs the save, retry and poll timers.

class FakeServer {
	rows = new Map<string, { raw: string; revision: number }>();
	/** Requests answered with this error instead, oldest first (0 = the network did not answer). */
	failures: number[] = [];
	writes = 0;

	put(id: string, raw: string) {
		this.rows.set(id, { raw, revision: (this.rows.get(id)?.revision ?? 0) + 1 });
	}

	private stored(id: string): StoredMeeting | null {
		const row = this.rows.get(id);
		if (!row) return null;
		let document: unknown;
		try {
			document = JSON.parse(row.raw);
		} catch {
			document = row.raw;
		}
		return { id, revision: row.revision, document };
	}

	private answer() {
		const status = this.failures.shift();
		if (status !== undefined) throw new MeetingApiError(status, `fake ${status}`);
	}

	api(): MeetingApi {
		return {
			list: async () => {
				this.answer();
				return [...this.rows.keys()].map((id) => this.stored(id)!);
			},
			get: async (id) => {
				this.answer();
				return this.stored(id);
			},
			create: async (m: Meeting) => {
				this.answer();
				const row = this.rows.get(m.id);
				if (row) throw new MeetingApiError(409, 'exists', row.revision);
				this.writes++;
				this.put(m.id, JSON.stringify(m));
				return { revision: 1 };
			},
			save: async (id, base, m: Meeting) => {
				this.answer();
				const row = this.rows.get(id);
				if (!row) throw new MeetingApiError(404, 'no such meeting');
				if (row.revision !== base) throw new MeetingApiError(409, 'stale', row.revision);
				this.writes++;
				this.put(id, JSON.stringify(m));
				return { revision: base + 1 };
			}
		};
	}
}

const settle = () => vi.advanceTimersByTimeAsync(6000);

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

// One server for every machine: the user named here is the signed-in account, and every board
// reader sees the same meetings, so the fake keeps one store.
meetingRepoContract('ServerMeetingRepo', () => {
	const server = new FakeServer();
	return {
		open: () => ServerMeetingRepo.open(server.api()),
		writeElsewhere: (_user, id, raw) => server.put(id, raw),
		settle: async () => {
			await settle();
		}
	};
});

const at = (m: Meeting, currentAgenda: number): Meeting => ({
	...m,
	session: { ...m.session, currentAgenda }
});

const agendaOnServer = (server: FakeServer, id: string) =>
	(JSON.parse(server.rows.get(id)!.raw) as Meeting).session.currentAgenda;

describe('ServerMeetingRepo', () => {
	it('gathers quick changes into one write', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		const m = seedMeeting('rapat-1');
		for (let i = 1; i <= 5; i++) repo.save(at(m, i));
		expect(repo.status('rapat-1')).toBe('saving');
		await settle();
		expect(server.writes).toBe(1);
		expect(agendaOnServer(server, 'rapat-1')).toBe(5);
		expect(repo.status('rapat-1')).toBe('saved');
	});

	it('sends at once on flush', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		repo.save(seedMeeting('rapat-1'));
		repo.flush();
		await vi.advanceTimersByTimeAsync(0);
		expect(server.writes).toBe(1);
	});

	it('on a conflict, shows the server’s meeting and keeps the local edits', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		const m = seedMeeting('rapat-1');
		repo.save(at(m, 3));
		await settle();
		const seen: number[] = [];
		const statuses: string[] = [];
		repo.subscribe('rapat-1', (x) => seen.push(x.session.currentAgenda));
		repo.onStatus('rapat-1', (s) => statuses.push(s));

		// Another machine saves first; this tab, still on the older revision, saves next.
		server.put('rapat-1', JSON.stringify(at(m, 7)));
		repo.save(at(m, 4));
		await settle();

		expect(repo.status('rapat-1')).toBe('conflict');
		expect(statuses).toContain('conflict');
		expect(repo.get('rapat-1')).toEqual(at(m, 7));
		expect(repo.conflict('rapat-1')).toEqual(at(m, 4));
		expect(seen).toEqual([4, 7]);
		// Nothing was overwritten on the server.
		expect(agendaOnServer(server, 'rapat-1')).toBe(7);

		// The Corsec re-applies the edit on the server's version; it lands and the conflict clears.
		repo.save(at(repo.get('rapat-1')!, 4));
		await settle();
		expect(repo.status('rapat-1')).toBe('saved');
		expect(repo.conflict('rapat-1')).toBeNull();
		expect(agendaOnServer(server, 'rapat-1')).toBe(4);
	});

	it('creating a meeting another machine already created is a conflict, not an overwrite', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		const m = seedMeeting('rapat-1');
		server.put('rapat-1', JSON.stringify(at(m, 6)));
		repo.save(at(m, 0));
		await settle();
		expect(repo.status('rapat-1')).toBe('conflict');
		expect(repo.get('rapat-1')).toEqual(at(m, 6));
		expect(agendaOnServer(server, 'rapat-1')).toBe(6);
	});

	it('reports a failed save, keeps the change and retries it until it lands', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		const statuses: string[] = [];
		repo.onStatus('rapat-1', (s) => statuses.push(s));
		server.failures = [0, 503];
		const m = seedMeeting('rapat-1');
		repo.save(at(m, 2));
		await vi.advanceTimersByTimeAsync(1000);
		expect(repo.status('rapat-1')).toBe('failed');
		expect(repo.get('rapat-1')).toEqual(at(m, 2));
		expect(server.rows.size).toBe(0);

		await vi.advanceTimersByTimeAsync(5000); // second attempt: 503
		expect(repo.status('rapat-1')).toBe('failed');
		await vi.advanceTimersByTimeAsync(5000); // third attempt lands
		expect(repo.status('rapat-1')).toBe('saved');
		expect(agendaOnServer(server, 'rapat-1')).toBe(2);
		expect(statuses).toEqual(['saving', 'failed', 'failed', 'saved']);
	});

	it('a change made while a save failed goes out with the retry', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		server.failures = [0];
		const m = seedMeeting('rapat-1');
		repo.save(at(m, 2));
		await vi.advanceTimersByTimeAsync(1000);
		repo.save(at(m, 3));
		await settle();
		expect(repo.status('rapat-1')).toBe('saved');
		expect(agendaOnServer(server, 'rapat-1')).toBe(3);
	});

	it('does not retry a refusal the server will repeat (no write grant)', async () => {
		const server = new FakeServer();
		const repo = await ServerMeetingRepo.open(server.api());
		server.failures = [403];
		repo.save(seedMeeting('rapat-1'));
		await settle();
		await settle();
		expect(repo.status('rapat-1')).toBe('failed');
		expect(server.writes).toBe(0);
		expect(server.failures).toEqual([]);
	});

	it('refuses to open when the server refuses the list', async () => {
		const server = new FakeServer();
		server.failures = [403];
		await expect(ServerMeetingRepo.open(server.api())).rejects.toMatchObject({ status: 403 });
	});
});
