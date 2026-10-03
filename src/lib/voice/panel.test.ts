import { describe, expect, it, vi } from 'vitest';

import { DISCLOSURE_VERSION, type VoiceCapabilities } from './call';
import { LIVE_DISCLOSURE_VERSION } from './live';
import {
	addTurn,
	panelModes,
	speakSealedAnswer,
	startPanelCall,
	viewFromPath,
	type PanelCallSteps
} from './panel';

const caps = (overrides: Partial<VoiceCapabilities> = {}): VoiceCapabilities => ({
	enabled: true,
	granted: true,
	acknowledged: true,
	disclosure_version: DISCLOSURE_VERSION,
	live: { granted: true, acknowledged: true, disclosure_version: LIVE_DISCLOSURE_VERSION },
	...overrides
});

const steps = (capabilities: VoiceCapabilities | null, overrides: Partial<PanelCallSteps> = {}) => {
	const calls: string[] = [];
	const s: PanelCallSteps = {
		capabilities: vi.fn(async () => capabilities),
		disclose: vi.fn(async () => (calls.push('disclose'), true)),
		acknowledge: vi.fn(async (v: string) => void calls.push(`ack ${v}`)),
		discloseLive: vi.fn(async () => (calls.push('discloseLive'), true)),
		acknowledgeLive: vi.fn(async (v: string) => void calls.push(`ackLive ${v}`)),
		startCall: vi.fn(async () => (calls.push('startCall'), { chat_id: 'c-1', model: 'm' })),
		setContext: vi.fn(
			async (chatId: string, view: string) => void calls.push(`context ${chatId} ${view}`)
		),
		...overrides
	};
	return { s, calls };
};

describe('viewFromPath', () => {
	it('names the tab the path is on', () => {
		expect(viewFromPath('/ruang-pimpinan/rka')).toBe('rka');
		expect(viewFromPath('/ruang-pimpinan/board/records/x')).toBe('board');
	});
	it('is null anywhere else', () => {
		expect(viewFromPath('/ruang-pimpinan')).toBeNull();
		expect(viewFromPath('/c/rka')).toBeNull();
		expect(viewFromPath('/ruang-pimpinan/rkax')).toBeNull();
	});
});

describe('panelModes', () => {
	it('offers nothing without the switch or the call grant', () => {
		expect(panelModes(null)).toEqual([]);
		expect(panelModes(caps({ granted: false }))).toEqual([]);
		expect(panelModes(caps({ enabled: false }))).toEqual([]);
	});
	it('offers GPT-Live only with its grant', () => {
		expect(panelModes(caps())).toEqual(['governed', 'live']);
		expect(panelModes(caps({ live: undefined }))).toEqual(['governed']);
		expect(
			panelModes(caps({ live: { granted: false, acknowledged: false, disclosure_version: 'x' } }))
		).toEqual(['governed']);
	});
});

describe('startPanelCall', () => {
	it('starts a normal call and tells the server which tab is open', async () => {
		const { s, calls } = steps(caps());
		expect(await startPanelCall(s, 'governed', 'rka')).toEqual({
			chat_id: 'c-1',
			mode: 'governed'
		});
		expect(calls).toEqual(['startCall', 'context c-1 rka']);
	});

	it('asks for both disclosures before a first GPT-Live call', async () => {
		const live = {
			granted: true,
			acknowledged: false,
			disclosure_version: LIVE_DISCLOSURE_VERSION
		};
		const { s, calls } = steps(caps({ acknowledged: false, live }));
		expect(await startPanelCall(s, 'live', 'board')).toEqual({ chat_id: 'c-1', mode: 'live' });
		expect(calls).toEqual([
			'discloseLive',
			`ackLive ${LIVE_DISCLOSURE_VERSION}`,
			'disclose',
			`ack ${DISCLOSURE_VERSION}`,
			'startCall',
			'context c-1 board'
		]);
	});

	it('starts nothing when a disclosure is declined', async () => {
		const { s, calls } = steps(caps({ acknowledged: false }), {
			disclose: vi.fn(async () => false)
		});
		expect(await startPanelCall(s, 'governed', 'rka')).toBeNull();
		expect(calls).toEqual([]);
	});

	it('falls back to a normal call when GPT-Live is asked for without its grant', async () => {
		const { s } = steps(caps({ live: undefined }));
		expect(await startPanelCall(s, 'live', 'rka')).toEqual({ chat_id: 'c-1', mode: 'governed' });
	});

	it('still starts the call when the tab cannot be recorded', async () => {
		const { s } = steps(caps(), { setContext: vi.fn(async () => Promise.reject({ code: 'x' })) });
		expect(await startPanelCall(s, 'governed', 'board')).toEqual({
			chat_id: 'c-1',
			mode: 'governed'
		});
	});

	it('records no tab off the leadership pages', async () => {
		const { s, calls } = steps(caps());
		await startPanelCall(s, 'governed', null);
		expect(calls).toEqual(['startCall']);
	});
});

describe('addTurn', () => {
	it('appends and keeps the last turns only', () => {
		let turns = [] as ReturnType<typeof addTurn>;
		for (let i = 0; i < 60; i++) turns = addTurn(turns, { who: 'caller', text: `${i}` }, 50);
		expect(turns).toHaveLength(50);
		expect(turns[0].text).toBe('10');
		expect(turns.at(-1)?.text).toBe('59');
	});
});

describe('speakSealedAnswer', () => {
	it('reads every part in order', async () => {
		const played: string[] = [];
		await speakSealedAnswer(
			{
				parts: async () => 2,
				part: async (n) => `audio-${n}`,
				play: async (audio) => void played.push(audio)
			},
			new AbortController().signal
		);
		expect(played).toEqual(['audio-0', 'audio-1']);
	});

	it('stops fetching once aborted', async () => {
		const controller = new AbortController();
		const part = vi.fn(async (n: number) => `audio-${n}`);
		await speakSealedAnswer(
			{
				parts: async () => 3,
				part,
				play: async () => controller.abort()
			},
			controller.signal
		);
		expect(part).toHaveBeenCalledTimes(1);
	});

	it('retries while the answer is not sealed yet', async () => {
		let tries = 0;
		const played: string[] = [];
		await speakSealedAnswer(
			{
				parts: async () => {
					if (++tries < 3) throw { code: 'voice_tts_not_ready' };
					return 1;
				},
				part: async () => 'a',
				play: async (a) => void played.push(a),
				wait: async () => {}
			},
			new AbortController().signal
		);
		expect(played).toEqual(['a']);
	});
});
