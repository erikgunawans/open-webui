import type { Action, ActionState, ClosureRequestView, Overview } from '$lib/apis/leadership';

// Reading an action the same way in both data modes. Labels stay in the components, where the
// i18n extractor can see their literal `$i18n.t('...')` calls; these only decide which one.

// Everything but a closed or cancelled action still needs someone's attention.
export const isOpenAction = (state: ActionState): boolean =>
	state !== 'closed' && state !== 'cancelled';

// A records-mode action's latest closure request, or null. The sample's closure is opaque.
export const closureRequest = (action: Action): ClosureRequestView | null => {
	const closure = action.closure as Partial<ClosureRequestView> | null;
	return closure && typeof closure === 'object' && typeof closure.request_id === 'string'
		? (closure as ClosureRequestView)
		: null;
};

export type ClosureNote = 'recorded' | 'requested' | 'returned' | 'closed' | 'none';

// What the register says about BOD closure, for either mode.
export const closureNote = (action: Action): ClosureNote => {
	const request = closureRequest(action);
	if (request) {
		if (request.status === 'open') return 'requested';
		return request.status === 'closed' ? 'closed' : 'returned';
	}
	return action.closure ? 'recorded' : 'none';
};

// The sample is a handful of examples from a deck; the records store is the register.
export const isSampleRegister = (overview: Pick<Overview, 'actions_source'>): boolean =>
	overview.actions_source !== 'records';

// The BOD's queue: recorded actions whose closure request is waiting for a decision.
export const awaitingReview = (actions: Action[]): Action[] =>
	actions.filter((action) => action.state === 'awaiting_bod_closure');
