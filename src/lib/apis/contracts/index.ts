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
