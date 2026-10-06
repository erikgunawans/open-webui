import { actions, decisions, waitsByStatus } from './selectors';
import {
	AGENDA_DECISIONS,
	DECISION_STATUS,
	RUMUSAN,
	SYARAT,
	filled,
	text,
	type Meeting,
	type NotulenRecord,
	type PropValue
} from './types';

// What a Keputusan must carry before it counts (Erik, 2026-10-06): every Keputusan its Rumusan, a
// Disetujui bersyarat its Syarat, a Ditunda the date it comes back. The Layar and Notulen record a
// Keputusan only once these are filled. Tutup rapat checks the whole meeting first.

export { RUMUSAN };
export const UNDECIDED = 'Belum diputuskan';
export const ULANG = 'Tanggal pembahasan ulang';

const needs = (status: string): string[] =>
	status === UNDECIDED || !status
		? []
		: status === 'Disetujui bersyarat'
			? [RUMUSAN, SYARAT]
			: status === 'Ditunda'
				? [RUMUSAN, ULANG]
				: [RUMUSAN];

/** The kolom still empty before `status` can be recorded on this Usulan (none = it can). */
export const decisionGaps = (r: NotulenRecord, status = text(r.values[DECISION_STATUS])) =>
	needs(status).filter((k) => !filled(r.values[k]));

/** The counts Tutup rapat asks about before the meeting closes. A Ditunda still waits, so it counts
 *  as belum diputuskan here as on the rail (Erik, 2026-10-07), and never also as "tanpa rumusan". */
export const closingGaps = (m: Meeting) => {
	const decs = decisions(m);
	const gaps = {
		undecided: decs.filter(waitsByStatus).length,
		noPic: actions(m).filter((r) => !text(r.values['PIC utama']).trim()).length,
		noRumusan: decs.filter((r) => !waitsByStatus(r) && !filled(r.values[RUMUSAN])).length
	};
	return { ...gaps, any: gaps.undecided + gaps.noPic + gaps.noRumusan > 0 };
};

/** "2 usulan belum diputuskan · 1 tindakan tanpa PIC" — only the counts that are not zero. */
export const gapLine = (g: ReturnType<typeof closingGaps>) =>
	[
		g.undecided ? `${g.undecided} usulan belum diputuskan` : '',
		g.noPic ? `${g.noPic} tindakan tanpa PIC` : '',
		g.noRumusan ? `${g.noRumusan} keputusan tanpa rumusan` : ''
	]
		.filter(Boolean)
		.join(' · ');

/** "Buka kembali": the meeting runs again on its last agenda, and the reason is kept. */
export const reopenMeeting = (m: Meeting, reason: string, now: number): Meeting => {
	const { closedAt, ...session } = m.session;
	if (closedAt === undefined || !reason.trim()) return m;
	return {
		...m,
		session: {
			...session,
			agendaEnteredAt: now,
			reopenings: [...(session.reopenings ?? []), { at: now, reason: reason.trim() }]
		}
	};
};

/** Record a Keputusan with the kolom it needs, in one write. Refused (null) while a gap remains. */
export const decide = (
	m: Meeting,
	recordId: string,
	status: string,
	values: Record<string, PropValue> = {}
): Meeting | null => {
	const r = m.records[AGENDA_DECISIONS].find((x) => x.id === recordId);
	if (!r) return null;
	const next = { ...r, values: { ...r.values, ...values, [DECISION_STATUS]: status } };
	if (decisionGaps(next, status).length) return null;
	return {
		...m,
		records: m.records.map((coll, i) =>
			i !== AGENDA_DECISIONS ? coll : coll.map((x) => (x.id === recordId ? next : x))
		)
	};
};
