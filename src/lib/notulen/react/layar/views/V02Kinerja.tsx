import { Badge, Card } from '@jup/ui';

import { kinerjaNotes, kpiTiles } from '../../../layar-model';
import { Bar, Head, Nothing, nf, type ViewProps } from './common';

// 02 Kinerja: KPI tiles with the deviation tone (CAPEX/OPEX inverted), the monthly revenue chart
// and the causes / corrections. Figures are Rp miliar unless the unit says otherwise.

export const V02Kinerja = ({ meeting, agenda }: ViewProps) => {
	const tiles = kpiTiles(meeting).slice(0, 8);
	const notes = kinerjaNotes(meeting);
	const max = Math.max(1, ...notes.monthly.map(([, r, t]) => Math.max(r, t)));

	return (
		<div className="lr-view">
			<Head
				agenda={agenda}
				right={
					<div className="lr-tagline">
						{notes.period ? (
							<Badge tone="info" variant="outline">
								{notes.period}
							</Badge>
						) : null}
						<span className="lr-sub">Rp miliar kecuali dinyatakan lain</span>
					</div>
				}
			/>
			{tiles.length ? (
				<div className="lr-kpis">
					{tiles.map((k) => (
						<div className="lr-kpi" key={k.id}>
							<div className="lr-kpi__h">
								<span>{k.ind}</span>
								<Badge tone={k.tone} size="sm">
									{`${k.d > 0 ? '+' : ''}${nf(k.d)}%`}
								</Badge>
							</div>
							<div className="lr-kpi__v">
								{nf(k.real)}
								{k.pct ? '%' : ''}
							</div>
							<Bar pct={(k.real / k.target) * 100} tone={k.tone === 'success' ? 'brand' : k.tone} />
							<div className="lr-sub">
								{k.cost ? 'Anggaran' : 'Target'} {nf(k.target)}
								{k.pct ? '%' : ''}
							</div>
						</div>
					))}
				</div>
			) : (
				<Nothing what="indikator dengan target dan realisasi" />
			)}
			<div className="lr-g2 lr-g2--chart">
				<Card
					title="Revenue bulanan vs target"
					description={
						notes.monthly.length
							? `Rp miliar · ${notes.monthly[0][0]}–${notes.monthly[notes.monthly.length - 1][0]}${notes.year ? ` ${notes.year}` : ''}`
							: 'Rp miliar'
					}
					padding="md"
				>
					{notes.monthly.length ? (
						<>
							<div className="lr-chart" role="img" aria-label="Revenue bulanan dibanding target">
								{notes.monthly.map(([b, r, t]) => (
									<div className="lr-chart__c" key={b}>
										<div className="lr-chart__bars">
											<div className="lr-chart__t" style={{ bottom: `${(t / max) * 100}%` }} />
											<div
												className={`lr-chart__b${r < t ? ' is-under' : ''}`}
												style={{ height: `${(r / max) * 100}%` }}
											/>
										</div>
										<span className="lr-mono lr-sub">{b}</span>
									</div>
								))}
							</div>
							<div className="lr-legend">
								<span>
									<i className="lr-sw lr-sw--b" />
									Realisasi ≥ target
								</span>
								<span>
									<i className="lr-sw lr-sw--u" />
									Di bawah target
								</span>
								<span>
									<i className="lr-sw lr-sw--t" />
									Target
								</span>
							</div>
						</>
					) : (
						<Nothing what="data revenue bulanan" />
					)}
				</Card>
				<Card title="Penyebab & langkah koreksi" padding="md">
					{notes.pairs.length ? (
						<dl className="lr-dl">
							{notes.pairs.map(([dt, dd]) => (
								<div key={dt + dd} style={{ display: 'contents' }}>
									<dt>{dt}</dt>
									<dd>{dd}</dd>
								</div>
							))}
						</dl>
					) : (
						<Nothing what="penyebab dan langkah koreksi" />
					)}
				</Card>
			</div>
		</div>
	);
};
