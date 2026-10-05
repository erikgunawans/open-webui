import { Badge, Card } from '@jup/ui';

import { issues } from '../../../layar-model';
import { Head, Nothing, type ViewProps } from './common';

// 03 Isu Lintas Direktorat: one card per cross-directorate issue.

export const V03Isu = ({ meeting, agenda }: ViewProps) => {
	const rows = issues(meeting);
	return (
		<div className="lr-view">
			<Head agenda={agenda} />
			{rows.length ? (
				<div className="lr-stack">
					{rows.map((x, i) => (
						<Card key={x.id} padding="md">
							<div className="lr-issue">
								<div className="lr-issue__n lr-mono">{String(i + 1).padStart(2, '0')}</div>
								<div className="lr-issue__b">
									<div className="lr-h3">{x.isu}</div>
									{x.unit ? <div className="lr-sub">{x.unit}</div> : null}
									<div className="lr-issue__g">
										<div>
											<div className="lr-k">Dampak</div>
											<div>{x.dampak || '—'}</div>
										</div>
										<div>
											<div className="lr-k">Keputusan yang diperlukan</div>
											<div className="lr-strong">{x.perlu || '—'}</div>
										</div>
									</div>
								</div>
								<div className="lr-issue__m">
									<div className="lr-k">PIC</div>
									<div>{x.pic || '—'}</div>
									<div className="lr-k lr-mt">Target</div>
									<div className="lr-mono">{x.target}</div>
									{x.ref ? (
										<Badge tone="info" variant="outline">
											{x.ref}
										</Badge>
									) : null}
								</div>
							</div>
						</Card>
					))}
				</div>
			) : (
				<Nothing what="isu lintas direktorat" />
			)}
		</div>
	);
};
