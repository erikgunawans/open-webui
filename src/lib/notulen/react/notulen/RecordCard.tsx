import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Card, IconButton, Textarea } from '@jup/ui';
import { ChevronDown, Trash2 } from 'lucide-react';

import { INFO_GROUPS, ITEM_NOUN, SUMMARY_KEYS, toneOf } from '../../agendas';
import { agendaNo } from '../../capture';
import { decisionGaps } from '../../keputusan';
import { coreFields, otherFields } from '../../kolom';
import {
	DBS,
	DECISION_STATUS,
	labelOf,
	text,
	titleField,
	type NotulenRecord,
	type PropDef,
	type PropValue
} from '../../types';
import { PropField } from '../fields/PropField';

// One entry: a collapsible card. Informasi Rapat shows every kolom in the template's groups; an
// agenda entry shows its kolom inti in working order, any other kolom already filled, and the rest
// behind "Tampilkan semua kolom".

const LONG = ['rich_text', 'files'];
const two = (n: number) => String(n).padStart(2, '0');

type Props = {
	db: number;
	r: NotulenRecord;
	index: number;
	total: number;
	open: boolean;
	onToggle: () => void;
	onChange: (next: NotulenRecord) => void;
	onDelete: () => void;
};

const infoGroups = (): [string, PropDef[]][] =>
	INFO_GROUPS.map(([g, names]) => [g, names.map((n) => DBS[0].fields.find((f) => f.name === n)!)]);

const gridClass = (g: string, fs: PropDef[]) =>
	g === 'Checklist finalisasi'
		? 'nt-grid--checks'
		: fs.every((f) => LONG.includes(f.type))
			? 'nt-grid--long'
			: 'nt-grid--short';

/** Kolom kept in working order: long text spans the row, short kolom share it. */
const cellClass = (f: PropDef) =>
	`nt-cell${LONG.includes(f.type) ? ' nt-cell--long' : f.type === 'date' || f.type === 'multi_select' ? ' nt-cell--wide' : ''}`;

