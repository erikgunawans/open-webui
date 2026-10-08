import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider, ToastProvider } from '@jup/ui';

import { readOnlyRepo, type MeetingRepo } from '../repo';
import { seedMeeting } from '../seed';
import type { Meeting } from '../types';
import { LayarApp } from './layar/LayarApp';
import { MeetingList } from './MeetingList';
import { NotulenApp } from './notulen/NotulenApp';
import { useMeeting, type SaveState } from './useMeeting';

// Story 16: a board reader without `rapat.write` reads the server's meetings and writes none. The
// write path is closed in the repository and in useMeeting; the screens drop their edit controls.

const ID = 'rd-2026-10-09-ab12';

/** A server-like repository that counts every write it is asked for. */
const counting = (meetings: Meeting[] = []) => {
	const writes: string[] = [];
	const repo: MeetingRepo = {
		remote: true,
		list: () => meetings,
		get: (id) => meetings.find((m) => m.id === id) ?? null,
		save: (m) => {
			writes.push(`save:${m.id}`);
			return true;
		},
		quarantine: (id) => {
			writes.push(`quarantine:${id}`);
			return null;
		},
		subscribe: () => () => {}
	};
	return { repo, writes };
};

const wrap = (node: React.ReactNode) =>
	renderToStaticMarkup(
		<JupUIProvider storageKey={null}>
			<ToastProvider>{node}</ToastProvider>
		</JupUIProvider>
	);

describe('useMeeting, read-only', () => {
	const open = (repo: MeetingRepo) => {
		let out: { saved: SaveState; update: (c: (m: Meeting) => Meeting) => void } | null = null;
		const Probe = () => {
			const [, update, saved] = useMeeting(repo, ID, () => seedMeeting(ID));
			out = { saved, update };
			return null;
		};
		renderToStaticMarkup(<Probe />);
		return out!;
	};

	it('opens a meeting the server does not have without seeding or setting anything aside', () => {
		// Flagged read-only but still counting: the hook itself must not write.
		const { repo, writes } = counting();
		const { saved } = open({ ...repo, readOnly: true });
		expect(writes).toEqual([]);
		expect(saved.ok).toBe(true);
	});

	it('takes no change and reports no failed save', () => {
		const { repo, writes } = counting([seedMeeting(ID)]);
		const { saved, update } = open({ ...repo, readOnly: true });
		update((m) => ({ ...m, session: { ...m.session, currentAgenda: 5 } }));
		expect(writes).toEqual([]);
		expect(saved.ok).toBe(true);
	});

	it('with the write grant, a change is still saved', () => {
		const { repo, writes } = counting([seedMeeting(ID)]);
		open(repo).update((m) => ({ ...m, session: { ...m.session, currentAgenda: 5 } }));
		expect(writes).toEqual([`save:${ID}`]);
	});
});

describe('the screens, read-only', () => {
	const notulen = (repo: MeetingRepo) =>
		wrap(
			<NotulenApp
				repo={repo}
				meetingId={ID}
				init={() => seedMeeting(ID)}
				layarHref={`/rapat/${ID}/layar`}
				viewKey={`view:${ID}`}
			/>
		);
	const layar = (repo: MeetingRepo, agenda = 7) => {
		const m = seedMeeting(ID);
		const at = { ...m, session: { ...m.session, currentAgenda: agenda } };
		return wrap(<LayarApp repo={repo} meetingId={ID} init={() => at} demo={false} />);
	};

	it('Notulen: Hanya baca, fields disabled, no edit actions; reading and printing stay', () => {
		const html = notulen(readOnlyRepo(counting([seedMeeting(ID)]).repo));
		expect(html).toContain('Hanya baca');
		expect(html).toMatch(/<fieldset class="nt-freeze" disabled/);
		for (const gone of ['Tutup rapat', 'Buka kembali', 'Lainnya', 'aria-label="Catat cepat"'])
			expect(html).not.toContain(gone);
		expect(html).toContain('Cetak / PDF');
		expect(html).toContain('Simpan HTML terisi');
	});

	it('Notulen with the grant keeps every action', () => {
		const html = notulen(counting([seedMeeting(ID)]).repo);
		expect(html).not.toContain('Hanya baca');
		expect(html).toContain('Tutup rapat');
		expect(html).toContain('Lainnya');
	});

	it('Layar: a mirror, with no navigation, Keputusan or Tutup rapat controls', () => {
		const ro = layar(readOnlyRepo(counting().repo));
		expect(ro).toContain('Hanya baca · mengikuti Corsec');
		expect(ro).not.toContain('Selesai dibahas');
		expect(ro).not.toContain('lr-dec__acts');
		expect(ro).toMatch(/class="lr-nav__i[^"]*"[^>]*disabled/);
		const last = layar(readOnlyRepo(counting().repo), 8);
		expect(last).not.toContain('Tutup rapat');

		const rw = layar(counting().repo);
		expect(rw).toContain('Selesai dibahas');
		expect(rw).not.toContain('Hanya baca');
	});

	it('List: no Rapat baru for a reader who may not write', () => {
		const list = (repo: MeetingRepo) =>
			wrap(<MeetingList repo={repo} base="/rapat" newId={() => 'rd-new'} open={() => {}} />);
		expect(list(readOnlyRepo(counting().repo))).not.toContain('Rapat baru');
		expect(list(counting().repo)).toContain('Rapat baru');
	});
});
