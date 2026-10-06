import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { AGENDAS } from '../../agendas';
import { actionId, decisionId, jakartaLocal, people } from '../../layar-model';
import { actions, decisions, fmtDate, mainInfo, meetingName, targetOf } from '../../selectors';
import {
	DBS,
	filled,
	isDate,
	text,
	titleField,
	type Meeting,
	type NotulenRecord,
	type PropDef,
	type PropValue,
	PERTIMBANGAN,
	SYARAT
} from '../../types';
import { numberAffixes } from '../fields/PropField';

// "Cetak / PDF": the Risalah Rapat Direksi — the minutes as a formal document, not the form. Only
// what was filled is printed: the meeting's particulars and attendance, the executive summary,
// agendas 1–6 entry by entry, decisions and actions as tables, the closing, and a signature block.
// "Simpan HTML terisi" stays the complete copy of every field (snapshot.tsx).

const COMPANY = 'PT Jakarta Utilitas Propertindo';
const SUMMARY = [
	'Kondisi perusahaan',
	'Pencapaian & deviasi utama',
	'Isu perhatian Direksi',
	'Ringkasan keputusan utama',
	'Tindak lanjut mendesak'
];

const asDate = (x: string) => new Date(x.length === 10 ? `${x}T00:00` : x);
const longDate = (x: string) =>
	asDate(x).toLocaleDateString('id-ID', {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});
const dayDate = (x: string) =>
	asDate(x).toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' });
const clock = (x: string) => (x.length > 10 ? x.slice(11, 16).replace(':', '.') : '');

/** A value as the Risalah prints it; empty when there is nothing to print. */
export const shown = (f: PropDef, v: PropValue | undefined): string => {
	if (!filled(v) || f.type === 'checkbox') return '';
	if (isDate(v)) return fmtDate(v);
	if (Array.isArray(v)) return v.join(', ');
	const s = text(v);
	if (f.type !== 'number') return s.trim();
	const n = Number(s.replace(',', '.'));
	if (!Number.isFinite(n)) return s;
	const { prefix, suffix } = numberAffixes(f.name);
	return `${prefix ? `${prefix} ` : ''}${n.toLocaleString('id-ID')}${suffix ?? ''}`;
};

const field = (db: number, name: string) => DBS[db].fields.find((f) => f.name === name)!;
const val = (db: number, r: NotulenRecord | undefined, name: string) =>
	r ? shown(field(db, name), r.values[name]) : '';

const Para = ({ children }: { children: string }) => <p className="rs-pre">{children}</p>;

const Row = ({ k, children }: { k: string; children: ReactNode }) =>
	children ? (
		<tr>
			<th scope="row">{k}</th>
			<td>{children}</td>
		</tr>
	) : null;

// Called, not rendered as a component: an empty list must be null so Row drops the line.
const peopleList = (v: PropValue | undefined) => {
	const ps = people(v);
	if (!ps.length) return null;
	return (
		<ol className="rs-people">
			{ps.map(([n, j]) => (
				<li key={n}>
					{n}
					{j ? <span className="rs-muted"> — {j}</span> : null}
				</li>
			))}
		</ol>
	);
};

/** Agendas 1–6: each entry with a title or any filled field, its fields as a definition list. */
const AgendaEntries = ({ db, records }: { db: number; records: NotulenRecord[] }) => {
	const tf = titleField(db);
	const rows = records
		.map((r) => ({
			r,
			title: text(r.values[tf.name]).trim(),
			fields: DBS[db].fields
				.filter((f) => f.type !== 'title')
				.map((f) => [f.name, shown(f, r.values[f.name])] as const)
				.filter(([, s]) => s)
		}))
		// A Kinerja indicator is only its name until a number is entered: the starters print nothing.
		.filter((x) => (db === 2 ? false : x.title) || x.fields.length || x.r.body.trim());
	if (!rows.length) return <p className="rs-muted">Tidak ada butir pembahasan untuk agenda ini.</p>;
	return (
		<>
			{rows.map(({ r, title, fields }, i) => (
				<div className="rs-entry" key={r.id}>
					<h4>
						{db}.{i + 1} {title || 'Tanpa judul'}
					</h4>
					{fields.length ? (
						<dl>
							{fields.map(([k, s]) => (
								<div key={k}>
									<dt>{k}</dt>
									<dd className="rs-pre">{s}</dd>
								</div>
							))}
						</dl>
					) : null}
					{r.body.trim() ? <Para>{r.body.trim()}</Para> : null}
				</div>
			))}
		</>
	);
};

