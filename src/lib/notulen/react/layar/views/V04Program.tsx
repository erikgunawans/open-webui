import { toneOf } from '../../../agendas';
import { programs } from '../../../layar-model';
import { Bar, Head, Nothing, StatusBadge, nf, type ViewProps } from './common';

// 04 Program Prioritas: progress, budget against realisation (Rp miliar), next milestone, status;
// budget absorption in the header.

export const V04Program = ({ meeting, agenda }: ViewProps) => {
	const rows = programs(meeting);
	const [ang, real] = rows.reduce((s, p) => [s[0] + p.ang, s[1] + p.real], [0, 0]);

	return (
		<div className="lr-view">
			<Head
				agenda={agenda}
				right={
					ang > 0 ? (
						<div className="lr-tagline">
							<span className="lr-k">Serapan anggaran</span>
							<span className="lr-bignum">{nf((real / ang) * 100)}%</span>
							<span className="lr-sub">
								Rp {nf(real)} M dari Rp {nf(ang)} M
							</span>
						</div>
					) : undefined
				}
			/>
			{rows.length ? (
				<div className="lr-table lr-table--prog" role="table" aria-label="Program prioritas">
					<div className="lr-tr lr-th" role="row">
						<span role="columnheader">Program / proyek</span>
						<span role="columnheader">Progres</span>
						<span role="columnheader">Anggaran · realisasi (Rp M)</span>
						<span role="columnheader">Milestone berikutnya</span>
						<span role="columnheader">Status</span>
					</div>
					{rows.map((p) => {
						const tone = toneOf(p.status, 'layar');
						return (
							<div className="lr-tr" role="row" key={p.id}>
								<span role="cell">
									<span className="lr-strong">{p.nama}</span>
									{p.sub ? <span className="lr-sub">{p.sub}</span> : null}
								</span>
								<span role="cell" className="lr-progress">
									{p.pct !== null ? (
										<>
											<Bar
												pct={p.pct}
												tone={
													tone === 'danger' ? 'danger' : tone === 'warning' ? 'warning' : 'brand'
												}
											/>
											<span className="lr-mono">{p.pct}%</span>
										</>
									) : (
										<span className="lr-sub">—</span>
									)}
								</span>
								<span role="cell" className="lr-mono">
									{nf(p.ang)} · <span className="lr-strong">{nf(p.real)}</span>
								</span>
								<span role="cell">{p.milestone}</span>
								<span role="cell">
									<StatusBadge s={p.status} />
								</span>
							</div>
						);
					})}
				</div>
			) : (
				<Nothing what="program prioritas" />
			)}
		</div>
	);
};
