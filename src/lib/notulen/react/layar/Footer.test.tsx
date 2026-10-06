import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider } from '@jup/ui';

import { closingGaps } from '../../keputusan';
import { seedMeeting } from '../../seed';
import { demoMeeting } from '../../demo';
import { CloseAsk } from './Footer';

const render = (gaps: ReturnType<typeof closingGaps>) =>
	renderToStaticMarkup(
		<JupUIProvider storageKey={null}>
			<CloseAsk gaps={gaps} onClose={() => {}} onBack={() => {}} onCancel={() => {}} />
		</JupUIProvider>
	);

/** Each button as [label, variant, autofocus]. */
const buttons = (html: string) =>
	[...html.matchAll(/<button[^>]*class="jup-btn jup-btn--(\w+)[^"]*"([^>]*)>(.*?)<\/button>/g)].map(
		(m) => [m[3].replace(/<[^>]+>/g, ''), m[1], /autofocus/.test(m[0])] as const
	);

describe('Tutup rapat on the Layar', () => {
	it('defaults to going back to 07 while gaps remain', () => {
		const gaps = closingGaps(demoMeeting(0));
		expect(gaps.any).toBe(true);
		expect(buttons(render(gaps))).toEqual([
			['Batal', 'ghost', false],
			['Tutup tetap', 'outline', false],
			['Kembali ke 07', 'primary', true]
		]);
	});

	it('defaults to closing when nothing is open', () => {
		const gaps = closingGaps(seedMeeting('r', 0));
		expect(gaps.any).toBe(false);
		expect(buttons(render(gaps))).toEqual([
			['Batal', 'ghost', false],
			['Tutup rapat', 'primary', true]
		]);
	});
});
