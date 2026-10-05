import type { Meeting } from './types';

// Where a Meeting lives. Both screens go through this interface only, so the localStorage
// implementation below can be swapped for an API or realtime backend without touching them.
//
// localStorage is per browser on one device: the `storage` event keeps tabs of the SAME browser in
// step (a laptop tab and a display tab on one machine). A secretariat laptop and a separate
// boardroom PC need a server-backed repo.

export type Unsubscribe = () => void;

export interface MeetingRepo {
	get(id: string): Meeting | null;
	/** Store the meeting; false when it could not be stored (it still reaches this tab's listeners). */
	save(meeting: Meeting): boolean;
	/** Called with the stored meeting whenever another tab (or this one) saves it. */
	subscribe(id: string, cb: (meeting: Meeting) => void): Unsubscribe;
}

const PREFIX = 'jup-rapat-direksi:v1:';

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

	get(id: string): Meeting | null {
		try {
			return parseMeeting(this.storage.getItem(this.key(id)));
		} catch {
			return null;
		}
	}

	save(meeting: Meeting): boolean {
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
