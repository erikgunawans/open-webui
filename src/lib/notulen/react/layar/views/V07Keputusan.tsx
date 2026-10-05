import { useEffect, useState } from 'react';
import { Button, Card, Tag } from '@jup/ui';
import { Check } from 'lucide-react';

import { decisionId } from '../../../layar-model';
import { decisions } from '../../../selectors';
import { DECISION_STATUS, text } from '../../../types';
import { Head, Nothing, StatusBadge, type ViewProps } from './common';

// 07 Decision Making: the Board decides live. A status written here goes straight into
// "7. Decision Making › Status keputusan" of the Meeting; clicking the active status again reverts
// it to "Belum diputuskan". Tolak asks once, in place (no modal over the projected screen); every
// change can also be taken back from the Layar notice.

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
	// The record whose rejection is awaiting a second click; any other selection drops it.
	const [confirming, setConfirming] = useState<string | null>(null);
	const asking = !!d && confirming === d.id;

	useEffect(() => {
		if (!asking) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') setConfirming(null);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [asking]);

	const choose = (id: string, status: string, on: boolean) => {
		if (!on && status === 'Ditolak') {
			setConfirming(id);
			return;
		}
		setConfirming(null);
		onDecide(id, on ? 'Belum diputuskan' : status);
	};

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
					<div className="lr-dec__list" role="group" aria-label="Daftar keputusan">
						{list.map((x, i) => (
							<button
								type="button"
								aria-current={x.id === d.id ? 'true' : undefined}
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
						{asking ? (
							<div
								className="lr-dec__acts lr-dec__confirm"
								role="group"
								aria-label="Konfirmasi tolak"
							>
								<span className="lr-dec__confirm-q">Tolak usulan ini?</span>
								<Button
									variant="danger"
									size="lg"
									autoFocus
									onClick={() => {
										setConfirming(null);
										onDecide(d.id, 'Ditolak');
									}}
								>
									Ya, tolak
								</Button>
								<Button variant="outline" size="lg" onClick={() => setConfirming(null)}>
									Batal
								</Button>
							</div>
						) : (
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
											onClick={() => choose(d.id, s, on)}
										>
											{label}
										</Button>
									);
								})}
							</div>
						)}
					</Card>
				</div>
			) : (
				<Nothing what="usulan keputusan" />
			)}
		</div>
	);
};
