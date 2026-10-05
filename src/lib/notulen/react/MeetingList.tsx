import { Alert, Badge, Button, Card } from '@jup/ui';
import { FilePlus2, Monitor, NotebookPen } from 'lucide-react';

import { toneOf } from '../agendas';
import type { LocalStorageMeetingRepo } from '../repo';
import { fmtDate, mainInfo, meetingName, pendingDecisions } from '../selectors';
import { text } from '../types';
import './notulen/notulen.css';

// The "Rapat Direksi" tab: the reader's meetings on this browser, a new one, and the demo.

export type MeetingListProps = {
	repo: LocalStorageMeetingRepo;
	base: string;
	newId: () => string;
	open: (href: string) => void;
};

export const MeetingList = ({ repo, base, newId, open }: MeetingListProps) => {
	const meetings = repo.list().filter((m) => m.id !== 'demo');
	return (
		<div className="nt-list">
			<Alert tone="info" title="Notulen tersimpan di peramban ini">
				Notulen dan status rapat tersimpan di peramban dan perangkat ini saja, untuk akun Anda.
				Layar rapat mengikuti dari tab lain peramban yang sama, bukan dari perangkat lain.
			</Alert>
			<div className="nt-list__head">
				<h2 className="nt-h2">Notulen rapat</h2>
				<Button
					variant="primary"
					iconLeft={<FilePlus2 size={16} aria-hidden="true" />}
					onClick={() => open(`${base}/${newId()}/notulen`)}
				>
					Rapat baru
				</Button>
			</div>
			{meetings.length ? (
				meetings.map((m) => {
					const v = mainInfo(m)?.values ?? {};
					const status = text(v['Status validasi']);
					return (
						<Card
							key={m.id}
							padding="md"
							title={meetingName(m)}
							description={
								<span className="nt-rec__meta">
									<span className="nt-mono">{m.id}</span>
									{fmtDate(v['Tanggal & waktu']) ? (
										<span>{fmtDate(v['Tanggal & waktu'])}</span>
									) : null}
									{status ? (
										<Badge tone={toneOf(status)} dot>
											{status}
										</Badge>
									) : null}
									<span>{pendingDecisions(m).length} perlu keputusan</span>
								</span>
							}
							actions={
								<div className="nt-actions">
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
							}
						/>
					);
				})
			) : (
				<p className="nt-empty">Belum ada notulen di peramban ini. Gunakan Rapat baru.</p>
			)}
			<Card
				padding="md"
				title="Rapat contoh"
				description="Data dummy (fiktif) untuk mencoba layar rapat."
				actions={
					<div className="nt-actions">
						<Button variant="secondary" size="sm" onClick={() => open(`${base}/demo/notulen`)}>
							Notulen
						</Button>
						<Button
							variant="ghost"
							size="sm"
							iconLeft={<Monitor size={16} aria-hidden="true" />}
							onClick={() => window.open(`${base}/demo/layar`, '_blank', 'noopener')}
						>
							Layar
						</Button>
					</div>
				}
			/>
		</div>
	);
};
