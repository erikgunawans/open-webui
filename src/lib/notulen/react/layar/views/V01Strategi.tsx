import { strategicRows } from '../../../layar-model';
import { Bar, Head, Nothing, StatusBadge, type ViewProps } from './common';

// 01 Strategic Update: target, current position, progress (from the meeting plan; the template
// has no progress field) and the strategy evaluation.

export const V01Strategi = ({ meeting, agenda }: ViewProps) => {
	const rows = strategicRows(meeting);
	return (
		<div className="lr-view">
			<Head agenda={agenda} />
			{rows.length ? (
				<div className="lr-table lr-table--strat" role="table" aria-label="Sasaran strategis">
					<div className="lr-tr lr-th" role="row">
						<span role="columnheader">Sasaran strategis</span>
						<span role="columnheader">Target</span>
						<span role="columnheader">Posisi terkini</span>
						<span role="columnheader">Pencapaian</span>
						<span role="columnheader">Evaluasi</span>
					</div>
					{rows.map((s) => (
						<div className="lr-tr" role="row" key={s.id}>
							<span role="cell">
								<span className="lr-strong">{s.sasaran}</span>
								{s.sub ? <span className="lr-sub">{s.sub}</span> : null}
							</span>
							<span role="cell" className="lr-mono">
								{s.target || '—'}
							</span>
							<span role="cell" className="lr-mono lr-strong">
								{s.posisi || '—'}
							</span>
							<span role="cell" className="lr-progress">
								{s.pct !== null ? (
									<>
										<Bar pct={s.pct} tone={s.pct >= 75 ? 'brand' : 'warning'} />
										<span className="lr-mono">{s.pct}%</span>
									</>
								) : (
									<span className="lr-sub">—</span>
								)}
							</span>
							<span role="cell">
								<StatusBadge s={s.evaluasi} />
							</span>
						</div>
					))}
				</div>
			) : (
				<Nothing what="sasaran strategis" />
			)}
		</div>
	);
};
