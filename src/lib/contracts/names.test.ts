import { describe, expect, it } from 'vitest';

import { applyNames, findCodes } from './names';

describe('findCodes', () => {
	it('finds each code once, including multi-letter codes', () => {
		expect(findCodes('Perorangan A dan Perorangan AB; lagi Perorangan A')).toEqual([
			'Perorangan A',
			'Perorangan AB'
		]);
	});

	it('ignores lowercase and partial words', () => {
		expect(findCodes('perorangan A, PeroranganB, Perorangan Ab')).toEqual([]);
	});
});

describe('applyNames', () => {
	it('puts the name beside a known code and leaves unknown codes alone', () => {
		expect(applyNames('Pihak: Perorangan A dan Perorangan B', { 'Perorangan A': 'Budi' })).toBe(
			'Pihak: Budi (Perorangan A) dan Perorangan B'
		);
	});

	it('does not touch text without codes', () => {
		expect(applyNames('Tanpa kode', { 'Perorangan A': 'Budi' })).toBe('Tanpa kode');
	});
});
