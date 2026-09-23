import type { LeadershipView } from '$lib/apis/leadership';

// The reporting contexts P1 can show, one per view. Each is a labelled example from a presented
// deck, not a published meeting record. A later stage adds real contexts; until then any other
// id in the URL is shown as unavailable rather than quietly swapped for this one.
export const SUPPORTED: Record<LeadershipView, { context: string; period: string; scope: string }> =
	{
		board: {
			context: 'example-board-2026-08',
			period: '2026-01-01/2026-08-31',
			scope: 'jup-consolidated'
		},
		rka: {
			context: 'example-rka-2027-draft-1',
			period: '2027-01-01/2027-12-31',
			scope: 'jup-consolidated'
		}
	};

const VIEW_ORDER: LeadershipView[] = ['board', 'rka'];

// Board opens first for a reader granted both; a reader granted one lands on that one.
export const defaultView = (views: LeadershipView[]): LeadershipView | null =>
	VIEW_ORDER.find((view) => views.includes(view)) ?? null;

export type ContextProblem = 'scope' | 'context' | 'period';

// Checks the identifiers a shared link carries. Omitted keys mean "this view's example"; a
// supplied key that does not match is a problem to show, never a silent fallback to another
// period. Returns the first key that does not fit, or null. `record` is checked by the page,
// which knows what the view contains.
export const validateContextQuery = (
	search: URLSearchParams,
	view: LeadershipView
): ContextProblem | null => {
	const supported = SUPPORTED[view];
	for (const key of ['scope', 'context', 'period'] as const) {
		const value = search.get(key);
		if (value !== null && value !== supported[key]) return key;
	}
	return null;
};
