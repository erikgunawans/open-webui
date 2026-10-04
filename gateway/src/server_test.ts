/** The server with Teams not yet configured (#90, before E8): health answers, Teams refuses. */

import { expect, test } from 'bun:test';
import { createServer, teamsConfigured, whatsappConfigured } from './server';
import { hmacHasher } from './hash';

test('Teams counts as configured only with all three settings', () => {
	expect(teamsConfigured({})).toBe(false);
	expect(teamsConfigured({ BOT_APP_ID: 'a', BOT_APP_SECRET: 's' })).toBe(false);
	expect(teamsConfigured({ BOT_APP_ID: 'a', BOT_APP_SECRET: 's', JUP_TENANT_ID: 't' })).toBe(true);
});

test('WhatsApp counts as configured only with all four settings', () => {
	const all = {
		WHATSAPP_APP_SECRET: 's',
		WHATSAPP_VERIFY_TOKEN: 'v',
		WHATSAPP_ACCESS_TOKEN: 't',
		WHATSAPP_PHONE_NUMBER_ID: '1'
	};
	expect(whatsappConfigured(all)).toBe(true);
	for (const name of Object.keys(all)) {
		expect(whatsappConfigured({ ...all, [name]: ' ' })).toBe(false);
	}
});

test('health answers, Teams and WhatsApp refuse while unconfigured, anything else is 404', async () => {
	const calls: unknown[] = [];
	const server = createServer(
		{
			teams: {
				verifier: {
					verify: async () => {
						throw new Error('teams is not configured');
					}
				},
				sender: { typing: async () => {}, text: async () => {} },
				resolver: { resolve: async () => 'x@y' },
				entos: { turn: async (r) => (calls.push(r), { kind: 'refused' }) },
				tenantId: '',
				hash: hmacHasher('k'.repeat(32)),
				log: () => {}
			},
			whatsapp: null
		},
		0
	);
	try {
		const base = `http://localhost:${server.port}`;
		expect(await (await fetch(`${base}/health`)).text()).toBe('ok');
		const teams = await fetch(`${base}/api/messages`, { method: 'POST', body: '{}' });
		expect(teams.status).toBe(401);
		for (const method of ['GET', 'POST']) {
			const closed = await fetch(`${base}/api/whatsapp?hub.mode=subscribe`, { method });
			expect(closed.status).toBe(401);
		}
		expect((await fetch(`${base}/elsewhere`)).status).toBe(404);
		expect(calls).toEqual([]);
	} finally {
		server.stop(true);
	}
});
