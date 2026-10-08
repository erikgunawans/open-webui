import { DEMO_ID, demoMeeting } from '../demo';
import { httpMeetingApi } from '../meeting-api';
import { LocalStorageMeetingRepo, type MeetingRepo } from '../repo';
import { newId, seedMeeting } from '../seed';
import { ServerMeetingRepo } from '../server-repo';
import { LayarApp } from './layar/LayarApp';
import { MeetingList } from './MeetingList';
import { NotulenApp } from './notulen/NotulenApp';
import { mountIsland, type Island } from './mount';

// The one module the Svelte routes import (lazily). Everything the React screens need is wired
// here: the repository, the demo meeting, and each surface's theme (the Layar keeps its own, light
// by default; the list and the Notulen follow the app).
//
// The repository is the server's when the server keeps Ruang Pimpinan records (`server` is given),
// and this browser's otherwise. The illustrative demo meeting always stays in this browser.

export const RAPAT_BASE = '/ruang-pimpinan/rapat';

export type Surface = 'list' | 'notulen' | 'layar';

type Options = {
	surface: Surface;
	meetingId: string;
	userId: string;
	/** Client-side navigation, so the Svelte router keeps its state. */
	navigate: (href: string) => void;
	/** Given only when the server keeps records: meetings are then stored there. */
	server?: { apiBase: string; token: string; scopeId: string };
};

const meetingNewId = () => `rd-${new Date().toISOString().slice(0, 10)}-${newId().slice(0, 4)}`;

export const mountRapat = async (target: HTMLElement, o: Options): Promise<Island<object>> => {
	const local = new LocalStorageMeetingRepo(localStorage, window, o.userId);
	const demo = o.meetingId === DEMO_ID;
	const repo: MeetingRepo =
		o.server && !demo
			? await ServerMeetingRepo.open(httpMeetingApi({ ...o.server, base: o.server.apiBase }))
			: local;
	const init = () => (demo ? demoMeeting() : seedMeeting(o.meetingId));
	const themeKey = (s: Surface) => `jup-rapat-theme:${s}:${o.userId}`;

	if (o.surface === 'layar')
		return mountIsland(
			target,
			LayarApp,
			{ repo, meetingId: o.meetingId, init, demo },
			// Light by default (Erik, 2026-10-05); the reader's own choice wins once made.
			{ theme: 'light', storageKey: themeKey('layar'), className: 'lr-root' }
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
				viewKey: `jup-rapat-view:${o.userId}:${o.meetingId}`,
				demo
			},
			{ theme: 'app', storageKey: null, className: 'nt-root' }
		) as Island<object>;

	return mountIsland(
		target,
		MeetingList,
		{ repo, demoRepo: local, base: RAPAT_BASE, newId: meetingNewId, open: o.navigate },
		{ theme: 'app', storageKey: null, className: 'nt-root' }
	) as Island<object>;
};
