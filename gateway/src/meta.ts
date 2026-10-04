/**
 * The real WhatsApp adapter: the Cloud API sender. It does not run in the tests (no network
 * there); the handler tests use a fake at the same interface. It goes live in E9.4 (#105).
 */

import type { WhatsAppSender } from './whatsapp';

export const GRAPH_VERSION = 'v25.0';

type Fetch = typeof fetch;

export class CloudApiSender implements WhatsAppSender {
	constructor(
		private readonly opts: {
			phoneNumberId: string;
			accessToken: string;
			fetch?: Fetch;
		}
	) {}

	private async post(body: Record<string, unknown>): Promise<void> {
		const response = await (this.opts.fetch ?? fetch)(
			`https://graph.facebook.com/${GRAPH_VERSION}/${this.opts.phoneNumberId}/messages`,
			{
				method: 'POST',
				headers: {
					authorization: `Bearer ${this.opts.accessToken}`,
					'content-type': 'application/json'
				},
				body: JSON.stringify({ messaging_product: 'whatsapp', ...body })
			}
		);
		if (!response.ok) throw new Error(`cloud api ${response.status}`);
	}

	read(messageId: string): Promise<void> {
		return this.post({ status: 'read', message_id: messageId, typing_indicator: { type: 'text' } });
	}

	text(to: string, text: string, replyTo: string): Promise<void> {
		return this.post({
			recipient_type: 'individual',
			to,
			context: { message_id: replyTo },
			type: 'text',
			text: { preview_url: false, body: text }
		});
	}
}
