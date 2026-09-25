<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import {
		approveSubmission,
		getReviewQueue,
		getSubmission,
		rejectSubmission,
		type QueueFilter,
		type Submission,
		type SubmissionDetail
	} from '$lib/apis/kb-review';
	import { formatEventTimeId } from '$lib/leadership/format';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ReviewError from './ReviewError.svelte';
	import StateLabel from './StateLabel.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	const REASON_MAX = 1000;

	let filter: QueueFilter = 'pending';
	let items: Submission[] = [];
	let loading = true;
	let loadProblem: unknown = null;

	let show = false;
	let detail: SubmissionDetail | null = null;
	let opening = false;
	let problem: unknown = null;
	let busy = false;
	let rejecting = false;
	let reason = '';

	let FILTERS: { value: QueueFilter; label: string }[];
	$: FILTERS = [
		{ value: 'pending', label: $i18n.t('Waiting for review') },
		{ value: 'approved', label: $i18n.t('Approved') },
		{ value: 'rejected', label: $i18n.t('Rejected') },
		{ value: 'all', label: $i18n.t('All') }
	];

	const load = async () => {
		loading = true;
		try {
			items = (await getReviewQueue(localStorage.token, filter)).items;
			loadProblem = null;
		} catch (caught) {
			loadProblem = caught;
		} finally {
			loading = false;
		}
	};

	onMount(load);

	const setFilter = (value: QueueFilter) => {
		filter = value;
		load();
	};

	const open = async (item: Submission) => {
		detail = null;
		problem = null;
		rejecting = false;
		reason = '';
		show = true;
		opening = true;
		try {
			detail = await getSubmission(localStorage.token, item.file_id);
		} catch (caught) {
			problem = caught;
		} finally {
			opening = false;
		}
	};

	const decided = async () => {
		show = false;
		detail = null;
		await load();
	};

	const approve = async () => {
		if (!detail) return;
		problem = null;
		busy = true;
		try {
			await approveSubmission(localStorage.token, detail.file_id, detail.content_sha256);
			await decided();
		} catch (caught) {
			problem = caught;
		} finally {
			busy = false;
		}
	};

	const reject = async () => {
		if (!detail) return;
		problem = null;
		if (!reason.trim()) {
			problem = $i18n.t('A rejection needs a reason.');
			return;
		}
		busy = true;
		try {
			await rejectSubmission(localStorage.token, detail.file_id, reason.trim());
			await decided();
		} catch (caught) {
			problem = caught;
		} finally {
			busy = false;
		}
	};

	const who = (name: string | null | undefined, id: string | null) => name || id || '—';
</script>

