import { describe, expect, it, vi } from 'vitest';

import {
	LIVE_DISCLOSURE,
	LIVE_DISCLOSURE_VERSION,
	addCaption,
	chooseCallMode,
	greetingEvent,
	liveMode,
	ndjsonEvents
} from './live';
import { DISCLOSURE } from './call';

const live = (
	over: Partial<{ granted: boolean; acknowledged: boolean; disclosure_version: string }> = {}
) => ({
	enabled: true,
	live: { granted: true, acknowledged: true, disclosure_version: LIVE_DISCLOSURE_VERSION, ...over }
});

describe('whether GPT-Live is offered (#34)', () => {
	it('is hidden without the switch or the live grant', () => {
		expect(liveMode(null)).toBe('hidden');
		expect(liveMode({ ...live(), enabled: false })).toBe('hidden');
		expect(liveMode(live({ granted: false }))).toBe('hidden');
		expect(liveMode({ enabled: true })).toBe('hidden');
	});

	it('asks for its own disclosure until it is acknowledged', () => {
		expect(liveMode(live({ acknowledged: false }))).toBe('disclose');
	});

	it('asks again when the server holds another disclosure version', () => {
		expect(liveMode(live({ disclosure_version: '2000-01-01' }))).toBe('disclose');
	});

	it('is ready once granted and acknowledged', () => {
		expect(liveMode(live())).toBe('ready');
	});
});

describe('the GPT-Live disclosure text (ADR-0018)', () => {
	const id = LIVE_DISCLOSURE.id.join(' ');
	const en = LIVE_DISCLOSURE.en.join(' ');

	it('is versioned like the server', () => {
		expect(LIVE_DISCLOSURE_VERSION).toBe('2026-10-03');
	});

	it('says what is heard is a paraphrase that may differ in figures or caveats (a)', () => {
		expect(id).toMatch(/parafrase/);
		expect(id).toMatch(/angka/);
		expect(en).toMatch(/paraphrase/);
		expect(en).toMatch(/figures or caveats/);
	});

	it('names the real sources, within access rights, and never "strategy documents" (Erik 10-03)', () => {
		expect(id).toMatch(
			/basis pengetahuan JUP, kartu kontrak, dan Ruang Pimpinan, sesuai hak akses Anda/
		);
		expect(en).toMatch(
			/knowledge base, contract cards and Ruang Pimpinan, within your access rights/
		);
		expect(id).not.toMatch(/dokumen strategi/);
		expect(en).not.toMatch(/strategy documents/);
	});

	it('says the assistant may answer itself, without those sources (b)', () => {
		expect(id).toMatch(/menjawab sebagian pertanyaan sendiri/);
		expect(en).toMatch(/answer some questions itself/);
	});

	it('names OpenAI, the whole session, the US and up to 30 days (c)', () => {
		expect(id).toMatch(/Seluruh sesi/);
		expect(id).toMatch(/Amerika Serikat/);
		expect(id).toMatch(/30 hari/);
		expect(en).toMatch(/whole session/);
		expect(en).toMatch(/United States/);
		expect(en).toMatch(/30 days/);
	});

	it('points to the standard call for word-for-word answers', () => {
		expect(en).toMatch(/word for word/);
	});

	it('is its own text, not the governed call disclosure', () => {
		expect(LIVE_DISCLOSURE.en).not.toEqual(DISCLOSURE.en);
		expect(LIVE_DISCLOSURE.id.length).toBe(LIVE_DISCLOSURE.en.length);
	});
});

describe('the call-long stream (#36)', () => {
	const from = async function* (chunks: string[]) {
		for (const chunk of chunks) yield chunk;
	};
	const all = async (chunks: string[]) => {
		const out = [];
		for await (const event of ndjsonEvents(from(chunks))) out.push(event);
		return out;
	};

	it('yields one event per line, however the chunks fall', async () => {
		expect(
			await all([
				'{"type":"sess',
				'ion","session_id":"live_1","sdp":"v=0"}\n{"type":"pi',
				'ng"}\n',
				'{"type":"ended"}\n'
			])
		).toEqual([
			{ type: 'session', session_id: 'live_1', sdp: 'v=0' },
			{ type: 'ping' },
			{ type: 'ended' }
		]);
	});

	it('keeps a final line with no newline', async () => {
		expect(await all(['{"type":"ended"}'])).toEqual([{ type: 'ended' }]);
	});

	it('skips blank lines', async () => {
		expect(await all(['\n\n{"type":"ping"}\n\n'])).toEqual([{ type: 'ping' }]);
	});
});

