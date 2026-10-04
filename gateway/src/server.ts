/**
 * jup-gateway's HTTP entry: `POST /api/messages` (Teams), `GET /health`.
 *
 * Production reads its settings from the environment (Secret Manager in #90). `GATEWAY_DEV=1`
 * (`bun run dev`) swaps the Teams side for local stand-ins: no token check, replies printed to the
 * console, and senders mapped from `DEV_MAPPING` (`objectId=email,…`). The ent-os side stays
 * real when `ENTOS_URL` is set, otherwise a local echo answers. Dev mode refuses to start on Cloud
 * Run (`K_SERVICE` set).
 */

import {
	BotConnectorSender,
	BotFrameworkVerifier,
	EntraAppTokens,
	GraphResolver
} from './botframework';
import { HttpEntOs, IdentityPlatformTokens, selfCheck } from './entos';
import { hmacHasher } from './hash';
import { handle, type TeamsDeps } from './teams';
import type { EntOsClient, Log } from './types';

const log: Log = (event, fields) =>
	console.log(JSON.stringify({ severity: 'INFO', event, ...fields, ts: new Date().toISOString() }));

function required(name: string): string {
	const value = process.env[name]?.trim();
	if (!value) throw new Error(`${name} is not set`);
	return value;
}

/** The ent-os client and its sign-in, from the environment. */
function entosFromEnv() {
	const baseUrl = required('ENTOS_URL');
	const tokens = new IdentityPlatformTokens({
		serviceAccount: required('GATEWAY_SERVICE_ACCOUNT'),
		apiKey: required('IDENTITY_PLATFORM_API_KEY')
	});
	return { baseUrl, tokens, client: new HttpEntOs({ baseUrl, tokens }) };
}

/**
 * Teams answers only once the bot is registered (E8, #82): until `BOT_APP_ID`, `BOT_APP_SECRET`
 * and `JUP_TENANT_ID` are all set, every Teams request is refused with 401 and nothing else runs.
 */
const closedTeams: Pick<TeamsDeps, 'verifier' | 'sender' | 'resolver'> = {
	verifier: {
		verify: async () => {
			throw new Error('teams is not configured');
		}
	},
	sender: {
		typing: async () => {
			throw new Error('teams is not configured');
		},
		text: async () => {
			throw new Error('teams is not configured');
		}
	},
	resolver: { resolve: async () => null }
};

export function teamsConfigured(env: Record<string, string | undefined> = process.env): boolean {
	return ['BOT_APP_ID', 'BOT_APP_SECRET', 'JUP_TENANT_ID'].every((name) => !!env[name]?.trim());
}

function productionDeps(): TeamsDeps {
	const shared = {
		entos: entosFromEnv().client,
		hash: hmacHasher(required('GATEWAY_HMAC_KEY')),
		log
	};
	if (!teamsConfigured()) return { ...closedTeams, tenantId: '', ...shared };
	const tenantId = required('JUP_TENANT_ID');
	const entra = new EntraAppTokens({
		tenantId,
		clientId: required('BOT_APP_ID'),
		clientSecret: required('BOT_APP_SECRET')
	});
	return {
		verifier: new BotFrameworkVerifier(required('BOT_APP_ID')),
		sender: new BotConnectorSender(entra),
		resolver: new GraphResolver(entra),
		tenantId,
		...shared
	};
}

function devDeps(): TeamsDeps {
	if (process.env.K_SERVICE) throw new Error('GATEWAY_DEV must not run on Cloud Run');
	const mapping = new Map(
		(process.env.DEV_MAPPING ?? '')
			.split(',')
			.map((pair) => pair.split('=').map((part) => part.trim()))
			.filter((pair): pair is [string, string] => pair.length === 2 && !!pair[0] && !!pair[1])
	);
	const echo: EntOsClient = {
		async turn(request) {
			return {
				kind: 'reply',
				reply: `(dev echo) ${request.text}`,
				chatUrl: '',
				outcome: 'answered'
			};
		}
	};
	return {
		verifier: { verify: async () => ({ serviceUrl: 'https://dev.local/' }) },
		sender: {
			typing: async () => log('dev_typing', {}),
			text: async (_target, text) => log('dev_reply', { text })
		},
		resolver: { resolve: async ({ objectId }) => mapping.get(objectId) ?? null },
		entos: process.env.ENTOS_URL ? entosFromEnv().client : echo,
		tenantId: process.env.JUP_TENANT_ID ?? 'dev-tenant',
		hash: hmacHasher(process.env.GATEWAY_HMAC_KEY ?? 'dev-only-key-not-a-secret-0123456789'),
		log
	};
}

export function createServer(deps: TeamsDeps, port: number) {
	return Bun.serve({
		port,
		async fetch(request) {
			const { pathname } = new URL(request.url);
			// Not /healthz: Cloud Run reserves paths ending in "z" and answers them itself with a 404.
			if (request.method === 'GET' && pathname === '/health') return new Response('ok');
			if (request.method === 'POST' && pathname === '/api/messages') {
				const { response, work } = await handle(request, deps);
				void work; // answered at once; the turn carries on (Cloud Run CPU is always allocated)
				return response;
			}
			return new Response(null, { status: 404 });
		}
	});
}

if (import.meta.main) {
	const dev = process.env.GATEWAY_DEV === '1';
	const server = createServer(dev ? devDeps() : productionDeps(), Number(process.env.PORT ?? 8080));
	log('gateway_started', { port: server.port, dev, teams: !dev && teamsConfigured() });
	// Set by `deploy.sh` only when SELFCHECK=1: proves this revision's identity through IAP (#90).
	const onBehalfOf = process.env.SELFCHECK_ON_BEHALF_OF?.trim();
	if (!dev && onBehalfOf) {
		const { baseUrl, tokens } = entosFromEnv();
		selfCheck({ baseUrl, tokens, onBehalfOf }).then(
			(result) => log('selfcheck', { ...result }),
			(error) => log('selfcheck', { ok: false, detail: String(error) })
		);
	}
}
