import { Badge, Tag } from '@jup/ui';

import { toneOf } from '../../../agendas';
import { risks } from '../../../layar-model';
import { Head, Nothing, StatusBadge, type ViewProps } from './common';

// 05 Risk & Compliance: one row per risk, the left edge toned by its level.

const LEVELS = ['Tinggi', 'Sedang', 'Rendah'];

export const V05Risiko = ({ meeting, agenda }: ViewProps) => {
	const rows = risks(meeting);
	return (
		<div className="lr-view">
			<Head
				agenda={agenda}
				right={
					<div className="lr-tagline">
						{LEVELS.map((l) => (
							<Badge key={l} tone={toneOf(l, 'layar')} variant="solid">
								{`${rows.filter((r) => r.lvl === l).length} ${l}`}
							</Badge>
						))}
					</div>
				}
			/>
			{rows.length ? (
				<div className="lr-stack lr-stack--tight">
					{rows.map((r) => (
						<div className={`lr-risk lr-risk--${toneOf(r.lvl, 'layar')}`} key={r.id}>
							<div className="lr-risk__lvl">
								<span className="lr-k">Tingkat</span>
								<span className="lr-strong">{r.lvl || '—'}</span>
							</div>
							<div>
								<div className="lr-h3">{r.r}</div>
								{r.mitigasi ? <div className="lr-sub">{r.mitigasi}</div> : null}
								{r.kat.length ? (
									<div className="lr-tags">
										{r.kat.map((k) => (
											<Tag key={k} size="sm">
												{k}
											</Tag>
										))}
									</div>
								) : null}
							</div>
							<div>
								<div className="lr-k">Risk owner</div>
								<div>{r.owner || '—'}</div>
							</div>
							<div>
								<div className="lr-k">Tenggat</div>
								<div className="lr-mono">{r.tenggat}</div>
							</div>
							<div>
								<StatusBadge s={r.status} />
							</div>
						</div>
					))}
				</div>
			) : (
				<Nothing what="risiko" />
			)}
		</div>
	);
};