describe('choosing the call mode (#37)', () => {
	const steps = (
		over: Partial<Record<'choose' | 'discloseLive' | 'acknowledgeLive', unknown>> = {}
	) => ({
		choose: vi.fn(async () => 'live' as const),
		discloseLive: vi.fn(async () => true),
		acknowledgeLive: vi.fn(async () => {}),
		...over
	});

	it('asks nothing without the live grant: the governed call, as before', async () => {
		const s = steps();
		expect(await chooseCallMode(live({ granted: false }), s as never)).toBe('governed');
		expect(s.choose).not.toHaveBeenCalled();
	});

	it('the caller may still choose the governed call', async () => {
		const s = steps({ choose: vi.fn(async () => 'governed' as const) });
		expect(await chooseCallMode(live(), s as never)).toBe('governed');
		expect(s.discloseLive).not.toHaveBeenCalled();
	});

	it('GPT-Live, already acknowledged, starts without the disclosure', async () => {
		const s = steps();
		expect(await chooseCallMode(live(), s as never)).toBe('live');
		expect(s.discloseLive).not.toHaveBeenCalled();
	});

	it('GPT-Live, not yet acknowledged, shows its disclosure and acknowledges this version', async () => {
		const s = steps();
		expect(await chooseCallMode(live({ acknowledged: false }), s as never)).toBe('live');
		expect(s.acknowledgeLive).toHaveBeenCalledWith(LIVE_DISCLOSURE_VERSION);
	});

	it('declining the GPT-Live disclosure starts nothing', async () => {
		const s = steps({ discloseLive: vi.fn(async () => false) });
		expect(await chooseCallMode(live({ acknowledged: false }), s as never)).toBeNull();
		expect(s.acknowledgeLive).not.toHaveBeenCalled();
	});

	it('backing out of the choice starts nothing', async () => {
		const s = steps({ choose: vi.fn(async () => null) });
		expect(await chooseCallMode(live(), s as never)).toBeNull();
	});
});

describe('the greeting (#37)', () => {
	it('is an Indonesian instruction for the whole session, not a delegation update', () => {
		const event = greetingEvent();
		expect(event.type).toBe('session.instructions.append');
		expect(event.delegation_id).toBeNull();
		expect(event.content).toMatch(/bahasa Indonesia/);
	});
});

describe('captions (#37)', () => {
	const heard = (delta: string, start_ms = 0) => ({
		type: 'session.input_transcript.delta',
		delta,
		start_ms
	});
	const said = (delta: string, start_ms = 0) => ({
		type: 'session.output_transcript.delta',
		delta,
		start_ms
	});

	it('joins fragments from the same speaker and starts a new caption on a change', () => {
		let captions = addCaption([], heard('Apa status ', 100));
		captions = addCaption(captions, heard('SPBG?'));
		captions = addCaption(captions, said('Masih di G1.', 900));
		expect(captions).toEqual([
			{ who: 'caller', text: 'Apa status SPBG?', start: 100 },
			{ who: 'assistant', text: 'Masih di G1.', start: 900 }
		]);
	});

	it('ignores every other event', () => {
		expect(addCaption([], { type: 'session.delegation.created' })).toEqual([]);
		expect(addCaption([], null)).toEqual([]);
	});

	it('keeps only the last few', () => {
		let captions: ReturnType<typeof addCaption> = [];
		for (let i = 0; i < 10; i++)
			captions = addCaption(captions, i % 2 ? heard(`q${i}`) : said(`a${i}`));
		expect(captions).toHaveLength(6);
		expect(captions[5].text).toBe('q9');
	});
});
