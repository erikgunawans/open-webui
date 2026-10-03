// The office preview panel (Track O, O4): which Word, Excel or PowerPoint file is open in the
// chat's right-hand column, and when one opens by itself.
//
// Presentation only. The panel loads the file through the app's own content route, which serves a
// file only to its owner (or an admin), so holding an id here grants nothing.
import { get, writable } from 'svelte/store';

import { chatId, showArtifacts, showControls, showEmbeds } from '$lib/stores';

export type OfficeKind = 'xlsx' | 'docx' | 'pptx';

export type PreviewItem = {
	type?: string;
	id?: string;
	name?: string;
	content_type?: string;
	meta?: { content_type?: string; name?: string };
};

export type OpenPreview = { item: PreviewItem; kind: OfficeKind; chatId: string };

const MIME: Record<string, OfficeKind> = {
	'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
	'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
	'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx'
};

// The large-screen breakpoint ChatControls uses; below it the column is a full-screen drawer.
export const LARGE_SCREEN = '(min-width: 1024px)';

/** The office format of a stored chat file, or null for anything the panel does not show. */
export const officeKind = (item: PreviewItem | null | undefined): OfficeKind | null => {
	if (!item || item.type !== 'file' || !item.id) return null;
	const mime = item.content_type ?? item.meta?.content_type ?? '';
	if (MIME[mime]) return MIME[mime];
	const name = (item.name ?? item.meta?.name ?? '').toLowerCase();
	const ext = name.slice(name.lastIndexOf('.') + 1);
	return ext === 'xlsx' || ext === 'docx' || ext === 'pptx' ? ext : null;
};

/** The office file that `next` adds to `previous`, newest last; null when none was added. */
export const addedOfficeFile = (
	previous: PreviewItem[] | null | undefined,
	next: PreviewItem[] | null | undefined
): PreviewItem | null => {
	const known = new Set((previous ?? []).map((file) => file?.id).filter(Boolean));
	const added = (next ?? []).filter((file) => officeKind(file) && !known.has(file.id));
	return added.length ? added[added.length - 1] : null;
};

/** Which sheet a workbook opens on: the first data sheet of a JUP workbook, past its cover. */
export const firstSheet = (names: string[]): string =>
	names.length > 1 && names[0] === 'Info' ? names[1] : (names[0] ?? '');

export const officePreview = writable<OpenPreview | null>(null);

// True while a chat's right-hand column is mounted. Elsewhere (knowledge, workspace) a file
// keeps opening in the vendor's modal.
export const officePreviewAvailable = writable(false);

export const openOfficePreview = (item: PreviewItem): boolean => {
	const kind = officeKind(item);
	if (!kind || !get(officePreviewAvailable)) return false;
	showArtifacts.set(false);
	showEmbeds.set(false);
	officePreview.set({ item, kind, chatId: get(chatId) });
	showControls.set(true);
	return true;
};

export const closeOfficePreview = () => officePreview.set(null);

/**
 * Open a file the assistant just attached, the way other assistants open their artifacts.
 * Large screens only: on a phone the column is a full-screen drawer, so the chip stays one tap.
 */
export const autoOpenOfficePreview = (
	previous: PreviewItem[] | null | undefined,
	next: PreviewItem[] | null | undefined,
	isLargeScreen: () => boolean = () =>
		typeof window !== 'undefined' && window.matchMedia(LARGE_SCREEN).matches
): boolean => {
	const added = addedOfficeFile(previous, next);
	return added !== null && isLargeScreen() ? openOfficePreview(added) : false;
};

// Another panel taking the column, or the column closing, ends the preview, so reopening the
// column shows its own tabs rather than a stale file.
showArtifacts.subscribe((shown) => shown && closeOfficePreview());
showEmbeds.subscribe((shown) => shown && closeOfficePreview());
showControls.subscribe((shown) => !shown && closeOfficePreview());
