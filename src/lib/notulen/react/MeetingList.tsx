import { Alert, Badge, Button } from '@jup/ui';
import { CloudUpload, FilePlus2, Monitor, NotebookPen } from 'lucide-react';
import { useState } from 'react';

import { toneOf } from '../agendas';
import { DEMO_ID, demoMeeting } from '../demo';
import type { MoveOutcome, MoveReport } from '../migrate';
import type { MeetingRepo } from '../repo';
import { fmtDate, mainInfo, meetingName, pendingDecisions } from '../selectors';
import { text, valueLabel, type Meeting } from '../types';
import './notulen/notulen.css';

// The "Rapat Direksi" tab, in the KPI 2026 tab's form: a header over a heavy rule, then one table
// of the reader's meetings (on the server when records are enabled, else on this browser), with
// the demo meeting as its last row.

export type MeetingListProps = {
	repo: MeetingRepo;
	/** Where the demo meeting lives: always this browser. Defaults to `repo`. */
	demoRepo?: MeetingRepo;
	base: string;
	newId: () => string;
	open: (href: string) => void;
	/**
	 * Given when meetings are on the server and the reader may write them: the meetings this
	 * browser still holds from before, and the one-time move (`migrate.ts`).
	 */
	move?: { pending: () => Meeting[]; run: () => Promise<MoveReport> };
};

const OUTCOME: Record<MoveOutcome['result'], string> = {
	moved: 'Dipindahkan ke server',
	on_server: 'Sudah ada di server',
	kept: 'Di server sudah ada notulen lain dengan nomor ini; salinan di peramban tetap disimpan',
	refused: 'Ditolak server; salinan di peramban tetap disimpan'
};

const MoveOffer = ({
	move,
	onMoved
}: {
	move: NonNullable<MeetingListProps['move']>;
	/** The table reads the repository again: moved meetings are listed at once. */
	onMoved: () => void;
}) => {
	const [busy, setBusy] = useState(false);
	const [report, setReport] = useState<{ names: Map<string, string>; report: MoveReport } | null>(
		null
	);
	const pending = move.pending();
	if (!pending.length && !report) return null;
	const run = async () => {
		const names = new Map(pending.map((m) => [m.id, meetingName(m)]));
		setBusy(true);
		try {
			setReport({ names, report: await move.run() });
		} finally {
			setBusy(false);
			onMoved();
		}
	};
	const done = report?.report.ok ? report.report.outcomes : [];
	return (
		<Alert
			tone={report && !report.report.ok ? 'warning' : 'info'}
			title={
				pending.length
					? `${pending.length} notulen masih tersimpan di peramban ini`
					: 'Semua notulen dari peramban ini sudah di server'
			}
			className="nt-save-alert"
		>
			{pending.length ? (
				<p>
					Notulen ini dibuat sebelum rapat disimpan di server. Pindahkan sekali agar terbuka dari
					perangkat mana pun. Notulen yang sudah ada di server tidak ditimpa, dan salinan di
					peramban dihapus hanya setelah server menyimpannya.
				</p>
			) : null}
			{report && !report.report.ok ? (
				<p role="alert">
					{report.report.status === 403
						? 'Akun Anda belum memiliki izin menulis notulen.'
						: 'Server tidak dapat dihubungi atau menolak permintaan.'}{' '}
					Tidak ada yang dipindahkan; salinan di peramban tetap disimpan.
				</p>
			) : null}
			{done.length ? (
				<ul className="nt-move-results" aria-live="polite">
					{done.map((o) => (
						<li key={o.id}>
							<strong>{report?.names.get(o.id) ?? o.id}</strong>{' '}
							<span className="nt-mono nt-muted">{o.id}</span> — {OUTCOME[o.result]}
						</li>
					))}
				</ul>
			) : null}
			{pending.length ? (
				<div className="nt-actions">
					<Button
						variant="secondary"
						size="sm"
						disabled={busy}
						iconLeft={<CloudUpload size={16} aria-hidden="true" />}
						onClick={() => void run()}
					>
						{busy ? 'Memindahkan…' : 'Pindahkan ke server'}
					</Button>
				</div>
			) : null}
		</Alert>
	);
};

const Row = ({
	m,
	base,
	open,
	demo
}: {
	m: Meeting;
	base: string;
	open: (href: string) => void;
	demo?: boolean;
}) => {
	const v = mainInfo(m)?.values ?? {};
	const status = text(v['Status validasi']);
	const when = fmtDate(v['Tanggal & waktu']);
	return (
		<tr className={demo ? 'nt-trow is-demo' : 'nt-trow'}>
			<td>
				<div className="nt-trow__name">{meetingName(m)}</div>
				<div className="nt-mono nt-muted">
					{demo ? 'Data dummy (fiktif) untuk mencoba layar rapat' : m.id}
				</div>
			</td>
			<td className="nt-mono">{when || '—'}</td>
			<td>
				{demo ? (
					<Badge variant="outline">Contoh</Badge>
				) : status ? (
					<Badge tone={toneOf(status)} dot>
						{valueLabel('Status validasi', status)}
					</Badge>
				) : (
					<span className="nt-muted">—</span>
				)}
			</td>
			<td className="nt-mono nt-r">{pendingDecisions(m).length}</td>
			<td>
				<div className="nt-actions nt-actions--end">
					<Button
						variant="secondary"
						size="sm"
						iconLeft={<NotebookPen size={16} aria-hidden="true" />}
						onClick={() => open(`${base}/${m.id}/notulen`)}
					>
						Notulen
					</Button>
					<Button
						variant="ghost"
						size="sm"
						iconLeft={<Monitor size={16} aria-hidden="true" />}
						onClick={() => window.open(`${base}/${m.id}/layar`, '_blank', 'noopener')}
					>
						Layar
					</Button>
				</div>
			</td>
		</tr>
	);
};

