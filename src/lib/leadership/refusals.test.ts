import { describe, expect, test } from 'vitest';
import { cleanServerText, recogniseServerText } from './refusals';

// Each input is the text the server sends today, copied from backend/jup/leadership and the
// router. A reworded server message falls back to English, which these tests then catch.
const code = (text: string) => recogniseServerText(text)?.code ?? null;

describe('recogniseServerText', () => {
	test('fixed refusals', () => {
		expect(code('the due date is unchanged; a revision must move it')).toBe('due_unchanged');
		expect(code('the PIC cannot change while a closure request is with the BOD')).toBe(
			'pic_locked'
		);
		expect(code('No account has that email.')).toBe('no_account');
		expect(code('four-eyes publication: the author of a draft cannot publish it')).toBe(
			'four_eyes'
		);
		expect(code('this reviewer has already voted to close on this evidence')).toBe('already_voted');
		expect(code('This candidate was already reviewed.')).toBe('already_reviewed');
	});

	test('refusals built around a value', () => {
		expect(code("an owner cannot move an action from 'closed' to 'blocked'")).toBe(
			'owner_move_refused'
		);
		expect(
			code(
				"an owner cannot move an action to 'closed'; closure is requested with evidence and decided by the BOD"
			)
		).toBe('owner_cannot_close');
		expect(code("no closure request is open on an action that is 'in_progress'")).toBe(
			'no_request_open'
		);
		expect(code("only a closed action is reopened, not one that is 'blocked'")).toBe(
			'not_reopenable'
		);
		expect(
			code("completion evidence is submitted on an action in progress, not one that is 'blocked'")
		).toBe('completion_not_in_progress');
		expect(code("'2026-13' is not a month due date")).toBe('due_invalid');
		expect(code("'2026-02' has no month 13")).toBe('due_invalid');
		expect(code('meeting_date must be a YYYY-MM-DD date')).toBe('date_format');
	});

	test('values the translation needs are captured', () => {
		expect(recogniseServerText("no replacement action 'A-9'")).toEqual({
			code: 'replacement_unknown',
			values: { id: 'A-9' }
		});
		expect(recogniseServerText('evidence files are limited to 26214400 bytes')?.values.size).toBe(
			'25 MB'
		);
		expect(
			recogniseServerText('the file was declared as application/pdf but its content is image/png')
				?.values
		).toEqual({ declared: 'application/pdf', actual: 'image/png' });
		expect(recogniseServerText('reason is required')).toEqual({
			code: 'field_required',
			values: { field: 'reason' }
		});
	});

	test('the exact cancellation message wins over the generic "needs a reason"', () => {
		expect(code('a supersession request, and only one, names its replacement action')).toBe(
			'replacement_missing'
		);
		expect(code('a cancellation request needs a reason')).toBe('reason_needed');
		expect(code('a return needs a reason')).toBe('reason_needed');
	});

	test('candidate-file breaches keep their path as detail', () => {
		expect(recogniseServerText("$.candidates[0].key: 'k1' appears twice")).toEqual({
			code: 'invalid_file',
			values: { detail: "$.candidates[0].key: 'k1' appears twice" }
		});
		expect(code('the file is not UTF-8 JSON without floats: Expecting value')).toBe('invalid_file');
	});

	test('an unreadable body is malformed, not shown as JSON', () => {
		expect(code('[{"type":"missing","loc":["body","pic_email"]}]')).toBe('malformed');
	});

	test('flag reasons', () => {
		expect(code('no staleness policy is recorded')).toBe('flag_no_stale_policy');
		expect(code('the owner has not updated this action')).toBe('flag_never_updated');
		expect(recogniseServerText('the due date is quarter-precise, not a day')).toEqual({
			code: 'flag_due_not_day',
			values: { precision: 'quarter' }
		});
	});

	test("an Error's name prefix is not part of the message", () => {
		expect(code('LeadershipRequestError: the evidence file is empty')).toBe('file_empty');
		expect(cleanServerText('Error: offline')).toBe('offline');
	});

	test('unknown text is left alone', () => {
		expect(recogniseServerText('The server is on fire.')).toBeNull();
		expect(recogniseServerText('Isian ini wajib.')).toBeNull();
	});
});
