import { useEffect, useRef, useState } from 'react';
import { Button, Dialog, useJupTheme, useToast } from '@jup/ui';

import type { MeetingRepo } from '../../repo';
import { captureRecord, type Capture } from '../../capture';
import type { AgendaNotes, Meeting, NotulenRecord } from '../../types';
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
	demo?: boolean;
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

export const NotulenApp = ({ repo, meetingId, init, layarHref, viewKey, demo }: NotulenProps) => {
	const [meeting, update, saved, unreadable] = useMeeting(repo, meetingId, init);
	const [view, setView] = useState<View>(() => readView(viewKey));
	const [confirmReset, setConfirmReset] = useState(false);
	const { toast } = useToast();
	const { resolvedTheme } = useJupTheme();
	const top = useRef<HTMLDivElement>(null);
	const main = useRef<HTMLElement>(null);
	// Set by a sidebar choice, so focus follows the reader to the new view (not on first load).
	const moved = useRef(false);
	// Ikuti layar: Notulen jumps with the Layar until the Corsec opens another agenda by hand.
	const [follow, setFollow] = useState(true);
	const onLayar = meeting.session.closedAt ? null : meeting.session.currentAgenda;
	const lastLayar = useRef(onLayar);
	useEffect(() => {
		if (onLayar === lastLayar.current) return;
		lastLayar.current = onLayar;
		if (follow && onLayar != null) setView(String(onLayar) as View);
	}, [onLayar, follow]);

	useEffect(() => {
		try {
			localStorage.setItem(viewKey, view);
		} catch {
			/* storage blocked */
		}
	}, [view, viewKey]);

	const setRecords = (db: number) => (records: NotulenRecord[]) =>
		update((m) => ({ ...m, records: m.records.map((x, i) => (i === db ? records : x)) }));

	const go = (v: View) => {
		if (onLayar != null) setFollow(v === String(onLayar));
		moved.current = true;
		setView(v);
		top.current?.scrollIntoView({ block: 'start' });
	};

	// A keyboard or screen-reader user lands on the new view's heading instead of staying in the nav.
	useEffect(() => {
		if (!moved.current) return;
		moved.current = false;
		const h = main.current?.querySelector<HTMLElement>('h2');
		h?.setAttribute('tabindex', '-1');
		h?.focus({ preventScroll: true });
	}, [view]);

	const capture = (c: Capture) => {
		const { db: to, record } = captureRecord(c);
		update((m) => ({
			...m,
			records: m.records.map((x, i) => (i === to ? [...x, record] : x))
		}));
		const where = to === c.from ? '' : ` ke Agenda 0${to}`;
		toast({
			title: `${c.kind[0].toUpperCase()}${c.kind.slice(1)} dicatat${where}`,
			tone: 'success'
		});
	};
	const notesOf = (d: number): AgendaNotes => meeting.notes?.[d] ?? { text: '', risalah: false };
	const setNotes = (d: number) => (n: AgendaNotes) =>
		update((m) => ({ ...m, notes: { ...m.notes, [d]: n } }));
	const followLayar = (on: boolean) => {
		setFollow(on);
		if (on && onLayar != null) go(String(onLayar) as View);
	};

	const print = async () => {
		const { printRisalah } = await import('./risalah');
		printRisalah(meeting);
	};

	const save = async () => {
		const { downloadSnapshot } = await import('./snapshot');
		downloadSnapshot(meeting, resolvedTheme);
		toast({
			title: 'HTML terisi diunduh',
			// Only claim the browser copy when the last write actually landed.
			description: saved.ok
				? 'Salinan baca-saja; isian tetap tersimpan di peramban ini.'
				: 'Simpan file ini baik-baik: isian belum tersimpan di peramban ini.',
			tone: 'success'
		});
	};

	// The unreadable data exactly as it was stored, so an admin can recover it.
	const downloadOld = () => {
		if (!unreadable) return;
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([unreadable.raw], { type: 'application/json' }));
		a.download = `rapat-${meetingId}-data-lama.json`;
		a.click();
		URL.revokeObjectURL(a.href);
	};

	// Reset keeps the meeting it replaced in memory for one Urungkan.
	const reset = () => {
		const before = meeting;
		update(() => init());
		setConfirmReset(false);
		go('0');
		toast({
			title: 'Template dikembalikan',
			tone: 'neutral',
			duration: 15000,
			action: { label: 'Urungkan', onClick: () => update(() => before) }
		});
	};

	const db = /^[0-8]$/.test(view) ? Number(view) : null;

	return (
		<div className="nt-app" ref={top}>
			<Header
				meeting={meeting}
				layarHref={layarHref}
				saved={saved}
				unreadable={unreadable}
				onDownloadOld={downloadOld}
				onReset={() => setConfirmReset(true)}
				onPrint={print}
				onSave={save}
				demo={demo}
			/>
			<div className="nt-shell">
				<Nav
					meeting={meeting}
					view={view}
					onView={go}
					onLayar={onLayar}
					follow={follow}
					onFollow={followLayar}
				/>
				<main className="nt-main" ref={main}>
					{view === 'views' ? (
						<DerivedViews meeting={meeting} />
					) : view === 'guide' ? (
						<Guide />
					) : (
						<AgendaView
							key={view}
							db={db ?? 0}
							records={meeting.records[db ?? 0]}
							setRecords={setRecords(db ?? 0)}
							toast={toast}
							live={{ onCapture: capture, notes: notesOf(db ?? 0), onNotes: setNotes(db ?? 0) }}
						/>
					)}
				</main>
			</div>
			<Dialog
				open={confirmReset}
				onClose={() => setConfirmReset(false)}
				title="Reset notulen?"
				description="Seluruh isian dikembalikan ke template awal. Selama 15 detik setelahnya masih bisa diurungkan; setelah itu tidak."
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
