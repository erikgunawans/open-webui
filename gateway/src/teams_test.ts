/**
 * The Teams inbound handler at its seam (#89): a Request in, a Response and the posted replies out,
 * with fake verifier, sender, resolver and ent-os client. Named `*_test.ts` so the repo's vitest
 * (frontend CI) does not collect it; `bun test` does.
 */

import { describe, expect, test } from 'bun:test';
import { hmacHasher, teamsConversation, teamsIdentity } from './hash';
import { handle, type TeamsDeps } from './teams';
import { NOT_CONNECTED, UNAVAILABLE } from './texts';
import type { EntOsClient, ReplyTarget, TurnOutcome, TurnRequest } from './types';

const TENANT = 'fc521bfb-40c2-4b87-95a7-65e0e888fdf8';
const SERVICE_URL = 'https://smba.trafficmanager.net/apac/';
const OBJECT_ID = '32e72910-ff35-4eeb-9a6c-7fd9a5542b8e';
const CONVERSATION = 'a:1personal-conversation-id';
const EMAIL = 'erik@jakarta-utilitas.com';
const KEY = 'test-key-0123456789abcdef0123456789abcdef';

function activity(overrides: Record<string, unknown> = {}) {
	return {
		type: 'message',
		id: 'act-1',
		serviceUrl: SERVICE_URL,
		text: 'status proyek SPBG?',
		from: { id: '29:raw-teams-user-id', aadObjectId: OBJECT_ID },
		conversation: { id: CONVERSATION, conversationType: 'personal', tenantId: TENANT },
		channelData: { tenant: { id: TENANT } },
		...overrides
	};
}

