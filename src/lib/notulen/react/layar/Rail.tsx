import { Badge } from '@jup/ui';

import { decisionId } from '../../layar-model';
import {
	actions,
	decisions,
	fmtShort,
	highRisks,
	nearestOpenActions,
	targetOf
} from '../../selectors';
import { DECISION_STATUS, text, type Meeting } from '../../types';

// Right rail: decision/new-action/high-risk counts, the decisions still waiting, and the nearest
// open deadlines. All counts are read from the Meeting, so a decision set on agenda 07 (here or
// in another tab) moves them at once.

type Props = {
	meeting: Meeting;
	onDecision: (recordId: string) => void;
	onActions: () => void;
};

export const Rail = ({ meeting, onDecision, onActions }: Props) => {
	const all = decisions(meeting);
	const status = (id: string) =>
		text(meeting.records[7].find((r) => r.id === id)?.values[DECISION_STATUS]) ||
		'Belum diputuskan';
	const pending = all.filter((r) => ['Belum diputuskan', 'Ditunda'].includes(status(r.id)));
	const decided = all.filter((r) => status(r.id) !== 'Belum diputuskan').length;
	const fresh = actions(meeting).filter(
		(r) => r.values['Asal tindak lanjut'] === 'Rapat ini'
	).length;

	return (
		<aside className="lr-rail" aria-label="Ringkasan rapat">
			<div className="lr-stats">
				<div>
					<span className="lr-k">Keputusan</span>
					<span className="lr-bignum">
						{decided}
						<span className="lr-sub">/{all.length}</span>
					</span>
				</div>
				<div>
					<span className="lr-k">Tindakan baru</span>
					<span className="lr-bignum">{fresh}</span>
				</div>
				<div>
					<span className="lr-k">Risiko tinggi</span>
					<span className="lr-bignum lr-danger">{highRisks(meeting).length}</span>
				</div>
			</div>
			<section className="lr-rail__s">
				<div className="lr-rail__h">
					<span>Perlu keputusan</span>
					<Badge tone="warning">{pending.length}</Badge>
				</div>
				{pending.length ? (
					pending.map((r) => (
						<button
							type="button"
							key={r.id}
							className="lr-rail__item"
							onClick={() => onDecision(r.id)}
						>
							<span className="lr-mono lr-strong">{decisionId(r, all.indexOf(r))}</span>
							<span className="lr-rail__t">{text(r.values['Topik keputusan'])}</span>
							{status(r.id) === 'Ditunda' ? (
								<Badge tone="warning" size="sm">
									Ditunda
								</Badge>
							) : null}
						</button>
					))
				) : (
					<p className="lr-sub">Semua usulan telah diputuskan.</p>
				)}
			</section>
			<section className="lr-rail__s">
				<div className="lr-rail__h">
					<span>Tenggat terdekat</span>
				</div>
				{nearestOpenActions(meeting).map((r) => (
					<button type="button" key={r.id} className="lr-rail__item" onClick={onActions}>
						<span className="lr-mono lr-cal">{fmtShort(targetOf(r))}</span>
						<span className="lr-rail__t">
							{text(r.values['Tindakan / deliverable'])}
							<span className="lr-sub">{text(r.values['PIC utama'])}</span>
						</span>
					</button>
				))}
			</section>
		</aside>
	);
};
