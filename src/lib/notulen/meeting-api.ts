import { MeetingApiError, type MeetingApi, type StoredMeeting } from './server-repo';
import type { Meeting } from './types';

// The leadership API's meeting routes (`/leadership/meetings`), as the server repository needs
// them. The server decides every grant on every request; a refusal arrives here as a
// MeetingApiError carrying the HTTP status (0 when the server was not reached) and, on a 409, the
// stored revision.

export type MeetingApiOptions = {
	/** The app's API base, `WEBUI_API_BASE_URL`. */
	base: string;
	token: string;
	scopeId: string;
	fetch?: typeof fetch;
};

export const httpMeetingApi = (o: MeetingApiOptions): MeetingApi => {
	const query = `?scope_id=${encodeURIComponent(o.scopeId)}`;
	const url = (id?: string) =>
		`${o.base}/leadership/meetings${id === undefined ? '' : `/${encodeURIComponent(id)}`}${query}`;

	const call = async (method: string, target: string, json?: unknown): Promise<Response> => {
		let res: Response;
		try {
			res = await (o.fetch ?? fetch)(target, {
				method,
				headers: {
					authorization: `Bearer ${o.token}`,
					...(json === undefined ? {} : { 'Content-Type': 'application/json' })
				},
				body: json === undefined ? undefined : JSON.stringify(json),
				cache: 'no-store'
			});
		} catch (error) {
			throw new MeetingApiError(0, `The server could not be reached: ${error}`);
		}
		if (res.ok) return res;
		const body = await res.json().catch(() => null);
		const detail = body?.detail;
		const message =
			typeof detail === 'string'
				? detail
				: typeof detail?.message === 'string'
					? detail.message
					: `The meeting request failed (${res.status}).`;
		const revision = typeof detail?.revision === 'number' ? detail.revision : undefined;
		throw new MeetingApiError(res.status, message, revision);
	};

	return {
		list: async () =>
			((await (await call('GET', url())).json()) as { meetings: StoredMeeting[] }).meetings,
		get: async (id) => {
			try {
				return (await (await call('GET', url(id))).json()) as StoredMeeting;
			} catch (error) {
				if (error instanceof MeetingApiError && error.status === 404) return null;
				throw error;
			}
		},
		create: async (meeting: Meeting) => (await call('POST', url(), { document: meeting })).json(),
		save: async (id, baseRevision, meeting: Meeting) =>
			(await call('PUT', url(id), { base_revision: baseRevision, document: meeting })).json()
	};
};
