import { WEBUI_API_BASE_URL } from '$lib/constants';

// The knowledge-base review queue (backend/open_webui/routers/jup_kb_review.py, ADR-0015).
// Staff with the `jup.kb.submit` grant submit documents; admins approve or reject them. An approved
// document goes into the separate "JUP Staff Contributions" collection, never the Strategy KB.

export type SubmissionState = 'pending' | 'approved' | 'rejected';
export type QueueFilter = SubmissionState | 'all';

export type KbReviewCapabilities = {
	submit: boolean;
	review: boolean;
};

export type Submission = {
	file_id: string;
	filename: string;
	content_type: string | null;
	size: number | null;
	state: SubmissionState;
	note: string | null;
	submitted_by: string;
	submitted_by_name?: string | null;
	submitted_at: number; // seconds
	reviewed_by: string | null;
	reviewed_by_name?: string | null;
	reviewed_at: number | null; // seconds
	reason: string | null;
	knowledge_id: string | null;
	// The text differs from what was submitted: the owner edited it through the files API.
	changed_since_review: boolean | null;
};

export type SubmissionDetail = Submission & {
	preview: { text: string; truncated: boolean; length: number };
	// Sent back with an approval, so the server approves the text the reviewer actually read.
	content_sha256: string;
};

// Carries the status and the server's stable refusal code, so the page can say what went wrong in
// the reader's language instead of echoing an English sentence.
export class KbReviewRequestError extends Error {
	readonly status: number;
	readonly code: string | null;

	constructor(status: number, code: string | null, message: string) {
		super(message);
		this.name = 'KbReviewRequestError';
		this.status = status;
		this.code = code;
	}

	// 403: signed in, understood, and still no. A 401 is the app's own session handling.
	get isAccessDenied(): boolean {
		return this.status === 403;
	}
}

const request = async <T>(
	token: string,
	path: string,
	init: { method?: string; body?: unknown; signal?: AbortSignal } = {}
): Promise<T> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/kb-review${path}`, {
		method: init.method ?? 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: init.body === undefined ? undefined : JSON.stringify(init.body),
		signal: init.signal
	});

	if (!res.ok) {
		const body = await res.json().catch(() => null);
		const detail = body?.detail;
		const code = typeof detail?.code === 'string' ? detail.code : null;
		const message =
			typeof detail?.message === 'string'
				? detail.message
				: typeof detail === 'string'
					? detail
					: `The review request failed (${res.status}).`;
		throw new KbReviewRequestError(res.status, code, message);
	}

	return res.json();
};

export const getKbReviewCapabilities = (token: string, signal?: AbortSignal) =>
	request<KbReviewCapabilities>(token, '/capabilities', { signal });

export const getMySubmissions = (token: string) =>
	request<{ items: Submission[] }>(token, '/submissions/mine');

export const getReviewQueue = (token: string, state: QueueFilter = 'pending') =>
	request<{ items: Submission[] }>(token, `/submissions?state=${encodeURIComponent(state)}`);

export const getSubmission = (token: string, fileId: string) =>
	request<SubmissionDetail>(token, `/submissions/${encodeURIComponent(fileId)}`);

export const submitForReview = (token: string, fileId: string, note: string | null) =>
	request<Submission>(token, '/submissions', { method: 'POST', body: { file_id: fileId, note } });

export const approveSubmission = (token: string, fileId: string, contentSha256: string) =>
	request<Submission>(token, `/submissions/${encodeURIComponent(fileId)}/approve`, {
		method: 'POST',
		body: { content_sha256: contentSha256 }
	});

export const rejectSubmission = (token: string, fileId: string, reason: string) =>
	request<Submission>(token, `/submissions/${encodeURIComponent(fileId)}/reject`, {
		method: 'POST',
		body: { reason }
	});
