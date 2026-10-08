import { WEBUI_API_BASE_URL } from '$lib/constants';

// Ruang Pimpinan's read API (P1). The server decides every grant on every request; nothing here
// is an access check, and a hidden sidebar entry is never the boundary.

export type LeadershipView = 'board' | 'rka';

export const LEADERSHIP_SCOPE = 'jup-consolidated';

export type Operation =
	| 'actions.submit'
	| 'actions.assign'
	| 'bod.review'
	| 'snapshots.publish'
	| 'imports.review'
	// Writing Rapat Direksi Notulen (the Corsec).
	| 'rapat.write';

export type Capabilities = {
	enabled: boolean;
	views: LeadershipView[];
	scope_ids: string[];
	// Each is its own grant on top of a view grant. `bod.review` and `snapshots.publish` are
	// listed only while the server has the matching policy configured.
	operations: Operation[];
	// The server keeps records (actions, Rapat Direksi meetings) rather than the illustrative sample.
	records: boolean;
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

// The sample's states (P1) and the records store's lifecycle (P2). Which set a view serves is
// the overview's `actions_source`; a component must render every one of them.
export type SampleActionState =
	| 'in_progress'
	| 'completion_submitted'
	| 'closed'
	| 'returned'
	| 'cancelled';
export type RecordActionState =
	| 'not_started'
	| 'in_progress'
	| 'blocked'
	| 'awaiting_bod_closure'
	| 'closed';
export type ActionState = SampleActionState | RecordActionState;

export type ClosureKind = 'completed' | 'cancelled' | 'superseded';

// A records-mode action's latest closure request. The sample's closure is opaque.
export type ClosureRequestView = {
	request_id: string;
	kind: ClosureKind;
	status: 'open' | 'closed' | 'returned';
	replacement_action_id: string | null;
};

export type Action = {
	id: string;
	title: string;
	owner_label: string;
	state: ActionState;
	source_as_of: string;
	// `null` in records mode when no due date is recorded; never guessed.
	due: Due | null;
	// `null` in records mode until the PIC's first progress update.
	progress_summary: string | null;
	source_ids: string[];
	verification_status: 'unverified' | 'verified';
	history_complete: boolean;
	completion_evidence: unknown[];
	closure: ClosureRequestView | unknown | null;
	// Present only on records-mode actions.
	record?: {
		version: number;
		pic_user_id: string | null;
		original_due: Due | null;
		evidence_revisions: number;
	};
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
	// Where `actions` came from: the dataset's sample, or the records store. Server setting only.
	actions_source: 'sample' | 'records';
	// Why a records-mode view has no action; `null` otherwise.
	actions_note: string | null;
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
// not cite, 409 is a record that moved since it was opened, 422 is a refused command, and 503 is
// a server that is not configured or whose data it refused to trust.
export class LeadershipRequestError extends Error {
	readonly status: number;
	// A 409's structured detail: the version or evidence revision the record is actually at.
	readonly conflict: { version?: number; evidence_id?: string } | null;

	constructor(
		status: number,
		message: string,
		conflict: { version?: number; evidence_id?: string } | null = null
	) {
		super(message);
		this.name = 'LeadershipRequestError';
		this.status = status;
		this.conflict = conflict;
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

	get isConflict(): boolean {
		return this.status === 409;
	}

	get isRefused(): boolean {
		return this.status === 422;
	}
}

const failure = async (res: Response): Promise<LeadershipRequestError> => {
	const body = await res.json().catch(() => null);
	const detail = body?.detail ?? `The Ruang Pimpinan request failed (${res.status}).`;
	if (typeof detail === 'string') return new LeadershipRequestError(res.status, detail);
	// The server's 409s carry {message, version} or {message, evidence_id}.
	if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
		const { message, version, evidence_id } = detail;
		return new LeadershipRequestError(res.status, message, {
			...(typeof version === 'number' ? { version } : {}),
			...(typeof evidence_id === 'string' ? { evidence_id } : {})
		});
	}
	return new LeadershipRequestError(res.status, JSON.stringify(detail));
};

const send = async (
	path: string,
	token: string,
	init: { method?: 'GET' | 'POST'; body?: BodyInit; json?: unknown; signal?: AbortSignal } = {}
): Promise<Response> => {
	const headers: Record<string, string> = { authorization: `Bearer ${token}` };
	let body = init.body;
	if (init.json !== undefined) {
		headers['Content-Type'] = 'application/json';
		body = JSON.stringify(init.json);
	}
	const res = await fetch(`${WEBUI_API_BASE_URL}/leadership${path}`, {
		method: init.method ?? 'GET',
		headers,
		body,
		// The server already sends no-store; this keeps a shared browser cache out of it too.
		cache: 'no-store',
		signal: init.signal
	});
	if (!res.ok) throw await failure(res);
	return res;
};

const request = async <T>(path: string, token: string, signal?: AbortSignal): Promise<T> =>
	(await send(path, token, { signal })).json();

const post = async <T>(
	path: string,
	token: string,
	json: unknown,
	signal?: AbortSignal
): Promise<T> => (await send(path, token, { method: 'POST', json, signal })).json();

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

// --- KPI 2026 (rides on the RKA read grant) ---------------------------------------------

export type KpiPerspective = { id: string; name: string; weight: number };

export type KpiItem = {
	id: string;
	p: string;
	so_k: string;
	so_d: string;
	name: string;
	definition: string;
	satuan: string;
	unit: 'rp' | 'pct' | 'count';
	formula: string;
	target: number;
	weight: number;
	monitoring: string;
	cum: boolean;
};

export type KpiCatalogue = {
	year: number;
	source: string;
	sample_is_illustrative: boolean;
	perspectives: KpiPerspective[];
	items: KpiItem[];
	sample: Record<string, (number | null)[]>;
};

export const getKpi = (token: string, scopeId: string, signal?: AbortSignal) =>
	request<KpiCatalogue>(
		`/kpi?${new URLSearchParams({ scope_id: scopeId }).toString()}`,
		token,
		signal
	);

// --- The action record (P2 T2, T7) ----------------------------------------------------------

// The records store's own due shape: `value` is `YYYY-MM-DD`, `YYYY-MM`, `YYYY` or `YYYY/YYYY`.
export type RecordedDue = { precision: Due['precision']; value: string };

export type ActionEventKind =
	| 'created'
	| 'state_changed'
	| 'due_revised'
	| 'progress_submitted'
	| 'evidence_submitted'
	| 'bod_decision'
	| 'pic_assigned'
	| (string & {});

export type HistoryEvent = {
	version: number;
	kind: ActionEventKind;
	author: string;
	// The author's display name from the host's user directory; null when they are no longer in it.
	author_name: string | null;
	// Epoch milliseconds.
	at: number;
	reason: string | null;
	payload: Record<string, unknown>;
	state_before: RecordActionState | null;
	state_after: RecordActionState | null;
	due_before: RecordedDue | null;
	due_after: RecordedDue | null;
};

// Derived beside the state, never instead of it. `null` is "cannot say", with a reason.
export type ActionFlags = {
	overdue: boolean | null;
	days_overdue: number | null;
	due_before_next_meeting: boolean | null;
	stale: boolean | null;
	reasons: Record<string, string>;
};

export type ActionRecord = {
	action: {
		id: string;
		title: string;
		pic_label: string;
		pic_user_id: string | null;
		state: RecordActionState;
		original_due: RecordedDue | null;
		current_due: RecordedDue | null;
		version: number;
		created_at: number;
		updated_at: number;
	};
	flags: ActionFlags;
	// An `evidence_submitted` event's `payload.evidence` names its revision as `evidence_id`.
	history: HistoryEvent[];
	// Every evidence revision, oldest first, in the evidence route's own shape.
	evidence: Evidence[];
};

export const getAction = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	signal?: AbortSignal
) =>
	request<ActionRecord>(
		`/actions/${encodeURIComponent(actionId)}?${viewQuery(view, scopeId)}`,
		token,
		signal
	);

// --- The PIC's writes (P2 T3) ---------------------------------------------------------------

export type ProgressForm = {
	expected_version: number;
	narrative: string;
	milestones_completed?: string[];
	remaining_work?: string | null;
	blocker?: string | null;
	next_step?: string | null;
	reported_at?: string | null;
	idempotency_key?: string | null;
};

export type ProgressResult = {
	action_id: string;
	version: number;
	event_id: string;
	replayed: boolean;
};

export const postProgress = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	form: ProgressForm
) =>
	post<ProgressResult>(
		`/actions/${encodeURIComponent(actionId)}/progress?${viewQuery(view, scopeId)}`,
		token,
		form
	);

