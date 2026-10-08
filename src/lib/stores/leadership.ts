import { derived, writable, type Readable } from 'svelte/store';

import { getCapabilities, type LeadershipView, type Operation } from '$lib/apis/leadership';
import { user } from '$lib/stores';

// What the signed-in reader may open in Ruang Pimpinan, for the sidebar entry and the section
// root. Presentation only: the server re-checks the grant on every read, so a stale value here
// can hide or show an entry but can never open a record.
//
// The state is keyed to the user id. When the account changes or signs out, the previous
// reader's views are dropped before anything new is fetched, so one person's grants are never
// shown to the next. No business data is held here.
export type LeadershipAccess = {
	userId: string | null;
	loading: boolean;
	enabled: boolean;
	views: LeadershipView[];
	scopeIds: string[];
	// What the reader may do beyond reading. Decides which forms are offered, never whether a
	// write is accepted: the server checks each capability on every request.
	operations: Operation[];
	// The server keeps records: Rapat Direksi then stores its meetings on the server.
	records: boolean;
};

const EMPTY: LeadershipAccess = {
	userId: null,
	loading: false,
	enabled: false,
	views: [],
	scopeIds: [],
	operations: [],
	records: false
};

const state = writable<LeadershipAccess>(EMPTY);

let controller: AbortController | null = null;

const load = async (userId: string) => {
	controller?.abort();
	const own = new AbortController();
	controller = own;
	state.set({ ...EMPTY, userId, loading: true });
	try {
		const capabilities = await getCapabilities(localStorage.token, own.signal);
		if (own.signal.aborted) return;
		state.set({
			userId,
			loading: false,
			enabled: capabilities.enabled,
			views: capabilities.views,
			scopeIds: capabilities.scope_ids,
			operations: capabilities.operations,
			records: capabilities.records === true
		});
	} catch {
		// Any failure leaves the entry unavailable. It must never disturb chat.
		if (!own.signal.aborted) state.set({ ...EMPTY, userId });
	}
};

let current: string | null = null;

user.subscribe((value) => {
	const id = value?.id ?? null;
	if (id === current) return;
	current = id;
	if (id === null) {
		controller?.abort();
		state.set(EMPTY);
		return;
	}
	load(id);
});

// Re-read on entering the section, so a grant made or revoked since sign-in shows up without a
// reload. The server stays the boundary either way.
export const refreshLeadershipAccess = () => {
	if (current) load(current);
};

export const leadershipAccess: Readable<LeadershipAccess> = derived(state, (value) => value);
