import { DEMO_ID, demoMeeting } from '../demo';
import { LocalStorageMeetingRepo } from '../repo';
import { newId, seedMeeting } from '../seed';
import { LayarApp } from './layar/LayarApp';
import { MeetingList } from './MeetingList';
import { NotulenApp } from './notulen/NotulenApp';
import { mountIsland, type Island } from './mount';

// The one module the Svelte routes import (lazily). Everything the React screens need is wired
// here: the per-user repository, the demo meeting, and each surface's theme (the Layar keeps its
// own, dark by default for a projector; the list and the Notulen follow the app).

export const RAPAT_BASE = '/ruang-pimpinan/rapat';

export type Surface = 'list' | 'notulen' | 'layar';

type Options = {
	surface: Surface;
	meetingId: string;
	userId: string;
	/** Client-side navigation, so the Svelte router keeps its state. */
	navigate: (href: string) => void;
};

const meetingNewId = () => `rd-${new Date().toISOString().slice(0, 10)}-${newId().slice(0, 4)}`;

export const mountRapat = (target: HTMLElement, o: Options): Island<object> => {
	const repo = new LocalStorageMeetingRepo(localStorage, window, o.userId);
	const demo = o.meetingId === DEMO_ID;
	const init = () => (demo ? demoMeeting() : seedMeeting(o.meetingId));
	const themeKey = (s: Surface) => `jup-rapat-theme:${s}:${o.userId}`;

	if (o.surface === 'layar')
		return mountIsland(
			target,
			LayarApp,
			{ repo, meetingId: o.meetingId, init, demo },
			// Dark is the suggestion for a projector; the reader's own choice wins once made.
			{ theme: 'dark', storageKey: themeKey('layar'), className: 'lr-root' }
		) as Island<object>;

	if (o.surface === 'notulen')
		return mountIsland(
			target,
			NotulenApp,
			{
				repo,
				meetingId: o.meetingId,
				init,
				layarHref: `${RAPAT_BASE}/${o.meetingId}/layar`,
				viewKey: `jup-rapat-view:${o.userId}:${o.meetingId}`
			},
			{ theme: 'app', storageKey: null, className: 'nt-root' }
		) as Island<object>;

	return mountIsland(
		target,
		MeetingList,
		{ repo, base: RAPAT_BASE, newId: meetingNewId, open: o.navigate },
		{ theme: 'app', storageKey: null, className: 'nt-root' }
	) as Island<object>;
};
