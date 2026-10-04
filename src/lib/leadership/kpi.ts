import type { KpiCatalogue, KpiItem, KpiPerspective } from '$lib/apis/leadership';

// The KPI 2026 tab's arithmetic, ported from Erik's "KPI Dashboard 2026" design (2026-10-05).
// Capaian = realisasi ÷ target; skor = min(capaian, cap) × bobot × 100; a cumulative KPI is held
// to a pro-rata quarterly target. The design's tweak defaults are fixed here: cap 110%, "perlu
// perhatian" from 85%, pro-rata on.

export const CAP = 1.1;
export const WARN = 0.85;
export const PRORATA = true;
export const QUARTERS = ['TW I', 'TW II', 'TW III', 'TW IV'] as const;

export type Realisasi = Record<string, (number | null)[]>;
export type StatusId = 'ok' | 'warn' | 'bad' | 'none';
export type Status = { id: StatusId; label: string };

export const STATUS_LABEL: Record<StatusId, string> = {
	ok: 'Tercapai',
	warn: 'Perlu perhatian',
	bad: 'Di bawah target',
	none: 'Belum diisi'
};

export const statusOf = (ach: number | null): Status => {
	const id: StatusId = ach == null ? 'none' : ach >= 1 ? 'ok' : ach >= WARN ? 'warn' : 'bad';
	return { id, label: STATUS_LABEL[id] };
};

export const targetAt = (k: KpiItem, q: number): number =>
	k.cum && PRORATA ? (k.target * (q + 1)) / 4 : k.target;

export type Row = {
	k: KpiItem;
	r: number | null;
	tg: number;
	ach: number | null;
	score: number;
	st: Status;
};
export type PerspectiveScore = {
	p: KpiPerspective;
	rows: Row[];
	score: number;
	max: number;
	filled: number;
};
export type Quarter = { rows: Row[]; per: PerspectiveScore[]; total: number; filled: number };

export const achievement = (r: number | null, tg: number): number | null =>
	r == null ? null : Math.max(0, r / tg);

export const compute = (cat: KpiCatalogue, real: Realisasi, q: number): Quarter => {
	const rows = cat.items.map((k): Row => {
		const r = real[k.id]?.[q] ?? null;
		const tg = targetAt(k, q);
		const ach = achievement(r, tg);
		const score = ach == null ? 0 : Math.min(ach, CAP) * k.weight * 100;
		return { k, r, tg, ach, score, st: statusOf(ach) };
	});
	const per = cat.perspectives.map((p) => {
		const rs = rows.filter((x) => x.k.p === p.id);
		return {
			p,
			rows: rs,
			score: rs.reduce((a, x) => a + x.score, 0),
			max: p.weight * 100,
			filled: rs.filter((x) => x.r != null).length
		};
	});
	return {
		rows,
		per,
		total: rows.reduce((a, x) => a + x.score, 0),
		filled: rows.filter((x) => x.r != null).length
	};
};

// --- Formatting (id-ID) ---

const SCALE = { rp: 1e9, pct: 0.01, count: 1 } as const;
export const SUFFIX = { rp: 'M', pct: '%', count: '' } as const;

export const nf = (v: number, d = 1) =>
	v.toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmt = (k: KpiItem, v: number | null): string => {
	if (v == null) return '—';
	if (k.unit === 'rp') return `Rp ${nf(v / 1e9, 2)} M`;
	if (k.unit === 'pct') return `${nf(v * 100, (v * 100) % 1 ? 1 : 0)}%`;
	return nf(v, v % 1 ? 1 : 0) + (k.satuan === 'Kali' ? '×' : '');
};

/** A stored value as the reader types it: rupiah in miliar, a fraction as a percent. */
export const toInput = (k: KpiItem, v: number | null): string =>
	v == null ? '' : String(+(v / SCALE[k.unit]).toFixed(4));

/** What the reader typed, back to a stored value. `undefined` = not a number, keep the old one. */
export const fromInput = (k: KpiItem, text: string): number | null | undefined => {
	const s = text.replace(',', '.').trim();
	if (s === '') return null;
	const n = Number(s);
	return Number.isFinite(n) ? n * SCALE[k.unit] : undefined;
};

// --- The reader's own realisasi, kept in this browser only ---

export const STORE = 'jup-kpi-2026-real-v1';

/** Stored realisasi if it is well-formed for this catalogue, else a fresh copy of the sample. */
export const loadRealisasi = (cat: KpiCatalogue, stored: string | null): Realisasi => {
	const fresh = (): Realisasi => JSON.parse(JSON.stringify(cat.sample));
	if (!stored) return fresh();
	try {
		const parsed = JSON.parse(stored);
		if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return fresh();
		const out = fresh();
		for (const k of cat.items) {
			const v = parsed[k.id];
			if (
				Array.isArray(v) &&
				v.length === 4 &&
				v.every((x) => x === null || (typeof x === 'number' && Number.isFinite(x)))
			)
				out[k.id] = v;
		}
		return out;
	} catch {
		return fresh();
	}
};