const Decisions = ({ m }: { m: Meeting }) => {
	const all = decisions(m);
	const index = new Map(m.records[7].map((r, i) => [r.id, i]));
	if (!all.length) return <p className="rs-muted">Tidak ada keputusan yang dicatat.</p>;
	return (
		<table className="rs-table">
			<thead>
				<tr>
					<th>No.</th>
					<th>Keputusan</th>
					<th>Status</th>
					<th>PIC pelaksanaan</th>
				</tr>
			</thead>
			<tbody>
				{all.map((r) => {
					const rumusan = val(7, r, 'Rumusan keputusan');
					// Syarat has its own kolom since 2026-10-06; older meetings kept it in Pertimbangan.
					const syarat =
						val(7, r, SYARAT) ||
						(val(7, r, 'Status keputusan') === 'Disetujui bersyarat'
							? val(7, r, PERTIMBANGAN)
							: '');
					const ulang = val(7, r, 'Tanggal pembahasan ulang');
					return (
						<tr key={r.id}>
							<td className="rs-mono">{decisionId(r, index.get(r.id) ?? 0)}</td>
							<td>
								<strong>{text(r.values['Topik keputusan'])}</strong>
								{rumusan ? <Para>{rumusan}</Para> : null}
								{syarat ? <p className="rs-pre rs-small">Syarat: {syarat}</p> : null}
								{ulang ? <p className="rs-small">Dibahas ulang: {ulang}</p> : null}
							</td>
							<td>{val(7, r, 'Status keputusan') || 'Belum diputuskan'}</td>
							<td className="rs-pre">{val(7, r, 'PIC pelaksanaan') || '—'}</td>
						</tr>
					);
				})}
			</tbody>
		</table>
	);
};

const Actions = ({ m }: { m: Meeting }) => {
	const all = actions(m);
	const index = new Map(m.records[8].map((r, i) => [r.id, i]));
	if (!all.length) return <p className="rs-muted">Tidak ada tindak lanjut yang dicatat.</p>;
	return (
		<table className="rs-table">
			<thead>
				<tr>
					<th>No.</th>
					<th>Tindakan / deliverable</th>
					<th>PIC utama</th>
					<th>Target</th>
					<th>Status</th>
				</tr>
			</thead>
			<tbody>
				{all.map((r) => {
					const ind = val(8, r, 'Indikator penyelesaian');
					const ref = val(8, r, 'Referensi keputusan / ID sebelumnya');
					return (
						<tr key={r.id}>
							<td className="rs-mono">{actionId(r, index.get(r.id) ?? 0)}</td>
							<td>
								<strong>{text(r.values['Tindakan / deliverable'])}</strong>
								{ind ? <p className="rs-pre rs-small">Indikator: {ind}</p> : null}
								{ref ? <p className="rs-small">Ref.: {ref}</p> : null}
							</td>
							<td className="rs-pre">{val(8, r, 'PIC utama') || '—'}</td>
							<td>{fmtDate(targetOf(r)) || '—'}</td>
							<td>{val(8, r, 'Status') || 'Belum mulai'}</td>
						</tr>
					);
				})}
			</tbody>
		</table>
	);
};

/** The agenda's Catatan pembahasan, only when the Corsec ticked "Sertakan di Risalah". */
const Notes = ({ m, db }: { m: Meeting; db: number }) => {
	const n = m.notes?.[db];
	return n?.risalah && n.text.trim() ? (
		<div className="rs-entry">
			<h4>Catatan pembahasan</h4>
			<Para>{n.text.trim()}</Para>
		</div>
	) : null;
};

const Signature = ({ role, name }: { role: string; name: string }) => (
	<div className="rs-sign">
		<div>{role}</div>
		<div className="rs-sign__space" />
		<div className="rs-sign__name">{name || ' '}</div>
	</div>
);

