import { stakeholders } from '../../../layar-model';
import { Head, Nothing, StatusBadge, type ViewProps } from './common';

// 06 Stakeholder Issues: who, what they ask, who answers, by when, how urgent.

export const V06Stakeholder = ({ meeting, agenda }: ViewProps) => {
	const rows = stakeholders(meeting);
	return (
		<div className="lr-view">
			<Head agenda={agenda} />
			{rows.length ? (
				<div className="lr-table lr-table--stake" role="table" aria-label="Isu stakeholder">
					<div className="lr-tr lr-th" role="row">
						<span role="columnheader">Pemangku kepentingan</span>
						<span role="columnheader">Isu / permintaan utama</span>
						<span role="columnheader">PIC komunikasi</span>
						<span role="columnheader">Target</span>
						<span role="columnheader">Urgensi</span>
					</div>
					{rows.map((s) => (
						<div className="lr-tr" role="row" key={s.id}>
							<span role="cell">
								<span className="lr-strong">{s.org}</span>
								{s.jenis ? <span className="lr-sub">{s.jenis}</span> : null}
							</span>
							<span role="cell">{s.isu || '—'}</span>
							<span role="cell">{s.pic || '—'}</span>
							<span role="cell" className="lr-mono">
								{s.target}
							</span>
							<span role="cell">
								<StatusBadge s={s.urg} />
							</span>
						</div>
					))}
				</div>
			) : (
				<Nothing what="isu stakeholder" />
			)}
		</div>
	);
};
