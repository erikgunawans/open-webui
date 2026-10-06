import { useEffect, useState } from 'react';
import { Button, Card, Input, Tag, Textarea } from '@jup/ui';
import { Check } from 'lucide-react';

import { agendaLabel } from '../../../agendas';
import { decisionGaps, RUMUSAN, ULANG } from '../../../keputusan';
import { decisionId } from '../../../layar-model';
import { decisions, isDecided } from '../../../selectors';
import { DECISION_STATUS, SYARAT, isDate, text, type PropValue } from '../../../types';
import { Head, Nothing, StatusBadge, type ViewProps } from './common';

// 07 Pengambilan Keputusan: the Board decides live. Choosing a Keputusan opens its kolom in place
// (no modal over the projected screen): the Rumusan always, the Syarat for Disetujui bersyarat, the
// date it comes back for Ditunda — typed where the room reads them as they are written. The
// Keputusan is recorded only once they are filled (Erik, 2026-10-06). Clicking the active status
// again reverts it to "Belum diputuskan"; every change can be taken back from the Layar notice.

const ACTS: [status: string, active: 'primary' | 'secondary' | 'danger', label: string][] = [
	['Disetujui', 'primary', 'Setujui'],
	['Disetujui bersyarat', 'secondary', 'Setujui bersyarat'],
	['Ditunda', 'secondary', 'Tunda'],
	['Ditolak', 'danger', 'Tolak']
];

type Props = ViewProps & {
	selected: string | null;
	onSelect: (recordId: string) => void;
	onDecide: (recordId: string, status: string, values?: Record<string, PropValue>) => void;
};

const QUESTION: Record<string, string> = {
	Disetujui: 'Setujui usulan ini',
	'Disetujui bersyarat': 'Setujui dengan syarat',
	Ditunda: 'Tunda usulan ini',
	Ditolak: 'Tolak usulan ini'
};

