import { describe, expect, it } from 'vitest';

import { relativeTime, toMillis } from './homeTime';

const NOW = Date.UTC(2026, 9, 3, 12, 0, 0);
const s = (ms: number) => Math.floor(ms / 1000);

describe('toMillis', () => {
	it('reads seconds, milliseconds and nanoseconds', () => {
		expect(toMillis(s(NOW))).toBe(s(NOW) * 1000);
		expect(toMillis(NOW)).toBe(NOW);
		expect(toMillis(NOW * 1_000_000)).toBe(NOW);
	});
});

describe('relativeTime', () => {
	it('says minutes and hours for today', () => {
		expect(relativeTime(s(NOW - 12 * 60_000), 'en-US', NOW)).toBe('12 minutes ago');
		expect(relativeTime(s(NOW - 3 * 3_600_000), 'en-US', NOW)).toBe('3 hours ago');
	});
	it('says yesterday, then a date', () => {
		expect(relativeTime(s(NOW - 26 * 3_600_000), 'en-US', NOW)).toBe('yesterday');
		expect(relativeTime(s(NOW - 10 * 86_400_000), 'en-US', NOW)).toBe('Sep 23');
	});
	it('follows the language', () => {
		expect(relativeTime(s(NOW - 26 * 3_600_000), 'id-ID', NOW)).toBe('kemarin');
	});
	it('calls anything under a minute now', () => {
		expect(relativeTime(s(NOW - 5_000), 'en-US', NOW)).toBe('now');
	});
});
