import { Alert, Badge, Button } from '@jup/ui';
import { Download, Monitor, Printer, RotateCcw } from 'lucide-react';

import { CHECKLIST, toneOf } from '../../agendas';
import { checklistCount, fmtDate, mainInfo, meetingName } from '../../selectors';
import { text, type Meeting } from '../../types';
import type { SaveState, Unreadable } from '../useMeeting';

// The Notulen header, in the KPI 2026 tab's form: eyebrow, meeting name and a meta line over a
// heavy rule, the actions to its right (layar, reset, print, the one primary: save). The theme is
// the app's, so there is no switch here. The storage note stays in view on every agenda, and says
// when the last edit was stored — or, when the browser refused it, stops the reader with an alert.

type Props = {
	meeting: Meeting;
	layarHref: string;
	saved: SaveState;
	/** Stored data that could not be read when the meeting opened; offered for download. */
	unreadable?: Unreadable;
	onDownloadOld?: () => void;
	onReset: () => void;
	onPrint: () => void;
	onSave: () => void;
	/** The fictional demo meeting: marked as on the Layar. */
	demo?: boolean;
};

const clock = (at: number) =>
	new Date(at).toLocaleTimeString('id-ID', {
		hour: '2-digit',
		minute: '2-digit',
		timeZone: 'Asia/Jakarta'
	});

export const Header = ({
	meeting,
	layarHref,
	saved,
	unreadable = null,
	onDownloadOld,
	onReset,
	onPrint,
	onSave,
	demo
}: Props) => {
	const mv = mainInfo(meeting)?.values ?? {};
	const status = text(mv['Status validasi']);
	const klas = text(mv['Klasifikasi dokumen']);
	const when = fmtDate(mv['Tanggal & waktu']);
	const where = text(mv['Ruang / lokasi']);

	return (
		<header className="nt-top">
			<div className="nt-top__in">
				<div className="nt-top__id">
					<div className="nt-eyebrow">Rapat Direksi · Notulen</div>
					<h1 className="nt-h1">{meetingName(meeting)}</h1>
					<div className="nt-top__meta">
						{status ? (
							<Badge tone={toneOf(status)} dot>
								{status}
							</Badge>
						) : null}
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
						{when ? <span className="nt-mono">{when}</span> : null}
						{where ? <span>{where}</span> : null}
						<span className="nt-mono nt-muted">
							Checklist {checklistCount(meeting)}/{CHECKLIST.length}
						</span>
					</div>
					<p className="nt-note">
						<span role="status" className="nt-saved">
							{saved.ok && saved.at !== null ? (
								<Badge tone="success" dot>
									Tersimpan · {clock(saved.at)} WIB
								</Badge>
							) : saved.ok ? (
								<Badge variant="outline">Tersimpan di peramban ini</Badge>
							) : null}
						</span>
						<span>
							Isian tersimpan otomatis di peramban dan perangkat ini saja, untuk akun Anda; belum
							ada salinan di server. Gunakan <strong>Simpan HTML terisi</strong> untuk membuat
							salinan berisi data.
						</span>
					</p>
					{saved.ok ? null : (
						<Alert
							tone="danger"
							title="Perubahan terakhir belum tersimpan"
							className="nt-save-alert"
							actions={
								<Button
									variant="danger"
									size="sm"
									iconLeft={<Download size={16} aria-hidden="true" />}
									onClick={onSave}
								>
									Simpan HTML terisi sekarang
								</Button>
							}
						>
							Penyimpanan peramban ini penuh atau diblokir, jadi isian hanya ada di tab ini dan
							hilang bila tab ditutup. Unduh salinannya sekarang; peringatan ini hilang begitu
							penyimpanan berhasil lagi.
						</Alert>
					)}
					{unreadable ? (
						<Alert
							tone="warning"
							title="Data lama rapat ini tidak dapat dibaca"
							className="nt-save-alert"
							actions={
								onDownloadOld ? (
									<Button
										variant="secondary"
										size="sm"
										iconLeft={<Download size={16} aria-hidden="true" />}
										onClick={onDownloadOld}
									>
										Unduh data lama
									</Button>
								) : null
							}
						>
							{unreadable.kept
								? 'Notulen dimulai dari template. Data lama tidak dihapus: salinannya disimpan terpisah di peramban ini dan bisa diunduh untuk dipulihkan oleh admin.'
								: 'Notulen dimulai dari template, tetapi tidak menimpa data lama karena salinannya tidak bisa dibuat. Unduh data lama sekarang sebelum mengisi.'}
						</Alert>
					) : null}
				</div>
				<div className="nt-actions">
					<Button
						variant="ghost"
						iconLeft={<Monitor size={16} aria-hidden="true" />}
						onClick={() => window.open(layarHref, '_blank', 'noopener')}
					>
						Buka layar
					</Button>
					<Button
						variant="ghost"
						iconLeft={<RotateCcw size={16} aria-hidden="true" />}
						onClick={onReset}
					>
						Reset
					</Button>
					<Button
						variant="secondary"
						iconLeft={<Printer size={16} aria-hidden="true" />}
						onClick={onPrint}
					>
						Cetak / PDF
					</Button>
					<Button
						variant="primary"
						iconLeft={<Download size={16} aria-hidden="true" />}
						onClick={onSave}
					>
						Simpan HTML terisi
					</Button>
				</div>
			</div>
		</header>
	);
};