export const V07Keputusan = ({ meeting, agenda, selected, onSelect, onDecide }: Props) => {
	const list = decisions(meeting);
	const d = list.find((x) => x.id === selected) ?? list[0];
	const statusOf = (r: (typeof list)[number]) =>
		text(r.values[DECISION_STATUS]) || 'Belum diputuskan';
	const decided = list.filter(isDecided).length;
	// The Keputusan being written for one Usulan; any other selection drops it.
	const [draft, setDraft] = useState<{ id: string; status: string } | null>(null);
	const [rumusan, setRumusan] = useState('');
	const [syarat, setSyarat] = useState('');
	const [ulang, setUlang] = useState('');
	const asking = !!d && draft?.id === d.id;

	useEffect(() => {
		if (!asking) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') setDraft(null);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [asking]);

	const choose = (id: string, status: string, on: boolean) => {
		if (on) {
			setDraft(null);
			onDecide(id, 'Belum diputuskan');
			return;
		}
		const r = list.find((x) => x.id === id);
		const u = r?.values[ULANG];
		setRumusan(text(r?.values[RUMUSAN]));
		setSyarat(text(r?.values[SYARAT]));
		setUlang(isDate(u) ? u.start.slice(0, 10) : '');
		setDraft({ id, status });
	};

	const values = (): Record<string, PropValue> => ({
		[RUMUSAN]: rumusan.trim(),
		...(draft?.status === 'Disetujui bersyarat' ? { [SYARAT]: syarat.trim() } : {}),
		...(draft?.status === 'Ditunda' && ulang ? { [ULANG]: { start: ulang, end: '' } } : {})
	});
	const missing =
		d && draft ? decisionGaps({ ...d, values: { ...d.values, ...values() } }, draft.status) : [];

	return (
		<div className="lr-view">
			<Head
				agenda={agenda}
				right={
					<div className="lr-tagline">
						<span className="lr-k">Diputuskan</span>
						<span className="lr-bignum">
							{decided}/{list.length}
						</span>
					</div>
				}
			/>
			{d ? (
				<div className="lr-dec">
					<div className="lr-dec__list" role="group" aria-label="Daftar keputusan">
						{list.map((x, i) => (
							<button
								type="button"
								aria-current={x.id === d.id ? 'true' : undefined}
								key={x.id}
								className={`lr-dec__item${x.id === d.id ? ' is-active' : ''}`}
								onClick={() => onSelect(x.id)}
							>
								<span className="lr-mono lr-strong">{decisionId(x, i)}</span>
								<span className="lr-dec__t">{text(x.values['Topik keputusan'])}</span>
								<StatusBadge s={statusOf(x)} />
							</button>
						))}
					</div>
					<Card padding="md" className="lr-dec__detail">
						<div className="lr-dec__top">
							<span className="lr-mono lr-k">
								{decisionId(d, list.indexOf(d))}
								{text(d.values.Agenda) ? ` · ${agendaLabel(text(d.values.Agenda))}` : ''}
							</span>
							<StatusBadge s={statusOf(d)} />
						</div>
						<div className="lr-h3 lr-h3--lg">{text(d.values['Topik keputusan'])}</div>
						<div className="lr-k lr-mt">Keputusan yang dimohonkan</div>
						<p className="lr-lead">{text(d.values['Keputusan yang dimohonkan']) || '—'}</p>
						{/* While a Keputusan is written, the form takes this room: the stage does not scroll, so
						    anything left here pushed "Catat keputusan" below the clip (critique, 2026-10-06). */}
						<div className="lr-g2 lr-g2--tight" hidden={asking}>
							<div>
								<div className="lr-k">Rekomendasi</div>
								<div>{text(d.values['Opsi & rekomendasi']) || '—'}</div>
							</div>
							<div>
								<div className="lr-k">Kewenangan / persetujuan lanjutan</div>
								<div className="lr-tags">
									{(
										(d.values['Kewenangan / persetujuan lanjutan'] as string[] | undefined) ?? []
									).map((k) => (
										<Tag key={k} size="sm">
											{k}
										</Tag>
									))}
								</div>
							</div>
							<div>
								<div className="lr-k">PIC pelaksanaan</div>
								<div>{text(d.values['PIC pelaksanaan']) || '—'}</div>
							</div>
						</div>
						{text(d.values[RUMUSAN]) && !asking ? (
							<div className="lr-mt">
								<div className="lr-k">Rumusan keputusan</div>
								<p className="lr-lead">{text(d.values[RUMUSAN])}</p>
								{text(d.values[SYARAT]) ? (
									<>
										<div className="lr-k">Syarat</div>
										<p className="lr-lead">{text(d.values[SYARAT])}</p>
									</>
								) : null}
							</div>
						) : null}
						{asking && draft ? (
							<form
								className="lr-dec__acts lr-dec__form"
								aria-label={QUESTION[draft.status]}
								onSubmit={(e) => {
									e.preventDefault();
									if (missing.length) return;
									onDecide(d.id, draft.status, values());
									setDraft(null);
								}}
							>
								<span
									className={`lr-dec__confirm-q${draft.status === 'Ditolak' ? ' is-danger' : ''}`}
								>
									{QUESTION[draft.status]}
								</span>
								<label className="lr-dec__field">
									<span className="lr-k">Rumusan keputusan</span>
									<Textarea
										autoFocus
										rows={2}
										autoResize
										maxRows={3}
										value={rumusan}
										onChange={(e) => setRumusan(e.target.value)}
										placeholder="Keputusan Direksi, dalam kalimat…"
									/>
								</label>
								{draft.status === 'Disetujui bersyarat' ? (
									<label className="lr-dec__field">
										<span className="lr-k">Syarat</span>
										<Textarea
											rows={2}
											autoResize
											maxRows={3}
											value={syarat}
											onChange={(e) => setSyarat(e.target.value)}
											placeholder="Syarat yang harus dipenuhi…"
										/>
									</label>
								) : null}
								{draft.status === 'Ditunda' ? (
									<label className="lr-dec__field">
										<span className="lr-k">Dibahas ulang pada</span>
										<Input type="date" value={ulang} onChange={(e) => setUlang(e.target.value)} />
									</label>
								) : null}
								<div className="lr-dec__confirm">
									<Button
										type="submit"
										variant={draft.status === 'Ditolak' ? 'danger' : 'primary'}
										size="lg"
										disabled={missing.length > 0}
									>
										Catat keputusan
									</Button>
									<Button type="button" variant="outline" size="lg" onClick={() => setDraft(null)}>
										Batal
									</Button>
									{missing.length ? (
										<span className="lr-k">Isi dulu: {missing.join(', ').toLowerCase()}</span>
									) : null}
								</div>
							</form>
						) : (
							<div className="lr-dec__acts">
								{ACTS.map(([s, variant, label]) => {
									const on = statusOf(d) === s;
									return (
										<Button
											key={s}
											variant={on ? variant : 'outline'}
											size="lg"
											aria-pressed={on}
											iconLeft={on ? <Check size={20} aria-hidden="true" /> : undefined}
											onClick={() => choose(d.id, s, on)}
										>
											{label}
										</Button>
									);
								})}
							</div>
						)}
					</Card>
				</div>
			) : (
				<Nothing what="usulan keputusan" />
			)}
		</div>
	);
};
