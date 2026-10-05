import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider } from '@jup/ui';

import { demoMeeting } from '../../../demo';
import { closeMeeting } from '../../../layar-model';
import { seedMeeting } from '../../../seed';
import { V09Penutupan } from './V09Penutupan';

const NOON = Date.UTC(2026, 9, 5, 4, 58);
const render = (m = demoMeeting(0)) => {
	const closed = closeMeeting(m, NOON);
	return renderToStaticMarkup(
		<JupUIProvider storageKey={null}>
			<V09Penutupan meeting={closed} closedAt={NOON} />
		</JupUIProvider>
	);
};

describe('V09Penutupan', () => {
	it('shows the closing time in WIB and the agendas covered', () => {
		const html = render();
		expect(html).toContain('Rapat ditutup');
		expect(html).toMatch(/11\.58<\/span>\s*WIB/);
		expect(html).toMatch(/dari 9 agenda dibahas/);
	});

	it('says plainly when nothing was decided or scheduled', () => {
		const html = render(seedMeeting('r', 0));
		expect(html).toContain('Tidak ada keputusan yang dicatat.');
		expect(html).toContain('Belum dijadwalkan');
	});
});
