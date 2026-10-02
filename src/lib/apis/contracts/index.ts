import { WEBUI_API_BASE_URL } from '$lib/constants';

// The contract knowledge base (backend/open_webui/routers/jup_contracts.py). Phase 1a: the title
// column in Admin → Pengguna (D3). A title is one of four managed groups whose `jup.contracts`
// grants are fixed by the server; admins set it, and the server re-checks the role on every call.

export type ContractTitle = 'direksi' | 'legal' | 'manager' | 'staff';

export type ContractTitles = {
	titles: { key: ContractTitle; label: string }[];
	// User id → the titles held. More than one means a group was edited by hand.
	users: Record<string, ContractTitle[]>;
};

export class ContractsRequestError extends Error {
	readonly status: number;
	readonly code: string | null;

	constructor(status: number, code: string | null, message: string) {
		super(message);
		this.name = 'ContractsRequestError';
		this.status = status;
		this.code = code;
	}
}

const request = async <T>(
	token: string,
	path: string,
	init: { method?: string; body?: unknown; signal?: AbortSignal } = {}
): Promise<T> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/contracts${path}`, {
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
				: `The contracts request failed (${res.status}).`;
		throw new ContractsRequestError(res.status, code, message);
	}

	return res.json();
};

export const getContractTitles = (token: string, signal?: AbortSignal) =>
	request<ContractTitles>(token, '/titles', { signal });

export const setContractTitle = (token: string, userId: string, title: ContractTitle | null) =>
	request<{ user_id: string; titles: ContractTitle[] }>(
		token,
		`/titles/${encodeURIComponent(userId)}`,
		{ method: 'PUT', body: { title } }
	);

export type ContractCapabilities = {
	cards: boolean;
	money: boolean;
	fulltext: boolean;
	names: boolean;
	review: boolean;
};

export const getContractCapabilities = (token: string, signal?: AbortSignal) =>
	request<ContractCapabilities>(token, '/capabilities', { signal });

// Names only for a reader holding the `names` grant; anyone else gets an empty map.
export const resolveContractCodes = (token: string, codes: string[]) =>
	request<{ names: Record<string, string> }>(token, '/parties/resolve', {
		method: 'POST',
		body: { codes }
	});

// --- Review (phase 2): the "Kartu Kontrak" tab. The `review` grant (Legal); every write names the
// version it was made against, and a stale one is refused with 409 `conflict`.

export type ContractState = 'draft' | 'approved' | 'returned';
export type ContractFlag = 'perorangan' | 'manual' | 'low_ocr';

export type ContractField = { isi: string; halaman: number[] };
export type ContractCard = Record<string, ContractField | string[] | number[]>;

export type ContractSummary = {
	id: string;
	run: string;
	number: string;
	partner: string | null;
	contract_number: string | null;
	title: string | null;
	doc_type: string | null;
	state: ContractState;
	version: number;
	end_date: string | null;
	units: string[];
	individuals: number;
	manual_pages: number;
	low_ocr_pages: number;
	updated_at: number;
};

export type ContractQueue = {
	total: number;
	limit: number;
	offset: number;
	counts: Record<ContractFlag | ContractState, number>;
	items: ContractSummary[];
};

export type ContractEvent = {
	id: string;
	version: number;
	kind: string;
	payload: Record<string, unknown>;
	reason: string | null;
	actor: string;
	at: number;
};

export type ContractLink = {
	id: string;
	run: string;
	number: string;
	title: string | null;
	kind: 'addendum' | 'related';
	// `related`: the other document is tied to this one; `main`: this one is tied to it.
	direction: 'related' | 'main';
};

export type ContractDetail = {
	contract: ContractSummary & {
		start_date: string | null;
		auto_renewal: boolean | null;
		page_count: number;
		manual_check_pages: number[];
		low_confidence_pages: number[];
		model: string | null;
	};
	card: ContractCard | null;
	card_sha256: string | null;
	draft_card: ContractCard | null;
	// `name` is null for a reviewer without the `names` grant.
	parties: { code: string; name: string | null }[];
	links: ContractLink[];
	events: ContractEvent[];
};

export type ContractPage = { halaman: number; teks: string; ocr_rendah: boolean };

export type ContractQueueQuery = {
	state?: ContractState;
	flag?: ContractFlag;
	q?: string;
	limit?: number;
	offset?: number;
};

const query = (params: ContractQueueQuery) => {
	const search = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		if (value !== undefined && value !== '') search.set(key, `${value}`);
	}
	const text = search.toString();
	return text ? `?${text}` : '';
};

const reviewPath = (id: string, rest = '') => `/review/${encodeURIComponent(id)}${rest}`;

export const getContractQueue = (token: string, params: ContractQueueQuery, signal?: AbortSignal) =>
	request<ContractQueue>(token, `/review/queue${query(params)}`, { signal });

export const getContractReview = (token: string, id: string, signal?: AbortSignal) =>
	request<ContractDetail>(token, reviewPath(id), { signal });

export const getContractReviewPages = (token: string, id: string, signal?: AbortSignal) =>
	request<{ pages: ContractPage[] }>(token, reviewPath(id, '/pages'), { signal });

export const editContractField = (
	token: string,
	id: string,
	body: { version: number; field: string; text: string; pages: number[] }
) =>
	request<{ version: number; state: ContractState; changed: boolean }>(
		token,
		reviewPath(id, '/field'),
		{ method: 'PATCH', body }
	);

export const approveContract = (token: string, id: string, version: number, cardSha256: string) =>
	request<{ version: number; state: ContractState }>(token, reviewPath(id, '/approve'), {
		method: 'POST',
		body: { version, card_sha256: cardSha256 }
	});

export const returnContract = (token: string, id: string, version: number, reason: string) =>
	request<{ version: number; state: ContractState }>(token, reviewPath(id, '/return'), {
		method: 'POST',
		body: { version, reason }
	});

export const setContractUnits = (token: string, id: string, version: number, units: string[]) =>
	request<{ version: number }>(token, reviewPath(id, '/units'), {
		method: 'PUT',
		body: { version, units }
	});

export const setContractDates = (
	token: string,
	id: string,
	body: { version: number; start: string | null; end: string | null; auto_renewal: boolean | null }
) => request<{ version: number }>(token, reviewPath(id, '/dates'), { method: 'PUT', body });

export const setContractParties = (token: string, id: string, version: number, names: string[]) =>
	request<{ version: number }>(token, reviewPath(id, '/parties'), {
		method: 'PUT',
		body: { version, names }
	});

export const linkContract = (
	token: string,
	id: string,
	version: number,
	relatedId: string,
	kind: 'addendum' | 'related'
) =>
	request<{ version: number }>(token, reviewPath(id, '/links'), {
		method: 'POST',
		body: { version, related_id: relatedId, kind }
	});

export const unlinkContract = (token: string, id: string, relatedId: string, version: number) =>
	request<{ version: number }>(
		token,
		reviewPath(id, `/links/${encodeURIComponent(relatedId)}?version=${version}`),
		{ method: 'DELETE' }
	);

export const contractPdfUrl = (run: string, number: string) =>
	`${WEBUI_API_BASE_URL}/contracts/${encodeURIComponent(run === 'full' ? number : `${run}-${number}`)}/pdf`;
