/**
 * The WhatsApp inbound handler (E9.3, spec #101): one Cloud API webhook in, a 200 at once, the
 * answers sent back later.
 *
 * Order of trust: Meta's `X-Hub-Signature-256` is checked over the raw body before the body is read
 * for anything; only messages to our own phone number id are answered. The sender is only a phone
 * number, so the gateway never names a user: it sends the number's keyed hash and ent-os resolves
 * it from its Mapping (ADR-0012 amendment 2). `hubungkan <6 digits>` is the one other thing a
 * sender can do, and it goes to the link path only.
 *
 * Meta redelivers a webhook it thinks failed; a message id already seen is dropped, so a question
 * is never answered twice by the same instance.
 */

import { createHmac, timingSafeEqual } from 'node:crypto';
import { whatsappConversation, whatsappIdentity, type Hasher } from './hash';
import { CODE_INVALID, LINKED, NOT_CONNECTED, UNAVAILABLE } from './texts';
import { toWhatsApp } from './whatsapp_format';
import type { EntOsClient, EntOsLinker, Log } from './types';

/** Posts to the Cloud API. Both calls may throw; the handler logs and carries on. */
export interface WhatsAppSender {
	/** Marks the message read and shows "typing…" until the reply (or 25 s). */
	read(messageId: string): Promise<void>;
	text(to: string, text: string, replyTo: string): Promise<void>;
}

export interface WhatsAppDeps {
	/** True when `signature` is Meta's HMAC of exactly these bytes. */
	signed(raw: Uint8Array, signature: string | null): boolean;
	verifyToken: string;
	/** Our number's id; a webhook for any other number is ignored. */
	phoneNumberId: string;
	sender: WhatsAppSender;
	entos: EntOsClient & EntOsLinker;
	hash: Hasher;
	seen: RecentIds;
	log: Log;
}

export interface Handled {
	response: Response;
	/** What happens after the 200: read, the turn or the link, and the reply. Never rejects. */
	work: Promise<void>;
}

const done = Promise.resolve();
const status = (code: number) => ({ response: new Response(null, { status: code }), work: done });

/** Meta's signature check: `sha256=<hex HMAC-SHA256 of the raw body>` with the app secret. */
export function metaSignature(appSecret: string) {
	return (raw: Uint8Array, signature: string | null): boolean => {
		const given = signature?.match(/^sha256=([0-9a-f]{64})$/)?.[1];
		if (!given) return false;
		const expected = createHmac('sha256', appSecret).update(raw).digest();
		return timingSafeEqual(expected, Buffer.from(given, 'hex'));
	};
}

/** Message ids already handled, oldest dropped first. Per instance (gateway max 2). */
export class RecentIds {
	private readonly ids = new Set<string>();

	constructor(private readonly capacity = 5000) {}

	/** True the first time an id is offered, false after. */
	add(id: string): boolean {
		if (this.ids.has(id)) return false;
		this.ids.add(id);
		if (this.ids.size > this.capacity) this.ids.delete(this.ids.values().next().value!);
		return true;
	}
}

/** `GET /api/whatsapp`: Meta's one-time check when the webhook URL is set. */
export function verify(request: Request, deps: Pick<WhatsAppDeps, 'verifyToken'>): Response {
	const params = new URL(request.url).searchParams;
	const given = Buffer.from(params.get('hub.verify_token') ?? '');
	const expected = Buffer.from(deps.verifyToken);
	const matches = given.length === expected.length && timingSafeEqual(given, expected);
	if (params.get('hub.mode') !== 'subscribe' || !matches)
		return new Response(null, { status: 403 });
	return new Response(params.get('hub.challenge') ?? '', { status: 200 });
}

/** Message types that carry media or other content ent-os cannot read: answered with the notice. */
const ATTACHMENT_TYPES = new Set([
	'image',
	'document',
	'audio',
	'video',
	'sticker',
	'location',
	'contacts'
]);
const LINK_COMMAND = /^hubungkan\s+(\d{6})$/i;
/** A `wa_id`: digits only, country code first. */
const WA_ID = /^\d{7,20}$/;

interface Inbound {
	id: string;
	from: string;
	text: string;
	hasAttachment: boolean;
}