// The owner's own moves: start, block (reason required) and unblock. Closing is the BOD's.
export type StateForm = {
	expected_version: number;
	to_state: 'in_progress' | 'blocked';
	reason?: string | null;
	idempotency_key?: string | null;
};

export const postState = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	form: StateForm
) =>
	post<ProgressResult>(
		`/actions/${encodeURIComponent(actionId)}/state?${viewQuery(view, scopeId)}`,
		token,
		form
	);

export type Evidence = {
	id: string;
	action_id: string;
	revision: number;
	kind: 'file' | 'link';
	url: string | null;
	filename: string | null;
	content_type: string | null;
	size_bytes: number | null;
	sha256: string | null;
	submitted_by: string;
	created_at: number;
};

// Exactly one of `file` or `url`. `closure_kind` (or `completion`) opens a closure request on
// this revision: cancelled needs a `reason`, superseded names `replacement_action_id`.
export type EvidenceForm = {
	expected_version: number;
	completion?: boolean;
	closure_kind?: ClosureKind | null;
	reason?: string | null;
	replacement_action_id?: string | null;
	note?: string | null;
	idempotency_key?: string | null;
} & ({ file: File; url?: never } | { url: string; file?: never });

export type EvidenceResult = {
	action_id: string;
	version: number;
	replayed: boolean;
	closure_request_id: string | null;
	evidence: Evidence;
};

