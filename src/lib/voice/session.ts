import { writable } from 'svelte/store';

import { acknowledgeVoice, getVoiceCapabilities, startVoiceCall } from '$lib/apis/voice';
import { beginCall, type StartedCall, type VoiceCapabilities } from './call';

/** The caller's voice capabilities; `null` until read, or when they could not be read (button hidden). */
export const voiceCapabilities = writable<VoiceCapabilities | null>(null);

/** Set while the disclosure is open; called with the user's answer. */
export const disclosureRequest = writable<((accepted: boolean) => void) | null>(null);

/** The voice chat the start-call route just made; its page opens the call overlay once loaded. */
export const pendingVoiceCall = writable<string | null>(null);

/** The same chat, until its overlay has sent the opening line (`CALL_OPENING`). */
export const voiceCallOpening = writable<string | null>(null);

export const refreshVoiceCapabilities = async (token: string) => {
	const capabilities = await getVoiceCapabilities(token).catch(() => null);
	voiceCapabilities.set(capabilities);
	return capabilities;
};

const openDisclosure = () =>
	new Promise<boolean>((resolve) => disclosureRequest.set((accepted) => resolve(accepted)));

/** Runs the call flow; on success the caller navigates to `/c/<chat_id>`. */
export const runVoiceCall = async (token: string): Promise<StartedCall | null> => {
	const started = await beginCall({
		capabilities: () => refreshVoiceCapabilities(token),
		disclose: openDisclosure,
		acknowledge: (version) => acknowledgeVoice(token, version),
		startCall: () => startVoiceCall(token)
	});
	if (started) {
		pendingVoiceCall.set(started.chat_id);
		voiceCapabilities.update((c) => (c ? { ...c, acknowledged: true } : c));
	}
	return started;
};
