/** The server with Teams not yet configured (#90, before E8): health answers, Teams refuses. */

import { expect, test } from 'bun:test';
import { createServer, teamsConfigured } from './server';
import { hmacHasher } from './hash';

test('Teams counts as configured only with all three settings', () => {
	expect(teamsConfigured({})).toBe(false);
	expect(teamsConfigured({ BOT_APP_ID: 'a', BOT_APP_SECRET: 's' })).toBe(false);
	expect(teamsConfigured({ BOT_APP_ID: 'a', BOT_APP_SECRET: 's', JUP_TENANT_ID: 't' })).toBe(true);
});

test('health answers, an unsigned Teams request is refused, anything else is 404', async () => {
	const calls: unknown[] = [];
	const server = createServer(
		{
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
		0
	);
	try {
		const base = `http://localhost:${server.port}`;
		expect(await (await fetch(`${base}/health`)).text()).toBe('ok');
		const teams = await fetch(`${base}/api/messages`, { method: 'POST', body: '{}' });
		expect(teams.status).toBe(401);
		expect((await fetch(`${base}/elsewhere`)).status).toBe(404);
		expect(calls).toEqual([]);
	} finally {
		server.stop(true);
	}
});
