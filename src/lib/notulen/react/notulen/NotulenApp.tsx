import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Dialog, Textarea, useJupTheme, useToast } from '@jup/ui';

import type { MeetingRepo } from '../../repo';
import { captureLabel, captureRecord, type Capture } from '../../capture';
import { closingGaps, gapLine, reopenMeeting } from '../../keputusan';
import { closeMeeting, jakartaLocal } from '../../layar-model';
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
	// Ikuti layar starts on: while the meeting runs, open where the Layar is; once it is closed,
	// where this reader last was.
	const [view, setView] = useState<View>(() =>
		meeting.session.closedAt === undefined
			? (String(meeting.session.currentAgenda) as View)
			: readView(viewKey)
	);
	const [confirmReset, setConfirmReset] = useState(false);
	const [asking, setAsking] = useState<null | 'close' | 'reopen'>(null);
	const [reason, setReason] = useState('');
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
			title: `${captureLabel(c.kind, c.from)} dicatat${where}`,
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

	const closed = meeting.session.closedAt !== undefined;
	const gaps = closingGaps(meeting);
	// The Tutup rapat dialog opens on its primary. The dialog's focus trap puts focus on its first
	// control (the close icon) in its own effect; this parent effect runs after it and moves it on.
	// Buka kembali opens on its reason field, for the same reason.
	const closeDefault = useRef<HTMLButtonElement>(null);
	const reopenReason = useRef<HTMLTextAreaElement>(null);
	useEffect(() => {
		if (asking === 'close') closeDefault.current?.focus();
		if (asking === 'reopen') reopenReason.current?.focus();
	}, [asking]);
	const closeRapat = () => {
		update((m) => closeMeeting(m, Date.now()));
		setAsking(null);
		toast({ title: 'Rapat ditutup', description: 'Notulen kini hanya-baca.', tone: 'success' });
	};
	const reopen = () => {
		if (!reason.trim()) return;
		update((m) => reopenMeeting(m, reason, Date.now()));
		setAsking(null);
		setReason('');
		toast({ title: 'Rapat dibuka kembali', description: reason.trim(), tone: 'warning' });
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
			// Only claim the stored copy when the last write actually landed.
			description: saved.ok
				? `Salinan baca-saja; isian tetap tersimpan di ${repo.remote ? 'server' : 'peramban ini'}.`
				: `Simpan file ini baik-baik: isian belum tersimpan di ${repo.remote ? 'server' : 'peramban ini'}.`,
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

	// The edits a conflicting save could not store, as a readable HTML copy to re-enter from.
	const downloadConflict = async () => {
		if (!saved.conflict) return;
		const { downloadSnapshot } = await import('./snapshot');
		downloadSnapshot(saved.conflict, resolvedTheme);
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
				onTutup={() => setAsking('close')}
				onReopen={() => setAsking('reopen')}
				demo={demo}
				remote={!!repo.remote}
				onDownloadConflict={downloadConflict}
			/>
			{closed ? (
				<Alert tone="info" title="Rapat ditutup" className="nt-closed">
					Ditutup pukul {jakartaLocal(meeting.session.closedAt!).slice(11).replace(':', '.')} WIB.
					Notulen hanya-baca; untuk mengubahnya, gunakan <strong>Buka kembali</strong> dan tulis
					alasannya.
				</Alert>
			) : null}
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
					<fieldset className="nt-freeze" disabled={closed}>
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
					</fieldset>
				</main>
			</div>
			<Dialog
				open={asking === 'close'}
				onClose={() => setAsking(null)}
				title="Tutup rapat?"
				description={
					gaps.any
						? `${gapLine(gaps)}. Setelah ditutup, Notulen hanya-baca.`
						: 'Semua usulan sudah diputuskan. Setelah ditutup, Notulen hanya-baca.'
				}
				footer={
					<>
						<Button variant="ghost" onClick={() => setAsking(null)}>
							Batal
						</Button>
						{/* With gaps the safe way is the default (primary, focused); closing anyway is a
						    deliberate second choice. */}
						{gaps.any ? (
							<>
								<Button variant="outline" onClick={closeRapat}>
									Tutup tetap
								</Button>
								<Button
									ref={closeDefault}
									variant="primary"
									autoFocus
									onClick={() => {
										setAsking(null);
										go('7');
									}}
								>
									Kembali ke 07
								</Button>
							</>
						) : (
							<Button ref={closeDefault} variant="primary" autoFocus onClick={closeRapat}>
								Tutup rapat
							</Button>
						)}
					</>
				}
			/>
			<Dialog
				open={asking === 'reopen'}
				onClose={() => setAsking(null)}
				title="Buka kembali rapat?"
				description="Alasannya dicetak di Risalah."
				footer={
					<>
						<Button variant="ghost" onClick={() => setAsking(null)}>
							Batal
						</Button>
						<Button variant="primary" disabled={!reason.trim()} onClick={reopen}>
							Buka kembali
						</Button>
					</>
				}
			>
				<Textarea
					ref={reopenReason}
					autoFocus
					rows={3}
					value={reason}
					onChange={(e) => setReason(e.target.value)}
					placeholder="Alasan membuka kembali…"
					aria-label="Alasan membuka kembali"
				/>
			</Dialog>
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
