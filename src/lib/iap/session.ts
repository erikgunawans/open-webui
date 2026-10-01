import { writable } from 'svelte/store';

/**
 * IAP session expiry (#47).
 *
 * The IAP/GCIP session ends about an hour after sign-in. From then on IAP answers every request
 * itself and nothing reaches the app. Without a hint IAP answers a script's request with a 302 to
 * the cross-origin sign-in page, which `fetch` cannot follow and reports as a bare network error,
 * so a streaming answer stopped with no message. With `X-Requested-With: XMLHttpRequest` IAP
 * answers 401 and marks the response as its own, which the app can recognise
 * (https://docs.cloud.google.com/iap/docs/sessions-howto). A reload signs back in silently.
 */

export const IAP_GENERATED_HEADER = 'x-goog-iap-generated-response';

/** True once IAP has refused a request in this page; only a reload clears it. */
export const iapSessionExpired = writable(false);

const isSameOrigin = (input: RequestInfo | URL, origin: string) => {
	try {
		return new URL(input instanceof Request ? input.url : input, origin).origin === origin;
	} catch {
		return false;
	}
};

/**
 * Adds the AJAX hint to same-origin requests given as a URL. A `Request` object is passed through
 * untouched: rebuilding it could consume its body.
 */
export const withIapAjaxHeader = (
	input: RequestInfo | URL,
	init: RequestInit | undefined,
	origin: string
): [RequestInfo | URL, RequestInit | undefined] => {
	if (input instanceof Request || !isSameOrigin(input, origin)) {
		return [input, init];
	}
	const headers = new Headers(init?.headers);
	if (!headers.has('X-Requested-With')) {
		headers.set('X-Requested-With', 'XMLHttpRequest');
	}
	return [input, { ...init, headers }];
};

/** A 401 that IAP generated: the IAP session is gone, the app session may still be fine. */
export const isIapExpiry = (response: Response) =>
	response.status === 401 && response.headers.get(IAP_GENERATED_HEADER) === 'true';

type PendingMessage = {
	role?: string;
	done?: boolean;
	error?: unknown;
};

/**
 * Marks an answer that was still streaming when the session ended as interrupted, so the chat
 * stops treating it as in progress and sends new messages instead of queueing them.
 * Returns whether the message was changed.
 */
export const interruptPendingAnswer = (
	message: PendingMessage | null | undefined,
	note: string
) => {
	if (!message || message.role !== 'assistant' || message.done) {
		return false;
	}
	message.done = true;
	message.error = { content: note };
	return true;
};
