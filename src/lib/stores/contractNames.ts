import { writable } from 'svelte/store';

import { getContractCapabilities, resolveContractCodes } from '$lib/apis/contracts';
import { applyNames, findCodes } from '$lib/contracts/names';

// Names for "Perorangan X" codes in answers, for readers the server lets see them (D2). Presentation
// only: the server decides, per request, and answers an empty map to everyone else. Keyed to the user
// id, so one account's names never outlive it in the tab.
type State = { userId: string | null; allowed: boolean; names: Record<string, string> };

export const contractNames = writable<State>({ userId: null, allowed: false, names: {} });

let current: State = { userId: null, allowed: false, names: {} };
contractNames.subscribe((value) => (current = value));

const asked = new Set<string>();
let queued = new Set<string>();
let timer: ReturnType<typeof setTimeout> | null = null;

export const loadContractNames = async (userId: string | null | undefined) => {
	if (!userId || current.userId === userId) return;
	asked.clear();
	contractNames.set({ userId, allowed: false, names: {} });
	try {
		const capabilities = await getContractCapabilities(localStorage.token);
		if (current.userId === userId)
			contractNames.update((s) => ({ ...s, allowed: capabilities.names === true }));
	} catch {
		// No names. Never disturbs chat.
	}
};

const flush = async () => {
	timer = null;
	const codes = [...queued].slice(0, 50);
	queued = new Set();
	const userId = current.userId;
	try {
		const { names } = await resolveContractCodes(localStorage.token, codes);
		if (current.userId === userId)
			contractNames.update((s) => ({ ...s, names: { ...s.names, ...names } }));
	} catch {
		// Codes stay as codes.
	}
};

// Used by the message renderer. Asks the server for codes it has not seen, once each, batched.
export const withContractNames = (state: State, text: string): string => {
	if (!state.allowed || typeof text !== 'string' || !text.includes('Perorangan ')) return text;
	for (const code of findCodes(text)) {
		if (!asked.has(code)) {
			asked.add(code);
			queued.add(code);
		}
	}
	if (queued.size && !timer) timer = setTimeout(flush, 300);
	return applyNames(text, state.names);
};
