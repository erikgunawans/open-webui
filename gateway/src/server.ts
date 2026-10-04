/**
 * jup-gateway's HTTP entry: `POST /api/messages` (Teams), `GET|POST /api/whatsapp` (WhatsApp),
 * `GET /health`.
 *
 * Production reads its settings from the environment (Secret Manager in #90). `GATEWAY_DEV=1`
 * (`bun run dev`) swaps the Teams side for local stand-ins: no token check, replies printed to the
 * console, and senders mapped from `DEV_MAPPING` (`objectId=email,…`). The ent-os side stays
 * real when `ENTOS_URL` is set, otherwise a local echo answers. WhatsApp in dev mode skips the
 * signature, prints its replies and answers `hubungkan <code>` with "linked". Dev mode refuses to
 * start on Cloud Run (`K_SERVICE` set).
 */

import {
	BotConnectorSender,
	BotFrameworkVerifier,
	EntraAppTokens,
	GraphResolver
} from './botframework';
import { HttpEntOs, IdentityPlatformTokens, selfCheck } from './entos';
import { hmacHasher } from './hash';
import { CloudApiSender } from './meta';
import { handle, type TeamsDeps } from './teams';
import type { EntOsClient, EntOsLinker, Log } from './types';
import * as whatsapp from './whatsapp';

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

/**
 * WhatsApp answers only once the Meta app is wired (E9.4, #105): until all four settings are set,
 * every `/api/whatsapp` request is refused with 401 and nothing else runs.
 */
const WHATSAPP_SETTINGS = [
	'WHATSAPP_APP_SECRET',
	'WHATSAPP_VERIFY_TOKEN',
	'WHATSAPP_ACCESS_TOKEN',
	'WHATSAPP_PHONE_NUMBER_ID'
] as const;

export function whatsappConfigured(env: Record<string, string | undefined> = process.env): boolean {
	return WHATSAPP_SETTINGS.every((name) => !!env[name]?.trim());
}

export interface Deps {
	teams: TeamsDeps;
	/** Null until configured: `/api/whatsapp` is closed. */
	whatsapp: whatsapp.WhatsAppDeps | null;
}

function productionDeps(): Deps {
	const shared = {
		entos: entosFromEnv().client,
		hash: hmacHasher(required('GATEWAY_HMAC_KEY')),
		log
	};
	return { teams: productionTeams(shared), whatsapp: productionWhatsApp(shared) };
}

function productionWhatsApp(shared: Pick<whatsapp.WhatsAppDeps, 'entos' | 'hash' | 'log'>) {
	if (!whatsappConfigured()) return null;
	const phoneNumberId = required('WHATSAPP_PHONE_NUMBER_ID');
	return {
		signed: whatsapp.metaSignature(required('WHATSAPP_APP_SECRET')),
		verifyToken: required('WHATSAPP_VERIFY_TOKEN'),
		phoneNumberId,
		sender: new CloudApiSender({ phoneNumberId, accessToken: required('WHATSAPP_ACCESS_TOKEN') }),
		seen: new whatsapp.RecentIds(),
		...shared
	};
}

function productionTeams(shared: Pick<TeamsDeps, 'entos' | 'hash' | 'log'>): TeamsDeps {
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

function devDeps(): Deps {
	if (process.env.K_SERVICE) throw new Error('GATEWAY_DEV must not run on Cloud Run');
	const mapping = new Map(
		(process.env.DEV_MAPPING ?? '')
			.split(',')
			.map((pair) => pair.split('=').map((part) => part.trim()))
			.filter((pair): pair is [string, string] => pair.length === 2 && !!pair[0] && !!pair[1])
	);
	const echo: EntOsClient & EntOsLinker = {
		async turn(request) {
			return {
				kind: 'reply',
				reply: `(dev echo) ${request.text}`,
				chatUrl: '',
				outcome: 'answered'
			};
		},
		async link() {
			return 'linked';
		}
	};
	const entos = process.env.ENTOS_URL ? entosFromEnv().client : echo;
	const hash = hmacHasher(process.env.GATEWAY_HMAC_KEY ?? 'dev-only-key-not-a-secret-0123456789');
	const teams: TeamsDeps = {
		verifier: { verify: async () => ({ serviceUrl: 'https://dev.local/' }) },
		sender: {
			typing: async () => log('dev_typing', {}),
			text: async (_target, text) => log('dev_reply', { text })
		},
		resolver: { resolve: async ({ objectId }) => mapping.get(objectId) ?? null },
		entos,
		tenantId: process.env.JUP_TENANT_ID ?? 'dev-tenant',
		hash,
		log
	};
	const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID ?? 'dev-number';
	return {
		teams,
		whatsapp: {
			signed: () => true,
			verifyToken: process.env.WHATSAPP_VERIFY_TOKEN ?? 'dev-verify-token',
			phoneNumberId,
			sender: {
				read: async () => log('dev_read', {}),
				text: async (_to, text) => log('dev_reply', { text })
			},
			entos,
			hash,
			seen: new whatsapp.RecentIds(),
			log
		}
	};
}

const closed = () => new Response(null, { status: 401 });

export function createServer(deps: Deps, port: number) {
	return Bun.serve({
		port,
		async fetch(request) {
			const { pathname } = new URL(request.url);
			// Not /healthz: Cloud Run reserves paths ending in "z" and answers them itself with a 404.
			if (request.method === 'GET' && pathname === '/health') return new Response('ok');
			if (request.method === 'POST' && pathname === '/api/messages') {
				const { response, work } = await handle(request, deps.teams);
				void work; // answered at once; the turn carries on (Cloud Run CPU is always allocated)
				return response;
			}
			if (pathname === '/api/whatsapp') {
				if (!deps.whatsapp) return closed();
				if (request.method === 'GET') return whatsapp.verify(request, deps.whatsapp);
				if (request.method === 'POST') {
					const { response, work } = await whatsapp.handle(request, deps.whatsapp);
					void work;
					return response;
				}
			}
			return new Response(null, { status: 404 });
		}
	});
}

if (import.meta.main) {
	const dev = process.env.GATEWAY_DEV === '1';
	const server = createServer(dev ? devDeps() : productionDeps(), Number(process.env.PORT ?? 8080));
	log('gateway_started', {
		port: server.port,
		dev,
		teams: !dev && teamsConfigured(),
		whatsapp: dev || whatsappConfigured()
	});
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
