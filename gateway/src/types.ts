/**
 * The seams of the gateway (E7.5, spec #84). The inbound handler depends only on these; each
 * has a real adapter (Bot Framework, Graph, ent-os) and a fake in the tests.
 */

/** What a verified Bot Framework token proves about the request. */
export interface VerifiedCaller {
	/** The `serviceurl` claim: the only place a reply may be posted for this request. */
	serviceUrl: string;
}

/** Checks the `Authorization` header of an inbound Teams request. Throws when it is not valid. */
export interface Verifier {
	verify(authorization: string | null): Promise<VerifiedCaller>;
}

/** Where a reply goes: the Bot Connector conversation the message came from. */
export interface ReplyTarget {
	serviceUrl: string;
	conversationId: string;
	replyToId?: string;
}

/** Posts to Teams. Both calls may throw; the handler logs and carries on. */
export interface Sender {
	typing(target: ReplyTarget): Promise<void>;
	text(target: ReplyTarget, text: string): Promise<void>;
}

/**
 * Mapping: a Channel Identity to exactly one JUP user's app email, or null when unmapped.
 * The Teams resolver reads the Entra object id's email from Graph.
 */
export interface Resolver {
	resolve(identity: { tenantId: string; objectId: string }): Promise<string | null>;
}

/** The body `POST /api/jup/channel/turn` takes (`jup.channel.parse_request`). */
export interface TurnRequest {
	channel: 'teams' | 'whatsapp';
	identity_hash: string;
	conversation_key: string;
	text: string;
	has_attachment: boolean;
}

export type TurnOutcome =
	| { kind: 'reply'; reply: string; chatUrl: string; outcome: string }
	/** ent-os refused the user (unknown, pending, no grant, kill switch off): one neutral reply. */
	| { kind: 'refused' };

/**
 * Calls ent-os on behalf of a user: an email (Teams) or `whatsapp:<hash>` (ADR-0012 amendment 2).
 * Throws when ent-os is down, errors or times out.
 */
export interface EntOsClient {
	turn(request: TurnRequest, onBehalfOf: string): Promise<TurnOutcome>;
}

/** `refused`: the code is unknown, used, expired, someone else's, or too many tries (all 403). */
export type LinkOutcome = 'linked' | 'refused';

/**
 * `POST /api/jup/channel/link` on behalf of `link-code:<code>:<hash>`: links the number the code
 * was sent from. `hint` is its last four digits, for the web app. Throws like `turn`.
 */
export interface EntOsLinker {
	link(hint: string, onBehalfOf: string): Promise<LinkOutcome>;
}

export type Log = (event: string, fields: Record<string, unknown>) => void;
