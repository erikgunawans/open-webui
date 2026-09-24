import { describe, expect, test } from 'vitest';
import {
	allowedPurposes,
	dueProblem,
	evidenceProblem,
	ownerMoves,
	newIdempotencyKey,
	reviewProblem,
	type EvidenceInput
} from './submit';

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

describe('reviewProblem', () => {
	const base = { reason: '', returnTo: null, evidenceId: 'ev-2' } as const;

	test('a close needs only the evidence revision it judges', () => {
		expect(reviewProblem({ ...base, decision: 'close' })).toBeNull();
		expect(reviewProblem({ ...base, decision: 'close', evidenceId: null })).toBe('no_evidence');
	});

	test('a return needs a reason and where it goes back to', () => {
		expect(reviewProblem({ ...base, decision: 'return' })).toBe('reason_missing');
		expect(reviewProblem({ ...base, decision: 'return', reason: 'BA unsigned' })).toBe(
			'return_to_missing'
		);
		expect(
			reviewProblem({ ...base, decision: 'return', reason: 'BA unsigned', returnTo: 'blocked' })
		).toBeNull();
	});

	test('a reopening needs a reason and no evidence revision', () => {
		expect(reviewProblem({ ...base, decision: 'reopen', evidenceId: null })).toBe('reason_missing');
		expect(
			reviewProblem({ ...base, decision: 'reopen', evidenceId: null, reason: 'PGN reopened it' })
		).toBeNull();
	});
});

describe('ownerMoves', () => {
	test('the PIC starts, blocks and unblocks; nothing else', () => {
		expect(ownerMoves('not_started')).toEqual(['in_progress', 'blocked']);
		expect(ownerMoves('in_progress')).toEqual(['blocked']);
		expect(ownerMoves('blocked')).toEqual(['in_progress']);
	});

	test('no owner move while the BOD holds the action or once it is closed', () => {
		expect(ownerMoves('awaiting_bod_closure')).toEqual([]);
		expect(ownerMoves('closed')).toEqual([]);
	});
});

describe('dueProblem', () => {
	test('each precision takes its own shape', () => {
		expect(dueProblem('date', '2026-11-30')).toBeNull();
		expect(dueProblem('month', '2026-11')).toBeNull();
		expect(dueProblem('year', '2027')).toBeNull();
		expect(dueProblem('year_range', '2026/2027')).toBeNull();
	});

	test('a missing or misshapen value is named, never guessed', () => {
		expect(dueProblem('year', '  ')).toBe('value_missing');
		expect(dueProblem('year', '27')).toBe('value_shape');
		expect(dueProblem('month', '2026-11-30')).toBe('value_shape');
		expect(dueProblem('year_range', '2026–2027')).toBe('value_shape');
	});
});
