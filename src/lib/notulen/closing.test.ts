import { describe, expect, it } from 'vitest';

import { demoMeeting } from './demo';
import { closeMeeting, closingSummary, jakartaLocal, reopenAt } from './layar-model';
import { mainInfo } from './selectors';
import { seedMeeting } from './seed';

// 2026-10-05 04:58 UTC = 11:58 WIB.
const NOON = Date.UTC(2026, 9, 5, 4, 58);

describe('closing the meeting', () => {
	it('reads epoch ms on the Jakarta clock', () => {
		expect(jakartaLocal(NOON)).toBe('2026-10-05T11:58');
	});

	it('marks agenda 08 done, stays on it, and stamps an empty closing time', () => {
		const m = closeMeeting(seedMeeting('r', 0), NOON);
		expect(m.session.closedAt).toBe(NOON);
		expect(m.session.currentAgenda).toBe(8);
		expect(m.session.doneAgendas).toContain(8);
		const info = mainInfo(m)!;
		expect(info.values['Waktu rapat ditutup']).toEqual({ start: '2026-10-05T11:58', end: '' });
		expect(info.time['Waktu rapat ditutup']).toBe(true);
	});

	it('keeps a closing time already filled in', () => {
		const first = closeMeeting(seedMeeting('r', 0), NOON);
		const again = closeMeeting(reopenAt(first, 8, NOON + 60_000), NOON + 3_600_000);
		expect(mainInfo(again)!.values['Waktu rapat ditutup']).toEqual({
			start: '2026-10-05T11:58',
			end: ''
		});
		expect(again.session.closedAt).toBe(NOON + 3_600_000);
	});

	it('reopens at the chosen agenda without the closing mark', () => {
		const m = reopenAt(closeMeeting(seedMeeting('r', 0), NOON), 3, NOON + 1);
		expect('closedAt' in m.session).toBe(false);
		expect(m.session.currentAgenda).toBe(3);
		expect(m.session.agendaEnteredAt).toBe(NOON + 1);
	});

	it('summarises decisions by status and actions missing a PIC or target', () => {
		const m = demoMeeting(0);
		const s = closingSummary(m);
		const total = s.decisions.reduce((n, [, c]) => n + c, 0);
		expect(total).toBe(s.decisionList.length);
		expect(s.decisionList.length).toBeGreaterThan(0);
		expect(s.actions).toBeGreaterThan(0);
		expect(closingSummary(seedMeeting('r', 0))).toMatchObject({ actions: 0, decisionList: [] });
	});
});
