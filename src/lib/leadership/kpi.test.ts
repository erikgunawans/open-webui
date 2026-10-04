import { describe, expect, it } from 'vitest';

import type { KpiCatalogue, KpiItem } from '$lib/apis/leadership';
import { compute, fmt, fromInput, loadRealisasi, statusOf, targetAt, toInput } from './kpi';

const item = (over: Partial<KpiItem> = {}): KpiItem => ({
	id: 'k1',
	p: 'fin',
	so_k: '',
	so_d: '',
	name: 'Pendapatan',
	definition: '',
	satuan: 'Rp',
	unit: 'rp',
	formula: '',
	target: 400e9,
	weight: 0.3,
	monitoring: 'Tahunan',
	cum: true,
	...over
});

const catalogue = (items: KpiItem[], sample: KpiCatalogue['sample'] = {}): KpiCatalogue => ({
	year: 2026,
	source: 'test',
	sample_is_illustrative: true,
	perspectives: [{ id: 'fin', name: 'Financial', weight: 0.3 }],
	items,
	sample
});

describe('KPI scoring', () => {
	it('holds a cumulative KPI to a pro-rata quarterly target', () => {
		expect(targetAt(item(), 0)).toBe(100e9);
		expect(targetAt(item(), 3)).toBe(400e9);
		expect(targetAt(item({ cum: false }), 0)).toBe(400e9);
	});

	it('caps achievement at 110% when scoring', () => {
		const cat = catalogue([item()]);
		const q = compute(cat, { k1: [200e9, null, null, null] }, 0);
		expect(q.rows[0].ach).toBe(2);
		expect(q.total).toBeCloseTo(1.1 * 0.3 * 100);
		expect(q.per[0].max).toBeCloseTo(30);
	});

	it('scores a negative result as zero, not below', () => {
		const q = compute(catalogue([item()]), { k1: [-5e9, null, null, null] }, 0);
		expect(q.rows[0].ach).toBe(0);
		expect(q.total).toBe(0);
	});

	it('counts an empty quarter as not filled rather than failed', () => {
		const q = compute(catalogue([item()]), { k1: [null, null, null, null] }, 0);
		expect(q.filled).toBe(0);
		expect(q.rows[0].st.id).toBe('none');
	});

	it('names the three thresholds as the design does', () => {
		expect(statusOf(1).id).toBe('ok');
		expect(statusOf(0.85).id).toBe('warn');
		expect(statusOf(0.849).id).toBe('bad');
		expect(statusOf(null).id).toBe('none');
	});
});

describe('KPI formatting and input', () => {
	it('shows rupiah in miliar and fractions as percent', () => {
		expect(fmt(item(), 252156802078.44)).toBe('Rp 252,16 M');
		expect(fmt(item({ unit: 'pct', satuan: '%' }), 0.88)).toBe('88%');
		expect(fmt(item({ unit: 'count', satuan: 'Kali' }), 12)).toBe('12×');
	});

	it('round-trips what the reader types, with a decimal comma', () => {
		const pct = item({ unit: 'pct' });
		expect(fromInput(pct, '84,5')).toBeCloseTo(0.845);
		expect(toInput(pct, 0.845)).toBe('84.5');
		expect(fromInput(item(), '181.3')).toBeCloseTo(181.3e9);
		expect(fromInput(item(), '')).toBeNull();
		expect(fromInput(item(), 'abc')).toBeUndefined();
	});
});

describe('stored realisasi', () => {
	const cat = catalogue([item()], { k1: [1, 2, 3, null] });

	it('starts from the sample when nothing is stored or it is corrupt', () => {
		expect(loadRealisasi(cat, null)).toEqual({ k1: [1, 2, 3, null] });
		expect(loadRealisasi(cat, '{oops')).toEqual({ k1: [1, 2, 3, null] });
	});

	it('keeps a well-formed stored series and ignores a malformed one', () => {
		expect(loadRealisasi(cat, JSON.stringify({ k1: [9, null, null, null] }))).toEqual({
			k1: [9, null, null, null]
		});
		expect(loadRealisasi(cat, JSON.stringify({ k1: ['9'] }))).toEqual({ k1: [1, 2, 3, null] });
	});

	it('never hands back the catalogue sample itself', () => {
		const real = loadRealisasi(cat, null);
		real.k1[0] = 99;
		expect(cat.sample.k1[0]).toBe(1);
	});
});