export const evidenceFormData = (form: EvidenceForm): FormData => {
	const data = new FormData();
	data.set('expected_version', String(form.expected_version));
	if (form.completion) data.set('completion', 'true');
	const optional = [
		'closure_kind',
		'reason',
		'replacement_action_id',
		'note',
		'idempotency_key',
		'url'
	] as const;
	for (const key of optional) {
		const value = form[key];
		if (value !== undefined && value !== null && value !== '') data.set(key, value);
	}
	if (form.file) data.set('file', form.file, form.file.name);
	return data;
};

export const postEvidence = async (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	form: EvidenceForm
): Promise<EvidenceResult> =>
	(
		await send(
			`/actions/${encodeURIComponent(actionId)}/evidence?${viewQuery(view, scopeId)}`,
			token,
			{
				method: 'POST',
				body: evidenceFormData(form)
			}
		)
	).json();

// A link revision answers with its metadata; a file revision with the file itself.
export type EvidenceDownload =
	| { kind: 'link'; evidence: Evidence }
	| { kind: 'file'; blob: Blob; filename: string };

export const filenameFromDisposition = (header: string | null): string | null => {
	const match = header ? /filename\*=UTF-8''([^;]+)/i.exec(header) : null;
	if (!match) return null;
	try {
		return decodeURIComponent(match[1]);
	} catch {
		return null;
	}
};

export const getEvidence = async (
	token: string,
	view: LeadershipView,
	scopeId: string,
	evidenceId: string,
	signal?: AbortSignal
): Promise<EvidenceDownload> => {
	const res = await send(
		`/evidence/${encodeURIComponent(evidenceId)}?${viewQuery(view, scopeId)}`,
		token,
		{ signal }
	);
	if (res.headers.get('Content-Disposition')?.startsWith('attachment')) {
		const filename = filenameFromDisposition(res.headers.get('Content-Disposition')) ?? 'evidence';
		return { kind: 'file', blob: await res.blob(), filename };
	}
	return { kind: 'link', evidence: await res.json() };
};

// --- Who the PIC is -------------------------------------------------------------------------

// The person by the email they sign in with; the server stores their user id. Replacing a PIC
// needs a reason; a first assignment does not.
export type PicAssignForm = {
	expected_version: number;
	pic_email: string;
	pic_label?: string | null;
	reason?: string | null;
	idempotency_key?: string | null;
};

export const postPicAssignment = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	form: PicAssignForm
) =>
	post<{ action_id: string; version: number; replayed: boolean }>(
		`/actions/${encodeURIComponent(actionId)}/pic?${viewQuery(view, scopeId)}`,
		token,
		form
	);

