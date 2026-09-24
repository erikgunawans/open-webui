import { describe, expect, test } from 'vitest';
import { allowedPurposes, evidenceProblem, newIdempotencyKey, type EvidenceInput } from './submit';

const input = (overrides: Partial<EvidenceInput> = {}): EvidenceInput => ({
	purpose: 'evidence',
	mode: 'link',
	file: null,
	url: 'https://example.test/ba',
	reason: '',
	replacementActionId: '',
	...overrides
});

describe('allowedPurposes', () => {
	test('completion only from in progress', () => {
		expect(allowedPurposes('in_progress')).toEqual([
			'evidence',
			'completed',
			'cancelled',
			'superseded'
		]);
		expect(allowedPurposes('blocked')).toEqual(['evidence', 'cancelled', 'superseded']);
		expect(allowedPurposes('not_started')).toEqual(['evidence', 'cancelled', 'superseded']);
	});

	test('no new request while one is open, or once closed', () => {
		expect(allowedPurposes('awaiting_bod_closure')).toEqual(['evidence']);
		expect(allowedPurposes('closed')).toEqual(['evidence']);
	});
});

describe('evidenceProblem', () => {
	test('a plain https link is fine', () => {
		expect(evidenceProblem(input(), 'in_progress')).toBeNull();
	});

	test('a link must be https with a host', () => {
		expect(evidenceProblem(input({ url: 'http://example.test' }), 'in_progress')).toBe(
			'link_not_https'
		);
		expect(evidenceProblem(input({ url: 'not a url' }), 'in_progress')).toBe('link_not_https');
	});

	test('a file must be chosen', () => {
		expect(evidenceProblem(input({ mode: 'file' }), 'in_progress')).toBe('file_missing');
		const file = new File(['x'], 'ba.pdf');
		expect(evidenceProblem(input({ mode: 'file', file }), 'in_progress')).toBeNull();
	});

	test('cancellation needs a reason, supersession its replacement', () => {
		expect(evidenceProblem(input({ purpose: 'cancelled', reason: '  ' }), 'blocked')).toBe(
			'reason_missing'
		);
		expect(evidenceProblem(input({ purpose: 'cancelled', reason: 'moved' }), 'blocked')).toBeNull();
		expect(evidenceProblem(input({ purpose: 'superseded' }), 'blocked')).toBe(
			'replacement_missing'
		);
	});

	test('completion from anywhere but in progress, or over an open request, is refused', () => {
		expect(evidenceProblem(input({ purpose: 'completed' }), 'blocked')).toBe('not_in_progress');
		expect(
			evidenceProblem(input({ purpose: 'cancelled', reason: 'x' }), 'awaiting_bod_closure')
		).toBe('request_open');
	});
});

test('each form gets its own idempotency key', () => {
	expect(newIdempotencyKey()).not.toBe(newIdempotencyKey());
});
