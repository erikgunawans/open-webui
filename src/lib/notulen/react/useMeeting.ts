import { useCallback, useEffect, useRef, useState } from 'react';

import { refusedWhileClosed, type MeetingRepo } from '../repo';
import type { Meeting } from '../types';

// One Meeting, read from the repository and kept current by its subscription: a save from this
// tab or another one arrives through the same path, so Notulen and Layar never disagree.

/**
 * The outcome of this tab's last write. `at` is null until the first edit of this visit. A failed
 * write is sticky until a later one succeeds: the change lives only in this tab until then.
 *
 * A server-backed repository saves in the background, so two more states exist there: `pending`
 * while a change is on its way, and `conflict` holding the local edits a write could not store
 * because the meeting changed on another machine first (the screen shows the server's version).
 */
export type SaveState = {
	ok: boolean;
	at: number | null;
	pending?: boolean;
	conflict?: Meeting | null;
};

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

	// A repository that saves in the background reports each write's outcome here.
	useEffect(() => {
		if (!repo.onStatus) return;
		return repo.onStatus(id, (status) =>
			setSaved((prev) => {
				if (status === 'saving') return { ...prev, pending: true };
				if (status === 'saved') return { ok: true, at: Date.now(), pending: false, conflict: null };
				if (status === 'failed') return { ...prev, ok: false, pending: false };
				return { ...prev, ok: true, pending: false, conflict: repo.conflict?.(id) ?? null };
			})
		);
	}, [repo, id]);

	// Send what is pending when the page is hidden or closed, or the screen is left, rather than a
	// second later.
	useEffect(() => {
		if (!repo.flush) return;
		const flush = () => repo.flush?.();
		const onHide = () => document.visibilityState === 'hidden' && flush();
		window.addEventListener('pagehide', flush);
		document.addEventListener('visibilitychange', onHide);
		return () => {
			window.removeEventListener('pagehide', flush);
			document.removeEventListener('visibilitychange', onHide);
			flush();
		};
	}, [repo]);

	// While the last write is unconfirmed, closing or reloading the tab loses it: let the browser ask.
	useEffect(() => {
		if (saved.ok && !saved.pending) return;
		const hold = (e: BeforeUnloadEvent) => {
			e.preventDefault();
			e.returnValue = '';
		};
		window.addEventListener('beforeunload', hold);
		return () => window.removeEventListener('beforeunload', hold);
	}, [saved.ok, saved.pending]);

	/** Apply a change to the latest meeting and save it; the subscription re-renders. */
	const update = useCallback(
		(change: (m: Meeting) => Meeting) => {
			const next = change(current.current);
			// A closed meeting takes only Buka kembali; anything else is no change at all.
			if (refusedWhileClosed(current.current, next)) return;
			current.current = next;
			if (frozen) {
				setMeeting(next);
				setSaved({ ok: false, at: Date.now() });
				return;
			}
			const stored = repo.save(next);
			// A background save reports its own outcome (onStatus); the browser's is known now.
			if (!repo.onStatus) setSaved({ ok: stored, at: Date.now() });
		},
		[repo, frozen]
	);

	return [meeting, update, saved, opened.unreadable] as const;
};
