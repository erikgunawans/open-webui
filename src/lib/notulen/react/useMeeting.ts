import { useCallback, useEffect, useRef, useState } from 'react';

import type { MeetingRepo } from '../repo';
import type { Meeting } from '../types';

// One Meeting, read from the repository and kept current by its subscription: a save from this
// tab or another one arrives through the same path, so Notulen and Layar never disagree.

/**
 * The outcome of this tab's last write. `at` is null until the first edit of this visit. A failed
 * write is sticky until a later one succeeds: the change lives only in this tab until then.
 */
export type SaveState = { ok: boolean; at: number | null };

/**
 * Stored data that could not be read when this meeting opened (damaged, or from another version).
 * The screen starts from the template and offers `raw` for download; `kept` says whether a copy
 * also stays in this browser.
 */
export type Unreadable = { raw: string; kept: boolean } | null;

type Opened = { meeting: Meeting; saved: SaveState; unreadable: Unreadable };

// What was set aside on this page, per repository and meeting. Opening has a side effect (the
// quarantine and the template save), and React may run the opener twice (StrictMode) or mount the
// screen again: without this, the second run finds the template and the recovery alert is lost.
const setAside = new WeakMap<MeetingRepo, Map<string, NonNullable<Unreadable>>>();

const open = (repo: MeetingRepo, id: string, init: () => Meeting): Opened => {
	const earlier = setAside.get(repo)?.get(id) ?? null;
	const stored = repo.get(id);
	if (stored) return { meeting: stored, saved: { ok: true, at: null }, unreadable: earlier };
	const unreadable = earlier ?? repo.quarantine(id);
	if (unreadable) {
		const byId = setAside.get(repo) ?? new Map();
		byId.set(id, unreadable);
		setAside.set(repo, byId);
	}
	const fresh = init();
	// Never write over data that could not be copied aside first.
	if (unreadable && !unreadable.kept)
		return { meeting: fresh, saved: { ok: false, at: null }, unreadable };
	return { meeting: fresh, saved: { ok: repo.save(fresh), at: null }, unreadable };
};

export const useMeeting = (repo: MeetingRepo, id: string, init: () => Meeting) => {
	const [opened] = useState(() => open(repo, id, init));
	const [meeting, setMeeting] = useState<Meeting>(opened.meeting);
	const [saved, setSaved] = useState<SaveState>(opened.saved);
	const current = useRef(meeting);
	current.current = meeting;
	// The original could not be copied aside, so no write may land on its key this visit.
	const frozen = !!opened.unreadable && !opened.unreadable.kept;

	useEffect(
		() =>
			repo.subscribe(id, (m) => {
				current.current = m;
				setMeeting(m);
			}),
		[repo, id]
	);

	// While the last write is unconfirmed, closing or reloading the tab loses it: let the browser ask.
	useEffect(() => {
		if (saved.ok) return;
		const hold = (e: BeforeUnloadEvent) => {
			e.preventDefault();
			e.returnValue = '';
		};
		window.addEventListener('beforeunload', hold);
		return () => window.removeEventListener('beforeunload', hold);
	}, [saved.ok]);

	/** Apply a change to the latest meeting and save it; the subscription re-renders. */
	const update = useCallback(
		(change: (m: Meeting) => Meeting) => {
			const next = change(current.current);
			current.current = next;
			if (frozen) {
				setMeeting(next);
				setSaved({ ok: false, at: Date.now() });
				return;
			}
			setSaved({ ok: repo.save(next), at: Date.now() });
		},
		[repo, frozen]
	);

	return [meeting, update, saved, opened.unreadable] as const;
};
