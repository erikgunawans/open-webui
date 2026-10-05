import { Avatar, Card } from '@jup/ui';

import { people } from '../../../layar-model';
import { fmtDate, mainInfo } from '../../../selectors';
import { text, type PropValue } from '../../../types';
import { Head, type ViewProps } from './common';

// 00 Pembukaan & Ringkasan: condition, attendance, issues for the Board, urgent follow-ups.

const list = (v: PropValue | undefined) =>
	text(v)
		.split('\n')
		.map((x) => x.trim())
		.filter(Boolean);

export const V00Info = ({ meeting, agenda }: ViewProps) => {
	const mv = mainInfo(meeting)?.values ?? {};
	const present = people(mv.Peserta);
	const absent = people(mv['Peserta berhalangan']);
	const invited = list(mv['Peserta eksternal & jabatan']);
	const total = present.length + absent.length;
	const quorum = total > 0 && present.length * 2 > total;
	const period = fmtDate(mv['Periode pelaporan']);

	return (
		<div className="lr-view">
			<Head agenda={agenda} focus={period ? `Periode pelaporan ${period}` : ''} />
			<div className="lr-g2">
				<Card title="Kondisi perusahaan" padding="md">
					<p className="lr-lead">{text(mv['Kondisi perusahaan']) || '—'}</p>
				</Card>
				<Card
					title="Kehadiran"
					description={
						total
							? `${present.length} dari ${total} peserta hadir · kuorum ${quorum ? 'terpenuhi' : 'belum terpenuhi'}`
							: 'Peserta belum diisi'
					}
					padding="md"
				>
					<ul className="lr-people">
						{present.map(([n, j]) => (
							<li key={n}>
								<Avatar name={n} size="md" />
								<div>
									<div className="lr-strong">{n}</div>
									{j ? <div className="lr-sub">{j}</div> : null}
								</div>
							</li>
						))}
					</ul>
					{invited.length ? (
						<div className="lr-sub lr-mt">Undangan: {invited.join(' · ')}</div>
					) : null}
				</Card>
				<Card title="Isu perhatian Direksi" padding="md">
					<ol className="lr-ol">
						{list(mv['Isu perhatian Direksi']).map((x) => (
							<li key={x}>{x}</li>
						))}
					</ol>
				</Card>
				<Card title="Tindak lanjut mendesak" padding="md">
					<ol className="lr-ol">
						{list(mv['Tindak lanjut mendesak']).map((x) => (
							<li key={x}>{x}</li>
						))}
					</ol>
				</Card>
			</div>
		</div>
	);
};
