import { describe, expect, it } from 'vitest';

import { agendaLabel, agendaNumber } from './agendas';
import { agendaNo, captureLabel } from './capture';
import { demoMeeting } from './demo';
import { closingGaps, decisionGaps } from './keputusan';
import { closingSummary } from './layar-model';
import {
	decidedDecisions,
	decisions,
	isDecided,
	isIncomplete,
	pendingDecisions
} from './selectors';
import {
	ARAHAN,
	DBS,
	DECISION_STATUS,
	RUMUSAN,
	labelOf,
	optionLabel,
	text,
	type Meeting
} from './types';

// The 2026-10-06 design critique: display names over stored keys, one meaning of "diputuskan",
// and a demo meeting whose own Tutup rapat check passes.

const WAITING = ['Belum diputuskan', 'Ditunda'];

/** Set the first Usulan's statuses; a decided one gets a Rumusan unless `bare` (as stored before the rule). */
const withStatus = (m: Meeting, statuses: string[], bare = false): Meeting => ({
	...m,
	records: m.records.map((coll, i) =>
		i !== 7
			? coll
			: coll.map((r, j) =>
					j < statuses.length
						? {
								...r,
								values: {
									...r.values,
									[DECISION_STATUS]: statuses[j],
									...(bare || WAITING.includes(statuses[j])
										? { [RUMUSAN]: '' }
										: { [RUMUSAN]: 'Rumusan uji' })
								}
							}
						: r
				)
	)
});

describe('Agenda option labels', () => {
	it('shows a stored English option by the agenda name, and passes unknown text through', () => {
		expect(agendaLabel('1. Strategic Update')).toBe('1. Perkembangan Strategis');
		expect(agendaLabel('5. Risk & Compliance')).toBe('5. Risiko & Kepatuhan');
		expect(agendaLabel('8. Action Plan')).toBe('8. Rencana Tindak Lanjut');
		expect(agendaLabel('Lainnya')).toBe('Lainnya');
		expect(agendaLabel('')).toBe('');
		expect(agendaNumber('4. Program Prioritas')).toBe(4);
		expect(agendaNo('4. Program Prioritas')).toBe('04');
	});

	it('labels every Agenda option of 07 and 08 while the stored options stay as they were', () => {
		for (const db of [7, 8]) {
			const f = DBS[db].fields.find((x) => x.name === 'Agenda')!;
			expect(f.options[0]).toBe('1. Strategic Update');
			expect(f.options.map((o) => optionLabel(f, o))).toEqual([
				'1. Perkembangan Strategis',
				'2. Kinerja Perusahaan',
				'3. Isu Lintas Direktorat',
				'4. Program Prioritas',
				'5. Risiko & Kepatuhan',
				'6. Isu Pemangku Kepentingan',
				'7. Pengambilan Keputusan',
				'8. Rencana Tindak Lanjut'
			]);
		}
	});

	it('shows "Kesimpulan / arahan" as Arahan wherever the kolom exists', () => {
		const withArahan = DBS.map((d) => d.fields.find((f) => f.name === ARAHAN)).filter(Boolean);
		expect(withArahan.length).toBe(5);
		for (const f of withArahan) expect(labelOf(f!)).toBe('Arahan');
	});
});

describe('Catat cepat names', () => {
	it("calls a Butir by the agenda's own noun and keeps Usulan / Tindakan", () => {
		expect(captureLabel('butir', 1)).toBe('Sasaran');
		expect(captureLabel('butir', 3)).toBe('Isu');
		expect(captureLabel('butir', 5)).toBe('Risiko');
		expect(captureLabel('butir', 6)).toBe('Butir');
		expect(captureLabel('usulan', 3)).toBe('Usulan');
		expect(captureLabel('tindakan', 3)).toBe('Tindakan');
	});
});

describe('one meaning of diputuskan', () => {
	const m = withStatus(demoMeeting(0), ['Disetujui', 'Ditunda', 'Ditolak', 'Belum diputuskan']);

	it('counts a Ditunda as pending, not as decided', () => {
		const ids = (rs: ReturnType<typeof decisions>) => rs.map((r) => text(r.values['ID keputusan']));
		expect(ids(pendingDecisions(m))).toEqual(['D-02', 'D-04']);
		// D-05 is Disetujui in the demo source.
		expect(ids(decidedDecisions(m))).toEqual(['D-01', 'D-03', 'D-05']);
		expect(decisions(m).filter(isDecided).length + pendingDecisions(m).length).toBe(
			decisions(m).length
		);
	});

	it('gives the Penutupan the same decided count as the rail', () => {
		expect(closingSummary(m).decided).toBe(decidedDecisions(m).length);
	});

	it('keeps a status stored without its Rumusan with the Usulan that wait (critique, 2026-10-07)', () => {
		const bare = withStatus(demoMeeting(0), ['Disetujui'], true);
		const d1 = decisions(bare)[0];
		expect(isIncomplete(d1)).toBe(true);
		expect(isDecided(d1)).toBe(false);
		expect(pendingDecisions(bare)).toContain(d1);
		// Tutup rapat names it for what it is: a Keputusan without its Rumusan, not an undecided one.
		expect(closingGaps(bare)).toMatchObject({ noRumusan: 1 });
	});
});

describe('the demo meeting', () => {
	it('passes its own Tutup rapat check on rumusan', () => {
		expect(closingGaps(demoMeeting(0)).noRumusan).toBe(0);
	});

	it('carries every kolom its decided Usulan need', () => {
		for (const r of decidedDecisions(demoMeeting(0))) expect(decisionGaps(r)).toEqual([]);
	});
});
