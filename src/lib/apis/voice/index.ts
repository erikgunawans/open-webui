import { AUDIO_API_BASE_URL, WEBUI_API_BASE_URL } from '$lib/constants';
import type { StartedCall, VoiceCapabilities } from '$lib/voice/call';

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
