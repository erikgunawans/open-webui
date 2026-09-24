import { describe, expect, test } from 'vitest';
import { evidenceFormData, filenameFromDisposition } from './index';

describe('evidenceFormData', () => {
	test('a link revision sends the link and no empty fields', () => {
		const data = evidenceFormData({ expected_version: 3, url: 'https://example.test/a', note: '' });
		expect(data.get('expected_version')).toBe('3');
		expect(data.get('url')).toBe('https://example.test/a');
		expect(data.has('note')).toBe(false);
		expect(data.has('completion')).toBe(false);
		expect(data.has('file')).toBe(false);
	});

	test('a cancellation request carries its kind and reason', () => {
		const data = evidenceFormData({
			expected_version: 1,
			url: 'https://example.test/b',
			closure_kind: 'cancelled',
			reason: 'Scope moved to the 2027 RKA'
		});
		expect(data.get('closure_kind')).toBe('cancelled');
		expect(data.get('reason')).toBe('Scope moved to the 2027 RKA');
	});

	test('a file revision sends the file under its own name', () => {
		const file = new File(['%PDF'], 'bukti.pdf', { type: 'application/pdf' });
		const data = evidenceFormData({ expected_version: 2, file, completion: true });
		expect(data.get('completion')).toBe('true');
		expect((data.get('file') as File).name).toBe('bukti.pdf');
		expect(data.has('url')).toBe(false);
	});
});

describe('filenameFromDisposition', () => {
	test('decodes the RFC 5987 filename the server sends', () => {
		expect(filenameFromDisposition("attachment; filename*=UTF-8''laporan%20Q3.pdf")).toBe(
			'laporan Q3.pdf'
		);
	});

	test('anything else is null', () => {
		expect(filenameFromDisposition(null)).toBeNull();
		expect(filenameFromDisposition('attachment')).toBeNull();
		expect(filenameFromDisposition("attachment; filename*=UTF-8''%E0%A4%A")).toBeNull();
	});
});
