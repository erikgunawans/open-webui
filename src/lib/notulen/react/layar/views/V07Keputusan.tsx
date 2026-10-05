import { Button, Card, Tag } from '@jup/ui';
import { Check } from 'lucide-react';

import { decisionId } from '../../../layar-model';
import { decisions } from '../../../selectors';
import { DECISION_STATUS, text } from '../../../types';
import { Head, Nothing, StatusBadge, type ViewProps } from './common';

// 07 Decision Making: the Board decides live. A status written here goes straight into
// "7. Decision Making › Status keputusan" of the Meeting; clicking the active status again reverts
// it to "Belum diputuskan".

const ACTS: [status: string, active: 'primary' | 'secondary' | 'danger', label: string][] = [
	['Disetujui', 'primary', 'Setujui'],
	['Disetujui bersyarat', 'secondary', 'Setujui bersyarat'],
	['Ditunda', 'secondary', 'Tunda'],
	['Ditolak', 'danger', 'Tolak']
];

type Props = ViewProps & {
	selected: string | null;
	onSelect: (recordId: string) => void;
	onDecide: (recordId: string, status: string) => void;
};

export const V07Keputusan = ({ meeting, agenda, selected, onSelect, onDecide }: Props) => {
	const list = decisions(meeting);
	const d = list.find((x) => x.id === selected) ?? list[0];
	const statusOf = (r: (typeof list)[number]) =>
		text(r.values[DECISION_STATUS]) || 'Belum diputuskan';
	const decided = list.filter((x) => statusOf(x) !== 'Belum diputuskan').length;

	return (
		<div className="lr-view">
			<Head
				agenda={agenda}
				right={
					<div className="lr-tagline">
						<span className="lr-k">Diputuskan</span>
						<span className="lr-bignum">
							{decided}/{list.length}
						</span>
					</div>
				}
			/>
			{d ? (
				<div className="lr-dec">
					<div className="lr-dec__list" role="listbox" aria-label="Daftar keputusan">
						{list.map((x, i) => (
							<button
								type="button"
								role="option"
								aria-selected={x.id === d.id}
								key={x.id}
								className={`lr-dec__item${x.id === d.id ? ' is-active' : ''}`}
								onClick={() => onSelect(x.id)}
							>
								<span className="lr-mono lr-strong">{decisionId(x, i)}</span>
								<span className="lr-dec__t">{text(x.values['Topik keputusan'])}</span>
								<StatusBadge s={statusOf(x)} />
							</button>
						))}
					</div>
					<Card padding="md" className="lr-dec__detail">
						<div className="lr-dec__top">
							<span className="lr-mono lr-k">
								{decisionId(d, list.indexOf(d))}
								{text(d.values.Agenda) ? ` · ${text(d.values.Agenda)}` : ''}
							</span>
							<StatusBadge s={statusOf(d)} />
						</div>
						<div className="lr-h3 lr-h3--lg">{text(d.values['Topik keputusan'])}</div>
						<div className="lr-k lr-mt">Keputusan yang dimohonkan</div>
						<p className="lr-lead">{text(d.values['Keputusan yang dimohonkan']) || '—'}</p>
						<div className="lr-g2 lr-g2--tight">
							<div>
								<div className="lr-k">Rekomendasi</div>
								<div>{text(d.values['Opsi & rekomendasi']) || '—'}</div>
							</div>
							<div>
								<div className="lr-k">Kewenangan / persetujuan lanjutan</div>
								<div className="lr-tags">
									{(
										(d.values['Kewenangan / persetujuan lanjutan'] as string[] | undefined) ?? []
									).map((k) => (
										<Tag key={k} size="sm">
											{k}
										</Tag>
									))}
								</div>
							</div>
							<div>
								<div className="lr-k">PIC pelaksanaan</div>
								<div>{text(d.values['PIC pelaksanaan']) || '—'}</div>
							</div>
						</div>
						<div className="lr-dec__acts">
							{ACTS.map(([s, variant, label]) => {
								const on = statusOf(d) === s;
								return (
									<Button
										key={s}
										variant={on ? variant : 'outline'}
										size="lg"
										aria-pressed={on}
										iconLeft={on ? <Check size={20} aria-hidden="true" /> : undefined}
										onClick={() => onDecide(d.id, on ? 'Belum diputuskan' : s)}
									>
										{label}
									</Button>
								);
							})}
						</div>
					</Card>
				</div>
			) : (
				<Nothing what="usulan keputusan" />
			)}
		</div>
	);
};
