import { Check } from 'lucide-react';

import type { AgendaPlan } from '../../layar-model';

// Left nav: the nine agendas with presenter and minutes; current and done states.

export const AgendaNav = ({
	plan,
	current,
	done,
	onGo
}: {
	plan: AgendaPlan[];
	current: number;
	done: number[];
	onGo: (i: number) => void;
}) => (
	<nav className="lr-nav" aria-label="Agenda rapat">
		<div className="lr-k lr-nav__h">Agenda · {plan.reduce((n, a) => n + a.menit, 0)} menit</div>
		{plan.map((a, i) => {
			const st = i === current ? 'cur' : done.includes(i) ? 'done' : 'todo';
			return (
				<button
					type="button"
					key={a.no}
					className={`lr-nav__i lr-nav__i--${st}`}
					aria-current={i === current ? 'step' : undefined}
					onClick={() => onGo(i)}
				>
					<span className="lr-nav__no lr-mono">{a.no}</span>
					<span className="lr-nav__t">
						<span>{a.nav}</span>
						{a.pemapar ? <span className="lr-sub">{a.pemapar}</span> : null}
					</span>
					{st === 'done' ? (
						<span className="lr-mono lr-sub lr-nav__done">
							<Check size={18} strokeWidth={2.25} aria-label="Selesai" />
							{a.menit}′
						</span>
					) : (
						<span className="lr-mono lr-sub">{a.menit}′</span>
					)}
				</button>
			);
		})}
	</nav>
);
