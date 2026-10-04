/**
 * The WhatsApp inbound handler at its seam (#104): a signed webhook in, a Response and the sent
 * replies out, with fake Cloud API sender and ent-os client. The signature is real HMAC.
 */

import { describe, expect, test } from 'bun:test';
import { createHmac } from 'node:crypto';
import { hmacHasher, whatsappConversation, whatsappIdentity } from './hash';
import { CODE_INVALID, LINKED, NOT_CONNECTED, UNAVAILABLE } from './texts';
import type { LinkOutcome, TurnOutcome, TurnRequest } from './types';
import { handle, metaSignature, RecentIds, verify, type WhatsAppDeps } from './whatsapp';

const APP_SECRET = 'meta-app-secret-for-tests';
const PHONE_NUMBER_ID = '1173558312506997';
const WA_ID = '6281234567890';
const KEY = 'test-key-0123456789abcdef0123456789abcdef';
const hash = hmacHasher(KEY);
const IDENTITY = hash(whatsappIdentity(WA_ID));

function message(overrides: Record<string, unknown> = {}) {
	return {
		from: WA_ID,
		id: 'wamid.A',
		timestamp: '1759600000',
		type: 'text',
		text: { body: 'status proyek SPBG?' },
		...overrides
	};
}

function webhook(messages: unknown[], value: Record<string, unknown> = {}) {
	return {
		object: 'whatsapp_business_account',
		entry: [
			{
				id: '2041351150599623',
				changes: [
					{
						field: 'messages',
						value: {
							messaging_product: 'whatsapp',
							metadata: { display_phone_number: '15556537220', phone_number_id: PHONE_NUMBER_ID },
							contacts: [{ wa_id: WA_ID, profile: { name: 'Erik' } }],
							messages,
							...value
						}
					}
				]
			}
		]
	};
}

const sign = (raw: string, secret = APP_SECRET) =>
	'sha256=' + createHmac('sha256', secret).update(raw, 'utf8').digest('hex');

function request(body: unknown, signature?: string | null) {
	const raw = typeof body === 'string' ? body : JSON.stringify(body);
	const headers: Record<string, string> = { 'content-type': 'application/json' };
	const sig = signature === undefined ? sign(raw) : signature;
	if (sig !== null) headers['x-hub-signature-256'] = sig;
	return new Request('http://gateway/api/whatsapp', { method: 'POST', headers, body: raw });
}

class World {
	sent: { kind: 'read' | 'text'; id?: string; to?: string; text?: string; replyTo?: string }[] = [];
	turns: { request: TurnRequest; onBehalfOf: string }[] = [];
	links: { hint: string; onBehalfOf: string }[] = [];
	logs: { event: string; fields: Record<string, unknown> }[] = [];
	seen = new RecentIds();
	outcome: () => Promise<TurnOutcome> = async () => ({
		kind: 'reply',
		reply: 'Proyek SPBG on track.',
		chatUrl: 'https://non-jupe.jup.co.id/c/1',
		outcome: 'answered'
	});
	linkOutcome: () => Promise<LinkOutcome> = async () => 'linked';

	deps(overrides: Partial<WhatsAppDeps> = {}): WhatsAppDeps {
		return {
			signed: metaSignature(APP_SECRET),
			verifyToken: 'verify-me',
			phoneNumberId: PHONE_NUMBER_ID,
			sender: {
				read: async (id) => void this.sent.push({ kind: 'read', id }),
				text: async (to, text, replyTo) => void this.sent.push({ kind: 'text', to, text, replyTo })
			},
			entos: {
				turn: async (request, onBehalfOf) => {
					this.turns.push({ request, onBehalfOf });
					return this.outcome();
				},
				link: async (hint, onBehalfOf) => {
					this.links.push({ hint, onBehalfOf });
					return this.linkOutcome();
				}
			},
			hash,
			seen: this.seen,
			log: (event, fields) => void this.logs.push({ event, fields }),
			...overrides
		};
	}

	texts() {
		return this.sent.filter((s) => s.kind === 'text').map((s) => s.text);
	}
}

async function run(world: World, req: Request, overrides: Partial<WhatsAppDeps> = {}) {
	const handled = await handle(req, world.deps(overrides));
	await handled.work;
	return handled.response.status;
}

