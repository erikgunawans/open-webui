import { describe, expect, it } from 'vitest';

import { demoMeeting } from '../../demo';
import { decisionId } from '../../layar-model';
import { decisions } from '../../selectors';
import { seedMeeting } from '../../seed';
import { text } from '../../types';
import { risalahHtml } from './risalah';

describe('Risalah', () => {
	const m = demoMeeting(0);
	const html = risalahHtml(m);

	it('is a formal document with every decision and a signature block', () => {
		expect(html).toContain('Risalah Rapat Direksi');
		expect(html).toContain('PT Jakarta Utilitas Propertindo');
		decisions(m).forEach((r) => expect(html).toContain(decisionId(r, m.records[7].indexOf(r))));
		expect(html).toContain('Pimpinan Rapat');
		expect(html).toContain('Notulis');
		expect(html).toContain(text(m.records[0][0].values['Pimpinan rapat']));
		expect(html).toMatch(/counter\(pages\)/);
	});

	it('prints only what was filled: a fresh meeting says so instead of empty fields', () => {
		const fresh = risalahHtml(seedMeeting('r', 0));
		expect(fresh).toContain('Tidak ada keputusan yang dicatat.');
		expect(fresh).toContain('Waktu penutupan rapat belum dicatat.');
		expect(fresh).not.toContain('Kondisi perusahaan');
		expect(fresh).toContain('Draft — belum divalidasi');
		expect(fresh).not.toContain('Hadir');
		expect(fresh).not.toContain('Revenue');
	});

	it('escapes what people typed, in the body, the title and the page footer', () => {
		const evil = seedMeeting('r', 0);
		evil.records[0][0].values['Nama rapat'] = 'Rapat "X" </style><script>alert(1)</script>';
		const out = risalahHtml(evil);
		expect(out).not.toContain('<script>');
		expect(out.match(/<\/style>/g)).toHaveLength(1);
	});
});
