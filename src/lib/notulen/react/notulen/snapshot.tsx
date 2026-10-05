import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider, type JupResolvedTheme } from '@jup/ui';

import { AGENDAS } from '../../agendas';
import { meetingName } from '../../selectors';
import type { Meeting } from '../../types';
import { AgendaView } from './AgendaView';
import { DerivedViews } from './DerivedViews';
import { Header } from './Header';

// "Simpan HTML terisi": a read-only, self-contained copy of the filled notulen (every agenda
// expanded, then the derived views), with the page's own JUP and notulen styles inlined. Static
// rendering writes each input's value, each select's choice and each textarea's text into the
// markup, which a DOM outerHTML would not. No ToastProvider: it always portals into document.body,
// which renderToStaticMarkup rejects (React #257) — the live "Simpan HTML terisi" failed on it.

const ownCss = (): string => {
	const out: string[] = [];
	for (const sheet of Array.from(document.styleSheets)) {
		let rules: CSSRuleList;
		try {
			rules = sheet.cssRules;
		} catch {
			continue; // A cross-origin sheet: not ours.
		}
		for (const rule of Array.from(rules))
			if (/\.(jup|nt)-|\[data-jup/.test(rule.cssText)) out.push(rule.cssText);
	}
	return out.join('\n');
};

// The app tokens the island's surfaces point at (notulen.css, `.jup-root.nt-root`). The file has no
// app stylesheet, so their values as resolved on the page right now go in with it.
const APP_TOKENS = [
	'--jlp-card-bg',
	'--jlp-sunk',
	'--jlp-card-ring',
	'--jlp-card-lift',
	'--jup-ui-hairline',
	'--jup-ui-hairline-strong',
	'--jup-ui-radius-card',
	'--jup-ui-radius-control'
];

const appTokens = (): string => {
	const el = document.querySelector('.nt-root');
	if (!el || typeof getComputedStyle !== 'function') return '';
	const cs = getComputedStyle(el);
	const decl = APP_TOKENS.map((t) => [t, cs.getPropertyValue(t).trim()])
		.filter(([, v]) => v)
		.map(([t, v]) => `${t}: ${v};`)
		.join(' ');
	return decl ? `:root { ${decl} }\n` : '';
};

const escape = (s: string) =>
	s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

export const snapshotHtml = (meeting: Meeting, theme: JupResolvedTheme): string => {
	const noop = () => {};
	const body = renderToStaticMarkup(
		<JupUIProvider theme={theme} storageKey={null} className="nt-app nt-snapshot">
			<Header
				meeting={meeting}
				layarHref=""
				saved={{ ok: true, at: null }}
				onReset={noop}
				onPrint={noop}
				onSave={noop}
			/>
			<div className="nt-shell nt-shell--tabs">
				<main className="nt-main">
					{AGENDAS.map((_, i) => (
						<AgendaView
							key={i}
							db={i}
							records={meeting.records[i]}
							setRecords={noop}
							printing
							toast={() => ''}
						/>
					))}
					<DerivedViews meeting={meeting} />
				</main>
			</div>
		</JupUIProvider>
	);
	return (
		'<!doctype html>\n<html lang="id"><head><meta charset="utf-8">' +
		'<meta name="viewport" content="width=device-width, initial-scale=1">' +
		`<title>${escape(meetingName(meeting))}</title><style>${appTokens()}${ownCss()}</style></head>` +
		`<body>${body}</body></html>`
	);
};

// "Cetak / PDF" prints this same snapshot from a hidden frame, never the app page. The page sits
// inside the app shell's fixed-height, overflow-hidden panel, and Chrome printed it as one blank
// page; the snapshot has no shell to clip it. Always light: it is going on paper.
const PRINT_FRAME_ID = 'nt-print-frame';

export const printSnapshot = (meeting: Meeting): void => {
	document.getElementById(PRINT_FRAME_ID)?.remove();
	const frame = document.createElement('iframe');
	frame.id = PRINT_FRAME_ID;
	frame.title = 'Cetak notulen';
	frame.setAttribute('aria-hidden', 'true');
	frame.tabIndex = -1;
	frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
	frame.addEventListener('load', () => {
		const win = frame.contentWindow;
		if (!win) return;
		win.addEventListener('afterprint', () => frame.remove());
		win.focus();
		win.print();
	});
	frame.srcdoc = snapshotHtml(meeting, 'light');
	document.body.appendChild(frame);
};

export const downloadSnapshot = (meeting: Meeting, theme: JupResolvedTheme): void => {
	const url = URL.createObjectURL(
		new Blob([snapshotHtml(meeting, theme)], { type: 'text/html;charset=utf-8' })
	);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'Notulen_Rapat_Direksi_terisi.html';
	a.click();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
};
