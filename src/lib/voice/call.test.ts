import { describe, expect, it, vi } from 'vitest';

import {
	CALL_OPENING,
	DISCLOSURE,
	DISCLOSURE_VERSION,
	beginCall,
	callButton,
	opensWithGreeting,
	sealedAnswerParts,
	speaksSealedAnswers,
	type CallSteps,
	type VoiceCapabilities
} from './call';

const caps = (overrides: Partial<VoiceCapabilities> = {}): VoiceCapabilities => ({
	enabled: true,
	granted: true,
	acknowledged: true,
	disclosure_version: DISCLOSURE_VERSION,
	...overrides
});

const steps = (capabilities: VoiceCapabilities | null, overrides: Partial<CallSteps> = {}) => {
	const calls: string[] = [];
	const s: CallSteps = {
		capabilities: vi.fn(async () => {
			calls.push('capabilities');
			return capabilities;
		}),
		disclose: vi.fn(async () => {
			calls.push('disclose');
			return true;
		}),
		acknowledge: vi.fn(async (version: string) => {
			calls.push(`acknowledge ${version}`);
		}),
		startCall: vi.fn(async () => {
			calls.push('startCall');
			return { chat_id: 'chat-1', model: 'asisten-jup-suara' };
		}),
		...overrides
	};
	return { s, calls };
};

describe('the call button (#29)', () => {
	it('is hidden while voice is switched off, whatever else holds', () => {
		expect(callButton(caps({ enabled: false }))).toBe('hidden');
		expect(callButton(caps({ enabled: false, granted: true, acknowledged: true }))).toBe('hidden');
	});

	it('is hidden without the voice grant', () => {
		expect(callButton(caps({ granted: false }))).toBe('hidden');
	});

	it('is hidden until the capabilities are known, or when they could not be read', () => {
		expect(callButton(null)).toBe('hidden');
		expect(callButton(undefined)).toBe('hidden');
	});

	it('opens the disclosure first when it has not been acknowledged', () => {
		expect(callButton(caps({ acknowledged: false }))).toBe('disclose');
	});

	it('calls straight away once acknowledged', () => {
		expect(callButton(caps())).toBe('call');
	});
});

describe('starting a call (#29)', () => {
	it('shows the disclosure before the first call, acknowledges this text, then starts via the route', async () => {
		const { s, calls } = steps(caps({ acknowledged: false }));
		const started = await beginCall(s);
		expect(calls).toEqual([
			'capabilities',
			'disclose',
			`acknowledge ${DISCLOSURE_VERSION}`,
			'startCall'
		]);
		expect(started).toEqual({ chat_id: 'chat-1', model: 'asisten-jup-suara' });
	});

	it('starts via the route without the disclosure once acknowledged', async () => {
		const { s, calls } = steps(caps());
		expect(await beginCall(s)).toEqual({ chat_id: 'chat-1', model: 'asisten-jup-suara' });
		expect(calls).toEqual(['capabilities', 'startCall']);
	});

	it('starts nothing when the disclosure is declined', async () => {
		const { s, calls } = steps(caps({ acknowledged: false }), {
			disclose: vi.fn(async () => {
				calls.push('disclose');
				return false;
			})
		});
		expect(await beginCall(s)).toBeNull();
		expect(calls).toEqual(['capabilities', 'disclose']);
	});

	it('starts nothing, and shows nothing, when voice is off or not granted', async () => {
		for (const c of [caps({ enabled: false }), caps({ granted: false }), null]) {
			const { s, calls } = steps(c);
			expect(await beginCall(s)).toBeNull();
			expect(calls).toEqual(['capabilities']);
		}
	});

	it('never starts a call when the acknowledgement is refused', async () => {
		const { s, calls } = steps(caps({ acknowledged: false }), {
			acknowledge: vi.fn(async () => {
				calls.push('acknowledge');
				throw { code: 'voice_disclosure_changed', message: 'The disclosure has changed.' };
			})
		});
		await expect(beginCall(s)).rejects.toMatchObject({ code: 'voice_disclosure_changed' });
		expect(calls).not.toContain('startCall');
	});
});

