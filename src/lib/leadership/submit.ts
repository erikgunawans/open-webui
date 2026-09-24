import type { ClosureKind, RecordActionState } from '$lib/apis/leadership';

// The PIC's evidence form, checked before it is sent. The server applies the same rules and is
// the one that counts; this only saves a round trip and names the problem next to the field.

export type EvidencePurpose = 'evidence' | ClosureKind;

export type EvidenceInput = {
	purpose: EvidencePurpose;
	mode: 'file' | 'link';
	file: File | null;
	url: string;
	reason: string;
	replacementActionId: string;
};

export type EvidenceProblem =
	| 'file_missing'
	| 'link_not_https'
	| 'reason_missing'
	| 'replacement_missing'
	| 'not_in_progress'
	| 'request_open';

// Which closure requests the action's state allows: completion only from in progress; cancellation
// and supersession from any open state; nothing while a request is already open or once closed.
export const allowedPurposes = (state: RecordActionState): EvidencePurpose[] => {
	if (state === 'closed' || state === 'awaiting_bod_closure') return ['evidence'];
	const purposes: EvidencePurpose[] = ['evidence'];
	if (state === 'in_progress') purposes.push('completed');
	purposes.push('cancelled', 'superseded');
	return purposes;
};

export const evidenceProblem = (
	input: EvidenceInput,
	state: RecordActionState
): EvidenceProblem | null => {
	if (input.mode === 'file' && !input.file) return 'file_missing';
	if (input.mode === 'link') {
		let url: URL | null = null;
		try {
			url = new URL(input.url.trim());
		} catch {
			url = null;
		}
		if (!url || url.protocol !== 'https:' || !url.host) return 'link_not_https';
	}
	if (input.purpose !== 'evidence') {
		if (state === 'awaiting_bod_closure') return 'request_open';
		if (input.purpose === 'completed' && state !== 'in_progress') return 'not_in_progress';
	}
	if (input.purpose === 'cancelled' && !input.reason.trim()) return 'reason_missing';
	if (input.purpose === 'superseded' && !input.replacementActionId.trim())
		return 'replacement_missing';
	return null;
};

// One key per opened form: a double click or a retry after a dropped response replays the same
// submission instead of recording it twice.
export const newIdempotencyKey = (): string =>
	typeof crypto !== 'undefined' && 'randomUUID' in crypto
		? crypto.randomUUID()
		: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

// A BOD decision, checked before it is sent (the server applies the same rules).
export type ReviewProblem = 'reason_missing' | 'return_to_missing' | 'no_evidence';

export const reviewProblem = (input: {
	decision: 'close' | 'return' | 'reopen';
	reason: string;
	returnTo: 'in_progress' | 'blocked' | null;
	evidenceId: string | null;
}): ReviewProblem | null => {
	if (input.decision !== 'reopen' && !input.evidenceId) return 'no_evidence';
	if (input.decision !== 'close' && !input.reason.trim()) return 'reason_missing';
	if (input.decision === 'return' && !input.returnTo) return 'return_to_missing';
	return null;
};
