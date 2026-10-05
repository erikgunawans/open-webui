import { STANDARD_MINUTES } from './agendas';
import type { Meeting, MeetingSession, NotulenRecord, PropValue } from './types';

// A new meeting: one Informasi entry (the template's second; its empty twin and its Notion-only
// page body are dropped), Strategic ×1, Kinerja ×9 (eight starter indicators and one empty), and
// one empty form for each of agendas 3–8.

export const newId = (): string =>
	typeof crypto !== 'undefined' && 'randomUUID' in crypto
		? crypto.randomUUID().slice(0, 8)
		: Math.random().toString(36).slice(2, 10);

export const record = (
	values: Record<string, PropValue> = {},
	body = '',
	origin = 'Record kosong dari sumber'
): NotulenRecord => ({ id: newId(), values, body, time: {}, origin });

export const KINERJA_STARTERS = [
	'Revenue',
	'EBITDA',
	'Laba bersih',
	'Arus kas operasi',
	'Saldo kas akhir',
	'CAPEX',
	'OPEX',
	'KPI utama — isi nama KPI'
];

const EMPTY_FORM = 'Formulir kosong — belum ada record di sumber';

export const freshSession = (now = Date.now()): MeetingSession => ({
	currentAgenda: 0,
	doneAgendas: [],
	agendaEnteredAt: now
});

export const seedRecords = (): NotulenRecord[][] => [
	[record({ 'Nama rapat': 'Isi nama rapat', 'Status validasi': 'Draft' }, '', 'Record sumber')],
	[record()],
	[...KINERJA_STARTERS.map((n) => record({ Indikator: n }, '', 'Indikator awal')), record()],
	...[3, 4, 5, 6, 7, 8].map(() => [record({}, '', EMPTY_FORM)])
];

export const seedMeeting = (id: string, now = Date.now()): Meeting => ({
	id,
	records: seedRecords(),
	session: freshSession(now),
	plan: { agendas: STANDARD_MINUTES.map((menit) => ({ menit, pemapar: '' })) }
});
