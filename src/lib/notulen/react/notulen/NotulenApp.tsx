import { useEffect, useRef, useState } from 'react';
import { Button, Dialog, useJupTheme, useToast } from '@jup/ui';

import { AGENDAS } from '../../agendas';
import type { MeetingRepo } from '../../repo';
import { FOOTER } from '../../schema';
import type { Meeting, NotulenRecord } from '../../types';
import { useMeeting } from '../useMeeting';
import { AgendaView } from './AgendaView';
import { DerivedViews } from './DerivedViews';
import { Guide } from './Guide';
import { Header } from './Header';
import { Nav, type View } from './Nav';
import './notulen.css';

// Screen 1: the secretariat's input tool. Every edit saves through the repository at once, so the
// Layar (another tab of this browser) follows without a reload.

export type NotulenProps = {
	repo: MeetingRepo;
	meetingId: string;
	init: () => Meeting;
	layarHref: string;
	/** Where the reader's last view is remembered (per user and meeting). */
	viewKey: string;
};

const readView = (key: string): View => {
	try {
		const v = localStorage.getItem(key);
		if (v && (/^[0-8]$/.test(v) || v === 'views' || v === 'guide')) return v as View;
	} catch {
		/* storage blocked */
	}
	return '0';
};

export const NotulenApp = ({ repo, meetingId, init, layarHref, viewKey }: NotulenProps) => {
	const [meeting, update] = useMeeting(repo, meetingId, init);
	const [view, setView] = useState<View>(() => readView(viewKey));
	const [printing, setPrinting] = useState(false);
	const [confirmReset, setConfirmReset] = useState(false);
	const { toast } = useToast();
	const { resolvedTheme } = useJupTheme();
	const top = useRef<HTMLDivElement>(null);

	useEffect(() => {
		try {
			localStorage.setItem(viewKey, view);
		} catch {
			/* storage blocked */
		}
	}, [view, viewKey]);

	useEffect(() => {
		const off = () => setPrinting(false);
		window.addEventListener('afterprint', off);
		return () => window.removeEventListener('afterprint', off);
	}, []);

	const setRecords = (db: number) => (records: NotulenRecord[]) =>
		update((m) => ({ ...m, records: m.records.map((x, i) => (i === db ? records : x)) }));

	const go = (v: View) => {
		setView(v);
		top.current?.scrollIntoView({ block: 'start' });
	};

	const print = () => {
		setPrinting(true);
		setTimeout(() => window.print(), 300);
	};

	const save = async () => {
		const { downloadSnapshot } = await import('./snapshot');
		downloadSnapshot(meeting, resolvedTheme);
		toast({
			title: 'HTML terisi diunduh',
			description: 'Salinan baca-saja; isian tetap tersimpan di peramban ini.',
			tone: 'success'
		});
	};

	const reset = () => {
		update(() => init());
		setConfirmReset(false);
		go('0');
		toast({ title: 'Template dikembalikan', tone: 'neutral' });
	};

	const db = /^[0-8]$/.test(view) ? Number(view) : null;

	return (
		<div className="nt-app" ref={top}>
			<Header
				meeting={meeting}
				layarHref={layarHref}
				onReset={() => setConfirmReset(true)}
				onPrint={print}
				onSave={save}
			/>
			<div className="nt-shell">
				<Nav meeting={meeting} view={view} onView={go} />
				<main className="nt-main">
					{printing ? (
						<>
							{AGENDAS.map((_, i) => (
								<AgendaView
									key={`p${i}`}
									db={i}
									records={meeting.records[i]}
									setRecords={setRecords(i)}
									showTypes={false}
									printing
									toast={toast}
								/>
							))}
							<DerivedViews meeting={meeting} />
						</>
					) : view === 'views' ? (
						<DerivedViews meeting={meeting} />
					) : view === 'guide' ? (
						<Guide />
					) : (
						<AgendaView
							key={view}
							db={db ?? 0}
							records={meeting.records[db ?? 0]}
							setRecords={setRecords(db ?? 0)}
							showTypes
							toast={toast}
						/>
					)}
					<footer className="nt-foot">{FOOTER}</footer>
				</main>
			</div>
			<Dialog
				open={confirmReset}
				onClose={() => setConfirmReset(false)}
				title="Reset notulen?"
				description="Seluruh isian dikembalikan ke template awal. Tindakan ini tidak dapat dibatalkan."
				footer={
					<>
						<Button variant="ghost" onClick={() => setConfirmReset(false)}>
							Batal
						</Button>
						<Button variant="danger" onClick={reset}>
							Reset
						</Button>
					</>
				}
			/>
		</div>
	);
};
