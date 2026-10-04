/** Markdown → WhatsApp formatting (`toWhatsApp`), with the shapes seen in live answers 2026-10-05. */

import { expect, test } from 'bun:test';
import { toWhatsApp } from './whatsapp_format';

test('headings become one bold line', () => {
	expect(toWhatsApp('## Status Stage-Gate')).toBe('*Status Stage-Gate*');
	expect(toWhatsApp('### **Angka** (Tier 2)')).toBe('*Angka (Tier 2)*');
	expect(toWhatsApp('#hashtag stays')).toBe('#hashtag stays');
});

test('bold, italic and strike use WhatsApp marks', () => {
	expect(toWhatsApp('**Current Gate:** belum lulus G1')).toBe('*Current Gate:* belum lulus G1');
	expect(toWhatsApp('__tebal__ dan *miring* dan _miring_')).toBe(
		'*tebal* dan _miring_ dan _miring_'
	);
	expect(toWhatsApp('~~lama~~ baru')).toBe('~lama~ baru');
	expect(toWhatsApp('**Rp 63,3 miliar/tahun** — *bukan margin*')).toBe(
		'*Rp 63,3 miliar/tahun* — _bukan margin_'
	);
});

test('lists get bullets, numbered lists stay, nesting keeps its indent', () => {
	expect(toWhatsApp('- satu\n* dua\n  - tiga\n1. **empat**')).toBe(
		'• satu\n• dua\n  • tiga\n1. *empat*'
	);
});

test('links show their label and address; bare links stay', () => {
	expect(toWhatsApp('lihat [dokumen KPPS](https://x.example/kpps) ya')).toBe(
		'lihat dokumen KPPS (https://x.example/kpps) ya'
	);
	expect(toWhatsApp('[https://a.example/c/1](https://a.example/c/1)')).toBe(
		'https://a.example/c/1'
	);
	expect(toWhatsApp('Jawaban lengkap: https://non-jupe.jup.co.id/c/7783f056')).toBe(
		'Jawaban lengkap: https://non-jupe.jup.co.id/c/7783f056'
	);
});

test('code is left exactly as written', () => {
	expect(toWhatsApp('dokumen `gas-spbg-**reactivation**-g1.md`')).toBe(
		'dokumen `gas-spbg-**reactivation**-g1.md`'
	);
	expect(toWhatsApp('```\n## not a heading\n- not a bullet\n```')).toBe(
		'```\n## not a heading\n- not a bullet\n```'
	);
});

test('rules and table separators go; tables keep their rows', () => {
	expect(toWhatsApp('atas\n\n---\n\nbawah')).toBe('atas\n\nbawah');
	expect(toWhatsApp('| a | b |\n|---|:---:|\n| 1 | 2 |')).toBe('| a | b |\n| 1 | 2 |');
});

test('plain text, asterisks in arithmetic and the governance texts pass through', () => {
	for (const text of [
		'Akun ini belum terhubung ke Asisten JUP. Hubungi admin JUP.',
		'2 * 3 = 6',
		'Kode tidak berlaku. Buat kode baru di Pengaturan → Akun.'
	]) {
		expect(toWhatsApp(text)).toBe(text);
	}
});
