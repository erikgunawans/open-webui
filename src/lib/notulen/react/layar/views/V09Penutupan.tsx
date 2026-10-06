import { Card } from '@jup/ui';

import { closingSummary, jakartaLocal } from '../../../layar-model';
import { fmtDate, mainInfo } from '../../../selectors';
import { text } from '../../../types';
import { StatusBadge, type ViewProps } from './common';

// Penutupan: shown once "Tutup rapat" closes the meeting on agenda 08. What the Board leaves with —
// the closing time, the decisions by status, the actions and their gaps, the next meeting.

// Rows that fit the 1080px stage under the KPI row; the rest are counted, not clipped.
const MAX_ROWS = 7;

type Props = Pick<ViewProps, 'meeting'> & { closedAt: number };

export const V09Penutupan = ({ meeting, closedAt }: Props) => {
	const s = closingSummary(meeting);
	const mv = mainInfo(meeting)?.values ?? {};
	const nextTopic = text(mv['Topik rapat berikutnya']);
	const nextDate = fmtDate(mv['Rapat berikutnya']);
	const decided = s.decisions.filter(([, n]) => n > 0);

	return (
		<div className="lr-view">
			<header className="lr-ahead">
				<div>
					<div className="lr-eyebrow">Penutupan</div>
					<h2 className="lr-h2">Rapat ditutup</h2>
					<p className="lr-focus">
						Pukul{' '}
						<span className="lr-mono">{jakartaLocal(closedAt).slice(11).replace(':', '.')}</span>{' '}
						WIB · {s.agendasDone} dari {s.agendasTotal} agenda dibahas
					</p>
				</div>
			</header>
			<div className="lr-kpis">
				<div className="lr-kpi">
					<div className="lr-kpi__h">Keputusan</div>
					<div className="lr-kpi__v">
						{s.decided}
						<span className="lr-sub">/{s.decisionList.length}</span>
					</div>
				</div>
				<div className="lr-kpi">
					<div className="lr-kpi__h">Disetujui</div>
					<div className="lr-kpi__v">
						{s.decisions.filter(([k]) => k.startsWith('Disetujui')).reduce((n, [, c]) => n + c, 0)}
					</div>
				</div>
				<div className="lr-kpi">
					<div className="lr-kpi__h">Tindak lanjut</div>
					<div className="lr-kpi__v">{s.actions}</div>
				</div>
				<div className="lr-kpi">
					<div className="lr-kpi__h">Tanpa PIC / target</div>
					<div className={`lr-kpi__v${s.actionsIncomplete ? ' lr-danger' : ''}`}>
						{s.actionsIncomplete}
					</div>
				</div>
			</div>
			<div className="lr-g2 lr-mt">
				<Card
					title="Keputusan rapat ini"
					description={decided.map(([k, n]) => `${n} ${k.toLowerCase()}`).join(' · ') || undefined}
					padding="md"
				>
					{s.decisionList.length ? (
						<ul className="lr-closing__list">
							{s.decisionList.slice(0, MAX_ROWS).map((d) => (
								<li key={d.id} className="lr-closing__row">
									<span className="lr-mono lr-strong">{d.id}</span>
									<span>{d.topic}</span>
									<StatusBadge s={d.status} />
								</li>
							))}
							{s.decisionList.length > MAX_ROWS ? (
								<li className="lr-sub">
									+{s.decisionList.length - MAX_ROWS} keputusan lainnya di Notulen
								</li>
							) : null}
						</ul>
					) : (
						<p className="lr-sub">Tidak ada keputusan yang dicatat.</p>
					)}
				</Card>
				<Card title="Rapat berikutnya" padding="md">
					{nextTopic || nextDate ? (
						<>
							{nextDate ? <p className="lr-lead lr-mono">{nextDate}</p> : null}
							{nextTopic ? <p className="lr-lead">{nextTopic}</p> : null}
						</>
					) : (
						<p className="lr-sub">Belum dijadwalkan. Isi di Notulen › Informasi Rapat.</p>
					)}
				</Card>
			</div>
		</div>
	);
};
