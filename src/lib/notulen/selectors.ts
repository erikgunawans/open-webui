import { CHECKLIST } from './agendas';
import {
	AGENDA_ACTIONS,
	AGENDA_DECISIONS,
	ACTION_STATUS,
	DECISION_STATUS,
	RUMUSAN,
	SYARAT,
	filled,
	isDate,
	text,
	type DateValue,
	type Meeting,
	type NotulenRecord,
	type PropValue
} from './types';

// Read models over one Meeting, shared by Notulen (Tampilan pendukung, header) and Layar.

const v = (r: NotulenRecord, k: string): PropValue | undefined => r.values[k];

export const PLACEHOLDER_NAME = 'Isi nama rapat';

/** The Informasi record the header describes: the first with a real meeting name. */
export const mainInfo = (m: Meeting): NotulenRecord | undefined =>
	m.records[0].find((r) => text(v(r, 'Nama rapat')) && v(r, 'Nama rapat') !== PLACEHOLDER_NAME) ??
	m.records[0].find((r) => text(v(r, 'Nama rapat'))) ??
	m.records[0][0];

export const meetingName = (m: Meeting): string => {
	const name = text(mainInfo(m)?.values['Nama rapat']);
	return name && name !== PLACEHOLDER_NAME ? name : 'Notulen Rapat Direksi';
};

export const checklistCount = (m: Meeting): number => {
	const r = mainInfo(m);
	return r ? CHECKLIST.filter((k) => r.values[k] === true).length : 0;
};

const PENDING = ['', 'Belum diputuskan', 'Ditunda'];

/** Whether the stored status itself still waits: empty, Belum diputuskan or Ditunda. */
export const waitsByStatus = (r: NotulenRecord): boolean =>
	PENDING.includes(text(v(r, DECISION_STATUS)));

/** A decided status whose Rumusan (or, for bersyarat, Syarat) is empty: not yet a Keputusan. */
export const isIncomplete = (r: NotulenRecord): boolean =>
	!waitsByStatus(r) &&
	(!filled(v(r, RUMUSAN)) ||
		(text(v(r, DECISION_STATUS)) === 'Disetujui bersyarat' && !filled(v(r, SYARAT))));

export const decisions = (m: Meeting): NotulenRecord[] =>
	m.records[AGENDA_DECISIONS].filter((r) => text(v(r, 'Topik keputusan')));

/** Whether an Usulan counts as diputuskan: a Ditunda still waits, and so does a status recorded
 *  without its Rumusan (CONTEXT: without one it is not a Keputusan). */
export const isDecided = (r: NotulenRecord): boolean => !waitsByStatus(r) && !isIncomplete(r);

/** Usulan with a topic still waiting for a (complete) Keputusan. */
export const pendingDecisions = (m: Meeting): NotulenRecord[] =>
	decisions(m).filter((r) => !isDecided(r));

/** Usulan the Direksi have decided (Disetujui, Disetujui bersyarat, Ditolak): never a Ditunda. */
export const decidedDecisions = (m: Meeting): NotulenRecord[] => decisions(m).filter(isDecided);

export const highRisks = (m: Meeting): NotulenRecord[] =>
	m.records[5].filter((r) => v(r, 'Tingkat risiko') === 'Tinggi');

export const actions = (m: Meeting): NotulenRecord[] =>
	m.records[AGENDA_ACTIONS].filter((r) => text(v(r, 'Tindakan / deliverable')));

export const targetOf = (r: NotulenRecord): DateValue | undefined => {
	const t = v(r, 'Target waktu');
	return isDate(t) && t.start ? t : undefined;
};

/** Actions with a target, earliest first. */
export const actionCalendar = (m: Meeting): NotulenRecord[] =>
	actions(m)
		.filter((r) => targetOf(r))
		.sort((a, b) => targetOf(a)!.start.localeCompare(targetOf(b)!.start));

/** The nearest open actions for the Layar rail. */
export const nearestOpenActions = (m: Meeting, n = 4): NotulenRecord[] =>
	actionCalendar(m)
		.filter((r) => v(r, ACTION_STATUS) !== 'Selesai')
		.slice(0, n);

const ID_DATE = (x: string, withYear: boolean) => {
	const d = new Date(x.length === 10 ? `${x}T00:00` : x);
	return d.toLocaleDateString('id-ID', {
		day: 'numeric',
		month: 'short',
		...(withYear ? { year: 'numeric' } : {})
	});
};

/** "5 Okt 2026 09.00 – 5 Okt 2026 12.00"; empty when unset. */
export const fmtDate = (d: PropValue | undefined): string => {
	if (!isDate(d) || !d.start) return '';
	const one = (x: string) => ID_DATE(x, true) + (x.length > 10 ? ` ${x.slice(11, 16)}` : '');
	return one(d.start) + (d.end ? ` – ${one(d.end)}` : '');
};

/** "9 Okt" — the Layar's short form. */
export const fmtShort = (d: PropValue | undefined): string =>
	isDate(d) && d.start ? ID_DATE(d.start, false) : '—';

/** KPI deviation tone: cost rows (CAPEX, OPEX) are good at or under budget; others at or over. */
export const deviationTone = (
	indicator: string,
	real: number,
	target: number
): { d: number; tone: 'success' | 'warning' | 'danger'; cost: boolean } => {
	const cost = /^(CAPEX|OPEX)\b/i.test(indicator.trim());
	const d = target ? ((real - target) / target) * 100 : 0;
	const good = cost ? d <= 0 : d >= 0;
	return { d, cost, tone: good ? 'success' : Math.abs(d) <= 10 ? 'warning' : 'danger' };
};
