import { Checkbox, Field, Input, Select, Tag, Textarea } from '@jup/ui';

import { isDate, labelOf, optionLabel, type PropDef, type PropValue } from '../../types';
import { DateField } from './DateField';
import { FieldLabel } from './FieldLabel';

// Property type → control, exactly per the handoff README's mapping table. Every property's
// schema description becomes the field hint.

type Props = {
	f: PropDef;
	value: PropValue | undefined;
	timeOn: boolean;
	onChange: (v: PropValue) => void;
	onTime: (on: boolean) => void;
};

const str = (v: PropValue | undefined) => (typeof v === 'string' ? v : '');

export const numberAffixes = (name: string) => ({
	prefix: /Rp$/.test(name) ? 'Rp' : undefined,
	suffix: /persen/i.test(name) ? '%' : undefined
});

export const PropField = ({ f, value, timeOn, onChange, onTime }: Props) => {
	const label = <FieldLabel f={f} />;
	const hint = f.description ?? undefined;

	switch (f.type) {
		case 'checkbox':
			return (
				<div className="nt-check">
					<Checkbox
						label={labelOf(f)}
						hint={hint}
						checked={value === true}
						onChange={(e) => onChange(e.target.checked)}
					/>
				</div>
			);
		case 'date':
			return (
				<DateField
					f={f}
					value={isDate(value) ? value : undefined}
					timeOn={timeOn}
					onChange={onChange}
					onTime={onTime}
				/>
			);
		case 'select':
		case 'status':
			return (
				<Field label={label} hint={hint}>
					<Select
						value={str(value)}
						onChange={(e) => onChange(e.target.value)}
						options={[
							{ value: '', label: '— Pilih —' },
							...f.options.map((o) => ({ value: o, label: optionLabel(f, o) }))
						]}
					/>
				</Field>
			);
		case 'multi_select': {
			const arr = Array.isArray(value) ? value : [];
			return (
				<div className="nt-multi">
					<div className="nt-date__label">{label}</div>
					<div className="nt-tags" role="group" aria-label={labelOf(f)}>
						{f.options.map((o) => (
							<Tag
								key={o}
								selected={arr.includes(o)}
								onClick={() => onChange(arr.includes(o) ? arr.filter((x) => x !== o) : [...arr, o])}
							>
								{optionLabel(f, o)}
							</Tag>
						))}
					</div>
					<p className="nt-hint">{hint ?? 'Pilih satu atau lebih.'}</p>
				</div>
			);
		}
		case 'number':
			return (
				<Field label={label} hint={hint}>
					<Input
						type="number"
						inputMode="decimal"
						step="any"
						value={str(value)}
						placeholder="0"
						{...numberAffixes(f.name)}
						onChange={(e) => onChange(e.target.value)}
					/>
				</Field>
			);
		case 'url':
			return (
				<Field label={label} hint={hint}>
					<Input
						type="url"
						value={str(value)}
						placeholder="https://"
						onChange={(e) => onChange(e.target.value)}
					/>
				</Field>
			);
		case 'people':
			return (
				<Field label={label} hint={hint}>
					<Input
						value={str(value)}
						placeholder="Nama orang"
						onChange={(e) => onChange(e.target.value)}
					/>
				</Field>
			);
		case 'files':
			return (
				<Field label={label} hint={hint ?? 'Nama dokumen dan tautan — bukan unggahan file.'}>
					<Textarea
						rows={2}
						autoResize
						value={str(value)}
						placeholder="Nama dokumen dan tautan file"
						onChange={(e) => onChange(e.target.value)}
					/>
				</Field>
			);
		case 'rich_text':
			return (
				<Field label={label} hint={hint}>
					<Textarea
						rows={3}
						autoResize
						maxRows={14}
						value={str(value)}
						placeholder="Isi catatan…"
						onChange={(e) => onChange(e.target.value)}
					/>
				</Field>
			);
		default:
			return (
				<Field label={label} hint={hint}>
					<Input value={str(value)} placeholder="Isi…" onChange={(e) => onChange(e.target.value)} />
				</Field>
			);
	}
};