/** The messages of a webhook body worth answering, in order. Statuses and other numbers are skipped. */
function inbound(body: any, phoneNumberId: string, log: Log): Inbound[] {
	const found: Inbound[] = [];
	if (body?.object !== 'whatsapp_business_account' || !Array.isArray(body.entry)) return found;
	for (const entry of body.entry) {
		for (const change of Array.isArray(entry?.changes) ? entry.changes : []) {
			const value = change?.value;
			if (change?.field !== 'messages' || !Array.isArray(value?.messages)) continue;
			if (value?.metadata?.phone_number_id !== phoneNumberId) {
				log('whatsapp_ignored', { reason: 'other_number' });
				continue;
			}
			for (const message of value.messages) {
				const { id, from, type } = message ?? {};
				if (typeof id !== 'string' || !id || typeof from !== 'string' || !WA_ID.test(from))
					continue;
				if (type === 'text' && typeof message.text?.body === 'string') {
					const text = message.text.body.trim();
					if (text) found.push({ id, from, text, hasAttachment: false });
				} else if (ATTACHMENT_TYPES.has(type)) {
					const caption = message[type]?.caption;
					found.push({
						id,
						from,
						text: typeof caption === 'string' ? caption.trim() : '',
						hasAttachment: true
					});
				} else {
					log('whatsapp_ignored', { reason: 'type', type: String(type) });
				}
			}
		}
	}
	return found;
}

/** `POST /api/whatsapp`. */
export async function handle(request: Request, deps: WhatsAppDeps): Promise<Handled> {
	const raw = new Uint8Array(await request.arrayBuffer());
	if (!deps.signed(raw, request.headers.get('x-hub-signature-256'))) {
		deps.log('whatsapp_rejected', { reason: 'signature' });
		return status(401);
	}

	let body: unknown;
	try {
		body = JSON.parse(new TextDecoder().decode(raw));
	} catch {
		return status(400);
	}

	const messages = inbound(body, deps.phoneNumberId, deps.log).filter((message) => {
		if (deps.seen.add(message.id)) return true;
		deps.log('whatsapp_duplicate', { identity_hash: deps.hash(whatsappIdentity(message.from)) });
		return false;
	});
	// One after another: two messages of one webhook are usually one sender's, in order.
	const work = messages.reduce<Promise<void>>(
		(previous, message) => previous.then(() => answer(deps, message)),
		done
	);
	return { response: new Response(null, { status: 200 }), work };
}

async function answer(deps: WhatsAppDeps, message: Inbound): Promise<void> {
	const identityHash = deps.hash(whatsappIdentity(message.from));
	const send = async (text: string) => {
		try {
			await deps.sender.text(message.from, text, message.id);
		} catch (error) {
			deps.log('whatsapp_send_failed', { identity_hash: identityHash, detail: String(error) });
		}
	};

	try {
		await deps.sender.read(message.id);
	} catch (error) {
		deps.log('whatsapp_read_failed', { identity_hash: identityHash, detail: String(error) });
	}

	const code = message.hasAttachment ? null : message.text.match(LINK_COMMAND)?.[1];
	if (code) {
		try {
			const outcome = await deps.entos.link(
				message.from.slice(-4),
				`link-code:${code}:${identityHash}`
			);
			deps.log('link_' + outcome, { identity_hash: identityHash });
			return send(outcome === 'linked' ? LINKED : CODE_INVALID);
		} catch (error) {
			deps.log('entos_failed', { identity_hash: identityHash, detail: String(error) });
			return send(UNAVAILABLE);
		}
	}

	try {
		const outcome = await deps.entos.turn(
			{
				channel: 'whatsapp',
				identity_hash: identityHash,
				conversation_key: deps.hash(whatsappConversation(message.from)),
				text: message.text,
				has_attachment: message.hasAttachment
			},
			`whatsapp:${identityHash}`
		);
		if (outcome.kind === 'refused') {
			deps.log('turn_refused', { identity_hash: identityHash, reason: 'entos_refused' });
			return send(NOT_CONNECTED);
		}
		deps.log('turn_answered', { identity_hash: identityHash, outcome: outcome.outcome });
		return send(toWhatsApp(outcome.reply));
	} catch (error) {
		// Logged, never retried (spec #84): a retry could run the turn twice.
		deps.log('entos_failed', { identity_hash: identityHash, detail: String(error) });
		return send(UNAVAILABLE);
	}
}
