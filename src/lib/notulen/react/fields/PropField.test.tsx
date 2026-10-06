import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider } from '@jup/ui';

import { DBS, labelOf, type PropDef, type PropValue } from '../../types';
import { PropField, numberAffixes } from './PropField';
import { withTime } from './DateField';

const render = (f: PropDef, value?: PropValue, timeOn = false) =>
	renderToStaticMarkup(
		<JupUIProvider storageKey={null}>
			<PropField f={f} value={value} timeOn={timeOn} onChange={() => {}} onTime={() => {}} />
		</JupUIProvider>
	);

const all = DBS.flatMap((db) => db.fields.map((f) => [db.name, f] as const));

describe('PropField', () => {
	it('renders an editable control for every one of the 151 kolom (150 template + Syarat)', () => {
		expect(all).toHaveLength(151);
		for (const [db, f] of all) {
			const html = render(f);
			expect(html, `${db} › ${f.name}`).toMatch(/<(input|textarea|select|button)\b/);
			expect(html, `${db} › ${f.name}`).toContain(
				labelOf(f).replace(/&/g, '&amp;').replace(/</g, '&lt;')
			);
		}
	});

	it('offers every schema option, plus "— Pilih —" for selects without their own empty option', () => {
		for (const [, f] of all.filter(([, f]) => f.options.length)) {
			const html = render(f);
			for (const o of f.options) expect(html).toContain(o.replace(/&/g, '&amp;'));
			const ownEmpty = f.options.includes('Belum diputuskan');
			if (f.type !== 'multi_select') expect(html.includes('— Pilih —'), f.name).toBe(!ownEmpty);
		}
	});

	it('shows each schema description as a hint', () => {
		for (const [, f] of all.filter(([, f]) => f.description)) {
			const plain = f.description!.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
			expect(render(f)).toContain(plain);
		}
	});

	it('puts Rp before a rupiah number and % after a percent', () => {
		expect(numberAffixes('Anggaran Rp')).toEqual({ prefix: 'Rp', suffix: undefined });
		expect(numberAffixes('Deviasi persen')).toEqual({ prefix: undefined, suffix: '%' });
		expect(numberAffixes('Realisasi')).toEqual({ prefix: undefined, suffix: undefined });
	});

	it('gives a date start, an optional end and the Asia/Jakarta time switch', () => {
		const f = DBS[0].fields.find((x) => x.name === 'Tanggal & waktu')!;
		const html = render(f, { start: '2026-10-05', end: '' });
		expect(html).toContain('Mulai');
		expect(html).toContain('Selesai (opsional)');
		expect(html).toContain('Sertakan waktu · Asia/Jakarta');
		expect(html).toContain('type="date"');
		expect(render(f, { start: '2026-10-05T09:00', end: '' }, true)).toContain(
			'type="datetime-local"'
		);
	});

	it('converts date ↔ datetime when the time is switched', () => {
		expect(withTime('2026-10-05', true)).toBe('2026-10-05T00:00');
		expect(withTime('2026-10-05T09:30', true)).toBe('2026-10-05T09:30');
		expect(withTime('2026-10-05T09:30', false)).toBe('2026-10-05');
		expect(withTime('', true)).toBe('');
	});
});
