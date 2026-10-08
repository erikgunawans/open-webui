import { Alert, Badge, Button, DropdownMenu, Tooltip } from '@jup/ui';
import {
	Download,
	Lock,
	LockOpen,
	Monitor,
	MoreHorizontal,
	Printer,
	RotateCcw
} from 'lucide-react';

import { CHECKLIST, toneOf } from '../../agendas';
import { checklistCount, fmtDate, mainInfo, meetingName } from '../../selectors';
import { text, valueLabel, type Meeting } from '../../types';
import type { SaveState, Unreadable } from '../useMeeting';

// The Notulen header, in the KPI 2026 tab's form: eyebrow, meeting name and a meta line over a
// heavy rule, the actions to its right (layar, Tutup rapat, print, the one primary: save, and Reset
// last, inside "Lainnya", away from Tutup rapat). The theme is the app's, so there is no switch
// here. The saved badge in the meta line says when the last edit was stored, its tooltip where the
// data lives; when the browser refused a write, an alert stops the reader.

type Props = {
	meeting: Meeting;
	layarHref: string;
	saved: SaveState;
	/** Stored data that could not be read when the meeting opened; offered for download. */
	unreadable?: Unreadable;
	onDownloadOld?: () => void;
	/** Absent for a read-only reader: no Reset notulen. */
	onReset?: () => void;
	onPrint: () => void;
	onSave: () => void;
	/** Tutup rapat, or Buka kembali once closed: both ask first (NotulenApp). */
	onTutup?: () => void;
	onReopen?: () => void;
	/** The fictional demo meeting: marked as on the Layar. */
	demo?: boolean;
	/** A reader without the write grant (story 16): marked Hanya baca. */
	readOnly?: boolean;
	/** Kept on the server (records enabled), not in this browser. */
	remote?: boolean;
	/** The local edits a conflicting save could not store, offered for download. */
	onDownloadConflict?: () => void;
};

const clock = (at: number) =>
	new Date(at).toLocaleTimeString('id-ID', {
		hour: '2-digit',
		minute: '2-digit',
		timeZone: 'Asia/Jakarta'
	});

/** Where the data lives: the saved badge's tooltip (it was a paragraph on every agenda). */
export const STORAGE_NOTE =
	'Isian tersimpan otomatis di peramban dan perangkat ini saja, untuk akun Anda; belum ada salinan di server. Gunakan Simpan HTML terisi untuk membuat salinan berisi data.';

/** The same, for a meeting kept on the server. */
export const SERVER_NOTE =
	'Isian tersimpan otomatis di server, sekitar sekali per detik, dan terbuka dari perangkat mana pun tempat Anda masuk.';

export const Header = ({
	meeting,
	layarHref,
	saved,
	unreadable = null,
	onDownloadOld,
	onReset,
	onPrint,
	onSave,
	onTutup,
	onReopen,
	demo,
	readOnly = false,
	remote = false,
	onDownloadConflict
}: Props) => {
	const closed = meeting.session.closedAt !== undefined;
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
								{valueLabel('Status validasi', status)}
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
						{readOnly ? <Badge variant="outline">Hanya baca</Badge> : null}
						{when ? <span className="nt-mono">{when}</span> : null}
						{where ? <span>{where}</span> : null}
						<span className="nt-mono nt-muted">
							Checklist {checklistCount(meeting)}/{CHECKLIST.length}
						</span>
						<span role="status" className="nt-saved">
							{saved.ok && !readOnly ? (
								<Tooltip content={remote ? SERVER_NOTE : STORAGE_NOTE} placement="bottom">
									<span tabIndex={0} className="nt-saved__badge">
										{saved.pending ? (
											<Badge variant="outline">Menyimpan…</Badge>
										) : saved.at !== null ? (
											<Badge tone="success" dot>
												Tersimpan · {clock(saved.at)} WIB
											</Badge>
										) : (
											<Badge variant="outline">
												{remote ? 'Tersimpan di server' : 'Tersimpan di peramban ini'}
											</Badge>
										)}
									</span>
								</Tooltip>
							) : null}
						</span>
					</div>
					{saved.ok ? null : (
						<Alert
							tone="danger"
							title={
								remote
									? 'Perubahan terakhir belum tersimpan di server'
									: 'Perubahan terakhir belum tersimpan'
							}
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
							{remote
								? 'Server tidak terjangkau atau menolak penyimpanan, jadi isian terbaru hanya ada di tab ini. Aplikasi mencoba lagi bila server sedang tidak terjangkau. Unduh salinannya sekarang; peringatan ini hilang begitu penyimpanan berhasil lagi.'
								: 'Penyimpanan peramban ini penuh atau diblokir, jadi isian hanya ada di tab ini dan hilang bila tab ditutup. Unduh salinannya sekarang; peringatan ini hilang begitu penyimpanan berhasil lagi.'}
						</Alert>
					)}
					{saved.conflict ? (
						<Alert
							tone="warning"
							title="Rapat ini diubah di perangkat lain"
							className="nt-save-alert"
							actions={
								onDownloadConflict ? (
									<Button
										variant="secondary"
										size="sm"
										iconLeft={<Download size={16} aria-hidden="true" />}
										onClick={onDownloadConflict}
									>
										Unduh perubahan saya
									</Button>
								) : null
							}
						>
							Versi terbaru dari server sudah dimuat, jadi perubahan terakhir Anda tidak menimpanya.
							Perubahan itu tidak hilang: unduh untuk memasukkannya kembali. Peringatan ini hilang
							begitu penyimpanan berikutnya berhasil.
						</Alert>
					) : null}
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
					{!onTutup || !onReopen ? null : closed ? (
						<Button
							variant="ghost"
							iconLeft={<LockOpen size={16} aria-hidden="true" />}
							onClick={onReopen}
						>
							Buka kembali
						</Button>
					) : (
						<Button
							variant="ghost"
							iconLeft={<Lock size={16} aria-hidden="true" />}
							onClick={onTutup}
						>
							Tutup rapat
						</Button>
					)}
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
					{onReset ? (
						<DropdownMenu
							label="Lainnya"
							align="end"
							trigger={
								<Button variant="ghost" iconLeft={<MoreHorizontal size={16} aria-hidden="true" />}>
									Lainnya
								</Button>
							}
							items={[
								{
									id: 'reset',
									label: 'Reset notulen',
									icon: <RotateCcw size={16} aria-hidden="true" />,
									disabled: closed,
									destructive: true,
									onSelect: onReset
								}
							]}
						/>
					) : null}
				</div>
			</div>
		</header>
	);
};
