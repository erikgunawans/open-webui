/**
 * The real Teams adapters: Bot Framework token check, Bot Connector replies, Graph mapping.
 * None of them runs in the tests (no network there); the handler tests use fakes at the same
 * interfaces. They go live in E8, once JUP IT registers the bot (#82).
 */

import { createRemoteJWKSet, jwtVerify } from 'jose';
import type { ReplyTarget, Resolver, Sender, VerifiedCaller, Verifier } from './types';

/** Bot Framework's signing keys; tokens from Teams to a bot are issued by `api.botframework.com`. */
const BOT_FRAMEWORK_KEYS = 'https://login.botframework.com/v1/.well-known/keys';
const BOT_FRAMEWORK_ISSUER = 'https://api.botframework.com';

export class BotFrameworkVerifier implements Verifier {
	private readonly keys = createRemoteJWKSet(new URL(BOT_FRAMEWORK_KEYS));

	constructor(private readonly appId: string) {}

	async verify(authorization: string | null): Promise<VerifiedCaller> {
		const token = authorization?.match(/^Bearer (.+)$/)?.[1];
		if (!token) throw new Error('no bearer token');
		const { payload } = await jwtVerify(token, this.keys, {
			issuer: BOT_FRAMEWORK_ISSUER,
			audience: this.appId,
			clockTolerance: 300
		});
		const serviceUrl = payload.serviceurl ?? payload.serviceUrl;
		if (typeof serviceUrl !== 'string' || !serviceUrl.startsWith('https://')) {
			throw new Error('token names no service url');
		}
		return { serviceUrl };
	}
}

type Fetch = typeof fetch;

/** App-only tokens for the single-tenant bot registration, cached until five minutes before expiry. */
export class EntraAppTokens {
	private cache = new Map<string, { token: string; expires: number }>();

	constructor(
		private readonly opts: {
			tenantId: string;
			clientId: string;
			clientSecret: string;
			fetch?: Fetch;
		}
	) {}

	async token(scope: string): Promise<string> {
		const hit = this.cache.get(scope);
		if (hit && Date.now() < hit.expires - 300_000) return hit.token;
		const response = await (this.opts.fetch ?? fetch)(
			`https://login.microsoftonline.com/${this.opts.tenantId}/oauth2/v2.0/token`,
			{
				method: 'POST',
				body: new URLSearchParams({
					grant_type: 'client_credentials',
					client_id: this.opts.clientId,
					client_secret: this.opts.clientSecret,
					scope
				})
			}
		);
		if (!response.ok) throw new Error(`entra token ${response.status}`);
		const { access_token, expires_in } = (await response.json()) as {
			access_token: string;
			expires_in: number;
		};
		this.cache.set(scope, { token: access_token, expires: Date.now() + expires_in * 1000 });
		return access_token;
	}
}

export class BotConnectorSender implements Sender {
	constructor(
		private readonly tokens: EntraAppTokens,
		private readonly http: Fetch = fetch
	) {}

	private async post(target: ReplyTarget, activity: Record<string, unknown>): Promise<void> {
		const base = target.serviceUrl.replace(/\/$/, '');
		const id = encodeURIComponent(target.conversationId);
		const url = target.replyToId
			? `${base}/v3/conversations/${id}/activities/${encodeURIComponent(target.replyToId)}`
			: `${base}/v3/conversations/${id}/activities`;
		const response = await this.http(url, {
			method: 'POST',
			headers: {
				authorization: `Bearer ${await this.tokens.token('https://api.botframework.com/.default')}`,
				'content-type': 'application/json'
			},
			body: JSON.stringify({ ...activity, replyToId: target.replyToId })
		});
		if (!response.ok) throw new Error(`bot connector ${response.status}`);
	}

	typing(target: ReplyTarget): Promise<void> {
		return this.post(target, { type: 'typing' });
	}

	text(target: ReplyTarget, text: string): Promise<void> {
		return this.post(target, { type: 'message', text, textFormat: 'markdown' });
	}
}

/**
 * The Teams Mapping: Entra object id → Graph → email. Only JUP's tenant reaches here (the handler
 * checks it first). The email is the ent-os account; whether that account exists, is active and
 * holds the grant is ent-os's decision, and its refusal gets the same reply as "unmapped".
 */
export class GraphResolver implements Resolver {
	constructor(
		private readonly tokens: EntraAppTokens,
		private readonly http: Fetch = fetch
	) {}

	async resolve({ objectId }: { tenantId: string; objectId: string }): Promise<string | null> {
		const response = await this.http(
			`https://graph.microsoft.com/v1.0/users/${encodeURIComponent(objectId)}?$select=mail,userPrincipalName,accountEnabled`,
			{
				headers: {
					authorization: `Bearer ${await this.tokens.token('https://graph.microsoft.com/.default')}`
				}
			}
		);
		if (response.status === 404) return null;
		if (!response.ok) throw new Error(`graph ${response.status}`);
		const user = (await response.json()) as {
			mail?: string | null;
			userPrincipalName?: string | null;
			accountEnabled?: boolean;
		};
		if (user.accountEnabled === false) return null;
		const email = (user.mail || user.userPrincipalName || '').trim().toLowerCase();
		return email.includes('@') ? email : null;
	}
}