describe('who may call', () => {
	test('a missing, malformed or wrong signature is refused before anything else happens', async () => {
		const body = webhook([message()]);
		for (const signature of [
			null,
			'sha256=nothex',
			sign(JSON.stringify(body), 'another-secret'),
			sign(JSON.stringify(body)).toUpperCase()
		]) {
			const world = new World();
			expect(await run(world, request(body, signature))).toBe(401);
			expect(world.sent).toEqual([]);
			expect(world.turns).toEqual([]);
		}
	});

	test('the signature covers the raw bytes: non-ASCII text passes, any change fails', async () => {
		const raw = JSON.stringify(
			webhook([message({ text: { body: 'Apa kabar, café — 日本 😀?' } })])
		);
		const world = new World();
		expect(await run(world, request(raw, sign(raw)))).toBe(200);
		expect(world.turns[0].request.text).toBe('Apa kabar, café — 日本 😀?');

		const reformatted = JSON.stringify(JSON.parse(raw), null, 1);
		expect(await run(new World(), request(reformatted, sign(raw)))).toBe(401);
	});

	test('a signed body that is not JSON is a 400', async () => {
		expect(await run(new World(), request('not json'))).toBe(400);
	});

	test('a webhook for another phone number id is acknowledged and ignored', async () => {
		const world = new World();
		const other = webhook([message()], {
			metadata: { display_phone_number: '1', phone_number_id: '999' }
		});
		expect(await run(world, request(other))).toBe(200);
		expect(world.sent).toEqual([]);
		expect(world.turns).toEqual([]);
	});
});

describe('the verify challenge', () => {
	const get = (query: string) => new Request(`http://gateway/api/whatsapp?${query}`);

	test('echoes the challenge only for subscribe with the right token', async () => {
		const ok = verify(get('hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=42'), {
			verifyToken: 'verify-me'
		});
		expect(ok.status).toBe(200);
		expect(await ok.text()).toBe('42');
		for (const query of [
			'hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=42',
			'hub.mode=subscribe&hub.verify_token=verify-mee&hub.challenge=42',
			'hub.mode=unsubscribe&hub.verify_token=verify-me&hub.challenge=42',
			'hub.challenge=42'
		]) {
			expect(verify(get(query), { verifyToken: 'verify-me' }).status).toBe(403);
		}
	});
});

describe('a question', () => {
	test('the 200 comes back before ent-os answers', async () => {
		const world = new World();
		let release!: () => void;
		const held = new Promise<void>((resolve) => (release = resolve));
		world.outcome = async () => {
			await held;
			return { kind: 'reply', reply: 'nanti', chatUrl: '', outcome: 'answered' };
		};
		const handled = await handle(request(webhook([message()])), world.deps());
		expect(handled.response.status).toBe(200);
		await Bun.sleep(5);
		expect(world.texts()).toEqual([]);
		release();
		await handled.work;
		expect(world.texts()).toEqual(['nanti']);
	});

	test('read + typing first, then the reply to the sender, quoting the question', async () => {
		const world = new World();
		expect(await run(world, request(webhook([message()])))).toBe(200);
		expect(world.sent).toEqual([
			{ kind: 'read', id: 'wamid.A' },
			{ kind: 'text', to: WA_ID, text: 'Proyek SPBG on track.', replyTo: 'wamid.A' }
		]);
	});

	test('ent-os gets keyed hashes, never the number, on behalf of whatsapp:<hash>', async () => {
		const world = new World();
		await run(world, request(webhook([message()])));
		const [{ request: sent, onBehalfOf }] = world.turns;
		expect(onBehalfOf).toBe(`whatsapp:${IDENTITY}`);
		expect(sent).toEqual({
			channel: 'whatsapp',
			identity_hash: IDENTITY,
			conversation_key: hash(whatsappConversation(WA_ID)),
			text: 'status proyek SPBG?',
			has_attachment: false
		});
		expect(IDENTITY).toMatch(/^[0-9a-f]{64}$/);
		expect(JSON.stringify(world.turns)).not.toContain(WA_ID);
		expect(JSON.stringify(world.logs)).not.toContain(WA_ID);
	});

	test('a refusal gets the neutral reply; an ent-os failure gets the outage reply, once', async () => {
		const refused = new World();
		refused.outcome = async () => ({ kind: 'refused' });
		await run(refused, request(webhook([message()])));
		expect(refused.texts()).toEqual([NOT_CONNECTED]);

		const down = new World();
		down.outcome = async () => {
			throw new Error('ent-os 502');
		};
		await run(down, request(webhook([message()])));
		expect(down.texts()).toEqual([UNAVAILABLE]);
		expect(down.turns.length).toBe(1);
	});

	test('a failing read or send is logged and never stops the work', async () => {
		const world = new World();
		const deps = world.deps({
			sender: {
				read: async () => {
					throw new Error('cloud api 500');
				},
				text: async () => {
					throw new Error('cloud api 500');
				}
			}
		});
		const handled = await handle(request(webhook([message()])), deps);
		await handled.work;
		expect(world.turns.length).toBe(1);
		expect(world.logs.map((l) => l.event)).toEqual([
			'whatsapp_read_failed',
			'turn_answered',
			'whatsapp_send_failed'
		]);
	});

	test('a redelivered message id is answered once', async () => {
		const world = new World();
		await run(world, request(webhook([message()])));
		await run(world, request(webhook([message()])));
		expect(world.turns.length).toBe(1);
		expect(world.texts()).toEqual(['Proyek SPBG on track.']);
		expect(world.logs.some((l) => l.event === 'whatsapp_duplicate')).toBe(true);
	});

	test('two messages in one webhook are answered in order', async () => {
		const world = new World();
		await run(
			world,
			request(
				webhook([
					message({ id: 'wamid.1', text: { body: 'satu' } }),
					message({ id: 'wamid.2', text: { body: 'dua' } })
				])
			)
		);
		expect(world.turns.map((t) => t.request.text)).toEqual(['satu', 'dua']);
	});
});

