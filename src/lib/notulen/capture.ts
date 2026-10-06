import { AGENDAS } from './agendas';
import { record } from './seed';
import {
	AGENDA_ACTIONS,
	AGENDA_DECISIONS,
	DBS,
	DECISION_STATUS,
	titleField,
	type DateValue,
	type NotulenRecord,
	type PropValue
} from './types';

// The quick-capture strip at the top of each agenda: one line + Enter makes a Butir pembahasan in
// that agenda, an Usulan in 07 or a Tindakan in 08. Usulan and Tindakan remember the agenda they
// came from through their stored "Agenda" kolom, so 07 stays the one place to decide them.

export type CaptureKind = 'butir' | 'usulan' | 'tindakan';

export const CAPTURED = 'Dicatat saat rapat';

/** The stored "Agenda" option for agenda `db` (1–8), e.g. "4. Program Prioritas". */
export const agendaOption = (db: number): string => {
	const f = DBS[AGENDA_DECISIONS].fields.find((x) => x.name === 'Agenda')!;
	return f.options[db - 1] ?? '';
};

/** Two-digit agenda number for a stored "Agenda" option ("4. Program Prioritas" → "04"), or "". */
export const agendaNo = (option: string): string => {
	const n = Number(/^(\d)\./.exec(option)?.[1]);
	return n >= 1 && n <= 8 ? AGENDAS[n].no : '';
};

/** Which kinds the strip offers on agenda `db`: a Butir only where the agenda has its own entries. */
export const kindsFor = (db: number): CaptureKind[] =>
	db === AGENDA_DECISIONS
		? ['usulan', 'tindakan']
		: db === AGENDA_ACTIONS
			? ['tindakan']
			: db >= 1
				? ['butir', 'usulan', 'tindakan']
				: [];

export interface Capture {
	kind: CaptureKind;
	/** The agenda the strip sits on. */
	from: number;
	title: string;
	pic?: string;
	/** ISO date. */
	due?: string;
}

/** The database a capture lands in and the entry it makes. */
export const captureRecord = (c: Capture): { db: number; record: NotulenRecord } => {
	const title = c.title.trim();
	if (c.kind === 'butir') {
		return { db: c.from, record: record({ [titleField(c.from).name]: title }, '', CAPTURED) };
	}
	const db = c.kind === 'usulan' ? AGENDA_DECISIONS : AGENDA_ACTIONS;
	const values: Record<string, PropValue> = { [titleField(db).name]: title };
	const agenda = agendaOption(c.from);
	if (agenda) values.Agenda = agenda;
	if (c.kind === 'usulan') values[DECISION_STATUS] = 'Belum diputuskan';
	else {
		values['Asal tindak lanjut'] = 'Rapat ini';
		values.Status = 'Belum mulai';
		if (c.pic?.trim()) values['PIC utama'] = c.pic.trim();
		if (c.due) values['Target waktu'] = { start: c.due, end: '' } satisfies DateValue;
	}
	return { db, record: record(values, '', CAPTURED) };
};
