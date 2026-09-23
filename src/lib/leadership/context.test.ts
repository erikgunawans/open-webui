import { describe, expect, test } from 'vitest';
import { defaultView, validateContextQuery } from './context';

describe('defaultView', () => {
	test('Board opens first for a reader granted both', () => {
		expect(defaultView(['board', 'rka'])).toBe('board');
		expect(defaultView(['rka', 'board'])).toBe('board');
	});

	test('a reader granted one view lands on it', () => {
		expect(defaultView(['rka'])).toBe('rka');
		expect(defaultView(['board'])).toBe('board');
	});

	test('no grant means no view', () => {
		expect(defaultView([])).toBeNull();
	});
});

describe('validateContextQuery', () => {
	test('omitted keys resolve to the view example', () => {
		expect(validateContextQuery(new URLSearchParams(''), 'board')).toBeNull();
		expect(
			validateContextQuery(new URLSearchParams('record=example-revenue-ytd'), 'rka')
		).toBeNull();
	});

	test('the exact supported ids are accepted', () => {
		const board = new URLSearchParams(
			'scope=jup-consolidated&context=example-board-2026-08&period=2026-01-01/2026-08-31'
		);
		expect(validateContextQuery(board, 'board')).toBeNull();
	});

	test('an unknown context is reported, not replaced', () => {
		expect(validateContextQuery(new URLSearchParams('context=unknown'), 'board')).toBe('context');
	});

	test("the other view's context is not accepted", () => {
		expect(
			validateContextQuery(new URLSearchParams('context=example-rka-2027-draft-1'), 'board')
		).toBe('context');
	});

	test('a different period or scope is reported', () => {
		expect(validateContextQuery(new URLSearchParams('period=2026-01-01/2026-12-31'), 'board')).toBe(
			'period'
		);
		expect(validateContextQuery(new URLSearchParams('scope=jup-spbg'), 'rka')).toBe('scope');
	});

	test('an empty value is not the supported value', () => {
		expect(validateContextQuery(new URLSearchParams('context='), 'board')).toBe('context');
	});
});