describe('what is not a plain question', () => {
	test('statuses only, empty text and unknown types are acknowledged and ignored', async () => {
		const world = new World();
		const statuses = webhook([], {
			messages: undefined,
			statuses: [{ id: 'wamid.A', status: 'read' }]
		});
		expect(await run(world, request(statuses))).toBe(200);
		expect(await run(world, request(webhook([message({ id: 'e', text: { body: '  ' } })])))).toBe(
			200
		);
		expect(await run(world, request(webhook([message({ id: 'r', type: 'reaction' })])))).toBe(200);
		expect(world.sent).toEqual([]);
		expect(world.turns).toEqual([]);
	});

	test('media carries the attachment flag and its caption', async () => {
		const world = new World();
		await run(
			world,
			request(
				webhook([
					message({ id: 'img', type: 'image', image: { id: 'm1', caption: ' lihat ini ' } }),
					message({ id: 'voice', type: 'audio', audio: { id: 'm2' } })
				])
			)
		);
		expect(world.turns.map((t) => [t.request.text, t.request.has_attachment])).toEqual([
			['lihat ini', true],
			['', true]
		]);
	});
});

describe('hubungkan <code>', () => {
	test('links on behalf of the code and the number, sending only the last four digits', async () => {
		const world = new World();
		await run(world, request(webhook([message({ text: { body: '  Hubungkan 123456 ' } })])));
		expect(world.links).toEqual([{ hint: '7890', onBehalfOf: `link-code:123456:${IDENTITY}` }]);
		expect(world.turns).toEqual([]);
		expect(world.texts()).toEqual([LINKED]);
	});

	test('a refused code gets "Kode tidak berlaku"; an ent-os failure the outage reply', async () => {
		const refused = new World();
		refused.linkOutcome = async () => 'refused';
		await run(refused, request(webhook([message({ text: { body: 'hubungkan 000000' } })])));
		expect(refused.texts()).toEqual([CODE_INVALID]);

		const down = new World();
		down.linkOutcome = async () => {
			throw new Error('ent-os 503');
		};
		await run(down, request(webhook([message({ text: { body: 'HUBUNGKAN 000000' } })])));
		expect(down.texts()).toEqual([UNAVAILABLE]);
	});

	test('anything not exactly six digits is a question, not a link', async () => {
		const world = new World();
		const bodies = [
			'hubungkan 12345',
			'hubungkan 1234567',
			'hubungkan abcdef',
			'tolong hubungkan 123456'
		];
		await run(
			world,
			request(webhook(bodies.map((body, i) => message({ id: `q${i}`, text: { body } }))))
		);
		expect(world.links).toEqual([]);
		expect(world.turns.map((t) => t.request.text)).toEqual(bodies);
	});
});

test('RecentIds forgets the oldest id past its capacity', () => {
	const ids = new RecentIds(2);
	expect(ids.add('a')).toBe(true);
	expect(ids.add('a')).toBe(false);
	ids.add('b');
	ids.add('c');
	expect(ids.add('a')).toBe(true);
	expect(ids.add('c')).toBe(false);
});
