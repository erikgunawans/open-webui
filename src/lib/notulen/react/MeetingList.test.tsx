import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider } from '@jup/ui';

import type { MeetingRepo } from '../repo';
import { seedMeeting } from '../seed';
import type { Meeting } from '../types';
import { MeetingList, type MeetingListProps } from './MeetingList';

// Pindahkan ke server is offered only on the server's list, to a reader who may write, while this
// browser still holds meetings from before.

const repo = (remote: boolean, meetings: Meeting[] = []): MeetingRepo => ({
	remote,
	list: () => meetings,
	get: () => null,
	save: () => true,
	quarantine: () => null,
	subscribe: () => () => {}
});

const render = (props: Partial<MeetingListProps>) =>
	renderToStaticMarkup(
		<JupUIProvider storageKey={null}>
			<MeetingList
				repo={repo(true)}
				base="/ruang-pimpinan/rapat"
				newId={() => 'rd-new'}
				open={() => {}}
				{...props}
			/>
		</JupUIProvider>
	);

const offer = (pending: Meeting[]) => ({
	pending: () => pending,
	run: async () => ({ ok: true as const, outcomes: [] })
});

describe('Pindahkan ke server', () => {
	it('offers the move while this browser holds meetings', () => {
		const html = render({ move: offer([seedMeeting('rd-a'), seedMeeting('rd-b')]) });
		expect(html).toContain('2 notulen masih tersimpan di peramban ini');
		expect(html).toContain('Pindahkan ke server');
		expect(html).toContain('tidak ditimpa');
	});

	it('offers nothing when there is nothing to move, no write grant, or no server', () => {
		expect(render({ move: offer([]) })).not.toContain('Pindahkan ke server');
		expect(render({})).not.toContain('Pindahkan ke server');
		expect(render({ repo: repo(false), move: offer([seedMeeting('rd-a')]) })).not.toContain(
			'Pindahkan ke server'
		);
	});
});
