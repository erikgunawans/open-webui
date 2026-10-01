import { describe, expect, it } from 'vitest';

import {
	IAP_GENERATED_HEADER,
	interruptPendingAnswer,
	isIapExpiry,
	withIapAjaxHeader
} from './session';

const ORIGIN = 'https://ops.axiara.ai';

describe('withIapAjaxHeader', () => {
	it('adds the AJAX hint to a same-origin path and keeps existing headers', () => {
		const [, init] = withIapAjaxHeader(
			'/api/v1/chats/',
			{ method: 'POST', headers: { Authorization: 'Bearer t' } },
			ORIGIN
		);
		const headers = new Headers(init?.headers);
		expect(headers.get('X-Requested-With')).toBe('XMLHttpRequest');
		expect(headers.get('Authorization')).toBe('Bearer t');
		expect(init?.method).toBe('POST');
	});

	it('adds it to an absolute same-origin URL with no init', () => {
		const [, init] = withIapAjaxHeader(`${ORIGIN}/api/config`, undefined, ORIGIN);
		expect(new Headers(init?.headers).get('X-Requested-With')).toBe('XMLHttpRequest');
	});

	it('leaves cross-origin requests alone', () => {
		const init = { headers: { A: '1' } };
		const [input, out] = withIapAjaxHeader('https://example.com/x', init, ORIGIN);
		expect(input).toBe('https://example.com/x');
		expect(out).toBe(init);
	});

	it('passes a Request object through untouched', () => {
		const request = new Request(`${ORIGIN}/api/x`, { method: 'POST', body: 'b' });
		const [input, init] = withIapAjaxHeader(request, undefined, ORIGIN);
		expect(input).toBe(request);
		expect(init).toBeUndefined();
	});

	it('does not overwrite a caller-set value', () => {
		const [, init] = withIapAjaxHeader(
			'/api/x',
			{ headers: { 'X-Requested-With': 'custom' } },
			ORIGIN
		);
		expect(new Headers(init?.headers).get('X-Requested-With')).toBe('custom');
	});
});

describe('isIapExpiry', () => {
	it('recognises a 401 that IAP generated', () => {
		const response = new Response('Invalid GCIP ID token', {
			status: 401,
			headers: { [IAP_GENERATED_HEADER]: 'true' }
		});
		expect(isIapExpiry(response)).toBe(true);
	});

	it("does not treat the app's own 401 as IAP expiry", () => {
		expect(isIapExpiry(new Response('{}', { status: 401 }))).toBe(false);
	});

	it('ignores other statuses', () => {
		const response = new Response('', { status: 403, headers: { [IAP_GENERATED_HEADER]: 'true' } });
		expect(isIapExpiry(response)).toBe(false);
	});
});

describe('interruptPendingAnswer', () => {
	it('marks a streaming assistant answer done with the note', () => {
		const message: { role: string; done: boolean; error?: unknown } = {
			role: 'assistant',
			done: false
		};
		expect(interruptPendingAnswer(message, 'terputus')).toBe(true);
		expect(message).toEqual({ role: 'assistant', done: true, error: { content: 'terputus' } });
	});

	it('leaves finished answers, user messages and nothing alone', () => {
		const done = { role: 'assistant', done: true };
		const user = { role: 'user' };
		expect(interruptPendingAnswer(done, 'x')).toBe(false);
		expect(interruptPendingAnswer(user, 'x')).toBe(false);
		expect(interruptPendingAnswer(null, 'x')).toBe(false);
		expect(done).toEqual({ role: 'assistant', done: true });
		expect(user).toEqual({ role: 'user' });
	});
});