export const MeetingList = ({
	repo,
	demoRepo = repo,
	base,
	newId,
	open,
	move
}: MeetingListProps) => {
	const [, setMoves] = useState(0);
	const remote = !!repo.remote;
	const meetings = repo.list().filter((m) => m.id !== DEMO_ID);
	// A meeting the list cannot read would otherwise just vanish. Opening it sets the data aside
	// and offers it for download (useMeeting), so the way back is one click.
	const unreadable = (repo.unreadableIds?.() ?? []).filter((id) => id !== DEMO_ID);
	// The demo row reads the stored demo when there is one, so its counts match what Layar shows.
	const demo = demoRepo.get(DEMO_ID) ?? demoMeeting();
	return (
		<div className="nt-list">
			<header className="nt-top">
				<div className="nt-top__in">
					<div className="nt-top__id">
						<div className="nt-eyebrow">Rapat Direksi</div>
						<h2 className="nt-h1">Notulen rapat</h2>
						<div className="nt-top__meta">
							<Badge variant="outline">
								{remote ? 'Tersimpan di server' : 'Tersimpan di peramban ini'}
							</Badge>
							<span className="nt-muted">
								{meetings.length} notulen ·{' '}
								{remote
									? 'Layar mengikuti dari perangkat mana pun'
									: 'Layar mengikuti dari tab lain peramban yang sama'}
							</span>
						</div>
					</div>
					<div className="nt-actions">
						<Button
							variant="primary"
							iconLeft={<FilePlus2 size={16} aria-hidden="true" />}
							onClick={() => open(`${base}/${newId()}/notulen`)}
						>
							Rapat baru
						</Button>
					</div>
				</div>
			</header>
			{remote && move ? <MoveOffer move={move} onMoved={() => setMoves((n) => n + 1)} /> : null}
			{unreadable.length ? (
				<Alert
					tone="warning"
					title={`${unreadable.length} notulen tidak dapat dibaca`}
					className="nt-save-alert"
				>
					<p>
						Datanya rusak atau dibuat versi lain aplikasi, jadi tidak tampil di tabel. Buka untuk
						memulihkan: data lama disisihkan dan dapat diunduh, tidak dihapus.
					</p>
					<div className="nt-unreadable">
						{unreadable.map((id) => (
							<Button
								key={id}
								variant="secondary"
								size="sm"
								iconLeft={<NotebookPen size={16} aria-hidden="true" />}
								onClick={() => open(`${base}/${id}/notulen`)}
							>
								Pulihkan <span className="nt-mono">{id}</span>
							</Button>
						))}
					</div>
				</Alert>
			) : null}
			<section className="nt-tablecard">
				<div className="nt-tablewrap">
					<table className="nt-table">
						<thead>
							<tr>
								<th scope="col">Rapat</th>
								<th scope="col">Tanggal</th>
								<th scope="col">Status validasi</th>
								<th scope="col" className="nt-r">
									Perlu keputusan
								</th>
								<th scope="col">
									<span className="nt-sr">Tindakan</span>
								</th>
							</tr>
						</thead>
						<tbody>
							{meetings.length ? (
								meetings.map((m) => <Row key={m.id} m={m} base={base} open={open} />)
							) : (
								<tr>
									<td colSpan={5} className="nt-tempty">
										Belum ada notulen {remote ? 'di server' : 'di peramban ini'}. Gunakan{' '}
										<strong>Rapat baru</strong>.
									</td>
								</tr>
							)}
							<Row m={demo} base={base} open={open} demo />
						</tbody>
					</table>
				</div>
			</section>
			{remote ? (
				<p className="nt-foot">
					Notulen dan status rapat tersimpan di server dan terbuka dari perangkat mana pun tempat
					Anda masuk. Rapat contoh tetap tersimpan di peramban ini saja.
				</p>
			) : (
				<p className="nt-foot">
					Notulen dan status rapat tersimpan di peramban dan perangkat ini saja, untuk akun Anda;
					belum ada salinan di server. Layar rapat mengikuti Notulen dari tab lain di peramban yang
					sama, bukan dari perangkat lain. Simpan salinan dengan <strong>Simpan HTML terisi</strong>{' '}
					setelah rapat.
				</p>
			)}
		</div>
	);
};