<section class="jlp-surface mt-4" aria-labelledby="kbr-queue-title">
	<h2 id="kbr-queue-title" class="jlp-surface-title">{$i18n.t('Review queue')}</h2>
	<p class="jlp-meta">
		{$i18n.t(
			'Open a submission to read it before deciding. Approving adds it to the JUP Staff Contributions collection; the Strategy KB is not touched.'
		)}
	</p>

	<div class="jlp-row-buttons mt-2" role="group" aria-label={$i18n.t('Filter by state')}>
		{#each FILTERS as option (option.value)}
			<button
				type="button"
				class="jlp-link"
				aria-pressed={filter === option.value}
				on:click={() => setFilter(option.value)}>{option.label}</button
			>
		{/each}
	</div>

	{#if loading}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if loadProblem}
		<p class="jlp-notice jlp-notice-refused mt-2"><ReviewError error={loadProblem} /></p>
	{:else if items.length === 0}
		<p class="jlp-meta mt-2">{$i18n.t('No submissions in this state.')}</p>
	{:else}
		<ul class="jlp-mini-list mt-2">
			{#each items as item (item.file_id)}
				<li class="jlp-mini">
					<strong>{item.filename}</strong>
					<span class="jlp-meta jlp-block">
						{who(item.submitted_by_name, item.submitted_by)} · {formatEventTimeId(
							item.submitted_at * 1000
						)}
					</span>
					<StateLabel state={item.state} />
					{#if item.changed_since_review}
						<span class="jlp-block jlp-negative"
							>{$i18n.t('The text changed after it was submitted.')}</span
						>
					{/if}
					<button
						type="button"
						class="jlp-link"
						aria-label={$i18n.t('Open submission {{name}}', { name: item.filename })}
						on:click={() => open(item)}>{$i18n.t('Open')}</button
					>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<Modal size="lg" bind:show ariaLabelledby="kbr-detail-title">
	<div class="jlp-root jlp-dialog" role="document">
		<div class="jlp-dialog-head">
			<h2 class="jlp-dialog-title" id="kbr-detail-title">
				{detail?.filename ?? $i18n.t('Submission')}
			</h2>
			<button type="button" class="jlp-link" on:click={() => (show = false)}
				>{$i18n.t('Close')}</button
			>
		</div>

		{#if opening}
			<div class="flex justify-center py-6"><Spinner className="size-5" /></div>
		{:else if detail}
			<dl class="jlp-dl">
				<dt>{$i18n.t('Submitted by')}</dt>
				<dd>{who(detail.submitted_by_name, detail.submitted_by)}</dd>
				<dt>{$i18n.t('Submitted')}</dt>
				<dd>{formatEventTimeId(detail.submitted_at * 1000)}</dd>
				<dt>{$i18n.t('State')}</dt>
				<dd><StateLabel state={detail.state} /></dd>
				<dt>{$i18n.t('Submitter note')}</dt>
				<dd>{detail.note ?? '—'}</dd>
				{#if detail.reviewed_by}
					<dt>{$i18n.t('Reviewed by')}</dt>
					<dd>
						{who(detail.reviewed_by_name, detail.reviewed_by)}
						{#if detail.reviewed_at}· {formatEventTimeId(detail.reviewed_at * 1000)}{/if}
					</dd>
				{/if}
				{#if detail.reason}
					<dt>{$i18n.t('Reason')}</dt>
					<dd>{detail.reason}</dd>
				{/if}
			</dl>

			{#if detail.changed_since_review}
				<p class="jlp-notice jlp-notice-refused mt-2">
					{$i18n.t('The text changed after it was submitted.')}
				</p>
			{/if}

			<h3 class="jlp-group-title mt-3" id="kbr-preview-title">{$i18n.t('Extracted text')}</h3>
			<pre
				class="jlp-meta mt-1 max-h-96 overflow-auto whitespace-pre-wrap"
				tabindex="0"
				aria-labelledby="kbr-preview-title">{detail.preview.text}</pre>
			{#if detail.preview.truncated}
				<p class="jlp-meta mt-1">
					{$i18n.t('Showing the first {{shown}} of {{total}} characters.', {
						shown: detail.preview.text.length,
						total: detail.preview.length
					})}
				</p>
			{/if}

			{#if detail.state === 'pending'}
				{#if rejecting}
					<form class="jlp-form mt-3" on:submit|preventDefault={reject}>
						<label class="jlp-field">
							<span>{$i18n.t('Reason for rejecting (the submitter sees it)')}</span>
							<textarea rows="3" maxlength={REASON_MAX} bind:value={reason} required></textarea>
						</label>
						<span class="jlp-row-buttons">
							<button type="submit" class="jlp-button" disabled={busy}
								>{$i18n.t('Reject submission')}</button
							>
							<button
								type="button"
								class="jlp-link"
								disabled={busy}
								on:click={() => (rejecting = false)}>{$i18n.t('Cancel')}</button
							>
						</span>
					</form>
				{:else}
					<span class="jlp-row-buttons mt-3">
						<button type="button" class="jlp-button" disabled={busy} on:click={approve}
							>{$i18n.t('Approve and add to the knowledge base')}</button
						>
						<button
							type="button"
							class="jlp-link"
							disabled={busy}
							on:click={() => (rejecting = true)}>{$i18n.t('Reject')}</button
						>
					</span>
				{/if}
			{/if}
		{/if}

		<div aria-live="polite">
			{#if problem}
				<p class="jlp-notice jlp-notice-refused mt-2"><ReviewError error={problem} /></p>
			{/if}
		</div>
	</div>
</Modal>
