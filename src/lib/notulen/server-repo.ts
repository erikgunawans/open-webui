import {
	parseMeeting,
	refusedWhileClosed,
	type MeetingRepo,
	type SaveStatus,
	type Unsubscribe
} from './repo';
import type { Meeting } from './types';

// The meeting repository backed by the server (D27 step 1): any machine the Corsec signs in on
// sees the same meeting. The screens keep their synchronous view of it: every meeting is loaded
// once when the repository opens, and from then on the cache answers `get` and `list` while
// writes and polls go to the server in the background.
//
// - Saving: `save` updates the cache and this tab's listeners at once, then sends the whole
//   meeting at most about once a second (and at once on `flush`, for blur and close).
// - Revisions: each write names the revision it was based on. A stale write is refused by the
//   server; the repository then loads the server's version, keeps the unsaved local edits under
//   `conflict(id)` and reports 'conflict'. Nothing is overwritten on either side.
// - A failed write is kept and retried, and reported as 'failed' until one lands. A refusal the
//   server will repeat (no write grant, a malformed meeting) is reported and not retried.
// - Tutup rapat and Buka kembali go to their own endpoints (the server audits them and refuses
//   every save to a closed meeting); which one a write needs follows from whether the meeting was
//   closed when the server last answered and whether the meeting being sent is.
// - Live view: while a meeting has subscribers, the server is polled for a newer revision (one
//   poll at a time). A failed poll changes nothing on screen; the next one catches up.

/** A stored meeting as the server sends it. The document is checked here before it is trusted. */
export type StoredMeeting = { id: string; revision: number; document: unknown };

/** A refused request: `status` is the HTTP status (0 when the server was not reached). */
export class MeetingApiError extends Error {
	constructor(
		readonly status: number,
		message: string,
		/** The stored revision, on a 409. */
		readonly revision?: number
	) {
		super(message);
	}
}

/** The HTTP surface the repository needs; `src/lib/apis/leadership` provides the real one. */
export interface MeetingApi {
	list(): Promise<StoredMeeting[]>;
	/** Null when there is no such meeting. */
	get(id: string): Promise<StoredMeeting | null>;
	create(meeting: Meeting): Promise<{ revision: number }>;
	save(id: string, baseRevision: number, meeting: Meeting): Promise<{ revision: number }>;
	/** Tutup rapat: store the closing meeting; the server refuses saves until a reopening. */
	close(id: string, baseRevision: number, meeting: Meeting): Promise<{ revision: number }>;
	/** Buka kembali: `meeting` is open again and carries `reason` as its last reopening. */
	reopen(
		id: string,
		baseRevision: number,
		reason: string,
		meeting: Meeting
	): Promise<{ revision: number }>;
}

export type ServerRepoTiming = {
	/** How long changes are gathered before they are sent. */
	saveEveryMs: number;
	/** How often an open meeting asks the server for a newer revision. */
	pollEveryMs: number;
	/** How long a failed write waits before it is tried again. */
	retryAfterMs: number;
};

const DEFAULT_TIMING: ServerRepoTiming = {
	saveEveryMs: 1000,
	pollEveryMs: 2000,
	retryAfterMs: 5000
};

/** The server repeats these refusals whatever is retried: no grant, a malformed meeting. */
const PERMANENT = new Set([403, 404, 422]);

type Entry = {
	meeting: Meeting;
	/** The stored revision this tab last saw; 0 while the meeting exists only here. */
	revision: number;
	/** A local change not yet accepted by the server. */
	dirty: boolean;
	/** Whether the server held the meeting closed when it last answered. */
	closed: boolean;
};

const isClosed = (m: Meeting) => m.session.closedAt !== undefined;

const lastReason = (m: Meeting) => m.session.reopenings?.at(-1)?.reason ?? '';

/** The meeting as Buka kembali left it, before it was closed again. */
const opened = (m: Meeting): Meeting => {
	const session = { ...m.session };
	delete session.closedAt;
	return { ...m, session };
};

