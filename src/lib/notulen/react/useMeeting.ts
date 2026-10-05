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

export const useMeeting = (repo: MeetingRepo, id: string, init: () => Meeting) => {
	const [saved, setSaved] = useState<SaveState>({ ok: true, at: null });
	const [meeting, setMeeting] = useState<Meeting>(() => {
		const stored = repo.get(id);
		if (stored) return stored;
		const fresh = init();
		if (!repo.save(fresh)) setSaved({ ok: false, at: Date.now() });
		return fresh;
	});
	const current = useRef(meeting);
	current.current = meeting;

	useEffect(
		() =>
			repo.subscribe(id, (m) => {
				current.current = m;
				setMeeting(m);
			}),
		[repo, id]
	);

	/** Apply a change to the latest meeting and save it; the subscription re-renders. */
	const update = useCallback(
		(change: (m: Meeting) => Meeting) => {
			const next = change(current.current);
			current.current = next;
			setSaved({ ok: repo.save(next), at: Date.now() });
		},
		[repo]
	);

	return [meeting, update, saved] as const;
};
