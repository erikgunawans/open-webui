import { WEBUI_API_BASE_URL } from '$lib/constants';

// Ruang Pimpinan's read API (P1). The server decides every grant on every request; nothing here
// is an access check, and a hidden sidebar entry is never the boundary.

export type LeadershipView = 'board' | 'rka';

export const LEADERSHIP_SCOPE = 'jup-consolidated';

export type Capabilities = {
	enabled: boolean;
	views: LeadershipView[];
	scope_ids: string[];
	// Empty in P1. Closure, publication and execution arrive as separate capabilities later.
	operations: string[];
	reason: string | null;
};

export type Unit = 'IDR_billion' | 'percent';

export type Reading = {
	// A decimal string, never a parsed float, so nothing on this side rounds a figure. `null` is
	// "unavailable" and always comes with a reason; zero is the string "0".
	value: string | null;
	unit: Unit;
	kind: 'actual' | 'budget' | 'forecast' | 'scenario';
	period_start: string;
	period_end: string;
	scope_id: string;
	missing_reason: string | null;
	definition_status: 'candidate' | 'approved';
};

export type Metric = {
	id: string;
	label: string;
	primary: Reading;
	baseline: Reading | null;
	comparison_kind: 'same_period_budget' | 'narrative_only' | 'prior_period';
	comparison_note: string | null;
	verification_status: 'unverified' | 'verified';
	source_ids: string[];
	// Actual minus budget, computed on the server and only for a like-for-like comparison.
	// Never an achievement ratio; `null` whenever the two readings are not comparable.
	variance: string | null;
};

export type Due =
	| { precision: 'month'; label: string; year: number; month: number }
	| { precision: 'year'; label: string; year: number }
	| { precision: 'year_range'; label: string; start_year: number; end_year: number }
	| { precision: 'date'; label: string; date: string };

export type Action = {
	id: string;
	title: string;
	owner_label: string;
	state: 'in_progress' | 'completion_submitted' | 'closed' | 'returned' | 'cancelled';
	source_as_of: string;
	due: Due;
	progress_summary: string;
	source_ids: string[];
	verification_status: 'unverified' | 'verified';
	history_complete: boolean;
	completion_evidence: unknown[];
	closure: unknown | null;
};

export type Assumption = {
	id: string;
	label: string;
	target_note: string;
	watch_note: string;
	source_ids: string[];
	action_ids: string[];
	verification_status: 'unverified' | 'verified';
};

export type ModuleState = {
	id: string;
	label: string;
	state: 'unavailable' | 'suggested' | 'source_example' | 'available';
	reason: string;
};

export type ReportingContext = {
	id: string;
	kind: 'current' | 'meeting' | 'source_example';
	workspace: LeadershipView;
	scope_id: string;
	period_start: string;
	period_end: string;
	label: string;
	report_status: string;
	source_ids: string[];
};

export type Overview = {
	schema_version: number;
	data_mode: 'illustrative';
	coverage: 'partial' | 'complete';
	revision: string;
	context: ReportingContext;
	metrics: Metric[];
	actions: Action[];
	assumptions: Assumption[];
	module_states: ModuleState[];
};

export type Source = {
	id: string;
	filename: string;
	document_date: string;
	physical_slides: number[];
	visibility: 'visible' | 'hidden';
	document_status: 'presented' | 'draft' | 'approved';
	verification_status: 'unverified' | 'verified';
};

// Kept apart by status so the page can say the right thing: 401 is a lost session (the app's
// own auth handling owns that), 403 is signed in and still no, 404 is a source this view does
// not cite, and 503 is a server that is not configured or whose data it refused to trust.
export class LeadershipRequestError extends Error {
	readonly status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = 'LeadershipRequestError';
		this.status = status;
	}

	get isAccessDenied(): boolean {
		return this.status === 403;
	}

	get isUnavailable(): boolean {
		return this.status === 503;
	}

	get isNotFound(): boolean {
		return this.status === 404;
	}
}

const request = async <T>(path: string, token: string, signal?: AbortSignal): Promise<T> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/leadership${path}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		},
		// The server already sends no-store; this keeps a shared browser cache out of it too.
		cache: 'no-store',
		signal
	});

	if (!res.ok) {
		const body = await res.json().catch(() => null);
		const detail = body?.detail ?? `The Ruang Pimpinan request failed (${res.status}).`;
		throw new LeadershipRequestError(
			res.status,
			typeof detail === 'string' ? detail : JSON.stringify(detail)
		);
	}

	return res.json();
};

const viewQuery = (view: LeadershipView, scopeId: string) =>
	new URLSearchParams({ view, scope_id: scopeId }).toString();

export const getCapabilities = (token: string, signal?: AbortSignal) =>
	request<Capabilities>('/capabilities', token, signal);

export const getOverview = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	signal?: AbortSignal
) => request<Overview>(`/overview?${viewQuery(view, scopeId)}`, token, signal);

export const getSource = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	sourceId: string,
	signal?: AbortSignal
) =>
	request<Source>(
		`/sources/${encodeURIComponent(sourceId)}?${viewQuery(view, scopeId)}`,
		token,
		signal
	);
