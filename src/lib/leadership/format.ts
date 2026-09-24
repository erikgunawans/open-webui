import type { Unit } from '$lib/apis/leadership';

// Presentation for the decimal strings the API serves. Nothing here parses a figure into a
// float: a value is shown with exactly the digits the source stated, and arithmetic stays on the
// server. Indonesian conventions: decimal comma, thousands dot, and a true minus sign.

const MINUS = '−';

// "144.47" -> "144,47", "-2.65" -> "−2,65", "1234.5" -> "1.234,5"
export const decimalId = (value: string): string => {
	const negative = value.startsWith('-');
	const unsigned = negative ? value.slice(1) : value;
	const [whole, fraction] = unsigned.split('.');
	const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
	return `${negative ? MINUS : ''}${grouped}${fraction !== undefined ? `,${fraction}` : ''}`;
};

// A reading in its unit: "Rp144,47 miliar", "−Rp2,65 miliar", "10,5%".
export const formatValue = (value: string, unit: Unit): string => {
	if (unit === 'percent') return `${decimalId(value)}%`;
	const negative = value.startsWith('-');
	return `${negative ? MINUS : ''}Rp${decimalId(negative ? value.slice(1) : value)} miliar`;
};

// A difference, which always shows its sign. Percent readings differ in percentage points,
// never in percent: 10,5% against 11,4% is −0,9 poin, not −7,9%.
export const formatVariance = (value: string, unit: Unit): string => {
	const signed = value.startsWith('-') || value === '0' ? value : `+${value}`;
	if (unit === 'percent') {
		return `${signed.startsWith('+') ? '+' : ''}${decimalId(signed.replace(/^\+/, ''))} poin persentase`;
	}
	const positive = signed.startsWith('+');
	return `${positive ? '+' : ''}${formatValue(signed.replace(/^\+/, ''), unit)}`;
};

// Share of a bar, for the actual-versus-budget comparison. Only ever called on two positive
// readings of the same unit, scope and period; returns null otherwise so nothing is drawn.
export const barShare = (value: string, reference: string): number | null => {
	const a = Number(value);
	const b = Number(reference);
	if (!Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) return null;
	const top = Math.max(a, b);
	return Math.round((a / top) * 1000) / 10;
};

// "2026-08-31" -> "31 Agustus 2026". Date-only boundaries stay date-only, with no time zone.
const MONTHS = [
	'Januari',
	'Februari',
	'Maret',
	'April',
	'Mei',
	'Juni',
	'Juli',
	'Agustus',
	'September',
	'Oktober',
	'November',
	'Desember'
];

export const formatDateId = (iso: string): string => {
	const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
	if (!match) return iso;
	const [, year, month, day] = match;
	return `${Number(day)} ${MONTHS[Number(month) - 1]} ${year}`;
};

// A recorded due date in Indonesian, as precise as it was recorded and no more:
// "2026-09-01" -> "1 September 2026", "2026-12" -> "Desember 2026", "2027/2028" -> "2027–2028".
export const recordedDueId = (due: { precision: string; value: string } | null): string | null => {
	if (!due) return null;
	if (due.precision === 'date') return formatDateId(due.value);
	if (due.precision === 'month') {
		const match = /^(\d{4})-(\d{2})$/.exec(due.value);
		return match ? `${MONTHS[Number(match[2]) - 1]} ${match[1]}` : due.value;
	}
	if (due.precision === 'year_range') return due.value.replace('/', '–');
	return due.value;
};

// An event time (epoch milliseconds) on the reporting calendar, WIB: "24 September 2026, 19.40 WIB".
export const formatEventTimeId = (ms: number): string => {
	const parts = new Intl.DateTimeFormat('en-GB', {
		timeZone: 'Asia/Jakarta',
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		hourCycle: 'h23'
	}).formatToParts(new Date(ms));
	const part = (type: string) => parts.find((item) => item.type === type)?.value ?? '';
	const date = formatDateId(`${part('year')}-${part('month')}-${part('day')}`);
	return `${date}, ${part('hour')}.${part('minute')} WIB`;
};

// A content hash, short enough to read aloud in a meeting and long enough to compare: "3f2a9c1e…".
export const shortHash = (hash: string): string =>
	hash.length > 12 ? `${hash.slice(0, 8)}…` : hash;
