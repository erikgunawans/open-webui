import { describe, expect, it } from 'vitest';

import { captureRecord } from './capture';
import { closingGaps, decide, decisionGaps, gapLine } from './keputusan';
import { record, seedMeeting } from './seed';
import { SYARAT, type Meeting } from './types';

const withUsulan = (): [Meeting, string] => {
	const m = seedMeeting('r', 0);
	const { record: u } = captureRecord({ kind: 'usulan', from: 4, title: 'Kemitraan PLTS' });
	m.records[7] = [u];
	m.records[8] = [];
	return [m, u.id];
};

describe('Keputusan', () => {
	it('needs a Rumusan for any Keputusan, a Syarat for bersyarat and a date for Ditunda', () => {
		const r = record({ 'Topik keputusan': 'X' });
		expect(decisionGaps(r, 'Belum diputuskan')).toEqual([]);
		expect(decisionGaps(r, 'Disetujui')).toEqual(['Rumusan keputusan']);
		expect(decisionGaps(r, 'Ditolak')).toEqual(['Rumusan keputusan']);
		expect(decisionGaps(r, 'Disetujui bersyarat')).toEqual(['Rumusan keputusan', SYARAT]);
		expect(decisionGaps(r, 'Ditunda')).toEqual(['Rumusan keputusan', 'Tanggal pembahasan ulang']);
	});

	it('records nothing while a kolom is missing, and everything in one write once filled', () => {
		const [m, id] = withUsulan();
		expect(decide(m, id, 'Disetujui bersyarat', { 'Rumusan keputusan': 'Disetujui' })).toBeNull();
		const next = decide(m, id, 'Disetujui bersyarat', {
			'Rumusan keputusan': 'Disetujui',
			[SYARAT]: 'Setelah review Legal'
		})!;
		expect(next.records[7][0].values).toMatchObject({
			'Status keputusan': 'Disetujui bersyarat',
			[SYARAT]: 'Setelah review Legal'
		});
		expect(decide(m, id, 'Belum diputuskan')).not.toBeNull();
	});
});

describe('Tutup rapat check', () => {
	it('counts undecided Usulan, Tindakan without a PIC, and Keputusan without a Rumusan', () => {
		const [m] = withUsulan();
		m.records[8] = [captureRecord({ kind: 'tindakan', from: 4, title: 'Review' }).record];
		m.records[7].push(record({ 'Topik keputusan': 'Lama', 'Status keputusan': 'Disetujui' }));
		const g = closingGaps(m);
		expect(g).toMatchObject({ undecided: 1, noPic: 1, noRumusan: 1, any: true });
		expect(gapLine(g)).toBe(
			'1 usulan belum diputuskan · 1 tindakan tanpa PIC · 1 keputusan tanpa rumusan'
		);
	});

	it('has nothing to ask about a meeting without Usulan or Tindakan', () => {
		const m = seedMeeting('r', 0);
		m.records[7] = [];
		m.records[8] = [];
		expect(closingGaps(m).any).toBe(false);
	});
});
