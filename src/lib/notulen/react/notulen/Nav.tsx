import { Fragment } from 'react';

import { AGENDAS } from '../../agendas';
import { pendingDecisions } from '../../selectors';
import type { Meeting } from '../../types';

// The sidebar: Informasi Rapat, agendas 1–8 with record counts, then the derived views (with the
// pending-decision count) and the guide. At ≤860px the CSS turns it into a horizontal row.

export type View = `${number}` | 'views' | 'guide';

export const Nav = ({
	meeting,
	view,
	onView
}: {
	meeting: Meeting;
	view: View;
	onView: (v: View) => void;
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
			{items.map((n, i) => (
				<Fragment key={n.id}>
					{i === AGENDAS.length ? <div className="nt-side__sep" /> : null}
					<button
						type="button"
						className={`nt-side__item${view === n.id ? ' is-active' : ''}`}
						aria-current={view === n.id ? 'page' : undefined}
						onClick={() => onView(n.id)}
					>
						<span>{n.label}</span>
						{n.badge != null ? <span className="nt-side__n">{n.badge}</span> : null}
					</button>
				</Fragment>
			))}
		</nav>
	);
};
