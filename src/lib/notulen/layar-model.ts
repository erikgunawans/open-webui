import { AGENDAS, STANDARD_MINUTES } from './agendas';
import { actions, decisions, deviationTone, fmtShort, mainInfo, targetOf } from './selectors';
import {
	DECISION_STATUS,
	filled,
	isDate,
	text,
	type Meeting,
	type NotulenRecord,
	type PropValue
} from './types';

// The Layar is a read model of one Meeting. Field mapping per the handoff README ("Production data
// flow"); every value comes from the schema's own property names. Rows with no title are left out:
// an empty template form is not something to put on the boardroom screen.

const t = (r: NotulenRecord, k: string) => text(r.values[k]);
const lines = (v: PropValue | undefined) =>
	text(v)
		.split('\n')
		.map((x) => x.trim())
		.filter(Boolean);
const num = (v: PropValue | undefined): number | null => {
	const n = Number(text(v).replace(',', '.'));
	return text(v).trim() !== '' && Number.isFinite(n) ? n : null;
};
const titled = (m: Meeting, db: number, title: string) => m.records[db].filter((r) => t(r, title));

export type AgendaPlan = { no: string; nav: string; focus: string; menit: number; pemapar: string };

export const agendaPlan = (m: Meeting): AgendaPlan[] =>
	AGENDAS.map((a, i) => ({
		no: a.no,
		nav: a.layar,
		focus: i === 0 ? '' : a.focus,
		menit: m.plan?.agendas[i]?.menit ?? STANDARD_MINUTES[i],
		pemapar: m.plan?.agendas[i]?.pemapar ?? ''
	}));

/** "Andi Pratama — Direktur Utama" lines → [name, position]. */
export const people = (v: PropValue | undefined): [string, string][] =>
	lines(v).map((l) => {
		const [n, ...rest] = l.split(/\s+[—–-]\s+/);
		return [n.trim(), rest.join(' — ').trim()];
	});

/** "Penyebab: …" lines → [label, text]; a line without a label continues the previous one. */
export const labelled = (v: PropValue | undefined): [string, string][] =>
	lines(v).reduce<[string, string][]>((out, l) => {
		const m = /^([^:]{2,24}):\s*(.+)$/.exec(l);
		if (m) out.push([m[1], m[2]]);
		else if (out.length) out[out.length - 1][1] += ` ${l}`;
		else out.push(['', l]);
		return out;
	}, []);

export const strategicRows = (m: Meeting) =>
	titled(m, 1, 'Sasaran strategis').map((r) => ({
		id: r.id,
		sasaran: t(r, 'Sasaran strategis'),
		sub: [t(r, 'Pemapar'), t(r, 'Deviasi & hambatan')].filter(Boolean).join(' · '),
		target: t(r, 'Target & indikator'),
		posisi: t(r, 'Posisi terkini / pencapaian'),
		pct: m.plan?.strategicProgress?.[r.id] ?? null,
		evaluasi: t(r, 'Evaluasi strategi')
	}));

export const kpiTiles = (m: Meeting) =>
	titled(m, 2, 'Indikator')
		.map((r) => ({ r, target: num(r.values['Target / anggaran']), real: num(r.values.Realisasi) }))
		.filter((x) => x.target !== null && x.real !== null)
		.map(({ r, target, real }) => {
			const ind = t(r, 'Indikator');
			const stored = num(r.values['Deviasi persen']);
			const dev = deviationTone(ind, real!, target!);
			// Deviasi persen is entered by hand (the Notulen says so); show it when given.
			return {
				id: r.id,
				ind,
				real: real!,
				target: target!,
				pct: t(r, 'Satuan') === 'Persen',
				...dev,
				d: stored ?? dev.d
			};
		});

export const kinerjaNotes = (m: Meeting) => {
	const rows = titled(m, 2, 'Indikator');
	const cause = rows.map((r) => r.values['Penyebab & langkah koreksi']).find((v) => text(v));
	const liq = rows.map((r) => t(r, 'Likuiditas & pendanaan')).find(Boolean) ?? '';
	const basis = rows.map((r) => t(r, 'Basis pelaporan')).find(Boolean) ?? '';
	const period = rows.map((r) => r.values['Periode laporan']).find((v) => isDate(v) && v.end);
	const until = isDate(period)
		? new Date(`${period.end.slice(0, 10)}T00:00`).toLocaleDateString('id-ID', {
				month: 'long',
				year: 'numeric'
			})
		: '';
	return {
		pairs: [...labelled(cause), ...(liq ? ([['Likuiditas', liq]] as [string, string][]) : [])],
		period: [basis, until].filter(Boolean).join(' '),
		year: isDate(period) ? period.end.slice(0, 4) : '',
		monthly: m.plan?.revenueMonthly ?? []
	};
};

export const issues = (m: Meeting) =>
	titled(m, 3, 'Isu').map((r) => ({
		id: r.id,
		isu: t(r, 'Isu'),
		unit: t(r, 'Direktorat / divisi terkait'),
		dampak: t(r, 'Dampak perusahaan'),
		perlu: t(r, 'Keputusan yang diperlukan'),
		pic: t(r, 'PIC koordinasi'),
		target: fmtShort(r.values['Target penyelesaian']),
		ref: t(r, 'Referensi keputusan / tindak lanjut')
	}));

