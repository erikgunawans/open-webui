import { Alert, Badge, Button } from '@jup/ui';
import { FilePlus2, Monitor, NotebookPen } from 'lucide-react';

import { toneOf } from '../agendas';
import { DEMO_ID, demoMeeting } from '../demo';
import type { LocalStorageMeetingRepo } from '../repo';
import { fmtDate, mainInfo, meetingName, pendingDecisions } from '../selectors';
import { text, valueLabel, type Meeting } from '../types';
import './notulen/notulen.css';

// The "Rapat Direksi" tab, in the KPI 2026 tab's form: a header over a heavy rule, then one table
// of the reader's meetings on this browser, with the demo meeting as its last row.

export type MeetingListProps = {
	repo: LocalStorageMeetingRepo;
	base: string;
	newId: () => string;
	open: (href: string) => void;
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

export const MeetingList = ({ repo, base, newId, open }: MeetingListProps) => {
	const meetings = repo.list().filter((m) => m.id !== DEMO_ID);
	// A meeting the list cannot read would otherwise just vanish. Opening it sets the data aside
	// and offers it for download (useMeeting), so the way back is one click.
	const unreadable = repo.unreadableIds().filter((id) => id !== DEMO_ID);
	// The demo row reads the stored demo when there is one, so its counts match what Layar shows.
	const demo = repo.get(DEMO_ID) ?? demoMeeting();
	return (
		<div className="nt-list">
			<header className="nt-top">
				<div className="nt-top__in">
					<div className="nt-top__id">
						<div className="nt-eyebrow">Rapat Direksi</div>
						<h2 className="nt-h1">Notulen rapat</h2>
						<div className="nt-top__meta">
							<Badge variant="outline">Tersimpan di peramban ini</Badge>
							<span className="nt-muted">
								{meetings.length} notulen · Layar mengikuti dari tab lain peramban yang sama
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
										Belum ada notulen di peramban ini. Gunakan <strong>Rapat baru</strong>.
									</td>
								</tr>
							)}
							<Row m={demo} base={base} open={open} demo />
						</tbody>
					</table>
				</div>
			</section>
			<p className="nt-foot">
				Notulen dan status rapat tersimpan di peramban dan perangkat ini saja, untuk akun Anda;
				belum ada salinan di server. Layar rapat mengikuti Notulen dari tab lain di peramban yang
				sama, bukan dari perangkat lain. Simpan salinan dengan <strong>Simpan HTML terisi</strong>{' '}
				setelah rapat.
			</p>
		</div>
	);
};
