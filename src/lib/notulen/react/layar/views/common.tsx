import type { ReactNode } from 'react';
import { Badge } from '@jup/ui';

import { toneOf } from '../../../agendas';
import type { AgendaPlan } from '../../../layar-model';
import type { Meeting } from '../../../types';

export type ViewProps = { meeting: Meeting; agenda: AgendaPlan };

export const nf = (n: number, d = 1) =>
	n.toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });

/** A status word as a Layar badge (its tone from the shared table). */
export const StatusBadge = ({
	s,
	variant
}: {
	s: string;
	variant?: 'subtle' | 'solid' | 'outline';
}) =>
	s ? (
		<Badge tone={toneOf(s, 'layar')} dot variant={variant}>
			{s}
		</Badge>
	) : null;

export const Bar = ({
	pct,
	tone = 'brand'
}: {
	pct: number;
	tone?: 'brand' | 'success' | 'warning' | 'danger';
}) => (
	<div className="lr-bar" role="presentation">
		<div
			className={`lr-bar__f lr-bar__f--${tone}`}
			style={{ transform: `scaleX(${Math.max(0, Math.min(100, pct)) / 100})` }}
		/>
	</div>
);

/** The agenda header: eyebrow, title, focus line and an optional right-hand summary. */
export const Head = ({
	agenda,
	focus,
	right
}: {
	agenda: AgendaPlan;
	focus?: string;
	right?: ReactNode;
}) => {
	const f = focus ?? agenda.focus;
	return (
		<header className="lr-ahead">
			<div>
				<div className="lr-eyebrow">
					Agenda {agenda.no}
					{agenda.pemapar ? ` · ${agenda.pemapar}` : ''}
				</div>
				<h2 className="lr-h2">{agenda.nav}</h2>
				{f ? <p className="lr-focus">{f}</p> : null}
			</div>
			{right}
		</header>
	);
};

export const Nothing = ({ what }: { what: string }) => (
	<p className="lr-sub">Belum ada {what} di notulen.</p>
);