export const programs = (m: Meeting) =>
	titled(m, 4, 'Program / proyek').map((r) => ({
		id: r.id,
		nama: t(r, 'Program / proyek'),
		sub: [t(r, 'Kategori'), t(r, 'PIC utama')].filter(Boolean).join(' · '),
		pct: num(r.values['Progres persen']),
		ang: (num(r.values['Anggaran Rp']) ?? 0) / 1e9,
		real: (num(r.values['Realisasi Rp']) ?? 0) / 1e9,
		milestone: t(r, 'Target milestone') || fmtShort(r.values['Tanggal milestone']),
		status: t(r, 'Status progres')
	}));

export const risks = (m: Meeting) =>
	titled(m, 5, 'Risiko / isu kepatuhan').map((r) => ({
		id: r.id,
		r: t(r, 'Risiko / isu kepatuhan'),
		lvl: t(r, 'Tingkat risiko'),
		kat: (r.values['Kategori dampak'] as string[] | undefined) ?? [],
		mitigasi: t(r, 'Mitigasi / kontrol'),
		owner: t(r, 'Risk owner / PIC'),
		tenggat: fmtShort(r.values.Tenggat),
		status: t(r, 'Status mitigasi')
	}));

export const stakeholders = (m: Meeting) =>
	titled(m, 6, 'Stakeholder / organisasi').map((r) => ({
		id: r.id,
		org: t(r, 'Stakeholder / organisasi'),
		jenis: t(r, 'Jenis stakeholder'),
		isu: t(r, 'Isu / permintaan utama'),
		pic: t(r, 'PIC komunikasi'),
		target: fmtShort(r.values['Target tindak lanjut']),
		urg: t(r, 'Urgensi')
	}));

/** A decision's on-screen id: its ID keputusan, else D-01… by position. */
export const decisionId = (r: NotulenRecord, i: number) =>
	t(r, 'ID keputusan') || `D-${String(i + 1).padStart(2, '0')}`;
export const actionId = (r: NotulenRecord, i: number) =>
	t(r, 'ID tindakan') || `A-${String(i + 1).padStart(2, '0')}`;

/** Epoch ms → "2026-10-05T11:58" on the Asia/Jakarta clock (the form every date value uses). */
export const jakartaLocal = (ms: number): string =>
	new Date(ms)
		.toLocaleString('sv-SE', { timeZone: 'Asia/Jakarta', hour12: false })
		.slice(0, 16)
		.replace(' ', 'T');

const CLOSED_AT = 'Waktu rapat ditutup';

/**
 * "Tutup rapat": the last agenda is done and the session is closed at `now`. The Informasi entry's
 * "Waktu rapat ditutup" takes that time only when it is still empty — a time the secretary typed
 * wins, and reopening and closing again keeps the first close.
 */
export const closeMeeting = (m: Meeting, now: number): Meeting => {
	const last = m.records.length - 1;
	const info = mainInfo(m);
	const stamp = info && !filled(info.values[CLOSED_AT]);
	return {
		...m,
		records: stamp
			? m.records.map((coll, i) =>
					i !== 0
						? coll
						: coll.map((r) =>
								r.id === info.id
									? {
											...r,
											values: { ...r.values, [CLOSED_AT]: { start: jakartaLocal(now), end: '' } },
											time: { ...r.time, [CLOSED_AT]: true }
										}
									: r
							)
				)
			: m.records,
		session: {
			...m.session,
			doneAgendas: [...new Set([...m.session.doneAgendas, last])],
			currentAgenda: last,
			closedAt: now
		}
	};
};

/** Leave the closing screen for agenda `i`; the meeting runs again. */
export const reopenAt = (m: Meeting, i: number, now: number): Meeting => {
	const { closedAt: _closed, ...session } = m.session;
	return { ...m, session: { ...session, currentAgenda: i, agendaEnteredAt: now } };
};

const DECISION_ORDER = [
	'Disetujui',
	'Disetujui bersyarat',
	'Ditunda',
	'Ditolak',
	'Belum diputuskan'
];

/** What the closing screen reports: agendas done, decisions by status, actions and their gaps. */
export const closingSummary = (m: Meeting) => {
	const decs = decisions(m);
	const acts = actions(m);
	const statusOf = (r: NotulenRecord) => t(r, DECISION_STATUS) || 'Belum diputuskan';
	return {
		agendasDone: new Set(m.session.doneAgendas).size,
		agendasTotal: m.records.length,
		decisions: DECISION_ORDER.map(
			(s) => [s, decs.filter((r) => statusOf(r) === s).length] as const
		),
		decisionList: decs.map((r, i) => ({
			id: decisionId(r, i),
			topic: t(r, 'Topik keputusan'),
			status: statusOf(r)
		})),
		actions: acts.length,
		actionsIncomplete: acts.filter((r) => !t(r, 'PIC utama') || !targetOf(r)).length
	};
};
