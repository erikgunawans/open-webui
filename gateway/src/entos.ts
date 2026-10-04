/**
 * The ent-os client: `POST /api/jup/channel/turn` through IAP, on behalf of a mapped user.
 *
 * IAP runs in external-identities mode, so IAM grants do nothing for a service account (#86).
 * The gateway signs in to Identity Platform with a custom token: it signs a JWT as itself
 * (`jup-gateway`, which holds token-creator on itself) through the IAM Credentials API, exchanges
 * it at `accounts:signInWithCustomToken`, and sends the ID token as `Authorization: Bearer`. The
 * ID token lasts an hour; it is refreshed five minutes early.
 *
 * Failures throw, and the handler sends the outage reply without retrying. Only a 403 is read as a
 * refusal: ent-os answers 403 for every reason a user may not use a Channel.
 */

import type { EntOsClient, TurnOutcome, TurnRequest } from './types';

const AUDIENCE =
	'https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit';
const METADATA_TOKEN =
	'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token';
export const ON_BEHALF_OF = 'x-jup-on-behalf-of';
/** ent-os answers within its own 120 s limit, after any earlier turn of the conversation. */
export const TURN_TIMEOUT_MS = 280_000;
const REFRESH_EARLY_MS = 5 * 60_000;

type Fetch = typeof fetch;

/** An ID token for the gateway, from a source that can sign as its service account. */
export interface TokenSource {
	token(): Promise<string>;
}

export class IdentityPlatformTokens implements TokenSource {
	private cached: { token: string; expires: number } | null = null;

	constructor(
		private readonly opts: {
			serviceAccount: string;
			apiKey: string;
			fetch?: Fetch;
			now?: () => number;
		}
	) {}

	async token(): Promise<string> {
		const now = (this.opts.now ?? Date.now)();
		if (this.cached && now < this.cached.expires - REFRESH_EARLY_MS) return this.cached.token;
		const http = this.opts.fetch ?? fetch;

		const meta = await http(METADATA_TOKEN, { headers: { 'Metadata-Flavor': 'Google' } });
		if (!meta.ok) throw new Error(`metadata token ${meta.status}`);
		const { access_token: access } = (await meta.json()) as { access_token: string };

		const iat = Math.floor(now / 1000);
		const claims = {
			iss: this.opts.serviceAccount,
			sub: this.opts.serviceAccount,
			aud: AUDIENCE,
			iat,
			exp: iat + 3600,
			uid: this.opts.serviceAccount.split('@')[0]
		};
		const signed = await http(
			`https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${this.opts.serviceAccount}:signJwt`,
			{
				method: 'POST',
				headers: { authorization: `Bearer ${access}`, 'content-type': 'application/json' },
				body: JSON.stringify({ payload: JSON.stringify(claims) })
			}
		);
		if (!signed.ok) throw new Error(`signJwt ${signed.status}`);
		const { signedJwt } = (await signed.json()) as { signedJwt: string };

		const exchanged = await http(
			`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${this.opts.apiKey}`,
			{
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ token: signedJwt, returnSecureToken: true })
			}
		);
		if (!exchanged.ok) throw new Error(`signInWithCustomToken ${exchanged.status}`);
		const { idToken, expiresIn } = (await exchanged.json()) as {
			idToken: string;
			expiresIn: string;
		};
		this.cached = { token: idToken, expires: now + Number(expiresIn || 3600) * 1000 };
		return idToken;
	}
}

export class HttpEntOs implements EntOsClient {
	constructor(
		private readonly opts: {
			baseUrl: string;
			tokens: TokenSource;
			fetch?: Fetch;
			timeoutMs?: number;
		}
	) {}

	async turn(request: TurnRequest, onBehalfOf: string): Promise<TurnOutcome> {
		const http = this.opts.fetch ?? fetch;
		const response = await http(`${this.opts.baseUrl.replace(/\/$/, '')}/api/jup/channel/turn`, {
			method: 'POST',
			headers: {
				authorization: `Bearer ${await this.opts.tokens.token()}`,
				[ON_BEHALF_OF]: onBehalfOf,
				'content-type': 'application/json'
			},
			body: JSON.stringify(request),
			signal: AbortSignal.timeout(this.opts.timeoutMs ?? TURN_TIMEOUT_MS)
		});
		if (response.status === 403) return { kind: 'refused' };
		if (!response.ok) throw new Error(`ent-os ${response.status}`);
		const body = (await response.json()) as {
			reply?: unknown;
			chat_url?: unknown;
			outcome?: unknown;
		};
		if (typeof body.reply !== 'string' || !body.reply) throw new Error('ent-os sent no reply');
		return {
			kind: 'reply',
			reply: body.reply,
			chatUrl: String(body.chat_url ?? ''),
			outcome: String(body.outcome ?? '')
		};
	}
}

/** What `selfCheck` saw: the HTTP status of each probe. */
export interface SelfCheck {
	channel: number;
	other: number;
	ok: boolean;
}

/**
 * Proves the running gateway's identity through IAP without running a turn (#90): the Channel
 * endpoint with an empty body must be admitted and then refused as malformed (422), and any other
 * path must be refused (403) even with the on-behalf-of header.
 */
export async function selfCheck(opts: {
	baseUrl: string;
	tokens: TokenSource;
	onBehalfOf: string;
	fetch?: Fetch;
}): Promise<SelfCheck> {
	const http = opts.fetch ?? fetch;
	const base = opts.baseUrl.replace(/\/$/, '');
	const headers = {
		authorization: `Bearer ${await opts.tokens.token()}`,
		[ON_BEHALF_OF]: opts.onBehalfOf,
		'content-type': 'application/json'
	};
	const channel = await http(`${base}/api/jup/channel/turn`, {
		method: 'POST',
		headers,
		body: '{}',
		redirect: 'manual'
	});
	const other = await http(`${base}/api/v1/auths/`, { headers, redirect: 'manual' });
	return {
		channel: channel.status,
		other: other.status,
		ok: channel.status === 422 && other.status === 403
	};
}
