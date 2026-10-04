/**
 * jup-gateway's HTTP entry: `POST /api/messages` (Teams), `GET /healthz`.
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
import { HttpEntOs, IdentityPlatformTokens } from './entos';
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

function productionDeps(): TeamsDeps {
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
		entos: new HttpEntOs({
			baseUrl: required('ENTOS_URL'),
			tokens: new IdentityPlatformTokens({
				serviceAccount: required('GATEWAY_SERVICE_ACCOUNT'),
				apiKey: required('IDENTITY_PLATFORM_API_KEY')
			})
		}),
		tenantId,
		hash: hmacHasher(required('GATEWAY_HMAC_KEY')),
		log
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
		entos: process.env.ENTOS_URL ? productionDeps().entos : echo,
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
			if (request.method === 'GET' && pathname === '/healthz') return new Response('ok');
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
	log('gateway_started', { port: server.port, dev });
}
