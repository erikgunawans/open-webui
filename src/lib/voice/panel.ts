/**
 * The Ruang Pimpinan assistant panel: voice and typing beside the page, never instead of it.
 *
 * A panel call is an ordinary voice call (`POST /voice/calls`, the same disclosures and grants as
 * the main chat). What differs is where it lives: the panel is mounted by the section layout, so
 * the call survives switching tabs, and each tab switch is recorded on the call's chat
 * (`PUT /voice/calls/{id}/context`) so the leadership tool knows what "this" means. Typed and
 * spoken questions go through `POST /voice/calls/{id}/turns`, the governed turn GPT-Live
 * delegations use; the panel never builds a prompt of its own. The browser APIs are injected so
 * the sequence is testable.
 */
import { writable } from 'svelte/store';

import { beginCall, callButton, sealedAnswerParts, type VoiceCapabilities } from './call';
import { chooseCallMode, liveMode, type CallMode } from './live';

export type LeadershipTab = 'board' | 'rka';

/** Whether the panel is open. The section layout reads it; the page's button sets it. */
export const assistantPanelOpen = writable(false);

/** The Ruang Pimpinan tab a path is on, or `null` off those pages. */
export const viewFromPath = (pathname: string): LeadershipTab | null => {
	const match = /^\/ruang-pimpinan\/(board|rka)(\/|$)/.exec(pathname);
	return match ? (match[1] as LeadershipTab) : null;
};

/** The call modes the panel offers: none without the switch and the call grant. */
export const panelModes = (capabilities: VoiceCapabilities | null | undefined): CallMode[] => {
	if (callButton(capabilities) === 'hidden') return [];
	return liveMode(capabilities) === 'hidden' ? ['governed'] : ['governed', 'live'];
};

export type PanelCallSteps = {
	capabilities: () => Promise<VoiceCapabilities | null>;
	disclose: () => Promise<boolean>;
	acknowledge: (version: string) => Promise<void>;
	discloseLive: () => Promise<boolean>;
	acknowledgeLive: (version: string) => Promise<void>;
	startCall: () => Promise<{ chat_id: string; model: string }>;
	setContext: (chatId: string, view: LeadershipTab) => Promise<unknown>;
};

export type PanelCall = { chat_id: string; mode: CallMode };

/**
 * Starts a call in the mode the caller picked in the panel. Either disclosure declined starts
 * nothing; GPT-Live without its grant is a normal call. A tab that cannot be recorded does not stop
 * the call: the assistant then reads every view the caller may see.
 */
export const startPanelCall = async (
	steps: PanelCallSteps,
	picked: CallMode,
	view: LeadershipTab | null
): Promise<PanelCall | null> => {
	const capabilities = await steps.capabilities();
	const mode = await chooseCallMode(capabilities, {
		choose: async () => picked,
		discloseLive: steps.discloseLive,
		acknowledgeLive: steps.acknowledgeLive
	});
	if (mode === null) return null;
	const started = await beginCall({
		capabilities: async () => capabilities,
		disclose: steps.disclose,
		acknowledge: steps.acknowledge,
		startCall: steps.startCall
	});
	if (!started) return null;
	if (view) await steps.setContext(started.chat_id, view).catch(() => null);
	return { chat_id: started.chat_id, mode };
};

export type Turn = { who: 'caller' | 'assistant'; text: string; pending?: boolean };

/** Appends a turn, keeping the last `keep`; the full record is the chat itself. */
export const addTurn = (turns: Turn[], turn: Turn, keep = 50): Turn[] =>
	[...turns, turn].slice(-keep);

export type SpeakSteps<A> = {
	parts: () => Promise<number>;
	part: (n: number) => Promise<A>;
	play: (audio: A) => Promise<void>;
	wait?: (ms: number) => Promise<void>;
};

/**
 * Reads a sealed answer aloud, part by part. The server reads only the answer it stored and sealed,
 * so each part is fetched by number; an abort (a hang-up, the next question) stops further fetches,
 * each of which is a billed request and a `voice_tts` line.
 */
export const speakSealedAnswer = async <A>(steps: SpeakSteps<A>, signal: AbortSignal) => {
	const count = await sealedAnswerParts(steps.parts, steps.wait ? { wait: steps.wait } : {});
	for (let n = 0; n < count; n++) {
		if (signal.aborted) return;
		const audio = await steps.part(n);
		if (signal.aborted) return;
		await steps.play(audio);
	}
};
