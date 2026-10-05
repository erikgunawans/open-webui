import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@jup/ui';

import { agendaPlan } from '../../layar-model';
import type { MeetingRepo } from '../../repo';
import { ACTION_STATUS, DECISION_STATUS, text, type Meeting } from '../../types';
import { useMeeting } from '../useMeeting';
import { AgendaNav } from './AgendaNav';
import { Footer } from './Footer';
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

const TONE: Record<string, 'success' | 'danger' | 'neutral' | 'warning'> = {
	Disetujui: 'success',
	Ditolak: 'danger',
	'Belum diputuskan': 'neutral'
};

export const LayarApp = ({ repo, meetingId, init, demo }: LayarProps) => {
	const [meeting, update] = useMeeting(repo, meetingId, init);
	const { toast } = useToast();
	const [now, setNow] = useState(() => new Date());
	const [selected, setSelected] = useState<string | null>(null);
	const plan = agendaPlan(meeting);
	const cur = Math.min(Math.max(meeting.session.currentAgenda, 0), plan.length - 1);
	const done = meeting.session.doneAgendas;

	useEffect(() => {
		const i = window.setInterval(() => setNow(new Date()), 1000);
		return () => window.clearInterval(i);
	}, []);

	const go = useCallback(
		(i: number) => {
			if (i < 0 || i >= plan.length) return;
			update((m) => ({
				...m,
				session: { ...m.session, currentAgenda: i, agendaEnteredAt: Date.now() }
			}));
		},
		[plan.length, update]
	);
	useAgendaKeys(cur, go);

	const finish = () => {
		update((m) => ({
			...m,
			session: {
				...m.session,
				doneAgendas: [...new Set([...m.session.doneAgendas, cur])],
				...(cur < plan.length - 1 ? { currentAgenda: cur + 1, agendaEnteredAt: Date.now() } : {})
			}
		}));
		toast({ title: `Agenda ${plan[cur].no} selesai dibahas`, tone: 'success' });
	};

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

	const decide = (recordId: string, status: string) => {
		const r = meeting.records[7].find((x) => x.id === recordId);
		setValue(7, recordId, DECISION_STATUS, status);
		const id = text(r?.values['ID keputusan']);
		toast({
			title: `${id ? `${id} · ` : ''}${status}`,
			description: text(r?.values['Topik keputusan']),
			tone: TONE[status] ?? 'warning'
		});
	};

	const elapsed = Math.max(0, Math.floor((now.getTime() - meeting.session.agendaEnteredAt) / 1000));
	const view = { meeting, agenda: plan[cur] };

	return (
		<Stage>
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
					<AgendaNav plan={plan} current={cur} done={done} onGo={go} />
					<main className="lr-main">
						{cur === 0 ? <V00Info key={0} {...view} /> : null}
						{cur === 1 ? <V01Strategi key={1} {...view} /> : null}
						{cur === 2 ? <V02Kinerja key={2} {...view} /> : null}
						{cur === 3 ? <V03Isu key={3} {...view} /> : null}
						{cur === 4 ? <V04Program key={4} {...view} /> : null}
						{cur === 5 ? <V05Risiko key={5} {...view} /> : null}
						{cur === 6 ? <V06Stakeholder key={6} {...view} /> : null}
						{cur === 7 ? (
							<V07Keputusan
								key={7}
								{...view}
								selected={selected}
								onSelect={setSelected}
								onDecide={decide}
							/>
						) : null}
						{cur === 8 ? (
							<V08Aksi key={8} {...view} onAdvance={(id, s) => setValue(8, id, ACTION_STATUS, s)} />
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
						onPrev={() => go(cur - 1)}
						onFinish={finish}
					/>
				</div>
			</div>
		</Stage>
	);
};