export const Risalah = ({ meeting }: { meeting: Meeting }) => {
	const info = mainInfo(meeting);
	const mv = info?.values ?? {};
	const when = isDate(mv['Tanggal & waktu']) ? mv['Tanggal & waktu'] : undefined;
	const start = when?.start ?? '';
	const end = when?.end ?? '';
	const hours = clock(start) ? `${clock(start)}${clock(end) ? ` – ${clock(end)}` : ''} WIB` : '';
	const closedAt = isDate(mv['Waktu rapat ditutup']) ? mv['Waktu rapat ditutup'].start : '';
	const klas = text(mv['Klasifikasi dokumen']);
	const status = text(mv['Status validasi']);
	const drafted = isDate(mv['Tanggal penyusunan']) ? mv['Tanggal penyusunan'].start : '';
	const signedOn = drafted || start;
	const summary = SUMMARY.map((k) => [k, val(0, info, k)] as const).filter(([, s]) => s);
	const nomor = meeting.plan?.nomor;

	return (
		<article className="rs">
			<header className="rs-kop">
				<div className="rs-kop__co">{COMPANY}</div>
				{klas ? <div className="rs-kop__klas">{klas}</div> : null}
			</header>
			<h1>Risalah Rapat Direksi</h1>
			<p className="rs-sub">
				{meetingName(meeting)}
				{nomor ? <span className="rs-mono"> · {nomor}</span> : null}
			</p>
			{status && status !== 'Disetujui' ? (
				<p className="rs-draft">{status} — belum divalidasi. Risalah ini bukan dokumen final.</p>
			) : null}

			<table className="rs-meta">
				<tbody>
					<Row k="Hari, tanggal">{start ? longDate(start) : ''}</Row>
					<Row k="Waktu">{hours}</Row>
					<Row k="Tempat">{val(0, info, 'Ruang / lokasi')}</Row>
					<Row k="Periode pelaporan">{val(0, info, 'Periode pelaporan')}</Row>
					<Row k="Pimpinan rapat">{val(0, info, 'Pimpinan rapat')}</Row>
					<Row k="Hadir">{peopleList(mv.Peserta)}</Row>
					<Row k="Berhalangan">{peopleList(mv['Peserta berhalangan'])}</Row>
					<Row k="Undangan">{peopleList(mv['Peserta eksternal & jabatan'])}</Row>
					<Row k="Notulis">{val(0, info, 'Notulis')}</Row>
				</tbody>
			</table>

			{summary.length ? (
				<section>
					<h2>Ringkasan eksekutif</h2>
					{summary.map(([k, s]) => (
						<div className="rs-entry" key={k}>
							<h4>{k}</h4>
							<Para>{s}</Para>
						</div>
					))}
				</section>
			) : null}

			{[1, 2, 3, 4, 5, 6].map((db) => (
				<section key={db}>
					<h2>{AGENDAS[db].title}</h2>
					<AgendaEntries db={db} records={meeting.records[db]} />
					<Notes m={meeting} db={db} />
				</section>
			))}
			<section>
				<h2>{AGENDAS[7].title}</h2>
				<Decisions m={meeting} />
				<Notes m={meeting} db={7} />
			</section>
			<section>
				<h2>{AGENDAS[8].title}</h2>
				<Actions m={meeting} />
				<Notes m={meeting} db={8} />
			</section>

			<section className="rs-close">
				<h2>Penutupan</h2>
				<p>
					{clock(closedAt)
						? `Rapat ditutup pukul ${clock(closedAt)} WIB.`
						: 'Waktu penutupan rapat belum dicatat.'}
				</p>
				{(meeting.session.reopenings ?? []).map((x) => (
					<p key={x.at} className="rs-pre">
						Dibuka kembali pukul {clock(jakartaLocal(x.at))} WIB: {x.reason}
					</p>
				))}
				{val(0, info, 'Rapat berikutnya') || val(0, info, 'Topik rapat berikutnya') ? (
					<p>
						Rapat berikutnya: {val(0, info, 'Rapat berikutnya') || 'tanggal belum ditetapkan'}
						{val(0, info, 'Topik rapat berikutnya')
							? ` — ${val(0, info, 'Topik rapat berikutnya')}`
							: ''}
						.
					</p>
				) : null}
				<p className="rs-place">Jakarta, {signedOn ? dayDate(signedOn) : '…'}</p>
				<div className="rs-signs">
					<Signature role="Pimpinan Rapat" name={val(0, info, 'Pimpinan rapat')} />
					<Signature role="Notulis" name={val(0, info, 'Notulis')} />
					{val(0, info, 'Diperiksa / disetujui oleh') ? (
						<Signature
							role="Diperiksa / disetujui"
							name={val(0, info, 'Diperiksa / disetujui oleh')}
						/>
					) : null}
				</div>
			</section>
		</article>
	);
};

// A CSS string literal: quotes and backslashes escaped, and `<` as \3c so no `</style>` survives.
const cssString = (s: string) =>
	`"${s.replace(/[\\"]/g, '\\$&').replace(/</g, '\\3c ').replace(/\n/g, ' ')}"`;

