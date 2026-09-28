import { writable } from 'svelte/store';

import {
	acknowledgeVoice,
	acknowledgeVoiceLive,
	getVoiceCapabilities,
	startVoiceCall
} from '$lib/apis/voice';
import { beginCall, type StartedCall, type VoiceCapabilities } from './call';
import { chooseCallMode, type CallMode } from './live';

/** The caller's voice capabilities; `null` until read, or when they could not be read (button hidden). */
export const voiceCapabilities = writable<VoiceCapabilities | null>(null);

/** Set while the disclosure is open; called with the user's answer. */
export const disclosureRequest = writable<((accepted: boolean) => void) | null>(null);

/** Set while the call-mode choice is open (#37); called with the chosen mode, or `null`. */
export const modeRequest = writable<((mode: CallMode | null) => void) | null>(null);

/** Set while the GPT-Live disclosure is open (#37); called with the user's answer. */
export const liveDisclosureRequest = writable<((accepted: boolean) => void) | null>(null);

/** The mode of the call the start-call route just made; read with `pendingVoiceCall`. */
export const pendingCallMode = writable<CallMode>('governed');

/** The voice chat whose GPT-Live call is open (#37); `null` when none is. */
export const liveCallChat = writable<string | null>(null);

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

const openModeChoice = () => new Promise<CallMode | null>((resolve) => modeRequest.set(resolve));

const openLiveDisclosure = () =>
	new Promise<boolean>((resolve) => liveDisclosureRequest.set(resolve));

/** Runs the call flow; on success the caller navigates to `/c/<chat_id>`. */
export const runVoiceCall = async (token: string): Promise<StartedCall | null> => {
	// With the GPT-Live grant, the caller picks the mode first (#37); without it nothing changes.
	const mode = await chooseCallMode(await refreshVoiceCapabilities(token), {
		choose: openModeChoice,
		discloseLive: openLiveDisclosure,
		acknowledgeLive: (version) => acknowledgeVoiceLive(token, version)
	});
	if (mode === null) return null;
	const started = await beginCall({
		capabilities: () => refreshVoiceCapabilities(token),
		disclose: openDisclosure,
		acknowledge: (version) => acknowledgeVoice(token, version),
		startCall: () => startVoiceCall(token)
	});
	if (started) {
		pendingCallMode.set(mode);
		pendingVoiceCall.set(started.chat_id);
		voiceCapabilities.update((c) => (c ? { ...c, acknowledged: true } : c));
	}
	return started;
};
