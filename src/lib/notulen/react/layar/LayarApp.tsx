import { useCallback, useEffect, useState } from 'react';

import { agendaPlan, closeMeeting, startLayarSession } from '../../layar-model';
import { closingGaps, decide as decideIn, reopenMeeting } from '../../keputusan';
import type { MeetingRepo } from '../../repo';
import { ACTION_STATUS, text, type Meeting, type PropValue } from '../../types';
import { useMeeting } from '../useMeeting';
import { AgendaNav } from './AgendaNav';
import { Footer } from './Footer';
import { Notice, useNotice, type NoticeTone } from './Notice';
import { Rail } from './Rail';
import { Stage } from './Stage';
import { TopBar } from './TopBar';
import { useAgendaKeys } from './useKeyboard';
import { V00Info } from './views/V00Info';
import { V01Strategi } from './views/V01Strategi';
import { V02Kinerja } from './views/V02Kinerja';
import { V03Isu } from './views/V03Isu';
import { V04Program } from './views/V04Program';
import { V05Risiko } from './views/V05Risiko';
import { V06Stakeholder } from './views/V06Stakeholder';
import { V07Keputusan } from './views/V07Keputusan';
import { V08Aksi } from './views/V08Aksi';
import { V09Penutupan } from './views/V09Penutupan';
import './layar.css';

// Screen 2: the boardroom display, a read model of the same Meeting the Notulen writes. Agenda
// progress lives in the meeting session; decisions and action statuses write back into agendas 7
// and 8. Every change goes through the repository, so another tab follows at once.

export type LayarProps = {
	repo: MeetingRepo;
	meetingId: string;
	init: () => Meeting;
	demo: boolean;
};

const TONE: Record<string, NoticeTone> = {
	Disetujui: 'success',
	Ditolak: 'danger',
	'Belum diputuskan': 'neutral'
};

