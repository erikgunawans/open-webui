import type { Meeting } from './types';

// Where a Meeting lives. Both screens go through this interface only: the localStorage
// implementation below, or the server-backed one (`server-repo.ts`) when Ruang Pimpinan keeps
// records on the server.
//
// localStorage is per browser on one device: the `storage` event keeps tabs of the SAME browser in
// step (a laptop tab and a display tab on one machine). A secretariat laptop and a separate
// boardroom PC need the server-backed repo.

export type Unsubscribe = () => void;

/**
 * Where a server-backed meeting's last change stands: stored, on its way, refused or unreachable
 * (kept and retried), or refused because the meeting changed elsewhere first (`conflict`).
 */
export type SaveStatus = 'saved' | 'saving' | 'failed' | 'conflict';

export interface MeetingRepo {
	/** Every readable meeting this user has, in storage order. */
	list(): Meeting[];
	/**
	 * Ids holding data that list() skips because it cannot be read. Only a repository that can hold
	 * unreadable data has it; a server refuses malformed meetings before storing them.
	 */
	unreadableIds?(): string[];
	get(id: string): Meeting | null;
	/**
	 * Store the meeting; false when it could not be stored (it still reaches this tab's listeners).
	 * A change a closed meeting refuses (`refusedWhileClosed`) is false and reaches no one.
	 */
	save(meeting: Meeting): boolean;
	/**
	 * When something is stored under `id` that is not a readable Meeting (damaged, or written by a
	 * different version), copy it aside before anything replaces it. Null when there is nothing
	 * unreadable; `kept` is false when the copy itself could not be stored — then the caller must
	 * not save over the original either.
	 */
	quarantine(id: string): { raw: string; kept: boolean } | null;
	/** Called with the stored meeting whenever another tab (or this one) saves it. */
	subscribe(id: string, cb: (meeting: Meeting) => void): Unsubscribe;

	// A repository that stores somewhere else than this tab saves in the background: `save` only
	// accepts the change, and these report what became of it. The browser repository has none.
	/** True when meetings are kept on the server rather than in this browser. */
	readonly remote?: boolean;
	status?(id: string): SaveStatus;
	onStatus?(id: string, cb: (status: SaveStatus) => void): Unsubscribe;
	/** The local edits a conflicting write could not store, until a later write lands. */
	conflict?(id: string): Meeting | null;
	/** Send pending changes now (the page is being hidden or closed). */
	flush?(): void;
}

/**
 * Tutup rapat freezes a meeting: while `stored` is closed, the only change it takes is Buka kembali —
 * `next` open again, with exactly one more reopening that has a written reason (keputusan.ts
 * `reopenMeeting`). Every repository refuses anything else; the server enforces the same.
 */
export const refusedWhileClosed = (stored: Meeting | null, next: Meeting): boolean => {
	if (stored?.session.closedAt === undefined) return false;
	const before = stored.session.reopenings ?? [];
	const after = next.session.reopenings ?? [];
	const reason = after[after.length - 1]?.reason;
	return !(
		next.session.closedAt === undefined &&
		after.length === before.length + 1 &&
		typeof reason === 'string' &&
		!!reason.trim()
	);
};

const PREFIX = 'jup-rapat-direksi:v1:';
/** Unreadable data moved aside by quarantine(), kept for recovery rather than overwritten. */
const QUARANTINE = 'jup-rapat-direksi-tidak-terbaca:';

const isMeeting = (v: unknown): v is Meeting => {
	if (!v || typeof v !== 'object') return false;
	const m = v as Meeting;
	return (
		typeof m.id === 'string' &&
		Array.isArray(m.records) &&
		m.records.length === 9 &&
		m.records.every(Array.isArray) &&
		!!m.session &&
		typeof m.session.currentAgenda === 'number' &&
		Array.isArray(m.session.doneAgendas)
	);
};

export const parseMeeting = (raw: string | null): Meeting | null => {
	if (!raw) return null;
	try {
		const v = JSON.parse(raw);
		return isMeeting(v) ? v : null;
	} catch {
		return null;
	}
};

export class LocalStorageMeetingRepo implements MeetingRepo {
	private listeners = new Map<string, Set<(m: Meeting) => void>>();

	constructor(
		private storage: Storage = localStorage,
		private events: Pick<Window, 'addEventListener' | 'removeEventListener'> = window,
		/** Per-user namespace, so two accounts on one browser never read each other's meetings. */
		private namespace = ''
	) {}

	key(id: string): string {
		return `${PREFIX}${this.namespace ? this.namespace + ':' : ''}${id}`;
	}

	/** The meetings stored for this namespace (this user, this browser), in storage order. */
	list(): Meeting[] {
		const prefix = this.key('');
		const out: Meeting[] = [];
		for (let i = 0; i < this.storage.length; i++) {
			const k = this.storage.key(i);
			if (k?.startsWith(prefix)) {
				const m = parseMeeting(this.storage.getItem(k));
				if (m) out.push(m);
			}
		}
		return out;
	}

	/** Ids stored for this namespace whose data list() skips because it cannot be read. */
	unreadableIds(): string[] {
		const prefix = this.key('');
		const out: string[] = [];
		for (let i = 0; i < this.storage.length; i++) {
			const k = this.storage.key(i);
			if (k?.startsWith(prefix) && !parseMeeting(this.storage.getItem(k)))
				out.push(k.slice(prefix.length));
		}
		return out;
	}

	get(id: string): Meeting | null {
		try {
			return parseMeeting(this.storage.getItem(this.key(id)));
		} catch {
			return null;
		}
	}

	save(meeting: Meeting): boolean {
		if (refusedWhileClosed(this.get(meeting.id), meeting)) return false;
		let stored = true;
		try {
			this.storage.setItem(this.key(meeting.id), JSON.stringify(meeting));
		} catch {
			// Storage full or blocked: the change holds in memory for this visit only, and the caller
			// must say so — the screens promise an automatic save.
			stored = false;
		}
		// The storage event never fires in the tab that wrote, so tell local listeners directly.
		this.listeners.get(meeting.id)?.forEach((cb) => cb(meeting));
		return stored;
	}

	quarantine(id: string): { raw: string; kept: boolean } | null {
		let raw: string | null;
		try {
			raw = this.storage.getItem(this.key(id));
		} catch {
			return null;
		}
		if (raw === null || parseMeeting(raw)) return null;
		try {
			// Outside PREFIX + namespace + ':', so list() never reads it back as a meeting.
			this.storage.setItem(`${QUARANTINE}${this.key(id)}:${Date.now()}`, raw);
			return { raw, kept: true };
		} catch {
			return { raw, kept: false };
		}
	}

	subscribe(id: string, cb: (meeting: Meeting) => void): Unsubscribe {
		const key = this.key(id);
		const onStorage = (e: StorageEvent) => {
			if (e.key !== key) return;
			const m = parseMeeting(e.newValue);
			if (m) cb(m);
		};
		this.events.addEventListener('storage', onStorage as EventListener);
		const set = this.listeners.get(id) ?? new Set();
		set.add(cb);
		this.listeners.set(id, set);
		return () => {
			this.events.removeEventListener('storage', onStorage as EventListener);
			set.delete(cb);
		};
	}
}
