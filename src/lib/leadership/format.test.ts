import { describe, expect, test } from 'vitest';
import {
	barShare,
	decimalId,
	formatDateId,
	formatEventTimeId,
	formatValue,
	formatVariance,
	recordedDueId,
	shortHash
} from './format';

describe('decimalId', () => {
	test('keeps the stated digits with Indonesian separators', () => {
		expect(decimalId('144.47')).toBe('144,47');
		expect(decimalId('-14.00')).toBe('−14,00');
		expect(decimalId('413')).toBe('413');
		expect(decimalId('1234.5')).toBe('1.234,5');
		expect(decimalId('0')).toBe('0');
	});
});

describe('formatValue', () => {
	test('money in billions of rupiah', () => {
		expect(formatValue('144.47', 'IDR_billion')).toBe('Rp144,47 miliar');
		expect(formatValue('-2.65', 'IDR_billion')).toBe('−Rp2,65 miliar');
	});

	test('percent', () => {
		expect(formatValue('10.5', 'percent')).toBe('10,5%');
	});
});

describe('formatVariance', () => {
	test('a money difference keeps its sign and unit', () => {
		expect(formatVariance('-14.00', 'IDR_billion')).toBe('−Rp14,00 miliar');
		expect(formatVariance('2.5', 'IDR_billion')).toBe('+Rp2,5 miliar');
		expect(formatVariance('0', 'IDR_billion')).toBe('Rp0 miliar');
	});

	test('a percent difference is in percentage points', () => {
		expect(formatVariance('-0.9', 'percent')).toBe('−0,9 poin persentase');
		expect(formatVariance('1.2', 'percent')).toBe('+1,2 poin persentase');
	});
});

describe('barShare', () => {
	test('the larger reading fills the bar', () => {
		expect(barShare('158.47', '158.47')).toBe(100);
		expect(barShare('144.47', '158.47')).toBe(91.2);
	});

	test('no bar for a loss, a zero or a non-number', () => {
		expect(barShare('-2.65', '-0.40')).toBeNull();
		expect(barShare('0', '10')).toBeNull();
		expect(barShare('abc', '10')).toBeNull();
	});
});

describe('formatDateId', () => {
	test('date-only boundaries in Indonesian', () => {
		expect(formatDateId('2026-08-31')).toBe('31 Agustus 2026');
		expect(formatDateId('2027-01-01')).toBe('1 Januari 2027');
	});

	test('anything else is shown as given', () => {
		expect(formatDateId('2026-08')).toBe('2026-08');
	});
});

describe('recordedDueId', () => {
	test('each precision, and never more precise than recorded', () => {
		expect(recordedDueId({ precision: 'date', value: '2026-09-01' })).toBe('1 September 2026');
		expect(recordedDueId({ precision: 'month', value: '2026-12' })).toBe('Desember 2026');
		expect(recordedDueId({ precision: 'year', value: '2027' })).toBe('2027');
		expect(recordedDueId({ precision: 'year_range', value: '2027/2028' })).toBe('2027–2028');
	});

	test('no due date is null', () => {
		expect(recordedDueId(null)).toBeNull();
	});
});

describe('formatEventTimeId', () => {
	test('an event time on the WIB calendar, whatever the browser zone', () => {
		// 2026-09-24T17:30:00Z is 00.30 on 25 September in Jakarta.
		expect(formatEventTimeId(Date.UTC(2026, 8, 24, 17, 30))).toBe('25 September 2026, 00.30 WIB');
		expect(formatEventTimeId(Date.UTC(2026, 0, 1, 2, 5))).toBe('1 Januari 2026, 09.05 WIB');
	});
});

describe('shortHash', () => {
	test('the first eight characters of a sha256', () => {
		expect(shortHash('3f2a9c1e' + '0'.repeat(56))).toBe('3f2a9c1e…');
		expect(shortHash('abc')).toBe('abc');
	});
});
