import { get, writable } from 'svelte/store';
import { beforeEach, describe, expect, test, vi } from 'vitest';

vi.mock('$lib/stores', () => ({
	chatId: writable('chat-1'),
	showArtifacts: writable(false),
	showControls: writable(false),
	showEmbeds: writable(false)
}));

import { chatId, showArtifacts, showControls, showEmbeds } from '$lib/stores';
import {
	addedOfficeFile,
	autoOpenOfficePreview,
	closeOfficePreview,
	firstSheet,
	officeKind,
	officePreview,
	officePreviewAvailable,
	openOfficePreview
} from './preview';

const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const sheet = { type: 'file', id: 'f-1', name: 'JUP-XLS-Kontrak-Draf.xlsx', content_type: XLSX };
const doc = { type: 'file', id: 'f-2', name: 'JUP-MEM-Memo-Draf.docx' };

beforeEach(() => {
	closeOfficePreview();
	showControls.set(false);
	showArtifacts.set(false);
	showEmbeds.set(false);
	chatId.set('chat-1');
	officePreviewAvailable.set(true);
});

describe('officeKind', () => {
	test('Word, Excel and PowerPoint files, by type or by name', () => {
		expect(officeKind(sheet)).toBe('xlsx');
		expect(officeKind(doc)).toBe('docx');
		expect(officeKind({ type: 'file', id: 'f', name: 'Deck.PPTX' })).toBe('pptx');
		expect(officeKind({ type: 'file', id: 'f', meta: { content_type: XLSX } })).toBe('xlsx');
	});

	test('anything else stays with the vendor modal', () => {
		expect(officeKind({ type: 'file', id: 'f', name: 'scan.pdf' })).toBeNull();
		expect(officeKind({ type: 'file', id: 'f', name: 'data.csv' })).toBeNull();
		expect(officeKind({ type: 'file', id: 'f', name: 'old.xls' })).toBeNull();
		expect(officeKind({ type: 'collection', id: 'k', name: 'x.xlsx' })).toBeNull();
		expect(officeKind({ type: 'file', name: 'no-id.xlsx' })).toBeNull();
		expect(officeKind(null)).toBeNull();
	});
});

describe('addedOfficeFile', () => {
	test('the newest office file the event adds', () => {
		expect(addedOfficeFile([], [doc, sheet])).toEqual(sheet);
		expect(addedOfficeFile([doc], [doc, sheet])).toEqual(sheet);
	});

	test('nothing when the files were already there or are not office files', () => {
		expect(addedOfficeFile([sheet], [sheet])).toBeNull();
		expect(addedOfficeFile(undefined, [{ type: 'file', id: 'p', name: 'a.pdf' }])).toBeNull();
		expect(addedOfficeFile([sheet], undefined)).toBeNull();
	});
});

test('a JUP workbook opens past its Info cover sheet', () => {
	expect(firstSheet(['Info', 'Kontrak'])).toBe('Kontrak');
	expect(firstSheet(['Info'])).toBe('Info');
	expect(firstSheet(['Sheet1', 'Info'])).toBe('Sheet1');
	expect(firstSheet([])).toBe('');
});

describe('openOfficePreview', () => {
	test('opens the column on the file and takes it from artifacts and embeds', () => {
		showArtifacts.set(true);
		expect(openOfficePreview(sheet)).toBe(true);
		expect(get(officePreview)).toEqual({ item: sheet, kind: 'xlsx', chatId: 'chat-1' });
		expect(get(showControls)).toBe(true);
		expect(get(showArtifacts)).toBe(false);
		expect(get(showEmbeds)).toBe(false);
	});

	test('does nothing outside a chat column or for other files', () => {
		officePreviewAvailable.set(false);
		expect(openOfficePreview(sheet)).toBe(false);
		officePreviewAvailable.set(true);
		expect(openOfficePreview({ type: 'file', id: 'p', name: 'a.pdf' })).toBe(false);
		expect(get(officePreview)).toBeNull();
		expect(get(showControls)).toBe(false);
	});

	test('closing the column, or another panel taking it, ends the preview', () => {
		openOfficePreview(sheet);
		showControls.set(false);
		expect(get(officePreview)).toBeNull();

		openOfficePreview(sheet);
		showEmbeds.set(true);
		expect(get(officePreview)).toBeNull();

		openOfficePreview(sheet);
		showArtifacts.set(true);
		expect(get(officePreview)).toBeNull();
	});
});

describe('autoOpenOfficePreview', () => {
	test('a file the assistant just attached opens by itself on a large screen', () => {
		expect(autoOpenOfficePreview([], [sheet], () => true)).toBe(true);
		expect(get(officePreview)?.item).toEqual(sheet);
	});

	test('not on a phone, and not for files already shown', () => {
		expect(autoOpenOfficePreview([], [sheet], () => false)).toBe(false);
		expect(autoOpenOfficePreview([sheet], [sheet], () => true)).toBe(false);
		expect(get(officePreview)).toBeNull();
	});
});
