import { Badge } from '@jup/ui';

import { ACTION_COLUMNS } from '../../../agendas';
import { actionId } from '../../../layar-model';
import { actions, fmtShort, targetOf } from '../../../selectors';
import { ACTION_STATUS, text } from '../../../types';
import { Head, StatusBadge, type ViewProps } from './common';

// 08 Action Plan: a four-column board. Clicking a tile advances its status cyclically (the Layar
// notice offers Urungkan); the change is written to "8. Action Plan › Status" of the Meeting.

export const nextStatus = (s: string) =>
	ACTION_COLUMNS[(ACTION_COLUMNS.indexOf(s) + 1) % ACTION_COLUMNS.length];

// `onAdvance` is absent for a read-only reader: the tiles show the board, they do not move it.
type Props = ViewProps & { onAdvance?: (recordId: string, status: string) => void };

export const V08Aksi = ({ meeting, agenda, onAdvance }: Props) => {
	const all = actions(meeting);
	const index = new Map(meeting.records[8].map((r, i) => [r.id, i]));
	const statusOf = (r: (typeof all)[number]) => text(r.values[ACTION_STATUS]) || 'Belum mulai';

	return (
		<div className="lr-view">
			<Head
				agenda={agenda}
				right={
					<div className="lr-tagline">
						<span className="lr-sub">Klik kartu untuk memajukan status</span>
					</div>
				}
			/>
			<div className="lr-board">
				{ACTION_COLUMNS.map((c) => {
					const items = all.filter((x) => statusOf(x) === c);
					return (
						<section className="lr-col" key={c} aria-label={c}>
							<div className="lr-col__h">
								<StatusBadge s={c} />
								<span className="lr-mono lr-sub">{items.length}</span>
							</div>
							{items.map((x) => (
								<button
									type="button"
									className="lr-tile"
									key={x.id}
									aria-label={`${text(x.values['Tindakan / deliverable'])}: ${c}${onAdvance ? `, majukan ke ${nextStatus(c)}` : ''}`}
									disabled={!onAdvance}
									onClick={() => onAdvance?.(x.id, nextStatus(c))}
								>
									<div className="lr-tile__top">
										<span className="lr-mono lr-strong">{actionId(x, index.get(x.id) ?? 0)}</span>
										<span className="lr-mono lr-sub">{fmtShort(targetOf(x))}</span>
									</div>
									<div className="lr-tile__t">{text(x.values['Tindakan / deliverable'])}</div>
									<div className="lr-sub">{text(x.values['PIC utama']) || '—'}</div>
									<div className="lr-tile__f">
										<span className="lr-sub">{text(x.values['Indikator penyelesaian'])}</span>
										{x.values['Asal tindak lanjut'] === 'Rapat sebelumnya' ? (
											<Badge size="sm" tone="info" variant="outline">
												Sebelumnya
											</Badge>
										) : null}
									</div>
								</button>
							))}
						</section>
					);
				})}
			</div>
		</div>
	);
};
