import { describe, expect, it } from 'vitest';

import { httpMeetingApi } from './meeting-api';
import { seedMeeting } from './seed';
import { MeetingApiError } from './server-repo';

type Sent = { url: string; init: RequestInit };

const respond = (status: number, body: unknown, sent: Sent[] = []) =>
	httpMeetingApi({
		base: '/api/v1',
		token: 'tok',
		scopeId: 'jup-consolidated',
		fetch: (async (url: string, init: RequestInit) => {
			sent.push({ url, init });
			return new Response(JSON.stringify(body), { status });
		}) as typeof fetch
	});

describe('httpMeetingApi', () => {
	it('saves the whole meeting with the revision it was based on', async () => {
		const sent: Sent[] = [];
		const api = respond(200, { id: 'rd-1', revision: 4 }, sent);
		const m = seedMeeting('rd-1');
		expect(await api.save('rd-1', 3, m)).toEqual({ id: 'rd-1', revision: 4 });
		expect(sent[0].url).toBe('/api/v1/leadership/meetings/rd-1?scope_id=jup-consolidated');
		expect(sent[0].init.method).toBe('PUT');
		expect(JSON.parse(sent[0].init.body as string)).toEqual({ base_revision: 3, document: m });
		expect((sent[0].init.headers as Record<string, string>).authorization).toBe('Bearer tok');
	});

	it('creates with POST and lists the stored meetings', async () => {
		const sent: Sent[] = [];
		await respond(201, { revision: 1 }, sent).create(seedMeeting('rd-1'));
		expect(sent[0].init.method).toBe('POST');
		expect(sent[0].url).toBe('/api/v1/leadership/meetings?scope_id=jup-consolidated');
		const listed = await respond(200, {
			meetings: [{ id: 'rd-1', revision: 1, document: {} }]
		}).list();
		expect(listed).toEqual([{ id: 'rd-1', revision: 1, document: {} }]);
	});

	it('carries the stored revision of a conflict', async () => {
		const api = respond(409, { detail: { message: 'changed elsewhere', revision: 7 } });
		await expect(api.save('rd-1', 3, seedMeeting('rd-1'))).rejects.toMatchObject({
			status: 409,
			revision: 7,
			message: 'changed elsewhere'
		});
	});

	it('reads a missing meeting as null and any other refusal as an error', async () => {
		expect(await respond(404, { detail: 'No such meeting.' }).get('rd-1')).toBeNull();
		await expect(respond(403, { detail: 'restricted' }).get('rd-1')).rejects.toMatchObject({
			status: 403
		});
	});

	it('reports an unreachable server as status 0', async () => {
		const api = httpMeetingApi({
			base: '/api/v1',
			token: 'tok',
			scopeId: 'jup-consolidated',
			fetch: (async () => {
				throw new TypeError('Failed to fetch');
			}) as typeof fetch
		});
		const error = await api.list().catch((e) => e);
		expect(error).toBeInstanceOf(MeetingApiError);
		expect(error.status).toBe(0);
	});
});
