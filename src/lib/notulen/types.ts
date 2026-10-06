import { agendaLabel } from './agendas';
import { SCHEMA } from './schema';

// The Notulen Rapat Direksi data model. One Meeting holds the nine record collections the
// template defines (index 0 = Informasi & Ringkasan Rapat, 1..8 = the agendas) and the live
// session the Layar drives. Both screens read and write the same Meeting.

export type PropType =
	| 'title'
	| 'rich_text'
	| 'people'
	| 'files'
	| 'checkbox'
	| 'select'
	| 'status'
	| 'multi_select'
	| 'date'
	| 'number'
	| 'url';

export interface PropDef {
	/** The stored name: the storage key. Never renamed. */
	name: string;
	/** What the UI calls it, when that differs from the stored name. */
	label?: string;
	/** What the UI shows for a stored option, when that differs from the option (the stored value). */
	optionLabels?: Record<string, string>;
	type: PropType;
	options: string[];
	description: string | null;
}

export interface DbDef {
	name: string;
	fields: PropDef[];
}

/** ISO date (`2026-10-05`) or datetime-local (`2026-10-05T09:00`), read as Asia/Jakarta. */
export interface DateValue {
	start: string;
	end: string;
}

export type PropValue = string | boolean | string[] | DateValue;

export interface NotulenRecord {
	id: string;
	values: Record<string, PropValue>;
	/** The record's page body ("Isi halaman / catatan panjang"). */
	body: string;
	/** Per date property: whether it carries a time. */
	time: Record<string, boolean>;
	/** Where the record came from, shown on its card ("Record sumber", "Record baru", …). */
	origin: string;
}

export interface MeetingSession {
	currentAgenda: number;
	doneAgendas: number[];
	/** Epoch ms when the current agenda was entered; drives the agenda timer. */
	agendaEnteredAt: number;
	/** Epoch ms the meeting was closed ("Tutup rapat"); unset while it runs or after reopening. */
	closedAt?: number;
	/** Every "Buka kembali" after a close, with the reason the Corsec gave; printed in the Risalah. */
	reopenings?: { at: number; reason: string }[];
}

/**
 * What the Layar shows that the 150-property template has no field for: the agenda plan (minutes
 * and presenter per agenda), the meeting number, strategic progress and the monthly revenue
 * series. Optional: a meeting without it gets the standard plan and the Layar omits the rest.
 */
export interface MeetingPlan {
	nomor?: string;
	agendas: { menit: number; pemapar: string }[];
	/** Strategic Update record id → progress percent (0–100). */
	strategicProgress?: Record<string, number>;
	/** [month label, realisation, target] in the Kinerja unit (Rp miliar). */
	revenueMonthly?: [string, number, number][];
}

/** One agenda's Catatan pembahasan: the Corsec's running notes. */
export interface AgendaNotes {
	text: string;
	/** "Sertakan di Risalah": printed under the agenda only when set. */
	risalah: boolean;
}

export interface Meeting {
	id: string;
	/** records[0..8], one collection per database in SCHEMA order. */
	records: NotulenRecord[][];
	session: MeetingSession;
	plan?: MeetingPlan;
	/** Catatan pembahasan by agenda index ("1"…"8"). Absent on meetings made before 2026-10-06. */
	notes?: Record<string, AgendaNotes>;
}

/** Stored keys the generated schema does not have: added here, never by renaming a field. */
export const SYARAT = 'Syarat';
export const PERTIMBANGAN = 'Pertimbangan / syarat persetujuan';
export const ARAHAN = 'Kesimpulan / arahan';
export const RUMUSAN = 'Rumusan keputusan';

// Display names over stored keys (critique, 2026-10-06 and 2026-10-07): "Kesimpulan / arahan" is
// shown as Arahan (CONTEXT avoids "kesimpulan"), the English "Agenda" options of 07/08 by the
// agenda's name, and the remaining English labels and options in Indonesian.
const LABELS: Record<string, string> = {
	[ARAHAN]: 'Arahan',
	'Tindakan / deliverable': 'Tindakan',
	'Risk owner / PIC': 'Pemilik risiko'
};
const OPTION_LABELS: Record<string, Record<string, string>> = {
	'Status validasi': { Draft: 'Konsep', 'Dalam review': 'Ditinjau' }
};
const display = (f: PropDef): PropDef =>
	f.name === 'Agenda'
		? { ...f, optionLabels: Object.fromEntries(f.options.map((o) => [o, agendaLabel(o)])) }
		: {
				...f,
				...(LABELS[f.name] ? { label: LABELS[f.name] } : {}),
				...(OPTION_LABELS[f.name] ? { optionLabels: OPTION_LABELS[f.name] } : {})
			};

// The generated schema plus what the 2026-10-06 grill added: Syarat as its own kolom, so the old
// "Pertimbangan / syarat persetujuan" (same key, kept for stored meetings) now means the reasoning.
export const DBS: readonly DbDef[] = (SCHEMA as unknown as readonly DbDef[]).map((d, i) => {
	const fields = d.fields.map(display);
	return i !== 7
		? { ...d, fields }
		: {
				...d,
				fields: [
					...fields.map((f) => (f.name === PERTIMBANGAN ? { ...f, label: 'Pertimbangan' } : f)),
					{
						name: SYARAT,
						type: 'rich_text' as const,
						options: [],
						description: 'Syarat yang menyertai keputusan Disetujui bersyarat.'
					}
				]
			};
});

export const labelOf = (f: PropDef) => f.label ?? f.name;

/** How the UI names one stored option of a select kolom. */
export const optionLabel = (f: PropDef, option: string) => f.optionLabels?.[option] ?? option;

/** The same, by kolom name, for badges that show a stored value outside its field. */
export const valueLabel = (name: string, value: string) => OPTION_LABELS[name]?.[value] ?? value;

export const DECISION_STATUS = 'Status keputusan';
export const ACTION_STATUS = 'Status';
export const AGENDA_DECISIONS = 7;
export const AGENDA_ACTIONS = 8;

export const titleField = (db: number): PropDef => DBS[db].fields.find((f) => f.type === 'title')!;

export const isDate = (v: PropValue | undefined): v is DateValue =>
	!!v && typeof v === 'object' && !Array.isArray(v);

/** Whether a value counts as filled ("n/N terisi", the checklist). */
export const filled = (v: PropValue | undefined): boolean => {
	if (v === undefined || v === null || v === '' || v === false) return false;
	if (Array.isArray(v)) return v.length > 0;
	if (isDate(v)) return !!(v.start || v.end);
	return true;
};

export const text = (v: PropValue | undefined): string => (typeof v === 'string' ? v : '');
