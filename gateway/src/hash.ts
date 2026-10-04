/**
 * Keyed hashes (HMAC-SHA256) of what identifies a sender and a conversation, so raw Channel
 * Identities never leave the gateway (spec #84). One key, from Secret Manager in production.
 * ent-os checks `identity_hash` is 64 lowercase hex characters.
 */

import { createHmac } from 'node:crypto';

export type Hasher = (value: string) => string;

export function hmacHasher(key: string): Hasher {
	if (key.length < 32) throw new Error('GATEWAY_HMAC_KEY must be at least 32 characters');
	return (value) => createHmac('sha256', key).update(value, 'utf8').digest('hex');
}

/** The Teams Channel Identity: tenant and Entra object id. */
export const teamsIdentity = (tenantId: string, objectId: string) =>
	`teams:identity:${tenantId}:${objectId}`;

/** A Teams conversation. In a 1:1 chat it is stable per sender. */
export const teamsConversation = (conversationId: string) => `teams:conversation:${conversationId}`;
