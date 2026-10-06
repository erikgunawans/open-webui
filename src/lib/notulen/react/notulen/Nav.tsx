import { Fragment } from 'react';
import { Switch } from '@jup/ui';

import { AGENDAS } from '../../agendas';
import { pendingDecisions } from '../../selectors';
import type { Meeting } from '../../types';

// The sidebar: Ikuti layar, Informasi Rapat, agendas 1–8 with entry counts and the "● Di layar"
// mark on the agenda the Layar shows, then the derived views (with the pending-decision count) and
// the guide. At ≤860px the CSS turns it into a horizontal row.

export type View = `${number}` | 'views' | 'guide';

export const Nav = ({
	meeting,
	view,
	onView,
	onLayar,
	follow,
	onFollow
}: {
	meeting: Meeting;
	view: View;
	onView: (v: View) => void;
	/** The agenda the Layar shows; null once the meeting is closed. */
	onLayar: number | null;
	follow: boolean;
	onFollow: (on: boolean) => void;
}) => {
	const pending = pendingDecisions(meeting).length;
	const items: { id: View; label: string; badge?: number }[] = [
		...AGENDAS.map((a, i) => ({
			id: String(i) as View,
			label: a.nav,
			badge: meeting.records[i].length
		})),
		{ id: 'views', label: 'Tampilan pendukung', badge: pending || undefined },
		{ id: 'guide', label: 'Panduan & checklist' }
	];
	return (
		<nav className="nt-side" aria-label="Navigasi agenda">
			{onLayar != null ? (
				<div className="nt-side__follow">
					<Switch
						size="sm"
						reverse
						label="Ikuti layar"
						checked={follow}
						onChange={(e) => onFollow(e.target.checked)}
					/>
				</div>
			) : null}
			{items.map((n, i) => (
				<Fragment key={n.id}>
					{i === AGENDAS.length ? <div className="nt-side__sep" /> : null}
					<button
						type="button"
						className={`nt-side__item${view === n.id ? ' is-active' : ''}`}
						aria-current={view === n.id ? 'page' : undefined}
						onClick={() => onView(n.id)}
					>
						<span className="nt-side__label">
							{n.label}
							{onLayar != null && n.id === String(onLayar) ? (
								<span className="nt-side__live">● Di layar</span>
							) : null}
						</span>
						{n.badge != null ? <span className="nt-side__n">{n.badge}</span> : null}
					</button>
				</Fragment>
			))}
		</nav>
	);
};