export const LayarApp = ({ repo, meetingId, init, demo }: LayarProps) => {
	const [meeting, update, saved, unreadable] = useMeeting(repo, meetingId, init);
	const { shown, notify, close } = useNotice();
	const [now, setNow] = useState(() => new Date());
	const [selected, setSelected] = useState<string | null>(null);
	const plan = agendaPlan(meeting);
	const cur = Math.min(Math.max(meeting.session.currentAgenda, 0), plan.length - 1);
	const done = meeting.session.doneAgendas;
	const closedAt = meeting.session.closedAt;
	// Board view without `rapat.write` (story 16): a mirror of the Corsec's Layar, no write controls.
	const readOnly = !!repo.readOnly;
	// The agenda view on screen; none while the closing screen is up.
	const onScreen = closedAt === undefined ? cur : -1;

	useEffect(() => {
		const i = window.setInterval(() => setNow(new Date()), 1000);
		return () => window.clearInterval(i);
	}, []);

	const go = useCallback(
		(i: number) => {
			// A closed meeting is frozen: moving around never reopens it (Buka kembali does, with a reason).
			if (i < 0 || i >= plan.length || closedAt !== undefined) return;
			update((m) =>
				m.session.currentAgenda === i
					? m
					: { ...m, session: { ...m.session, currentAgenda: i, agendaEnteredAt: Date.now() } }
			);
		},
		[plan.length, update, closedAt]
	);
	useAgendaKeys(cur, go);

	// The agenda timer counts from when the agenda came on screen in this Layar session. A stored
	// start from an earlier session (a rehearsal, a meeting reopened later) would greet the Board
	// with a red overrun, so a new session restarts it; a reload of the same tab keeps it.
	useEffect(() => {
		let tab: Storage;
		try {
			tab = window.sessionStorage;
		} catch {
			return;
		}
		const started = startLayarSession(meeting, tab, Date.now());
		if (started) update(() => started);
		// Once per mount, on the meeting as opened.
	}, []);

	const closeRapat = () => {
		update((m) => closeMeeting(m, Date.now()));
		notify({ title: 'Rapat ditutup', description: 'Notulen kini hanya-baca.', tone: 'success' });
	};
	const reopen = (reason: string) => {
		update((m) => reopenMeeting(m, reason, Date.now()));
		notify({ title: 'Rapat dibuka kembali', description: reason, tone: 'warning' });
	};

	const finish = () => {
		// The last agenda's primary opens the Tutup rapat check in the footer instead.
		if (cur === plan.length - 1) return;
		update((m) => ({
			...m,
			session: {
				...m.session,
				doneAgendas: [...new Set([...m.session.doneAgendas, cur])],
				...(cur < plan.length - 1 ? { currentAgenda: cur + 1, agendaEnteredAt: Date.now() } : {})
			}
		}));
		notify({ title: `Agenda ${plan[cur].no} selesai dibahas`, tone: 'success' });
	};

	// A write the browser refused leaves the change in this tab only; the operator must know before
	// the Board moves on. Every refused write re-asserts the warning (it outranks the status notice
	// of the same change), and it stays up until the next notice after a write that succeeded.
	useEffect(() => {
		if (saved.ok) return;
		notify(
			repo.remote
				? {
						title: 'Perubahan belum tersimpan di server',
						description:
							'Server tidak terjangkau atau menolak penyimpanan; aplikasi mencoba lagi. Jangan tutup tab ini sebelum tersimpan.',
						tone: 'danger',
						duration: 0
					}
				: {
						title: 'Perubahan belum tersimpan di peramban ini',
						description:
							'Penyimpanan penuh atau diblokir. Simpan salinan dari Notulen sebelum tab ini ditutup.',
						tone: 'danger',
						duration: 0
					}
		);
	}, [saved, notify, repo]);

	// A move on this screen lost to a change made on another machine: the newer one is now shown.
	useEffect(() => {
		if (!saved.conflict) return;
		notify({
			title: 'Rapat diubah di perangkat lain',
			description:
				'Layar memuat versi terbaru dari server. Ulangi langkah terakhir bila masih diperlukan.',
			tone: 'warning',
			duration: 0
		});
	}, [saved.conflict, notify]);

	// Damaged or other-version data was set aside, not shown: say so once, and where to recover it.
	useEffect(() => {
		if (!unreadable) return;
		notify({
			title: 'Data lama rapat ini tidak dapat dibaca',
			description: 'Layar dimulai dari template. Unduh data lama dari Notulen untuk dipulihkan.',
			tone: 'warning',
			duration: 0
		});
	}, [unreadable, notify]);

	const setValue = (db: number, recordId: string, key: string, value: string) =>
		update((m) => ({
			...m,
			records: m.records.map((coll, i) =>
				i !== db
					? coll
					: coll.map((r) =>
							r.id === recordId ? { ...r, values: { ...r.values, [key]: value } } : r
						)
			)
		}));

	// Every live status change can be taken back from the notice: a mis-tap in front of the Board
	// should cost one click, not three.
	const decide = (recordId: string, status: string, values: Record<string, PropValue> = {}) => {
		const r = meeting.records[7].find((x) => x.id === recordId);
		if (!r) return;
		const before = r.values;
		const next = decideIn(meeting, recordId, status, values);
		if (!next) return;
		update(() => next);
		const id = text(r.values['ID keputusan']);
		notify({
			title: `${id ? `${id} · ` : ''}${status}`,
			description: text(r.values['Topik keputusan']),
			tone: TONE[status] ?? 'warning',
			action: {
				label: 'Urungkan',
				onClick: () =>
					update((m) => ({
						...m,
						records: m.records.map((coll, i) =>
							i !== 7 ? coll : coll.map((x) => (x.id === recordId ? { ...x, values: before } : x))
						)
					}))
			}
		});
	};

	const advance = (recordId: string, status: string) => {
		const r = meeting.records[8].find((x) => x.id === recordId);
		const before = text(r?.values[ACTION_STATUS]) || 'Belum mulai';
		setValue(8, recordId, ACTION_STATUS, status);
		notify({
			title: `${text(r?.values['Tindakan / deliverable']) || 'Tindakan'} · ${status}`,
			tone: 'neutral',
			action: { label: 'Urungkan', onClick: () => setValue(8, recordId, ACTION_STATUS, before) }
		});
	};

	const elapsed = Math.max(0, Math.floor((now.getTime() - meeting.session.agendaEnteredAt) / 1000));
	const view = { meeting, agenda: plan[cur] };

	return (
		<Stage overlay={<Notice shown={shown} onClose={close} />}>
			<div className="lr-app">
				<div className="lr-grid">
					<TopBar
						meeting={meeting}
						agenda={plan[cur]}
						now={now}
						elapsed={elapsed}
						timer
						demo={demo}
					/>
					<AgendaNav plan={plan} current={cur} done={done} onGo={readOnly ? undefined : go} />
					<main className="lr-main">
						{closedAt !== undefined ? <V09Penutupan meeting={meeting} closedAt={closedAt} /> : null}
						{onScreen === 0 ? <V00Info key={0} {...view} /> : null}
						{onScreen === 1 ? <V01Strategi key={1} {...view} /> : null}
						{onScreen === 2 ? <V02Kinerja key={2} {...view} /> : null}
						{onScreen === 3 ? <V03Isu key={3} {...view} /> : null}
						{onScreen === 4 ? <V04Program key={4} {...view} /> : null}
						{onScreen === 5 ? <V05Risiko key={5} {...view} /> : null}
						{onScreen === 6 ? <V06Stakeholder key={6} {...view} /> : null}
						{onScreen === 7 ? (
							<V07Keputusan
								key={7}
								{...view}
								selected={selected}
								onSelect={setSelected}
								onDecide={readOnly ? undefined : decide}
							/>
						) : null}
						{onScreen === 8 ? (
							<V08Aksi key={8} {...view} onAdvance={readOnly ? undefined : advance} />
						) : null}
					</main>
					<Rail
						meeting={meeting}
						onDecision={(id) => {
							setSelected(id);
							go(7);
						}}
						onActions={() => go(8)}
					/>
					<Footer
						plan={plan}
						current={cur}
						done={done}
						closed={closedAt !== undefined}
						onPrev={() => go(cur - 1)}
						onFinish={finish}
						gaps={closingGaps(meeting)}
						onClose={closeRapat}
						onBackToDecisions={() => go(7)}
						onReopen={reopen}
						readOnly={readOnly}
					/>
				</div>
			</div>
		</Stage>
	);
};