const readable = (stored: StoredMeeting): Meeting | null => {
	if (!stored || typeof stored.revision !== 'number') return null;
	const raw =
		typeof stored.document === 'string' ? stored.document : JSON.stringify(stored.document);
	const meeting = parseMeeting(raw ?? null);
	return meeting && meeting.id === stored.id ? meeting : null;
};

export class ServerMeetingRepo implements MeetingRepo {
	readonly remote = true;
	private entries = new Map<string, Entry>();
	private listeners = new Map<string, Set<(m: Meeting) => void>>();
	private statusListeners = new Map<string, Set<(s: SaveStatus) => void>>();
	private statuses = new Map<string, SaveStatus>();
	private conflicts = new Map<string, Meeting>();
	private timers = new Map<string, ReturnType<typeof setTimeout>>();
	private inFlight = new Set<string>();
	private polls = new Map<string, ReturnType<typeof setInterval>>();
	/** Meetings whose poll has not been answered yet. */
	private polling = new Set<string>();
	private timing: ServerRepoTiming;

	private constructor(
		private api: MeetingApi,
		timing: Partial<ServerRepoTiming>
	) {
		this.timing = { ...DEFAULT_TIMING, ...timing };
	}

	/** Load every meeting the server holds for this reader; rejects when the server refuses. */
	static async open(api: MeetingApi, timing: Partial<ServerRepoTiming> = {}) {
		const repo = new ServerMeetingRepo(api, timing);
		for (const stored of await api.list()) {
			const meeting = readable(stored);
			if (meeting)
				repo.entries.set(meeting.id, {
					meeting,
					revision: stored.revision,
					dirty: false,
					closed: isClosed(meeting)
				});
		}
		return repo;
	}

	list(): Meeting[] {
		return [...this.entries.values()].filter((e) => e.revision > 0).map((e) => e.meeting);
	}

	get(id: string): Meeting | null {
		return this.entries.get(id)?.meeting ?? null;
	}

	/**
	 * Accepted into this tab at once; sending follows. The outcome arrives through `onStatus`.
	 * A change a closed meeting refuses is false at once and reaches no one.
	 */
	save(meeting: Meeting): boolean {
		const entry = this.entries.get(meeting.id);
		if (refusedWhileClosed(entry?.meeting ?? null, meeting)) return false;
		this.entries.set(meeting.id, {
			meeting,
			revision: entry?.revision ?? 0,
			dirty: true,
			closed: entry?.closed ?? false
		});
		this.notify(meeting.id, meeting);
		this.setStatus(meeting.id, 'saving');
		this.schedule(meeting.id, this.timing.saveEveryMs);
		return true;
	}

	/** The server checks every meeting before storing it, so nothing unreadable is ever held. */
	quarantine(): null {
		return null;
	}

	subscribe(id: string, cb: (meeting: Meeting) => void): Unsubscribe {
		const set = this.listeners.get(id) ?? new Set();
		set.add(cb);
		this.listeners.set(id, set);
		if (!this.polls.has(id))
			this.polls.set(
				id,
				setInterval(() => void this.poll(id), this.timing.pollEveryMs)
			);
		return () => {
			set.delete(cb);
			if (set.size) return;
			clearInterval(this.polls.get(id));
			this.polls.delete(id);
		};
	}

	status(id: string): SaveStatus {
		return this.statuses.get(id) ?? 'saved';
	}

	onStatus(id: string, cb: (status: SaveStatus) => void): Unsubscribe {
		const set = this.statusListeners.get(id) ?? new Set();
		set.add(cb);
		this.statusListeners.set(id, set);
		return () => set.delete(cb);
	}

	/** The local edits a conflicting write could not store, kept until a later write lands. */
	conflict(id: string): Meeting | null {
		return this.conflicts.get(id) ?? null;
	}

	/** Send every pending change now (blur, page hide), without waiting for the next tick. */
	flush(): void {
		for (const [id, entry] of this.entries) if (entry.dirty) this.schedule(id, 0);
	}

	private schedule(id: string, delay: number) {
		const pending = this.timers.get(id);
		// Gathering already: the timer will send the latest. Flush replaces it with an immediate one.
		if (pending !== undefined && delay > 0) return;
		clearTimeout(pending);
		this.timers.set(
			id,
			setTimeout(() => {
				this.timers.delete(id);
				void this.send(id);
			}, delay)
		);
	}

