/**
 * The Teams inbound handler (E7.5, spec #84): one Bot Framework activity in, a 200 at once, the
 * answer posted back later.
 *
 * Order of trust: the Bot Framework JWT is verified before the body is read for anything; the
 * tenant must be JUP's; the reply may only go to the `serviceurl` the token names. Only 1:1
 * (`personal`) messages are answered: group chats and channels are ignored, because the answer is
 * one user's governed view and must not be shown to a room.
 *
 * `handle` returns the HTTP response and, separately, the work still to do, so the server can
 * answer at once and a test can await the rest.
 */

import { teamsConversation, teamsIdentity, type Hasher } from './hash';
import { NOT_CONNECTED, UNAVAILABLE } from './texts';
import type { EntOsClient, Log, ReplyTarget, Resolver, Sender, Verifier } from './types';

export interface TeamsDeps {
	verifier: Verifier;
	sender: Sender;
	resolver: Resolver;
	entos: EntOsClient;
	/** JUP's Entra tenant id; a message from any other tenant is refused. */
	tenantId: string;
	hash: Hasher;
	log: Log;
}

export interface Handled {
	response: Response;
	/** What happens after the 200: typing, the turn and the reply. Never rejects. */
	work: Promise<void>;
}

const done = Promise.resolve();
const status = (code: number) => ({ response: new Response(null, { status: code }), work: done });

/** Teams sends formatted text as a `text/html` copy of the message; that is not an attachment. */
const isAttachment = (attachment: unknown) =>
	!!attachment &&
	typeof attachment === 'object' &&
	(attachment as { contentType?: unknown }).contentType !== 'text/html';

export async function handle(request: Request, deps: TeamsDeps): Promise<Handled> {
	let caller;
	try {
		caller = await deps.verifier.verify(request.headers.get('authorization'));
	} catch (error) {
		deps.log('teams_rejected', { reason: 'token', detail: String(error) });
		return status(401);
	}

	let activity: any;
	try {
		activity = await request.json();
	} catch {
		return status(400);
	}

	const tenantId = activity?.channelData?.tenant?.id ?? activity?.conversation?.tenantId;
	if (tenantId !== deps.tenantId) {
		deps.log('teams_rejected', { reason: 'tenant' });
		return status(403);
	}
	if (activity?.serviceUrl !== caller.serviceUrl) {
		deps.log('teams_rejected', { reason: 'service_url' });
		return status(403);
	}

	if (activity?.type !== 'message') return status(200);
	if (activity?.conversation?.conversationType !== 'personal' || activity?.conversation?.isGroup) {
		deps.log('teams_ignored', { reason: 'not_personal' });
		return status(200);
	}

	const objectId: unknown = activity?.from?.aadObjectId;
	const conversationId: unknown = activity?.conversation?.id;
	if (
		typeof objectId !== 'string' ||
		!objectId ||
		typeof conversationId !== 'string' ||
		!conversationId
	) {
		return status(400);
	}
	const text = typeof activity.text === 'string' ? activity.text.trim() : '';
	const hasAttachment =
		Array.isArray(activity.attachments) && activity.attachments.some(isAttachment);
	if (!text && !hasAttachment) return status(200);

	const target: ReplyTarget = {
		serviceUrl: caller.serviceUrl,
		conversationId,
		replyToId: activity.id
	};
	const work = answer(deps, target, {
		tenantId,
		objectId,
		conversationId,
		text,
		hasAttachment
	});
	return { response: new Response(null, { status: 200 }), work };
}

async function answer(
	deps: TeamsDeps,
	target: ReplyTarget,
	message: {
		tenantId: string;
		objectId: string;
		conversationId: string;
		text: string;
		hasAttachment: boolean;
	}
): Promise<void> {
	const identityHash = deps.hash(teamsIdentity(message.tenantId, message.objectId));
	const send = async (text: string) => {
		try {
			await deps.sender.text(target, text);
		} catch (error) {
			deps.log('teams_send_failed', { identity_hash: identityHash, detail: String(error) });
		}
	};

	try {
		await deps.sender.typing(target);
	} catch (error) {
		deps.log('teams_typing_failed', { identity_hash: identityHash, detail: String(error) });
	}

	let email: string | null;
	try {
		email = await deps.resolver.resolve({ tenantId: message.tenantId, objectId: message.objectId });
	} catch (error) {
		deps.log('mapping_failed', { identity_hash: identityHash, detail: String(error) });
		return send(UNAVAILABLE);
	}
	if (!email) {
		deps.log('turn_refused', { identity_hash: identityHash, reason: 'unmapped' });
		return send(NOT_CONNECTED);
	}

	try {
		const outcome = await deps.entos.turn(
			{
				channel: 'teams',
				identity_hash: identityHash,
				conversation_key: deps.hash(teamsConversation(message.conversationId)),
				text: message.text,
				has_attachment: message.hasAttachment
			},
			email
		);
		if (outcome.kind === 'refused') {
			deps.log('turn_refused', { identity_hash: identityHash, reason: 'entos_refused' });
			return send(NOT_CONNECTED);
		}
		deps.log('turn_answered', { identity_hash: identityHash, outcome: outcome.outcome });
		return send(outcome.reply);
	} catch (error) {
		// Logged, never retried (spec #84): a retry could run the turn twice.
		deps.log('entos_failed', { identity_hash: identityHash, detail: String(error) });
		return send(UNAVAILABLE);
	}
}
