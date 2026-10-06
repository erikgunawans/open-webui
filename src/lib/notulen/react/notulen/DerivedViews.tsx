import { Badge, Card } from '@jup/ui';

import { ACTION_COLUMNS, agendaLabel, toneOf } from '../../agendas';
import {
	actionCalendar,
	actions,
	fmtDate,
	highRisks,
	isIncomplete,
	pendingDecisions,
	targetOf
} from '../../selectors';
import { UNDECIDED } from '../../keputusan';
import { text, type Meeting, type NotulenRecord } from '../../types';

// "Tampilan pendukung": decisions, risks and follow-ups, recomputed from agendas 5, 7 and 8 on
// every change, including a decision set on the Layar in another tab.

const v = (r: NotulenRecord, k: string) => text(r.values[k]);
const NO_STATUS = 'Tanpa status';
const prefixed = (id: string, t: string) => (id ? `${id} — ${t}` : t);

const Empty = () => <p className="nt-empty">Belum ada butir yang sesuai.</p>;

const Row = ({ title, meta, badge }: { title: string; meta: string[]; badge?: string }) => (
	<li className="nt-vrow">
		<div className="nt-vrow__t">{title}</div>
		<div className="nt-vrow__m">{meta.filter(Boolean).join(' · ') || '—'}</div>
		{badge ? (
			<Badge tone={toneOf(badge)} size="sm">
				{badge}
			</Badge>
		) : null}
	</li>
);

export const DerivedViews = ({ meeting }: { meeting: Meeting }) => {
	const pending = pendingDecisions(meeting);
	const risks = highRisks(meeting);
	const acts = actions(meeting);
	const cal = actionCalendar(meeting);

	return (
		<section className="nt-agenda" aria-labelledby="nt-h-views">
			<header className="nt-ahead">
				<div className="nt-eyebrow">Tampilan pendukung</div>
				<h2 className="nt-h2" id="nt-h-views">
					Tinjauan keputusan, risiko & tindak lanjut
				</h2>
				<p className="nt-focus">
					Dihitung ulang dari agenda 5, 7, dan 8 setiap kali nilai berubah.
				</p>
			</header>
			<div className="nt-views">
				<Card
					title="Perlu Keputusan"
					description="Belum diputuskan, Ditunda, atau keputusan yang belum lengkap."
					actions={<Badge tone="warning">{pending.length}</Badge>}
				>
					{pending.length ? (
						<ul className="nt-vlist">
							{pending.map((r) => (
								<Row
									key={r.id}
									title={prefixed(v(r, 'ID keputusan'), v(r, 'Topik keputusan'))}
									meta={[agendaLabel(v(r, 'Agenda')), v(r, 'PIC pelaksanaan')]}
									badge={isIncomplete(r) ? 'Belum lengkap' : v(r, 'Status keputusan') || UNDECIDED}
								/>
							))}
						</ul>
					) : (
						<Empty />
					)}
				</Card>
				<Card
					title="Risiko Tinggi"
					description="Tinjau mitigasi, pemilik risiko, dan tenggat."
					actions={<Badge tone="danger">{risks.length}</Badge>}
				>
					{risks.length ? (
						<ul className="nt-vlist">
							{risks.map((r) => (
								<Row
									key={r.id}
									title={v(r, 'Risiko / isu kepatuhan') || 'Tanpa judul'}
									meta={[
										v(r, 'Mitigasi / kontrol'),
										v(r, 'Risk owner / PIC'),
										fmtDate(r.values['Tenggat'])
									]}
									badge={v(r, 'Status mitigasi') || undefined}
								/>
							))}
						</ul>
					) : (
						<Empty />
					)}
				</Card>
				<Card
					className="nt-views__wide"
					title="Tindak lanjut Direksi"
					description="Dikelompokkan berdasarkan Status. Terhambat memerlukan perhatian; Selesai setelah indikator terpenuhi."
				>
					<div className="nt-board">
						{/* Tindakan without a Status get their own column only when there are any. */}
						{[...ACTION_COLUMNS, NO_STATUS].map((s) => {
							const items = acts.filter((r) => (v(r, 'Status') || NO_STATUS) === s);
							if (s === NO_STATUS && !items.length) return null;
							return (
								<div key={s} className="nt-col">
									<div className="nt-col__h">
										<Badge tone={toneOf(s)} dot>
											{s}
										</Badge>
										<span className="nt-mono nt-muted">{items.length}</span>
									</div>
									{items.length ? (
										items.map((r) => (
											<div key={r.id} className="nt-tile">
												<div className="nt-vrow__t">
													{prefixed(v(r, 'ID tindakan'), v(r, 'Tindakan / deliverable'))}
												</div>
												<div className="nt-vrow__m">
													{[v(r, 'PIC utama'), fmtDate(targetOf(r)) || 'Tanpa target']
														.filter(Boolean)
														.join(' · ')}
												</div>
												{v(r, 'Indikator penyelesaian') ? (
													<div className="nt-vrow__m">{v(r, 'Indikator penyelesaian')}</div>
												) : null}
											</div>
										))
									) : (
										<p className="nt-empty nt-empty--sm">Belum ada tindakan.</p>
									)}
								</div>
							);
						})}
					</div>
				</Card>
				<Card
					className="nt-views__wide"
					title="Kalender Tindak Lanjut"
					description="Diurutkan berdasarkan Target waktu, paling awal lebih dulu. Milestone program ditinjau melalui agenda 4."
				>
					{cal.length ? (
						<ul className="nt-vlist">
							{cal.map((r) => (
								<li key={r.id} className="nt-vrow nt-vrow--cal">
									<span className="nt-mono nt-cal__d">{fmtDate(targetOf(r))}</span>
									<div>
										<div className="nt-vrow__t">{v(r, 'Tindakan / deliverable')}</div>
										<div className="nt-vrow__m">{v(r, 'PIC utama') || '—'}</div>
									</div>
									{v(r, 'Status') ? (
										<Badge tone={toneOf(v(r, 'Status'))} size="sm">
											{v(r, 'Status')}
										</Badge>
									) : null}
								</li>
							))}
						</ul>
					) : (
						<Empty />
					)}
				</Card>
			</div>
		</section>
	);
};