	private async send(id: string) {
		const entry = this.entries.get(id);
		if (!entry?.dirty) return;
		// One write per meeting at a time: the next one leaves when this one is answered.
		if (this.inFlight.has(id)) return;
		this.inFlight.add(id);
		const sent = entry.meeting;
		try {
			const revision = await this.write(id, entry, sent);
			const now = this.entries.get(id)!;
			const changedSince = now.meeting !== sent;
			this.entries.set(id, { ...now, revision, dirty: changedSince, closed: isClosed(sent) });
			this.conflicts.delete(id);
			if (changedSince) this.schedule(id, this.timing.saveEveryMs);
			else this.setStatus(id, 'saved');
		} catch (error) {
			const status = error instanceof MeetingApiError ? error.status : 0;
			if (status === 409) await this.resolveConflict(id);
			else {
				this.setStatus(id, 'failed');
				if (!PERMANENT.has(status)) this.schedule(id, this.timing.retryAfterMs);
			}
		} finally {
			this.inFlight.delete(id);
		}
	}

	/** Send `sent` the way its change needs; answers the revision the server now holds. */
	private async write(id: string, entry: Entry, sent: Meeting): Promise<number> {
		if (entry.revision === 0) return (await this.api.create(sent)).revision;
		let { revision } = entry;
		if (entry.closed) {
			// Buka kembali (and perhaps closed again before it was sent: the reopening goes first).
			const reopened = isClosed(sent) ? opened(sent) : sent;
			({ revision } = await this.api.reopen(id, revision, lastReason(sent), reopened));
			this.entries.set(id, { ...this.entries.get(id)!, revision, closed: false });
			if (!isClosed(sent)) return revision;
		}
		return isClosed(sent)
			? (await this.api.close(id, revision, sent)).revision
			: (await this.api.save(id, revision, sent)).revision;
	}

	/** The server holds a newer meeting: show it, and keep what this tab could not store. */
	private async resolveConflict(id: string) {
		const local = this.entries.get(id)!.meeting;
		let stored: StoredMeeting | null = null;
		try {
			stored = await this.api.get(id);
		} catch {
			stored = null;
		}
		const current = stored && readable(stored);
		if (!stored || !current) {
			// The server's version could not be read: keep the edits pending and try again later.
			this.setStatus(id, 'failed');
			this.schedule(id, this.timing.retryAfterMs);
			return;
		}
		this.conflicts.set(id, local);
		this.entries.set(id, {
			meeting: current,
			revision: stored.revision,
			dirty: false,
			closed: isClosed(current)
		});
		this.notify(id, current);
		this.setStatus(id, 'conflict');
	}

	private async poll(id: string) {
		const entry = this.entries.get(id);
		// Local edits on their way win until the server answers them; the revision check catches
		// anything written elsewhere in between. On a slow network the previous poll may still be
		// waiting: the next one is skipped rather than stacked behind it.
		if (entry?.dirty || this.inFlight.has(id) || this.polling.has(id)) return;
		this.polling.add(id);
		let stored: StoredMeeting | null;
		try {
			stored = await this.api.get(id);
		} catch {
			return; // Keep the last state; the next poll tries again.
		} finally {
			this.polling.delete(id);
		}
		if (!stored) return;
		const latest = this.entries.get(id);
		if (latest?.dirty || stored.revision <= (latest?.revision ?? 0)) return;
		const meeting = readable(stored);
		if (!meeting) return;
		this.entries.set(id, {
			meeting,
			revision: stored.revision,
			dirty: false,
			closed: isClosed(meeting)
		});
		this.notify(id, meeting);
	}

	private notify(id: string, meeting: Meeting) {
		this.listeners.get(id)?.forEach((cb) => cb(meeting));
	}

	private setStatus(id: string, status: SaveStatus) {
		this.statuses.set(id, status);
		this.statusListeners.get(id)?.forEach((cb) => cb(status));
	}
}
