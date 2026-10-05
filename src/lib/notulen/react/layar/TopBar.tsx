import { Badge, IconButton, useJupTheme } from '@jup/ui';
import { Moon, Sun } from 'lucide-react';

import { mainInfo, meetingName } from '../../selectors';
import { isDate, text, type Meeting, type PropValue } from '../../types';
import type { AgendaPlan } from '../../layar-model';

// Top bar: identity, meeting name and meta on the left; the live clock and the agenda timer on
// the right. The timer turns danger once the agenda runs past its allotment.

const mmss = (s: number) =>
	`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

const dayAndTime = (v: PropValue | undefined): [string, string] => {
	if (!isDate(v) || !v.start) return ['', ''];
	const { start, end } = v;
	const day = new Date(start.length === 10 ? `${start}T00:00` : start).toLocaleDateString('id-ID', {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});
	const hm = (x: string) => x.slice(11, 16).replace(':', '.');
	const time = start.length > 10 ? `${hm(start)}${end.length > 10 ? `–${hm(end)}` : ''} WIB` : '';
	return [day, time];
};

type Props = {
	meeting: Meeting;
	agenda: AgendaPlan;
	now: Date;
	elapsed: number;
	timer: boolean;
	demo: boolean;
};

export const TopBar = ({ meeting, agenda, now, elapsed, timer, demo }: Props) => {
	const { resolvedTheme, setTheme } = useJupTheme();
	const mv = mainInfo(meeting)?.values ?? {};
	const [day, time] = dayAndTime(mv['Tanggal & waktu']);
	const klas = text(mv['Klasifikasi dokumen']);
	const over = elapsed > agenda.menit * 60;
	const dark = resolvedTheme === 'dark';

	return (
		<header className="lr-top">
			<div className="lr-top__id">
				<div className="lr-eyebrow">PT Jakarta Utilitas Propertindo · Notulen Rapat Direksi</div>
				<h1 className="lr-h1">{meetingName(meeting)}</h1>
				<div className="lr-top__meta">
					{meeting.plan?.nomor ? <span className="lr-mono">{meeting.plan.nomor}</span> : null}
					{day ? <span>{[day, time].filter(Boolean).join(' · ')}</span> : null}
					{text(mv['Ruang / lokasi']) ? <span>{text(mv['Ruang / lokasi'])}</span> : null}
					{klas ? (
						<Badge tone={klas === 'Rahasia' ? 'danger' : 'info'} variant="outline">
							{klas}
						</Badge>
					) : null}
					{demo ? (
						<Badge tone="warning" variant="subtle">
							Data dummy
						</Badge>
					) : null}
					<IconButton
						label={dark ? 'Gunakan tema terang' : 'Gunakan tema gelap'}
						variant="ghost"
						size="sm"
						onClick={() => setTheme(dark ? 'light' : 'dark')}
					>
						{dark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
					</IconButton>
				</div>
			</div>
			<div className="lr-clock">
				<div className="lr-clock__t lr-mono">
					{now.toLocaleTimeString('id-ID', {
						hour: '2-digit',
						minute: '2-digit',
						timeZone: 'Asia/Jakarta'
					})}
					<span className="lr-sub"> WIB</span>
				</div>
				{timer ? (
					<div className={`lr-clock__a${over ? ' is-over' : ''}`} role="timer" aria-live="off">
						<span className="lr-k">Agenda {agenda.no}</span>
						<span className="lr-mono">
							{mmss(elapsed)} / {String(agenda.menit).padStart(2, '0')}:00
						</span>
					</div>
				) : null}
			</div>
		</header>
	);
};
