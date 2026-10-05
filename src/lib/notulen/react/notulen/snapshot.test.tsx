import { describe, expect, it } from 'vitest';

import { demoMeeting } from '../../demo';
import { snapshotHtml } from './snapshot';

describe('Simpan HTML terisi', () => {
	// A defined document is the live condition: @jup/ui ToastProvider portals only when one exists,
	// and that portal is what broke "Simpan HTML terisi" in the browser (React #257).
	(globalThis as { document?: unknown }).document ??= { styleSheets: [] };

	it('renders the demo meeting to a self-contained page', () => {
		const html = snapshotHtml(demoMeeting(0), 'light');
		expect(html).toMatch(/^<!doctype html>/);
		expect(html).toContain('Usulan perubahan RKAP 2026 ke RUPS-LB');
	});
});
