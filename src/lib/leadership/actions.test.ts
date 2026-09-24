import { describe, expect, test } from 'vitest';
import type { Action } from '$lib/apis/leadership';
import { closureNote, closureRequest, isOpenAction, isSampleRegister } from './actions';

const action = (overrides: Partial<Action> = {}): Action => ({
	id: 'act-1',
	title: 'Title',
	owner_label: 'PIC',
	state: 'in_progress',
	source_as_of: '2026-09-24',
	due: null,
	progress_summary: null,
	source_ids: [],
	verification_status: 'unverified',
	history_complete: true,
	completion_evidence: [],
	closure: null,
	...overrides
});

describe('isOpenAction', () => {
	test('every records-mode state but closed is open', () => {
		for (const state of [
			'not_started',
			'in_progress',
			'blocked',
			'awaiting_bod_closure'
		] as const) {
			expect(isOpenAction(state)).toBe(true);
		}
		expect(isOpenAction('closed')).toBe(false);
	});

	test('a cancelled sample action is not open', () => {
		expect(isOpenAction('cancelled')).toBe(false);
		expect(isOpenAction('completion_submitted')).toBe(true);
	});
});

describe('closureNote', () => {
	const request = (status: 'open' | 'closed' | 'returned') => ({
		request_id: 'req-1',
		kind: 'completed' as const,
		status,
		replacement_action_id: null
	});

	test('a records-mode request is named by its status', () => {
		expect(closureNote(action({ closure: request('open') }))).toBe('requested');
		expect(closureNote(action({ closure: request('closed') }))).toBe('closed');
		expect(closureNote(action({ closure: request('returned') }))).toBe('returned');
	});

	test('a sample closure is only "recorded", and no closure is none', () => {
		expect(closureNote(action({ closure: { anything: true } }))).toBe('recorded');
		expect(closureNote(action())).toBe('none');
	});

	test('closureRequest ignores an opaque sample closure', () => {
		expect(closureRequest(action({ closure: { anything: true } }))).toBeNull();
		expect(closureRequest(action({ closure: request('open') }))?.request_id).toBe('req-1');
	});
});

describe('isSampleRegister', () => {
	test('only the records source is a register', () => {
		expect(isSampleRegister({ actions_source: 'sample' })).toBe(true);
		expect(isSampleRegister({ actions_source: 'records' })).toBe(false);
	});
});
