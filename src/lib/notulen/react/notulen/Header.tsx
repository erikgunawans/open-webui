import { Badge, Button, IconButton, useJupTheme } from '@jup/ui';
import { Download, Monitor, Moon, Printer, RotateCcw, Sun } from 'lucide-react';

import { CHECKLIST, toneOf } from '../../agendas';
import { checklistCount, fmtDate, mainInfo, meetingName } from '../../selectors';
import { text, type Meeting } from '../../types';

// The sticky Notulen header: eyebrow, meeting name, validation/classification/date/place/checklist
// meta, and the actions (theme, layar, reset, print, the one primary: save).

type Props = {
	meeting: Meeting;
	layarHref: string;
	onReset: () => void;
	onPrint: () => void;
	onSave: () => void;
};

export const Header = ({ meeting, layarHref, onReset, onPrint, onSave }: Props) => {
	const { resolvedTheme, setTheme } = useJupTheme();
	const mv = mainInfo(meeting)?.values ?? {};
	const status = text(mv['Status validasi']);
	const klas = text(mv['Klasifikasi dokumen']);
	const when = fmtDate(mv['Tanggal & waktu']);
	const where = text(mv['Ruang / lokasi']);
	const dark = resolvedTheme === 'dark';

	return (
		<header className="nt-top">
			<div className="nt-top__in">
				<div className="nt-top__id">
					<div className="nt-eyebrow">Rapat Direksi / Notulen</div>
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
				</div>
				<div className="nt-actions">
					<IconButton
						label={dark ? 'Gunakan tema terang' : 'Gunakan tema gelap'}
						variant="ghost"
						onClick={() => setTheme(dark ? 'light' : 'dark')}
					>
						{dark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
					</IconButton>
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
