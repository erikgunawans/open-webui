import { renderToStaticMarkup } from 'react-dom/server';
import { JupUIProvider, ToastProvider, type JupResolvedTheme } from '@jup/ui';

import { AGENDAS } from '../../agendas';
import { meetingName } from '../../selectors';
import type { Meeting } from '../../types';
import { AgendaView } from './AgendaView';
import { DerivedViews } from './DerivedViews';
import { Header } from './Header';

// "Simpan HTML terisi": a read-only, self-contained copy of the filled notulen (every agenda
// expanded, then the derived views), with the page's own JUP and notulen styles inlined. Static
// rendering writes each input's value, each select's choice and each textarea's text into the
// markup, which a DOM outerHTML would not.

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

const escape = (s: string) =>
	s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

export const snapshotHtml = (meeting: Meeting, theme: JupResolvedTheme): string => {
	const noop = () => {};
	const body = renderToStaticMarkup(
		<JupUIProvider theme={theme} storageKey={null} className="nt-app nt-snapshot">
			<ToastProvider>
				<Header meeting={meeting} layarHref="" onReset={noop} onPrint={noop} onSave={noop} />
				<div className="nt-shell nt-shell--tabs">
					<main className="nt-main">
						{AGENDAS.map((_, i) => (
							<AgendaView
								key={i}
								db={i}
								records={meeting.records[i]}
								setRecords={noop}
								showTypes={false}
								printing
							/>
						))}
						<DerivedViews meeting={meeting} />
					</main>
				</div>
			</ToastProvider>
		</JupUIProvider>
	);
	return (
		'<!doctype html>\n<html lang="id"><head><meta charset="utf-8">' +
		'<meta name="viewport" content="width=device-width, initial-scale=1">' +
		`<title>${escape(meetingName(meeting))}</title><style>${ownCss()}</style></head>` +
		`<body>${body}</body></html>`
	);
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
