<script lang="ts">
	// O4: a Word, Excel or PowerPoint file in the chat's right-hand column. The renderers are the
	// vendor's own (FileItemModal: SheetJS + excelToTable, DocxPreview, pptxToImages); this adds the
	// column, a header that carries the file's Draf status and classification, and a download link.
	// View-only by design (Erik 10-03): editing in place is the parked "edit an uploaded file" item.
	import DOMPurify from 'dompurify';
	import { getContext } from 'svelte';
	import type { Readable } from 'svelte/store';
	import type { WorkBook } from 'xlsx';

	import { getFileById, getFileContentById } from '$lib/apis/files';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { closeOfficePreview, firstSheet, type OpenPreview } from '$lib/office/preview';

	import DocxPreview from '$lib/components/common/DocxPreview.svelte';
	import PptxPreview from '$lib/components/common/PptxPreview.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	type I18n = { t: (key: string, values?: Record<string, unknown>) => string };
	const i18n = getContext<Readable<I18n>>('i18n');

	export let preview: OpenPreview;

	let loadedId: string | null = null;
	let loading = false;
	let error = '';
	let status = '';
	let classification = '';

	let workbook: WorkBook | null = null;
	let sheetNames: string[] = [];
	let selectedSheet = '';
	let sheetHtml = '';

	let docxData: ArrayBuffer | null = null;
	let slides: string[] = [];
	let currentSlide = 0;

	$: fileId = preview?.item?.id ?? '';
	$: name = preview?.item?.name ?? preview?.item?.meta?.name ?? '';
	$: contentUrl = `${WEBUI_API_BASE_URL}/files/${fileId}/content`;

	const reset = () => {
		error = '';
		status = '';
		classification = '';
		workbook = null;
		sheetNames = [];
		selectedSheet = '';
		sheetHtml = '';
		docxData = null;
		slides = [];
		currentSlide = 0;
	};

	const load = async (target: OpenPreview) => {
		const id = target.item.id as string;
		loadedId = id;
		reset();
		loading = true;
		try {
			const [record, data] = await Promise.all([
				getFileById(localStorage.token, id).catch(() => null),
				getFileContentById(id)
			]);
			if (loadedId !== id) return;
			if (!data) throw new Error('the file content was empty');
			const office = record?.meta?.data?.jup_office;
			status = office?.status ?? '';
			classification = office?.classification ?? '';

			if (target.kind === 'xlsx') {
				const { read } = await import('xlsx');
				workbook = read(data, { type: 'array' });
				sheetNames = workbook.SheetNames;
				selectedSheet = firstSheet(sheetNames);
			} else if (target.kind === 'docx') {
				docxData = data;
			} else {
				const { pptxToImages } = await import('$lib/utils/pptxToHtml');
				slides = (await pptxToImages(data)).images;
			}
		} catch (e) {
			console.error('Office preview failed:', e);
			if (loadedId === id) {
				error = $i18n.t('This file could not be shown here. Download it to open it.');
			}
		} finally {
			if (loadedId === id) loading = false;
		}
	};

	const renderSheet = async (book: WorkBook, sheet: string) => {
		const { excelToTable } = await import('$lib/utils/excelToTable');
		const result = await excelToTable(book.Sheets[sheet]);
		if (workbook === book && selectedSheet === sheet) {
			sheetHtml = DOMPurify.sanitize(result.html);
		}
	};

	$: if (preview && fileId && fileId !== loadedId) load(preview);
	$: if (workbook && selectedSheet) renderSheet(workbook, selectedSheet);
</script>

<div class="flex h-full w-full flex-col" data-jup-office-preview={preview.kind}>
	<div class="flex shrink-0 items-start gap-2 px-3 pt-3 pb-2">
		<div class="min-w-0 flex-1">
			<div class="truncate text-sm font-medium text-gray-900 dark:text-gray-100" title={name}>
				{name}
			</div>
			{#if status || classification}
				<div class="mt-1 flex flex-wrap gap-1.5 text-xs">
					{#if status}
						<span class="jup-office-badge rounded-full px-2 py-0.5">{status}</span>
					{/if}
					{#if classification}
						<span class="jup-office-badge jup-office-badge--level rounded-full px-2 py-0.5">
							{classification}
						</span>
					{/if}
				</div>
			{/if}
		</div>
		<a
			class="shrink-0 rounded-full px-3 py-1 text-xs font-medium bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-900 dark:text-gray-100 transition"
			href={contentUrl}
			download={name}
		>
			{$i18n.t('Download')}
		</a>
		<button
			class="shrink-0 rounded-full p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
			type="button"
			aria-label={$i18n.t('Close preview')}
			on:click={closeOfficePreview}
		>
			<XMark className="size-4" />
		</button>
	</div>

	{#if sheetNames.length > 1}
		<div
			class="flex shrink-0 gap-1 overflow-x-auto scrollbar-none border-b border-gray-100 dark:border-gray-850 px-3 text-sm"
			role="tablist"
		>
			{#each sheetNames as sheetName}
				<button
					class="min-w-fit border-b-2 px-3 py-1.5 transition {selectedSheet === sheetName
						? 'border-current text-gray-900 dark:text-white'
						: 'border-transparent text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					type="button"
					role="tab"
					aria-selected={selectedSheet === sheetName}
					on:click={() => (selectedSheet = sheetName)}>{sheetName}</button
				>
			{/each}
		</div>
	{/if}

	<div class="min-h-0 flex-1 overflow-auto px-3 py-2">
		{#if loading}
			<div class="flex justify-center py-8"><Spinner className="size-5" /></div>
		{:else if error}
			<div class="p-4 text-sm text-red-600 dark:text-red-400">{error}</div>
		{:else if preview.kind === 'xlsx'}
			{#if sheetHtml}
				<div class="office-preview text-sm">{@html sheetHtml}</div>
			{:else}
				<div class="p-4 text-sm text-gray-500">{$i18n.t('This sheet is empty.')}</div>
			{/if}
		{:else if preview.kind === 'docx' && docxData}
			<DocxPreview data={docxData} className="h-full" />
		{:else if preview.kind === 'pptx' && slides.length}
			<PptxPreview {slides} bind:currentSlide className="h-full" />
		{/if}
	</div>
</div>

<style>
	/* Soft badge tokens from src/jup-tokens.css: ink on fill measures 16.20:1 light; dark flips both. */
	.jup-office-badge {
		background: var(--jup-ui-fill);
		color: var(--jup-ui-ink);
	}
	.jup-office-badge--level {
		font-weight: 600;
	}
</style>
