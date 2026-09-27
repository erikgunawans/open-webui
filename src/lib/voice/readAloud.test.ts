import { describe, expect, it } from 'vitest';

import { readAloudUsesBrowser } from './readAloud';

describe('read-aloud on a typed answer (#28)', () => {
	it('uses the browser voice when OpenAI is the TTS engine', () => {
		// OpenAI reads only stored voice-call answers, by message id; a typed answer never goes there.
		expect(readAloudUsesBrowser('openai')).toBe(true);
	});

	it('uses the browser voice when no engine is set, as the vendor always did', () => {
		expect(readAloudUsesBrowser('')).toBe(true);
		expect(readAloudUsesBrowser(undefined)).toBe(true);
		expect(readAloudUsesBrowser(null)).toBe(true);
	});

	it('leaves any other server engine as the vendor had it', () => {
		for (const engine of ['transformers', 'elevenlabs', 'azure', 'mistral']) {
			expect(readAloudUsesBrowser(engine)).toBe(false);
		}
	});
});
