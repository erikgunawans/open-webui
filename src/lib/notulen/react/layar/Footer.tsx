import { Button } from '@jup/ui';

import type { AgendaPlan } from '../../layar-model';

// Footer: the timeline (segments sized by minutes) and the previous / done-and-next buttons.

type Props = {
	plan: AgendaPlan[];
	current: number;
	done: number[];
	onPrev: () => void;
	onFinish: () => void;
};

export const Footer = ({ plan, current, done, onPrev, onFinish }: Props) => {
	const last = current === plan.length - 1;
	return (
		<footer className="lr-foot">
			<div className="lr-timeline" aria-hidden="true">
				{plan.map((a, i) => (
					<div
						key={a.no}
						className={`lr-seg${i === current ? ' is-cur' : done.includes(i) ? ' is-done' : ''}`}
						style={{ flexGrow: a.menit }}
					>
						<span className="lr-mono">{a.no}</span>
					</div>
				))}
			</div>
			<div className="lr-foot__acts">
				<Button variant="ghost" onClick={onPrev} disabled={current === 0}>
					← Sebelumnya
				</Button>
				<Button variant="primary" onClick={onFinish}>
					{done.includes(current) ? 'Lanjut' : 'Selesai dibahas'}
					{last ? '' : ' →'}
				</Button>
			</div>
		</footer>
	);
};
