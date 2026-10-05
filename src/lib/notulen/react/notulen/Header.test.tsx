import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider } from '@jup/ui';

import { demoMeeting } from '../../demo';
import type { SaveState } from '../useMeeting';
import { Header } from './Header';

const render = (saved: SaveState) =>
	renderToStaticMarkup(
		<JupUIProvider storageKey={null}>
			<Header
				meeting={demoMeeting(0)}
				layarHref=""
				saved={saved}
				onReset={() => {}}
				onPrint={() => {}}
				onSave={() => {}}
			/>
		</JupUIProvider>
	);

describe('Notulen save status', () => {
	it('names where the data lives before the first edit', () => {
		const html = render({ ok: true, at: null });
		expect(html).toContain('Tersimpan di peramban ini');
		expect(html).not.toContain('belum tersimpan');
	});

	it('shows when the last edit was stored, in WIB', () => {
		// 2026-10-05 07:32 UTC is 14.32 in Jakarta.
		const html = render({ ok: true, at: Date.UTC(2026, 9, 5, 7, 32) });
		expect(html).toContain('Tersimpan · 14.32 WIB');
	});

	it('stops the reader with an alert and a rescue download when the browser refused a write', () => {
		const html = render({ ok: false, at: Date.UTC(2026, 9, 5, 7, 32) });
		expect(html).toContain('Perubahan terakhir belum tersimpan');
		expect(html).toContain('role="alert"');
		expect(html).toContain('Simpan HTML terisi sekarang');
		expect(html).not.toContain('Tersimpan ·');
	});
});
