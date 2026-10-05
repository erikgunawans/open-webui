import { describe, expect, it } from 'vitest';

import { demoMeeting } from './demo';
import {
	agendaPlan,
	issues,
	kinerjaNotes,
	kpiTiles,
	labelled,
	people,
	programs,
	risks,
	stakeholders,
	strategicRows
} from './layar-model';
import { deviationTone, nearestOpenActions, pendingDecisions } from './selectors';
import { seedMeeting } from './seed';
import { fitScale } from './react/layar/Stage';
import { agendaKey } from './react/layar/useKeyboard';
import { nextStatus } from './react/layar/views/V08Aksi';

describe('KPI deviation tone', () => {
	it('is success at or over target for revenue-type rows', () => {
		expect(deviationTone('Revenue', 412, 412).tone).toBe('success');
		expect(deviationTone('EBITDA', 146.1, 138.5).tone).toBe('success');
	});

	it('is inverted for CAPEX and OPEX: at or under budget is success', () => {
		expect(deviationTone('CAPEX', 168.2, 245).tone).toBe('success');
		expect(deviationTone('OPEX', 198.6, 212).tone).toBe('success');
		expect(deviationTone('OPEX', 220, 212).tone).toBe('warning');
		expect(deviationTone('CAPEX', 300, 245).tone).toBe('danger');
	});

	it('is warning within 10% and danger beyond', () => {
		expect(deviationTone('Revenue', 387.3, 412).tone).toBe('warning');
		expect(deviationTone('Arus kas operasi', 71.4, 96).tone).toBe('danger');
	});
});

describe('the Layar read model of the demo meeting', () => {
	const m = demoMeeting(0);

	it('plans nine agendas totalling 175 minutes', () => {
		const plan = agendaPlan(m);
		expect(plan).toHaveLength(9);
		expect(plan.reduce((n, a) => n + a.menit, 0)).toBe(175);
		expect(plan[7].no).toBe('07');
	});

	it('maps every agenda’s rows through the schema fields', () => {
		expect(strategicRows(m).map((r) => r.pct)).toEqual([77, 74, 96, 62]);
		expect(kpiTiles(m)).toHaveLength(8);
		expect(issues(m)[0].target).toBe('30 Okt');
		expect(programs(m)[0].ang).toBeCloseTo(96);
		expect(risks(m).filter((r) => r.lvl === 'Tinggi')).toHaveLength(2);
		expect(stakeholders(m)[0].urg).toBe('Mendesak');
	});

	it('reads causes, corrections and liquidity as labelled rows', () => {
		expect(kinerjaNotes(m).pairs.map(([k]) => k)).toEqual(['Penyebab', 'Koreksi', 'Likuiditas']);
		expect(kinerjaNotes(m).monthly).toHaveLength(9);
		expect(kinerjaNotes(m).year).toBe('2026');
		expect(kinerjaNotes(m).period).toBe('YTD September 2026');
	});

	it('lists pending decisions and the four nearest open actions', () => {
		expect(pendingDecisions(m)).toHaveLength(4);
		const soon = nearestOpenActions(m).map((r) => r.values['ID tindakan']);
		expect(soon).toEqual(['A-07', 'A-06', 'A-01', 'A-04']);
	});

	it('splits people and labelled lines', () => {
		expect(people('Andi Pratama — Direktur Utama\nRina')).toEqual([
			['Andi Pratama', 'Direktur Utama'],
			['Rina', '']
		]);
		expect(labelled('Penyebab: a\nlanjutan\nKoreksi: b')).toEqual([
			['Penyebab', 'a lanjutan'],
			['Koreksi', 'b']
		]);
	});

	it('shows nothing from an empty template form', () => {
		const fresh = seedMeeting('x');
		expect(strategicRows(fresh)).toHaveLength(0);
		expect(issues(fresh)).toHaveLength(0);
		expect(kpiTiles(fresh)).toHaveLength(0);
	});
});

describe('Layar mechanics', () => {
	it('scales the 1920×1080 stage to fit and never to zero', () => {
		expect(fitScale(1920, 1080)).toBe(1);
		expect(fitScale(1280, 720)).toBeCloseTo(2 / 3);
		expect(fitScale(3840, 2160)).toBe(2);
		expect(fitScale(1920, 1200)).toBe(1);
		expect(fitScale(0, 0)).toBeNull();
	});

	it('maps the agenda keys', () => {
		expect(agendaKey('ArrowRight')).toEqual({ step: 1 });
		expect(agendaKey('PageUp')).toEqual({ step: -1 });
		expect(agendaKey('7')).toEqual({ jump: 7 });
		expect(agendaKey('9')).toBeNull();
		expect(agendaKey('a')).toBeNull();
	});

	it('advances an action’s status cyclically', () => {
		expect(nextStatus('Belum mulai')).toBe('Berjalan');
		expect(nextStatus('Selesai')).toBe('Belum mulai');
	});
});