describe('the disclosure text (#29)', () => {
	const id = DISCLOSURE.id.join(' ');
	const en = DISCLOSURE.en.join(' ');

	it('says Google reads answers aloud, not OpenAI (#32, D23)', () => {
		expect(id).toMatch(/Google Text-to-Speech/);
		expect(en).toMatch(/Google Text-to-Speech/);
		expect(en).not.toMatch(/OpenAI[^.]*read answers aloud/);
		expect(id).not.toMatch(/OpenAI[^.]*membacakan jawaban/);
		expect(DISCLOSURE.id.length).toBe(DISCLOSURE.en.length);
	});

	it('is versioned like the server, so a changed text is acknowledged again', () => {
		expect(DISCLOSURE_VERSION).toBe('2026-09-28');
	});

	it('names OpenAI, the US and up to 30 days (D21), in both languages', () => {
		expect(id).toMatch(/OpenAI/);
		expect(id).toMatch(/Amerika Serikat/);
		expect(id).toMatch(/30 hari/);
		expect(en).toMatch(/OpenAI/);
		expect(en).toMatch(/United States/);
		expect(en).toMatch(/30 days/);
	});

	it('names OpenRouter and Xiaomi (D17)', () => {
		for (const text of [id, en]) {
			expect(text).toMatch(/OpenRouter/);
			expect(text).toMatch(/Xiaomi/);
		}
	});

	it('says voice answers only from the named strategy documents', () => {
		expect(id).toMatch(/dokumen strategi/);
		expect(en).toMatch(/strategy documents/);
	});

	it('says whatever is spoken is sent regardless, so no non-public figures (D16(e))', () => {
		expect(id).toMatch(/tetap terkirim/);
		expect(id).toMatch(/belum publik/);
		expect(en).toMatch(/sent regardless/);
		expect(en).toMatch(/not public/);
	});
});

describe('which answers are read by message id (#29)', () => {
	it('with OpenAI, only the sealed answer is read, never the streamed text', () => {
		expect(speaksSealedAnswers('openai')).toBe(true);
	});

	it('with Google (#32, D23), too', () => {
		expect(speaksSealedAnswers('google')).toBe(true);
	});

	it('leaves the browser voice and any other engine as the vendor had them', () => {
		for (const engine of ['', undefined, null, 'browser-kokoro', 'transformers', 'elevenlabs']) {
			expect(speaksSealedAnswers(engine)).toBe(false);
		}
	});
});

describe('waiting for the sealed answer (#29)', () => {
	const noWait = async () => {};

	it('returns the part count as soon as the answer is sealed', async () => {
		const parts = vi.fn(async () => 2);
		expect(await sealedAnswerParts(parts, { wait: noWait })).toBe(2);
		expect(parts).toHaveBeenCalledTimes(1);
	});

	it('retries while the answer is still being written or not yet sealed', async () => {
		const answers: Array<number | { code: string }> = [
			{ code: 'voice_tts_not_ready' },
			{ code: 'voice_tts_unsealed' },
			1
		];
		const parts = vi.fn(async () => {
			const next = answers.shift()!;
			if (typeof next === 'number') return next;
			throw next;
		});
		expect(await sealedAnswerParts(parts, { wait: noWait })).toBe(1);
		expect(parts).toHaveBeenCalledTimes(3);
	});

	it('gives up after a bounded number of tries', async () => {
		const parts = vi.fn(async () => {
			throw { code: 'voice_tts_unsealed' };
		});
		await expect(sealedAnswerParts(parts, { tries: 4, wait: noWait })).rejects.toMatchObject({
			code: 'voice_tts_unsealed'
		});
		expect(parts).toHaveBeenCalledTimes(4);
	});

	it('does not retry any other refusal', async () => {
		const parts = vi.fn(async () => {
			throw { code: 'voice_tts_not_voice' };
		});
		await expect(sealedAnswerParts(parts, { wait: noWait })).rejects.toMatchObject({
			code: 'voice_tts_not_voice'
		});
		expect(parts).toHaveBeenCalledTimes(1);
	});
});

describe('the call opening (greeting and pantun)', () => {
	it('is one fixed, visible line the voice model is told to answer with a greeting and a pantun', () => {
		expect(CALL_OPENING).toBe('Halo, saya memulai panggilan.');
	});

	it('is sent only on the call the start-call route just made, not on a reopened voice chat', () => {
		expect(opensWithGreeting('chat-1', 'chat-1')).toBe(true);
		expect(opensWithGreeting(null, 'chat-1')).toBe(false);
		expect(opensWithGreeting('chat-2', 'chat-1')).toBe(false);
		expect(opensWithGreeting('chat-1', undefined)).toBe(false);
	});
});
