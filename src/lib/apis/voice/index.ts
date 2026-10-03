import { AUDIO_API_BASE_URL, WEBUI_API_BASE_URL } from '$lib/constants';
import type { StartedCall, VoiceCapabilities } from '$lib/voice/call';
import { ndjsonEvents } from '$lib/voice/live';

// The voice routes (#26, #28). A refusal throws its `{code, message}` so the caller can branch on it.

const request = async (token: string, url: string, init: RequestInit = {}) => {
	const res = await fetch(url, {
		...init,
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`,
			...(init.body ? { 'Content-Type': 'application/json' } : {}),
			...init.headers
		}
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw body?.detail ?? { code: 'voice_error', message: res.statusText };
	}
	return res;
};

export const getVoiceCapabilities = async (token: string): Promise<VoiceCapabilities> =>
	(await request(token, `${WEBUI_API_BASE_URL}/voice/capabilities`)).json();

export const acknowledgeVoice = async (token: string, version: string): Promise<void> => {
	await request(token, `${WEBUI_API_BASE_URL}/voice/acknowledge`, {
		method: 'POST',
		body: JSON.stringify({ version })
	});
};

/** Acknowledges the GPT-Live disclosure (#34), separately from the call's. */
export const acknowledgeVoiceLive = async (token: string, version: string): Promise<void> => {
	await request(token, `${WEBUI_API_BASE_URL}/voice/live/acknowledge`, {
		method: 'POST',
		body: JSON.stringify({ version })
	});
};

/**
 * Sends the WebRTC offer; the server mints the GPT-Live session (#35) and holds this request open
 * for the whole call while it relays governed answers (#36). Resolves with the SDP answer once the
 * first line arrives; `ended` settles when the server closes the call, and `hangUp` ends it.
 */
export const startLiveSession = async (
	token: string,
	chatId: string,
	sdp: string
): Promise<{ session_id: string; sdp: string; ended: Promise<void>; hangUp: () => void }> => {
	const controller = new AbortController();
	const res = await request(token, `${WEBUI_API_BASE_URL}/voice/live/sessions`, {
		method: 'POST',
		body: JSON.stringify({ chat_id: chatId, sdp }),
		signal: controller.signal
	});
	const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
	const chunks = (async function* () {
		for (;;) {
			const { value, done } = await reader.read();
			if (done) return;
			yield value;
		}
	})();
	const events = ndjsonEvents(chunks);
	const first = await events.next();
	if (first.done || first.value.type !== 'session') {
		controller.abort();
		throw { code: 'voice_live_upstream', message: 'GPT-Live did not start the session.' };
	}
	const ended = (async () => {
		try {
			for await (const event of events) if (event.type === 'ended') return;
		} catch {
			// Hanging up aborts the stream; that is an ending too.
		}
	})();
	return {
		session_id: first.value.session_id,
		sdp: first.value.sdp,
		ended,
		hangUp: () => controller.abort()
	};
};

export const startVoiceCall = async (token: string): Promise<StartedCall> =>
	(await request(token, `${WEBUI_API_BASE_URL}/voice/calls`, { method: 'POST' })).json();

/** How many parts the sealed answer is read in. */
export const getAnswerSpeechParts = async (
	token: string,
	chatId: string,
	messageId: string
): Promise<number> => {
	const query = new URLSearchParams({ chat_id: chatId, message_id: messageId });
	const res = await request(token, `${WEBUI_API_BASE_URL}/voice/speech/parts?${query}`);
	return (await res.json()).parts;
};

/** One part of the sealed answer as audio. Never free text: the server refuses `input`. */
export const synthesizeAnswerPart = async (
	token: string,
	chatId: string,
	messageId: string,
	part: number
): Promise<Blob> => {
	const res = await request(token, `${AUDIO_API_BASE_URL}/speech`, {
		method: 'POST',
		headers: { Accept: 'audio/*' },
		body: JSON.stringify({ chat_id: chatId, message_id: messageId, part })
	});
	return res.blob();
};

/** Records which Ruang Pimpinan tab is open beside the caller's own panel call. */
export const setCallContext = async (
	token: string,
	chatId: string,
	view: 'board' | 'rka'
): Promise<{ view: string }> =>
	(
		await request(
			token,
			`${WEBUI_API_BASE_URL}/voice/calls/${encodeURIComponent(chatId)}/context`,
			{
				method: 'PUT',
				body: JSON.stringify({ view })
			}
		)
	).json();

/** Asks a typed or transcribed question in the caller's own voice call; resolves with the sealed answer. */
export const askInCall = async (
	token: string,
	chatId: string,
	text: string
): Promise<{ message_id: string; content: string }> =>
	(
		await request(token, `${WEBUI_API_BASE_URL}/voice/calls/${encodeURIComponent(chatId)}/turns`, {
			method: 'POST',
			body: JSON.stringify({ text })
		})
	).json();
