/** The ent-os client with a fake `fetch`: the Identity Platform sign-in and the Channel call (#89). */

import { expect, test } from 'bun:test';
import { HttpEntOs, IdentityPlatformTokens, ON_BEHALF_OF } from './entos';
import type { TurnRequest } from './types';

const SA = 'jup-gateway@jup-ops.iam.gserviceaccount.com';
const TURN: TurnRequest = {
	channel: 'teams',
	identity_hash: 'a'.repeat(64),
	conversation_key: 'b'.repeat(64),
	text: 'halo',
	has_attachment: false
};

function signInFetch(calls: string[]): typeof fetch {
	return (async (input: string | URL | Request, init?: RequestInit) => {
		const url = String(input);
		calls.push(url);
		if (url.startsWith('http://metadata.google.internal')) {
			expect(new Headers(init?.headers).get('Metadata-Flavor')).toBe('Google');
			return Response.json({ access_token: 'metadata-access' });
		}
		if (url.includes(':signJwt')) {
			expect(url).toContain(`/serviceAccounts/${SA}:signJwt`);
			const claims = JSON.parse(JSON.parse(String(init?.body)).payload);
			expect(claims).toMatchObject({ iss: SA, sub: SA, uid: 'jup-gateway' });
			return Response.json({ signedJwt: 'signed.jwt' });
		}
		if (url.includes('signInWithCustomToken')) {
			expect(url).toContain('key=browser-key');
			expect(JSON.parse(String(init?.body))).toEqual({
				token: 'signed.jwt',
				returnSecureToken: true
			});
			return Response.json({ idToken: 'id-token', expiresIn: '3600' });
		}
		throw new Error(`unexpected ${url}`);
	}) as typeof fetch;
}

test('the gateway signs in as itself through Identity Platform and caches the token', async () => {
	const calls: string[] = [];
	let now = 1_000_000;
	const tokens = new IdentityPlatformTokens({
		serviceAccount: SA,
		apiKey: 'browser-key',
		fetch: signInFetch(calls),
		now: () => now
	});
	expect(await tokens.token()).toBe('id-token');
	expect(await tokens.token()).toBe('id-token');
	expect(calls.length).toBe(3);
	now += 56 * 60_000; // inside the last five minutes: refreshed
	await tokens.token();
	expect(calls.length).toBe(6);
});

function entos(response: Response, seen: { headers?: Headers; body?: unknown } = {}) {
	return new HttpEntOs({
		baseUrl: 'https://non-jupe.jup.co.id/',
		tokens: { token: async () => 'id-token' },
		fetch: (async (input: string | URL | Request, init?: RequestInit) => {
			expect(String(input)).toBe('https://non-jupe.jup.co.id/api/jup/channel/turn');
			seen.headers = new Headers(init?.headers);
			seen.body = JSON.parse(String(init?.body));
			return response;
		}) as typeof fetch
	});
}

test('a turn carries the bearer token and the on-behalf-of email, and returns the reply', async () => {
	const seen: { headers?: Headers; body?: unknown } = {};
	const outcome = await entos(
		Response.json({ reply: 'Jawaban.', chat_url: 'https://x/c/1', outcome: 'answered' }),
		seen
	).turn(TURN, 'erik@jakarta-utilitas.com');
	expect(outcome).toEqual({
		kind: 'reply',
		reply: 'Jawaban.',
		chatUrl: 'https://x/c/1',
		outcome: 'answered'
	});
	expect(seen.headers?.get('authorization')).toBe('Bearer id-token');
	expect(seen.headers?.get(ON_BEHALF_OF)).toBe('erik@jakarta-utilitas.com');
	expect(seen.body).toEqual(TURN);
});

test('a 403 is a refusal; any other failure throws', async () => {
	expect(await entos(new Response(null, { status: 403 })).turn(TURN, 'x@y')).toEqual({
		kind: 'refused'
	});
	for (const response of [
		new Response(null, { status: 502 }),
		new Response(null, { status: 401 }),
		Response.json({ outcome: 'answered' })
	]) {
		await expect(entos(response).turn(TURN, 'x@y')).rejects.toThrow();
	}
});
