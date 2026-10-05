import { Button } from '@jup/ui';

import type { AgendaPlan } from '../../layar-model';

// Footer: the timeline (segments sized by minutes) and the previous / done-and-next buttons. On the
// last agenda the primary closes the meeting; once closed, the only action reopens agenda 08.

type Props = {
	plan: AgendaPlan[];
	current: number;
	done: number[];
	closed: boolean;
	onPrev: () => void;
	onFinish: () => void;
	onReopen: () => void;
};

export const Footer = ({ plan, current, done, closed, onPrev, onFinish, onReopen }: Props) => {
	const last = current === plan.length - 1;
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
			<div className="lr-foot__acts">
				{closed ? (
					<Button variant="ghost" onClick={onReopen}>
						← Buka kembali agenda {plan[current].no}
					</Button>
				) : (
					<>
						<Button variant="ghost" onClick={onPrev} disabled={current === 0}>
							← Sebelumnya
						</Button>
						<Button variant="primary" onClick={onFinish}>
							{last ? 'Tutup rapat' : done.includes(current) ? 'Lanjut →' : 'Selesai dibahas →'}
						</Button>
					</>
				)}
			</div>
		</footer>
	);
};
