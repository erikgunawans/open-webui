<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { uploadFile } from '$lib/apis/files';
	import { getMySubmissions, submitForReview, type Submission } from '$lib/apis/kb-review';
	import { formatEventTimeId } from '$lib/leadership/format';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ReviewError from './ReviewError.svelte';
	import StateLabel from './StateLabel.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	const ACCEPT = '.md,.txt,.pdf,.docx,.pptx,.xlsx,.csv';
	const NOTE_MAX = 1000;

	let files: FileList | null = null;
	let fileInput: HTMLInputElement;
	let note = '';
	let busy = false;
	let stage: 'idle' | 'uploading' | 'submitting' = 'idle';
	let problem: unknown = null;
	let done = false;

	let items: Submission[] = [];
	let loading = true;
	let loadProblem: unknown = null;

	const load = async () => {
		try {
			items = (await getMySubmissions(localStorage.token)).items;
			loadProblem = null;
		} catch (caught) {
			loadProblem = caught;
		} finally {
			loading = false;
		}
	};

	onMount(load);

	const submit = async () => {
		problem = null;
		done = false;
		const file = files?.[0];
		if (!file) {
			problem = $i18n.t('Choose a document to submit.');
			return;
		}
		busy = true;
		try {
			// Upload through the vendor files API and wait for its processing stream to finish, so
			// the server has the extracted text before the submission is recorded.
			stage = 'uploading';
			const uploaded = await uploadFile(localStorage.token, file);
			if (!uploaded?.id) throw new Error($i18n.t('The upload failed.'));
			if (uploaded.error) throw new Error(`${uploaded.error}`);
			stage = 'submitting';
			await submitForReview(localStorage.token, uploaded.id, note.trim() || null);
			files = null;
			if (fileInput) fileInput.value = '';
			note = '';
			done = true;
			await load();
		} catch (caught) {
			problem = caught;
		} finally {
			busy = false;
			stage = 'idle';
		}
	};
</script>

<section class="jlp-surface mt-4" aria-labelledby="kbr-submit-title">
	<h2 id="kbr-submit-title" class="jlp-surface-title">{$i18n.t('Submit a document')}</h2>
	<p class="jlp-meta">
		{$i18n.t(
			'The document is read by an admin before the assistant can use it. Text documents only: md, txt, pdf, docx, pptx, xlsx, csv.'
		)}
	</p>

	<form class="jlp-form" on:submit|preventDefault={submit}>
		<label class="jlp-field">
			<span>{$i18n.t('Document')}</span>
			<input type="file" accept={ACCEPT} bind:files bind:this={fileInput} disabled={busy} />
		</label>
		<label class="jlp-field">
			<span>{$i18n.t('Note for the reviewer (optional)')}</span>
			<textarea rows="3" maxlength={NOTE_MAX} bind:value={note} disabled={busy}></textarea>
		</label>
		<button type="submit" class="jlp-button" disabled={busy}>
			{#if stage === 'uploading'}
				{$i18n.t('Uploading and reading the document…')}
			{:else if stage === 'submitting'}
				{$i18n.t('Submitting…')}
			{:else}
				{$i18n.t('Submit for review')}
			{/if}
		</button>
	</form>

	<div aria-live="polite">
		{#if problem}
			<p class="jlp-notice jlp-notice-refused mt-2"><ReviewError error={problem} /></p>
		{:else if done}
			<p class="jlp-notice mt-2">{$i18n.t('Submitted. An admin will review it.')}</p>
		{/if}
	</div>

	<h3 class="jlp-group-title mt-4" id="kbr-mine-title">{$i18n.t('My submissions')}</h3>
	{#if loading}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if loadProblem}
		<p class="jlp-notice jlp-notice-refused"><ReviewError error={loadProblem} /></p>
	{:else if items.length === 0}
		<p class="jlp-meta">{$i18n.t('You have not submitted any documents yet.')}</p>
	{:else}
		<ul class="jlp-mini-list" aria-labelledby="kbr-mine-title">
			{#each items as item (item.file_id)}
				<li class="jlp-mini">
					<strong>{item.filename}</strong>
					<span class="jlp-meta jlp-block">
						{$i18n.t('Submitted')}: {formatEventTimeId(item.submitted_at * 1000)}
					</span>
					<StateLabel state={item.state} />
					{#if item.state === 'rejected' && item.reason}
						<span class="jlp-block mt-1">{$i18n.t('Reason')}: {item.reason}</span>
					{/if}
					{#if item.note}
						<span class="jlp-meta jlp-block">{$i18n.t('Your note')}: {item.note}</span>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>
