import { DEMO_ID } from './demo';
import type { LocalStorageMeetingRepo } from './repo';
import { MeetingApiError, type MoveResult, type ServerMeetingRepo } from './server-repo';
import type { Meeting } from './types';

// Pindahkan ke server (#161): the meetings this browser kept for the signed-in user before the
// server kept them, moved once. The server creates each one only if no meeting has its id; a copy
// in this browser is removed only once the server holds exactly that meeting, so nothing is lost
// whatever the answer. Unreadable data (and its quarantined copies) never leaves or moves.

export type MoveOutcome = {
	id: string;
	/**
	 * `moved`: on the server now, this browser's copy removed. `on_server`: the server already held
	 * this same meeting (copy removed). `kept`: the server holds a different meeting under this id,
	 * or the copy changed while it moved: the browser keeps its copy. `refused`: not a meeting the
	 * server accepts; kept.
	 */
	result: 'moved' | 'on_server' | 'kept' | 'refused';
};

export type MoveReport =
	| { ok: true; outcomes: MoveOutcome[] }
	/** The whole request was refused or not answered; every copy stays in this browser. */
	| { ok: false; status: number; message: string };

/** The meetings this browser still holds for the user, the demo meeting aside. */
export const meetingsToMove = (local: LocalStorageMeetingRepo): Meeting[] =>
	local.list().filter((m) => m.id !== DEMO_ID);

const outcome = (meeting: Meeting, r: MoveResult | undefined, removed: boolean): MoveOutcome => {
	if (r?.result === 'refused' || !r || r.id !== meeting.id)
		return { id: meeting.id, result: 'refused' };
	if (!removed) return { id: meeting.id, result: 'kept' };
	return { id: meeting.id, result: r.result === 'moved' ? 'moved' : 'on_server' };
};

export const moveToServer = async (
	local: LocalStorageMeetingRepo,
	server: Pick<ServerMeetingRepo, 'move'>
): Promise<MoveReport> => {
	const pending = meetingsToMove(local);
	if (!pending.length) return { ok: true, outcomes: [] };
	let results: MoveResult[];
	try {
		results = await server.move(pending);
	} catch (error) {
		return {
			ok: false,
			status: error instanceof MeetingApiError ? error.status : 0,
			message: `${error instanceof Error ? error.message : error}`
		};
	}
	return {
		ok: true,
		outcomes: pending.map((meeting, i) => {
			const r = results[i];
			const confirmed = !!r?.confirmed && r.id === meeting.id;
			return outcome(meeting, r, confirmed && local.remove(meeting));
		})
	};
};
