import { useEffect, useState } from 'react';
import { Button, Input } from '@jup/ui';

import { gapLine, type closingGaps } from '../../keputusan';
import type { AgendaPlan } from '../../layar-model';

// Footer: the timeline (segments sized by minutes) and the previous / done-and-next buttons. On the
// last agenda the primary asks the Tutup rapat check in place — what is still open, then "Tutup
// tetap" or back to 07 — the same in-place pattern as Tolak, never a modal over the projected
// screen. Once closed, the only action is "Buka kembali", which asks for the reason first.

type Props = {
	plan: AgendaPlan[];
	current: number;
	done: number[];
	closed: boolean;
	gaps: ReturnType<typeof closingGaps>;
	onPrev: () => void;
	onFinish: () => void;
	onClose: () => void;
	onBackToDecisions: () => void;
	onReopen: (reason: string) => void;
	/** A reader without the write grant (story 16): the timeline only, the Corsec moves the Layar. */
	readOnly?: boolean;
};

type Asking = null | 'close' | 'reopen';

/** The Tutup rapat check in place. With gaps the safe way is the default: "Kembali ke 07" is the
 *  primary and takes focus, so Enter does not close a meeting that still has open Usulan. */
export const CloseAsk = ({
	gaps,
	onClose,
	onBack,
	onCancel
}: {
	gaps: ReturnType<typeof closingGaps>;
	onClose: () => void;
	onBack: () => void;
	onCancel: () => void;
}) => (
	<div className="lr-foot__ask" role="group" aria-label="Tutup rapat">
		<span className="lr-foot__q">{gaps.any ? gapLine(gaps) : 'Tutup rapat sekarang?'}</span>
		{/* Same order as the Notulen dialog: Batal, the second choice, the primary last. */}
		<Button variant="ghost" onClick={onCancel}>
			Batal
		</Button>
		{gaps.any ? (
			<>
				<Button variant="outline" onClick={onClose}>
					Tutup tetap
				</Button>
				<Button variant="primary" autoFocus onClick={onBack}>
					Kembali ke 07
				</Button>
			</>
		) : (
			<Button variant="primary" autoFocus onClick={onClose}>
				Tutup rapat
			</Button>
		)}
	</div>
);

export const Footer = ({ plan, current, done, closed, gaps, readOnly, ...on }: Props) => {
	const last = current === plan.length - 1;
	const [asking, setAsking] = useState<Asking>(null);
	const [reason, setReason] = useState('');

	useEffect(() => {
		setAsking(null);
		setReason('');
	}, [closed, current]);
	useEffect(() => {
		if (!asking) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') setAsking(null);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [asking]);

	const acts = () => {
		if (readOnly) return <span className="lr-k">Hanya baca · mengikuti Corsec</span>;
		if (closed && asking === 'reopen')
			return (
				<form
					className="lr-foot__ask"
					aria-label="Buka kembali rapat"
					onSubmit={(e) => {
						e.preventDefault();
						if (reason.trim()) on.onReopen(reason);
					}}
				>
					<Input
						autoFocus
						value={reason}
						onChange={(e) => setReason(e.target.value)}
						placeholder="Alasan membuka kembali (dicetak di Risalah)…"
						aria-label="Alasan membuka kembali"
					/>
					<Button type="button" variant="ghost" onClick={() => setAsking(null)}>
						Batal
					</Button>
					<Button type="submit" variant="primary" disabled={!reason.trim()}>
						Buka kembali
					</Button>
				</form>
			);
		if (closed)
			return (
				<Button variant="ghost" onClick={() => setAsking('reopen')}>
					← Buka kembali rapat
				</Button>
			);
		if (last && asking === 'close')
			return (
				<CloseAsk
					gaps={gaps}
					onClose={on.onClose}
					onBack={on.onBackToDecisions}
					onCancel={() => setAsking(null)}
				/>
			);
		return (
			<>
				<Button variant="ghost" onClick={on.onPrev} disabled={current === 0}>
					← Sebelumnya
				</Button>
				<Button variant="primary" onClick={last ? () => setAsking('close') : on.onFinish}>
					{last ? 'Tutup rapat' : done.includes(current) ? 'Lanjut →' : 'Selesai dibahas →'}
				</Button>
			</>
		);
	};

	return (
		<footer className="lr-foot">
			<div className="lr-timeline" aria-hidden="true">
				{plan.map((a, i) => (
					<div
						key={a.no}
						className={`lr-seg${i === current && !closed ? ' is-cur' : done.includes(i) ? ' is-done' : ''}`}
						style={{ flexGrow: a.menit }}
					>
						<span className="lr-mono">{a.no}</span>
					</div>
				))}
			</div>
			<div className="lr-foot__acts">{acts()}</div>
		</footer>
	);
};