// A BOD member moves the due date with a reason; the original is kept (Erik, 2026-09-24).
export type DueRevisionForm = {
	expected_version: number;
	due: { precision: 'date' | 'month' | 'year' | 'year_range'; value: string };
	reason: string;
	idempotency_key?: string | null;
};

export const postDueRevision = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	form: DueRevisionForm
) =>
	post<ProgressResult>(
		`/actions/${encodeURIComponent(actionId)}/due?${viewQuery(view, scopeId)}`,
		token,
		form
	);

// --- The BOD's decisions (P2 T4) ------------------------------------------------------------

export type ClosureDecisionForm = {
	expected_version: number;
	decision: 'close' | 'return' | 'reopen';
	// The evidence revision the reviewer looked at; required to close or return.
	evidence_id?: string | null;
	reason?: string | null;
	return_to?: 'in_progress' | 'blocked' | null;
	idempotency_key?: string | null;
};

export type ClosureDecisionResult = {
	action_id: string;
	version: number;
	replayed: boolean;
	decision_id: string;
	outcome: 'closed' | 'vote_recorded' | 'returned' | 'reopened';
	close_votes: number;
	quorum: number;
};

export const postClosureDecision = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	actionId: string,
	form: ClosureDecisionForm
) =>
	post<ClosureDecisionResult>(
		`/actions/${encodeURIComponent(actionId)}/closure?${viewQuery(view, scopeId)}`,
		token,
		form
	);

// --- Meeting snapshots and RKA records (P2 T5) ----------------------------------------------

export type SnapshotVersion = {
	id: string;
	snapshot_id: string;
	view: LeadershipView;
	meeting_label: string;
	meeting_date: string | null;
	version: number;
	state: 'draft' | 'published';
	change_kind: 'draft' | 'publication' | 'correction';
	previous_version_id: string | null;
	content_hash: string;
	created_by: string;
	created_at: number;
};

export type SnapshotListItem = {
	latest: SnapshotVersion;
	// The meeting record; `null` while every version is a draft.
	published: SnapshotVersion | null;
};

// What a snapshot froze: the view's overview as it was served, plus the sources it cited. A
// sample-mode action carries `record` (its frozen event state) or `null` when it had none.
export type SnapshotContent = Overview & {
	view: LeadershipView;
	sources: Source[];
	actions: (Action & { record?: Record<string, unknown> | null })[];
};

export type SnapshotWithContent = SnapshotVersion & { content: SnapshotContent };

export type SnapshotDetail = {
	versions: SnapshotVersion[];
	// Never the draft in its place: `null` until something is published.
	published: SnapshotWithContent | null;
	latest: SnapshotWithContent;
};

export const getSnapshots = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	signal?: AbortSignal
) =>
	request<{ view: LeadershipView; snapshots: SnapshotListItem[] }>(
		`/snapshots?${viewQuery(view, scopeId)}`,
		token,
		signal
	);

// The last meeting record of one view against the one before it. Unavailable, never empty, until
// two meetings are published. A difference is the server's decimal arithmetic, and only between
// readings of the same unit, kind and scope; otherwise `difference_note` says which one differed.
export type MetricChange = {
	id: string;
	label: string;
	change: 'changed' | 'unchanged' | 'added' | 'removed';
	before: Reading | null;
	after: Reading | null;
	difference: string | null;
	difference_note: 'missing' | 'unit' | 'kind' | 'scope' | null;
};

export type ActionBrief = { id: string; title: string; state: string; due: string | null };

export type ActionChange = {
	id: string;
	title: string;
	state_before: string;
	state_after: string;
	due_before: string | null;
	due_after: string | null;
};

export type MeetingChanges =
	| { view: LeadershipView; available: false; published_meetings: number }
	| {
			view: LeadershipView;
			available: true;
			before: SnapshotVersion;
			after: SnapshotVersion;
			metrics: MetricChange[];
			// False when the two meetings froze actions from different sources (sample or records).
			actions_comparable: boolean;
			actions_source: 'sample' | 'records';
			actions: { added: ActionBrief[]; removed: ActionBrief[]; changed: ActionChange[] };
	  };

