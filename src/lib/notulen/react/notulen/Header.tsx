import { Badge, Button } from '@jup/ui';
import { Download, Monitor, Printer, RotateCcw } from 'lucide-react';

import { CHECKLIST, toneOf } from '../../agendas';
import { checklistCount, fmtDate, mainInfo, meetingName } from '../../selectors';
import { text, type Meeting } from '../../types';

// The Notulen header, in the KPI 2026 tab's form: eyebrow, meeting name and a meta line over a
// heavy rule, the actions to its right (layar, reset, print, the one primary: save). The theme is
// the app's, so there is no switch here. The storage note stays in view on every agenda.

type Props = {
	meeting: Meeting;
	layarHref: string;
	onReset: () => void;
	onPrint: () => void;
	onSave: () => void;
};

export const Header = ({ meeting, layarHref, onReset, onPrint, onSave }: Props) => {
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
						{when ? <span className="nt-mono">{when}</span> : null}
						{where ? <span>{where}</span> : null}
						<span className="nt-mono nt-muted">
							Checklist {checklistCount(meeting)}/{CHECKLIST.length}
						</span>
					</div>
					<p className="nt-note">
						<Badge variant="outline">Tersimpan di peramban ini</Badge>
						<span>
							Isian tersimpan otomatis di peramban dan perangkat ini saja, untuk akun Anda; belum
							ada salinan di server. Gunakan <strong>Simpan HTML terisi</strong> untuk membuat
							salinan berisi data.
						</span>
					</p>
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
