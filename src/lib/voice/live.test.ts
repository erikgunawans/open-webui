import { describe, expect, it } from 'vitest';

import { LIVE_DISCLOSURE, LIVE_DISCLOSURE_VERSION, liveMode } from './live';
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
		expect(LIVE_DISCLOSURE_VERSION).toBe('2026-09-28');
	});

	it('says what is heard is a paraphrase that may differ in figures or caveats (a)', () => {
		expect(id).toMatch(/parafrase/);
		expect(id).toMatch(/angka/);
		expect(en).toMatch(/paraphrase/);
		expect(en).toMatch(/figures or caveats/);
	});

	it('says the assistant may answer itself, outside the documents (b)', () => {
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