export const getMeetingChanges = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	signal?: AbortSignal
) => request<MeetingChanges>(`/meeting-changes?${viewQuery(view, scopeId)}`, token, signal);

export const getSnapshot = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	snapshotId: string,
	signal?: AbortSignal
) =>
	request<SnapshotDetail>(
		`/snapshots/${encodeURIComponent(snapshotId)}?${viewQuery(view, scopeId)}`,
		token,
		signal
	);

export const postSnapshotDraft = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	form: { meeting_label: string; meeting_date?: string | null }
) => post<SnapshotVersion>(`/snapshots?${viewQuery(view, scopeId)}`, token, form);

export const postSnapshotPublish = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	snapshotId: string,
	// The hash of the draft the publisher reviewed; anything else is a 409.
	form: { expected_version: number; content_hash: string }
) =>
	post<SnapshotVersion>(
		`/snapshots/${encodeURIComponent(snapshotId)}/publish?${viewQuery(view, scopeId)}`,
		token,
		form
	);

export type RkaRecord = {
	id: string;
	record_kind: 'baseline' | 'revision' | 'forecast';
	label: string;
	period_start: string;
	period_end: string;
	supersedes_id: string | null;
	content: Record<string, unknown>;
	content_hash: string;
	approved_by: string | null;
	approved_at: number | null;
	created_by: string;
	created_at: number;
};

export const getBaselines = (token: string, scopeId: string, signal?: AbortSignal) =>
	request<{ records: RkaRecord[] }>(
		`/baselines?${new URLSearchParams({ scope_id: scopeId }).toString()}`,
		token,
		signal
	);

// --- Reviewed imports (P2 T6) ---------------------------------------------------------------

export type ImportBatch = {
	id: string;
	source_filename: string;
	source_sha256: string;
	meeting_date: string | null;
	status: 'open' | 'reviewed';
	uploaded_by: string;
	created_at: number;
};

// One action as the deck states it. A null value always has its reason under `missing`.
export type CandidatePayload = {
	key: string;
	slide: string;
	external_id: string;
	title: string;
	owner_label: string | null;
	due: RecordedDue | null;
	state: RecordActionState | null;
	progress_summary: string | null;
	source_metadata: Record<string, unknown>;
	missing: Partial<Record<'owner_label' | 'due' | 'state' | 'progress_summary', string>>;
	source_document: string;
};

export type ImportCandidate = {
	id: string;
	candidate_key: string;
	match_kind: 'external_ref' | 'new' | 'conflict';
	matched_action_id: string | null;
	conflict: Record<string, unknown> | null;
	review_state: 'pending' | 'accepted' | 'acknowledged' | 'linked' | 'rejected';
	reviewed_by: string | null;
	reviewed_at: number | null;
	// Only a review makes a record verified; a claim inside the file never does.
	verification: 'verified' | 'unverified';
	payload: CandidatePayload;
};

export type ImportBatchDetail = ImportBatch & { candidates: ImportCandidate[] };

export const postImport = async (
	token: string,
	view: LeadershipView,
	scopeId: string,
	file: File
): Promise<{ batch_id: string; created: boolean }> => {
	const body = new FormData();
	body.set('file', file, file.name);
	return (
		await send(`/imports?${viewQuery(view, scopeId)}`, token, { method: 'POST', body })
	).json();
};

export const getImports = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	signal?: AbortSignal
) => request<{ batches: ImportBatch[] }>(`/imports?${viewQuery(view, scopeId)}`, token, signal);

export const getImport = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	batchId: string,
	signal?: AbortSignal
) =>
	request<ImportBatchDetail>(
		`/imports/${encodeURIComponent(batchId)}?${viewQuery(view, scopeId)}`,
		token,
		signal
	);

export const postCandidateReview = (
	token: string,
	view: LeadershipView,
	scopeId: string,
	candidateId: string,
	form: { decision: 'accept' | 'link' | 'reject'; action_id?: string | null }
) =>
	post<{
		candidate_id: string;
		review_state: ImportCandidate['review_state'];
		action_id: string | null;
	}>(
		`/imports/candidates/${encodeURIComponent(candidateId)}/review?${viewQuery(view, scopeId)}`,
		token,
		form
	);