const css = (footer: string) => `
@page {
	size: A4;
	margin: 22mm 20mm 20mm;
	@bottom-left { content: ${cssString(footer)}; font: 8pt Arial, sans-serif; color: #555; }
	@bottom-right { content: "Halaman " counter(page) " dari " counter(pages); font: 8pt Arial, sans-serif; color: #555; }
}
* { box-sizing: border-box; }
html { color: #111; background: #fff; }
body { margin: 0; font: 10.5pt/1.5 Arial, "Helvetica Neue", sans-serif; }
.rs { max-width: 170mm; margin: 0 auto; padding: 12mm 0; }
@media print { .rs { padding: 0; max-width: none; } }
.rs-kop { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2pt solid #111; padding-bottom: 3mm; }
.rs-kop__co { font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; font-size: 10pt; }
.rs-kop__klas { font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; font-size: 9pt; border: 1pt solid #111; padding: 0.5mm 2mm; }
h1 { font-size: 16pt; text-transform: uppercase; letter-spacing: 0.06em; text-align: center; margin: 8mm 0 1mm; }
.rs-sub { text-align: center; margin: 0 0 6mm; }
.rs-draft { text-align: center; font-weight: 700; border: 1pt dashed #111; padding: 1.5mm; margin: 0 0 6mm; }
h2 { font-size: 11.5pt; text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 0.75pt solid #111; padding-bottom: 1mm; margin: 7mm 0 3mm; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 0 0 1mm; break-after: avoid; }
p { margin: 0 0 2mm; }
.rs-pre { white-space: pre-line; }
.rs-small { font-size: 9pt; margin: 1mm 0 0; }
.rs-muted { color: #555; }
.rs-mono { font-family: "Courier New", monospace; white-space: nowrap; }
.rs-meta { width: 100%; border-collapse: collapse; margin-bottom: 2mm; }
.rs-meta th { text-align: left; font-weight: 400; color: #444; width: 38mm; padding: 1mm 4mm 1mm 0; vertical-align: top; white-space: nowrap; }
.rs-meta td { padding: 1mm 0; vertical-align: top; }
.rs-meta th::after { content: ":"; float: right; }
.rs-people { margin: 0; padding-left: 5mm; }
.rs-entry { margin: 0 0 4mm; break-inside: avoid; }
dl { margin: 0; display: grid; grid-template-columns: 52mm 1fr; gap: 0.5mm 4mm; }
dl > div { display: contents; }
dt { color: #444; }
dd { margin: 0; }
.rs-table { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
.rs-table th, .rs-table td { border: 0.75pt solid #777; padding: 1.5mm 2mm; text-align: left; vertical-align: top; }
.rs-table thead th { background: #eee; font-weight: 700; }
.rs-table thead { display: table-header-group; }
.rs-table tr { break-inside: avoid; }
.rs-table td p { margin: 1mm 0 0; }
.rs-close { break-inside: avoid; }
.rs-place { margin-top: 8mm; }
.rs-signs { display: grid; grid-template-columns: repeat(auto-fit, minmax(45mm, 1fr)); gap: 8mm; margin-top: 2mm; }
.rs-sign__space { height: 22mm; }
.rs-sign__name { border-top: 0.75pt solid #111; padding-top: 1mm; font-weight: 700; white-space: pre-line; }
`;

export const risalahHtml = (meeting: Meeting): string => {
	const name = meetingName(meeting);
	const klas = text(mainInfo(meeting)?.values['Klasifikasi dokumen']);
	const footer = `Risalah · ${name}${klas ? ` · ${klas}` : ''}`;
	const esc = (s: string) =>
		s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);
	return (
		'<!doctype html>\n<html lang="id"><head><meta charset="utf-8">' +
		'<meta name="viewport" content="width=device-width, initial-scale=1">' +
		`<title>Risalah — ${esc(name)}</title><style>${css(footer).replace(/<\//g, '<\\/')}</style></head>` +
		`<body>${renderToStaticMarkup(<Risalah meeting={meeting} />)}</body></html>`
	);
};

// Printed from a hidden frame, never the app page: the page sits inside the app shell's
// fixed-height, overflow-hidden panel, and Chrome printed it as one blank page.
const PRINT_FRAME_ID = 'nt-print-frame';

export const printRisalah = (meeting: Meeting): void => {
	document.getElementById(PRINT_FRAME_ID)?.remove();
	const frame = document.createElement('iframe');
	frame.id = PRINT_FRAME_ID;
	frame.title = 'Cetak risalah';
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
	frame.srcdoc = risalahHtml(meeting);
	document.body.appendChild(frame);
};