export const RecordCard = ({ db, r, index, total, open, ...on }: Props) => {
	const tf = titleField(db);
	const title = text(r.values[tf.name]);
	const set = (name: string, v: PropValue) =>
		on.onChange({ ...r, values: { ...r.values, [name]: v } });
	const setTime = (name: string, t: boolean) =>
		on.onChange({ ...r, time: { ...r.time, [name]: t } });
	// A Keputusan chosen in 07 is recorded only once its kolom are filled (Rumusan; Syarat for
	// bersyarat; the date for Ditunda). Until then it waits here and its kolom join the kolom inti.
	const [pending, setPending] = useState<string | null>(null);
	const gaps = pending ? decisionGaps(r, pending) : [];
	useEffect(() => {
		if (pending && !decisionGaps(r, pending).length) {
			set(DECISION_STATUS, pending);
			setPending(null);
		}
	});
	const chooseDecision = (v: PropValue) => {
		const status = text(v);
		if (!status || !decisionGaps(r, status).length) {
			setPending(null);
			set(DECISION_STATUS, v);
		} else setPending(status);
	};
	const field = (f: PropDef) =>
		db === 7 && f.name === DECISION_STATUS ? (
			<PropField
				key={f.name}
				f={f}
				value={pending ?? r.values[f.name]}
				timeOn={false}
				onChange={chooseDecision}
				onTime={() => undefined}
			/>
		) : (
			<PropField
				key={f.name}
				f={f}
				value={r.values[f.name]}
				timeOn={!!r.time[f.name]}
				onChange={(v) => set(f.name, v)}
				onTime={(t) => setTime(f.name, t)}
			/>
		);
	const bodyId = `nt-rec-${r.id}`;
	const [all, setAll] = useState(false);
	const others = db === 0 ? null : otherFields(db, r, pending ?? undefined);
	const from = db === 7 || db === 8 ? agendaNo(text(r.values.Agenda)) : '';
	const ordered = (g: string, fs: PropDef[]) =>
		fs.length ? (
			<section key={g} className="nt-group">
				<h3 className="nt-group__h">{g}</h3>
				<div className="nt-grid nt-grid--core">
					{fs.map((f) => (
						<div key={f.name} className={cellClass(f)}>
							{field(f)}
						</div>
					))}
				</div>
			</section>
		) : null;
	const showBody = db === 0 || all || !!r.body;

	return (
		<Card
			className={`nt-rec${open ? ' is-open' : ''}`}
			padding="md"
			title={
				<button
					type="button"
					className="nt-rec__toggle"
					aria-expanded={open}
					aria-controls={bodyId}
					onClick={on.onToggle}
				>
					<span className="nt-rec__chev">
						<ChevronDown size={16} aria-hidden="true" />
					</span>
					<span className="nt-rec__title">
						{title || <span className="nt-muted">Tanpa judul</span>}
					</span>
				</button>
			}
			description={
				<span className="nt-rec__meta">
					<span className="nt-mono">
						{two(index + 1)} / {two(total)}
					</span>
					{from && db !== Number(from) ? <span className="nt-from">dari Agenda {from}</span> : null}
					{SUMMARY_KEYS.filter((k) => text(r.values[k])).map((k) => (
						<Badge key={k} tone={toneOf(text(r.values[k]))} dot>
							{text(r.values[k])}
						</Badge>
					))}
				</span>
			}
			actions={
				<IconButton label={`Hapus ${ITEM_NOUN[db]}`} size="sm" onClick={on.onDelete}>
					<Trash2 size={16} aria-hidden="true" />
				</IconButton>
			}
		>
			{open ? (
				<div className="nt-rec__body" id={bodyId}>
					<div className="nt-titlefield">{field(tf)}</div>
					{pending ? (
						<Alert tone="warning" title={`Keputusan "${pending}" belum dicatat`}>
							Dicatat setelah{' '}
							{gaps
								.map((k) => labelOf(DBS[7].fields.find((f) => f.name === k)!).toLowerCase())
								.join(' dan ')}{' '}
							diisi.{' '}
							<Button variant="ghost" size="sm" onClick={() => setPending(null)}>
								Batalkan pilihan
							</Button>
						</Alert>
					) : null}
					{db === 0
						? infoGroups().map(([g, fs]) => {
								const shown = fs.filter((f) => f.type !== 'title');
								return (
									<section key={g} className="nt-group">
										<h3 className="nt-group__h">
											{g}
											{g === 'Checklist finalisasi' ? (
												<span className="nt-mono">
													{' '}
													· {shown.filter((f) => r.values[f.name] === true).length}/{shown.length}
												</span>
											) : null}
										</h3>
										<div className={`nt-grid ${gridClass(g, shown)}`}>{shown.map(field)}</div>
									</section>
								);
							})
						: [
								ordered('Kolom inti', coreFields(db, r, pending ?? undefined)),
								ordered('Kolom lain yang terisi', others!.filled),
								all ? ordered('Kolom lain', others!.empty) : null
							]}
					{showBody ? (
						<section className="nt-group">
							<h3 className="nt-group__h">Catatan lain</h3>
							<Textarea
								rows={3}
								autoResize
								maxRows={20}
								value={r.body}
								placeholder={`Catatan lain untuk ${ITEM_NOUN[db]} ini…`}
								aria-label="Catatan lain"
								onChange={(e) => on.onChange({ ...r, body: e.target.value })}
							/>
						</section>
					) : null}
					{others && (others.empty.length || !r.body) ? (
						<div>
							<Button variant="ghost" size="sm" aria-expanded={all} onClick={() => setAll(!all)}>
								{all
									? 'Sembunyikan kolom kosong'
									: `Tampilkan semua kolom (${others.empty.length})`}
							</Button>
						</div>
					) : null}
				</div>
			) : null}
		</Card>
	);
};
