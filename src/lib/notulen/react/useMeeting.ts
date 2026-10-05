import { useCallback, useEffect, useRef, useState } from 'react';

import type { MeetingRepo } from '../repo';
import type { Meeting } from '../types';

// One Meeting, read from the repository and kept current by its subscription: a save from this
// tab or another one arrives through the same path, so Notulen and Layar never disagree.

export const useMeeting = (repo: MeetingRepo, id: string, init: () => Meeting) => {
	const [meeting, setMeeting] = useState<Meeting>(() => {
		const stored = repo.get(id);
		if (stored) return stored;
		const fresh = init();
		repo.save(fresh);
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
			repo.save(next);
		},
		[repo]
	);

	return [meeting, update] as const;
};
