import { Checkbox, Field, Input } from '@jup/ui';

import type { DateValue, PropDef } from '../../types';
import { FieldLabel } from './FieldLabel';

// A date property: start, an optional end, and whether the values carry a time (Asia/Jakarta).
// Turning the time on appends T00:00 to each set value; turning it off truncates to the date.

export const withTime = (x: string, on: boolean): string =>
	!x ? '' : on ? `${x.slice(0, 10)}T${x.length > 10 ? x.slice(11, 16) : '00:00'}` : x.slice(0, 10);

/** How a stored value is shown in the input of the current mode. */
const shown = (x: string, on: boolean): string =>
	!x ? '' : on ? (x.length === 10 ? `${x}T00:00` : x) : x.slice(0, 10);

type Props = {
	f: PropDef;
	value: DateValue | undefined;
	timeOn: boolean;
	onChange: (v: DateValue) => void;
	onTime: (on: boolean) => void;
};

export const DateField = ({ f, value, timeOn, onChange, onTime }: Props) => {
	const v = value ?? { start: '', end: '' };
	const type = timeOn ? 'datetime-local' : 'date';
	return (
		<div className="nt-date" role="group" aria-label={f.name}>
			<div className="nt-date__label">
				<FieldLabel f={f} />
			</div>
			<div className="nt-date__row">
				<Field label="Mulai">
					<Input
						type={type}
						value={shown(v.start, timeOn)}
						onChange={(e) => onChange({ ...v, start: e.target.value })}
					/>
				</Field>
				<Field label="Selesai (opsional)">
					<Input
						type={type}
						value={shown(v.end, timeOn)}
						onChange={(e) => onChange({ ...v, end: e.target.value })}
					/>
				</Field>
			</div>
			<Checkbox
				label="Sertakan waktu · Asia/Jakarta"
				checked={timeOn}
				onChange={(e) => {
					const on = e.target.checked;
					onChange({ start: withTime(v.start, on), end: withTime(v.end, on) });
					onTime(on);
				}}
			/>
			{f.description ? <p className="nt-hint">{f.description}</p> : null}
		</div>
	);
};
