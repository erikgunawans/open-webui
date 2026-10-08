// JUP: a note's file list while uploads are in flight.
//
// The server echoes every note update to the whole note room, the sender included. Before this,
// a save that fired mid-upload (title blur, a typed character) stored the `id: null` placeholder,
// the echo replaced the local list with the server's copy of it, and the finished upload filled
// in an object that was no longer in the list. The note kept `id: null` and the recording was
// unreachable (live 2026-10-09, note eb926a29). Three rules close it:
//   - a placeholder is never saved;
//   - an echo keeps the local placeholders it does not carry;
//   - a finished upload is matched by itemId in the CURRENT list, never by object identity.

export type NoteFile = {
	id?: string | null;
	itemId?: string;
	status?: string;
	[key: string]: unknown;
};

const isPending = (file: NoteFile | null | undefined) => file?.status === 'uploading';

/** The list as it may be saved: no upload placeholders. */
export const savableFiles = (files: NoteFile[] | null | undefined): NoteFile[] =>
	(files ?? []).filter((file) => !isPending(file));

/** The server's list, plus local uploads still in flight that it does not know about. */
export const mergeIncomingFiles = (
	incoming: NoteFile[] | null | undefined,
	local: NoteFile[] | null | undefined
): NoteFile[] => {
	const server = (incoming ?? []).filter((file) => !isPending(file));
	const pending = (local ?? []).filter(
		(file) => isPending(file) && !server.some((s) => s?.itemId && s.itemId === file.itemId)
	);
	return [...server, ...pending];
};

/** Replace the placeholder `itemId` with the uploaded file, or add it if an echo dropped it. */
export const settleUpload = (
	files: NoteFile[] | null | undefined,
	itemId: string,
	uploaded: NoteFile
): NoteFile[] => {
	const list = files ?? [];
	const done = { ...uploaded, itemId };
	return list.some((file) => file?.itemId === itemId)
		? list.map((file) => (file?.itemId === itemId ? done : file))
		: [...list, done];
};
