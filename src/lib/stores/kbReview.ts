import { derived, writable, type Readable } from 'svelte/store';

import { getContractCapabilities } from '$lib/apis/contracts';
import { getKbReviewCapabilities } from '$lib/apis/kb-review';
import { user } from '$lib/stores';

// What the signed-in account may do in the knowledge-base review queue, for the sidebar entry and
// the page. Presentation only: the server re-checks the grant and the role on every request.
// Keyed to the user id, like `leadershipAccess`, so one account's capabilities never outlive it.
export type KbReviewAccess = {
	userId: string | null;
	loading: boolean;
	submit: boolean;
	review: boolean;
	// The contract cards tab: the `jup.contracts.review` grant (Legal), not the admin role.
	contracts: boolean;
};

const EMPTY: KbReviewAccess = {
	userId: null,
	loading: false,
	submit: false,
	review: false,
	contracts: false
};

const state = writable<KbReviewAccess>(EMPTY);

let controller: AbortController | null = null;

const load = async (userId: string) => {
	controller?.abort();
	const own = new AbortController();
	controller = own;
	state.set({ ...EMPTY, userId, loading: true });
	try {
		// Each source fails on its own: no contract tables must not hide the document queue.
		const [capabilities, contracts] = await Promise.all([
			getKbReviewCapabilities(localStorage.token, own.signal).catch(() => null),
			getContractCapabilities(localStorage.token, own.signal).catch(() => null)
		]);
		if (own.signal.aborted) return;
		state.set({
			userId,
			loading: false,
			submit: capabilities?.submit === true,
			review: capabilities?.review === true,
			contracts: contracts?.review === true
		});
	} catch {
		// A failure hides the entry. It must never disturb chat.
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

// Re-read on entering the page, so a grant made or revoked since sign-in shows up without a reload.
export const refreshKbReviewAccess = () => {
	if (current) load(current);
};

export const kbReviewAccess: Readable<KbReviewAccess> = derived(state, (value) => value);