function request(body: unknown, authorization = 'Bearer valid') {
	return new Request('http://gateway/api/messages', {
		method: 'POST',
		headers: { authorization, 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
}

class World {
	sent: { kind: 'typing' | 'text'; target: ReplyTarget; text?: string }[] = [];
	calls: { request: TurnRequest; onBehalfOf: string }[] = [];
	logs: { event: string; fields: Record<string, unknown> }[] = [];
	mapping = new Map([[OBJECT_ID, EMAIL]]);
	outcome: () => Promise<TurnOutcome> = async () => ({
		kind: 'reply',
		reply: 'Proyek SPBG on track.',
		chatUrl: 'https://non-jupe.jup.co.id/c/1',
		outcome: 'answered'
	});

	deps(overrides: Partial<TeamsDeps> = {}): TeamsDeps {
		const entos: EntOsClient = {
			turn: async (request, onBehalfOf) => {
				this.calls.push({ request, onBehalfOf });
				return this.outcome();
			}
		};
		return {
			verifier: {
				verify: async (authorization) => {
					if (authorization !== 'Bearer valid') throw new Error('signature invalid');
					return { serviceUrl: SERVICE_URL };
				}
			},
			sender: {
				typing: async (target) => void this.sent.push({ kind: 'typing', target }),
				text: async (target, text) => void this.sent.push({ kind: 'text', target, text })
			},
			resolver: { resolve: async ({ objectId }) => this.mapping.get(objectId) ?? null },
			entos,
			tenantId: TENANT,
			hash: hmacHasher(KEY),
			log: (event, fields) => void this.logs.push({ event, fields }),
			...overrides
		};
	}

	texts() {
		return this.sent.filter((s) => s.kind === 'text').map((s) => s.text);
	}
}

async function run(world: World, req: Request, overrides: Partial<TeamsDeps> = {}) {
	const handled = await handle(req, world.deps(overrides));
	await handled.work;
	return handled.response.status;
}

describe('who may call', () => {
	test('a forged or missing token is refused before anything else happens', async () => {
		for (const auth of ['Bearer forged', '']) {
			const world = new World();
			expect(await run(world, request(activity(), auth))).toBe(401);
			expect(world.sent).toEqual([]);
			expect(world.calls).toEqual([]);
		}
	});

	test('a message from another tenant is refused', async () => {
		const world = new World();
		const foreign = activity({
			channelData: { tenant: { id: 'other-tenant' } },
			conversation: { id: CONVERSATION, conversationType: 'personal', tenantId: 'other-tenant' }
		});
		expect(await run(world, request(foreign))).toBe(403);
		expect(world.calls).toEqual([]);
		expect(world.sent).toEqual([]);
	});

	test('a body naming another service url than the token is refused', async () => {
		const world = new World();
		expect(await run(world, request(activity({ serviceUrl: 'https://attacker.example/' })))).toBe(
			403
		);
		expect(world.sent).toEqual([]);
	});
});

describe('the answer', () => {
	test('the 200 comes back before ent-os answers', async () => {
		const world = new World();
		let release!: () => void;
		const held = new Promise<void>((resolve) => (release = resolve));
		world.outcome = async () => {
			await held;
			return { kind: 'reply', reply: 'nanti', chatUrl: '', outcome: 'answered' };
		};
		const handled = await handle(request(activity()), world.deps());
		expect(handled.response.status).toBe(200);
		await Bun.sleep(5);
		expect(world.texts()).toEqual([]);
		release();
		await handled.work;
		expect(world.texts()).toEqual(['nanti']);
	});

	test('typing is sent first, then the reply, to the conversation the token allows', async () => {
		const world = new World();
		expect(await run(world, request(activity()))).toBe(200);
		expect(world.sent.map((s) => s.kind)).toEqual(['typing', 'text']);
		expect(world.sent[1]).toEqual({
			kind: 'text',
			target: { serviceUrl: SERVICE_URL, conversationId: CONVERSATION, replyToId: 'act-1' },
			text: 'Proyek SPBG on track.'
		});
	});

	test('ent-os gets keyed hashes, never the raw Teams ids, and acts for the mapped email', async () => {
		const world = new World();
		await run(world, request(activity()));
		const [{ request: sent, onBehalfOf }] = world.calls;
		const hash = hmacHasher(KEY);
		expect(onBehalfOf).toBe(EMAIL);
		expect(sent).toEqual({
			channel: 'teams',
			identity_hash: hash(teamsIdentity(TENANT, OBJECT_ID)),
			conversation_key: hash(teamsConversation(CONVERSATION)),
			text: 'status proyek SPBG?',
			has_attachment: false
		});
		expect(sent.identity_hash).toMatch(/^[0-9a-f]{64}$/);
		const wire = JSON.stringify(world.calls) + JSON.stringify(world.logs);
		for (const raw of [OBJECT_ID, CONVERSATION, '29:raw-teams-user-id', TENANT]) {
			expect(wire.includes(raw)).toBe(false);
		}
	});

	test('the 120 s reply from ent-os is passed on as it is', async () => {
		const world = new World();
		const processing = 'Jawaban masih diproses — lihat di https://non-jupe.jup.co.id/c/1';
		world.outcome = async () => ({
			kind: 'reply',
			reply: processing,
			chatUrl: '',
			outcome: 'processing'
		});
		await run(world, request(activity()));
		expect(world.texts()).toEqual([processing]);
	});

	test('an attachment is flagged to ent-os; the html copy of formatted text is not one', async () => {
		const world = new World();
		await run(
			world,
			request(activity({ attachments: [{ contentType: 'image/png', contentUrl: 'https://x' }] }))
		);
		await run(
			world,
			request(activity({ attachments: [{ contentType: 'text/html', content: '<p>x</p>' }] }))
		);
		await run(
			world,
			request(activity({ text: '', attachments: [{ contentType: 'application/pdf' }] }))
		);
		expect(world.calls.map((c) => [c.request.has_attachment, c.request.text])).toEqual([
			[true, 'status proyek SPBG?'],
			[false, 'status proyek SPBG?'],
			[true, '']
		]);
	});
});

describe('refusals and failures', () => {
	test('an unmapped sender gets the neutral reply and is never forwarded', async () => {
		const world = new World();
		world.mapping.clear();
		expect(await run(world, request(activity()))).toBe(200);
		expect(world.calls).toEqual([]);
		expect(world.texts()).toEqual([NOT_CONNECTED]);
		expect(world.logs.find((l) => l.event === 'turn_refused')?.fields.reason).toBe('unmapped');
	});

	test('an ent-os refusal gets the same neutral reply', async () => {
		const world = new World();
		world.outcome = async () => ({ kind: 'refused' });
		await run(world, request(activity()));
		expect(world.texts()).toEqual([NOT_CONNECTED]);
	});

	test('ent-os down gets the outage reply, logged, and is never retried', async () => {
		const world = new World();
		world.outcome = async () => {
			throw new Error('ent-os 502');
		};
		await run(world, request(activity()));
		expect(world.calls.length).toBe(1);
		expect(world.texts()).toEqual([UNAVAILABLE]);
		expect(world.logs.some((l) => l.event === 'entos_failed')).toBe(true);
	});

	test('a failing typing indicator does not stop the answer', async () => {
		const world = new World();
		const deps = world.deps();
		deps.sender.typing = async () => {
			throw new Error('429');
		};
		await (
			await handle(request(activity()), deps)
		).work;
		expect(world.texts()).toEqual(['Proyek SPBG on track.']);
	});
});

describe('what is ignored', () => {
	test('group chats and channels are ignored with a 200', async () => {
		for (const conversation of [
			{ id: 'g', conversationType: 'groupChat', isGroup: true, tenantId: TENANT },
			{ id: 'c', conversationType: 'channel', isGroup: true, tenantId: TENANT }
		]) {
			const world = new World();
			expect(await run(world, request(activity({ conversation })))).toBe(200);
			expect(world.sent).toEqual([]);
			expect(world.calls).toEqual([]);
		}
	});

	test('non-message activities and empty messages are acknowledged and dropped', async () => {
		for (const body of [activity({ type: 'conversationUpdate' }), activity({ text: '   ' })]) {
			const world = new World();
			expect(await run(world, request(body))).toBe(200);
			expect(world.sent).toEqual([]);
			expect(world.calls).toEqual([]);
		}
	});
});

test('the hash key must be long enough', () => {
	expect(() => hmacHasher('short')).toThrow();
});
