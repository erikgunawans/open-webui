import { describe, expect, it } from 'vitest';

import { mergeIncomingFiles, savableFiles, settleUpload, type NoteFile } from './note-files';

const placeholder: NoteFile = { type: 'file', id: null, status: 'uploading', itemId: 't1' };
const earlier: NoteFile = { type: 'file', id: 'f0', status: 'uploaded', itemId: 't0' };
const uploaded: NoteFile = { type: 'file', id: 'f1', status: 'uploaded', url: 'f1' };

describe('note files during an upload', () => {
	it('never saves an upload placeholder', () => {
		expect(savableFiles([earlier, placeholder])).toEqual([earlier]);
		expect(savableFiles(null)).toEqual([]);
	});

	it('keeps a local upload the echo does not carry', () => {
		expect(mergeIncomingFiles([earlier], [earlier, placeholder])).toEqual([earlier, placeholder]);
	});

	it('drops a placeholder an older server copy still carries', () => {
		expect(mergeIncomingFiles([earlier, { ...placeholder }], [earlier])).toEqual([earlier]);
	});

	it('settles the upload into the current list, not the original object', () => {
		// The 2026-10-09 sequence: placeholder added, echo swaps in copies, upload finishes.
		const local = [earlier, placeholder];
		const afterEcho = mergeIncomingFiles(
			local.map((f) => ({ ...f })),
			local
		);
		const settled = settleUpload(afterEcho, 't1', uploaded);
		expect(settled).toEqual([earlier, { ...uploaded, itemId: 't1' }]);
		expect(savableFiles(settled).some((f) => f.id === null)).toBe(false);
	});

	it('adds the upload when an echo removed its placeholder', () => {
		expect(settleUpload([earlier], 't1', uploaded)).toEqual([
			earlier,
			{ ...uploaded, itemId: 't1' }
		]);
	});
});
