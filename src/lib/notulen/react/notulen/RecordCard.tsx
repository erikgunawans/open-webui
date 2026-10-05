import { Badge, Card, IconButton, Textarea } from '@jup/ui';
import { ChevronDown, Trash2 } from 'lucide-react';

import { INFO_GROUPS, SUMMARY_KEYS, toneOf } from '../../agendas';
import {
	DBS,
	filled,
	text,
	titleField,
	type NotulenRecord,
	type PropDef,
	type PropValue
} from '../../types';
import { PropField } from '../fields/PropField';

// One record: a collapsible card with every property of its database, grouped as the template
// groups them, and the record's long page body.

const LONG = ['rich_text', 'files'];
const two = (n: number) => String(n).padStart(2, '0');

type Props = {
	db: number;
	r: NotulenRecord;
	index: number;
	total: number;
	open: boolean;
	showTypes: boolean;
	onToggle: () => void;
	onChange: (next: NotulenRecord) => void;
	onDelete: () => void;
};

const groupsFor = (db: number): [string, PropDef[]][] => {
	const fields = DBS[db].fields;
	if (db === 0)
		return INFO_GROUPS.map(([g, names]) => [
			g,
			names.map((n) => fields.find((f) => f.name === n)!)
		]);
	const rest = fields.filter((f) => f.type !== 'title');
	return [
		['Properti', rest.filter((f) => !LONG.includes(f.type))],
		['Uraian, pembahasan & arahan', rest.filter((f) => LONG.includes(f.type))]
	];
};

const gridClass = (g: string, fs: PropDef[]) =>
	g === 'Checklist finalisasi'
		? 'nt-grid--checks'
		: fs.every((f) => LONG.includes(f.type))
			? 'nt-grid--long'
			: 'nt-grid--short';

export const RecordCard = ({ db, r, index, total, open, showTypes, ...on }: Props) => {
	const fields = DBS[db].fields;
	const tf = titleField(db);
	const title = text(r.values[tf.name]);
	const set = (name: string, v: PropValue) =>
		on.onChange({ ...r, values: { ...r.values, [name]: v } });
	const setTime = (name: string, t: boolean) =>
		on.onChange({ ...r, time: { ...r.time, [name]: t } });
	const field = (f: PropDef) => (
		<PropField
			key={f.name}
			f={f}
			value={r.values[f.name]}
			timeOn={!!r.time[f.name]}
			showType={showTypes}
			onChange={(v) => set(f.name, v)}
			onTime={(t) => setTime(f.name, t)}
		/>
	);
	const nFilled = fields.filter((f) => filled(r.values[f.name])).length;
	const bodyId = `nt-rec-${r.id}`;

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
					<span>{r.origin}</span>
					<span className="nt-mono">
						{nFilled}/{fields.length} terisi
					</span>
					{SUMMARY_KEYS.filter((k) => text(r.values[k])).map((k) => (
						<Badge key={k} tone={toneOf(text(r.values[k]))} dot>
							{text(r.values[k])}
						</Badge>
					))}
				</span>
			}
			actions={
				<IconButton label="Hapus record" size="sm" onClick={on.onDelete}>
					<Trash2 size={16} aria-hidden="true" />
				</IconButton>
			}
		>
			{open ? (
				<div className="nt-rec__body" id={bodyId}>
					<div className="nt-titlefield">{field(tf)}</div>
					{groupsFor(db).map(([g, fs]) => {
						const shown = fs.filter((f) => f.type !== 'title');
						if (!shown.length) return null;
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
					})}
					<section className="nt-group">
						<h3 className="nt-group__h">Isi halaman / catatan panjang</h3>
						<Textarea
							rows={3}
							autoResize
							maxRows={20}
							value={r.body}
							placeholder="Catatan panjang untuk record ini…"
							aria-label="Isi halaman / catatan panjang"
							onChange={(e) => on.onChange({ ...r, body: e.target.value })}
						/>
					</section>
				</div>
			) : null}
		</Card>
	);
};
