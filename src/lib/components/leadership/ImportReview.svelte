<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getImport,
		getImports,
		postCandidateReview,
		postImport,
		LeadershipRequestError,
		type ImportBatch,
		type ImportBatchDetail,
		type ImportCandidate,
		type LeadershipView
	} from '$lib/apis/leadership';
	import { formatDateId, formatEventTimeId, recordedDueId } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// Rendered only for an `imports.review` holder; candidates are unreviewed material, and the
	// server refuses every read and write here without that grant.
	export let view: LeadershipView;
	export let scopeId: string;

	let batches: ImportBatch[] = [];
	let loading = true;
	let unavailable: string | null = null;
	let batch: ImportBatchDetail | null = null;
	let problem: string | null = null;
	let busy = false;
	let files: FileList | null = null;
	let linkTo: Record<string, string> = {};
	let controller: AbortController | null = null;

	const fail = (caught: unknown): string =>
		caught instanceof LeadershipRequestError && caught.isUnavailable
			? $i18n.t('Imports are not available on this server yet.')
			: caught instanceof LeadershipRequestError && caught.isAccessDenied
				? $i18n.t('You do not have access to this view')
				: caught instanceof LeadershipRequestError && caught.isConflict
					? $i18n.t('This candidate was already reviewed.')
					: caught instanceof Error
						? caught.message
						: `${caught}`;

	const loadBatches = async () => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		try {
			const result = await getImports(localStorage.token, view, scopeId, own.signal);
			if (!own.signal.aborted) batches = result.batches;
		} catch (caught) {
			if (!own.signal.aborted) unavailable = fail(caught);
		} finally {
			if (!own.signal.aborted) loading = false;
		}
	};

	const openBatch = async (id: string) => {
		problem = null;
		try {
			batch = await getImport(localStorage.token, view, scopeId, id);
			linkTo = {};
		} catch (caught) {
			problem = fail(caught);
		}
	};

	$: if (view && scopeId) loadBatches();
	onDestroy(() => controller?.abort());

	const upload = async () => {
		problem = null;
		const file = files?.[0];
		if (!file) {
			problem = $i18n.t('Choose a candidate file.');
			return;
		}
		busy = true;
		try {
			const result = await postImport(localStorage.token, view, scopeId, file);
			files = null;
			await loadBatches();
			await openBatch(result.batch_id);
			if (!result.created) problem = $i18n.t('This file was imported before; its batch is shown.');
		} catch (caught) {
			problem = fail(caught);
		} finally {
			busy = false;
		}
	};

	const review = async (candidate: ImportCandidate, decision: 'accept' | 'link' | 'reject') => {
		problem = null;
		const actionId = decision === 'link' ? (linkTo[candidate.id] ?? '').trim() : null;
		if (decision === 'link' && !actionId) {
			problem = $i18n.t('Name the recorded action to link this candidate to.');
			return;
		}
		busy = true;
		try {
			await postCandidateReview(localStorage.token, view, scopeId, candidate.id, {
				decision,
				action_id: actionId
			});
			if (batch) await openBatch(batch.id);
			await loadBatches();
		} catch (caught) {
			problem = fail(caught);
		} finally {
			busy = false;
		}
	};

	$: MATCH = {
		external_ref: $i18n.t('Matches a recorded action by its confirmed reference'),
		new: $i18n.t('New action candidate'),
		conflict: $i18n.t('Conflict with the recorded action')
	} as Record<string, string>;

	$: REVIEW = {
		pending: $i18n.t('Waiting for review'),
		accepted: $i18n.t('Accepted'),
		acknowledged: $i18n.t('Conflict acknowledged; recorded values kept'),
		linked: $i18n.t('Linked'),
		rejected: $i18n.t('Rejected')
	} as Record<string, string>;
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-imports-title">
	<h3 id="jlp-imports-title" class="jlp-surface-title">{$i18n.t('Reviewed imports')}</h3>
	<p class="jlp-meta">
		{$i18n.t(
			'A deck becomes records only through review. Nothing is verified until a reviewer accepts or links it, and conflicts are never resolved automatically.'
		)}
	</p>

	{#if loading}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if unavailable}
		<p class="jlp-meta">{unavailable}</p>
	{:else}
		<form class="jlp-form" on:submit|preventDefault={upload}>
			<label class="jlp-field">
				<span>{$i18n.t('Candidate file (JSON, prepared outside the app)')}</span>
				<input type="file" accept="application/json,.json" bind:files />
			</label>
			<button type="submit" class="jlp-button" disabled={busy}
				>{$i18n.t('Upload for review')}</button
			>
		</form>

		{#if batches.length}
			<ul class="jlp-mini-list">
				{#each batches as item (item.id)}
					<li class="jlp-mini" class:jlp-row-selected={batch?.id === item.id}>
						<strong>{item.source_filename}</strong>
						<span class="jlp-meta jlp-block">
							{item.meeting_date ? formatDateId(item.meeting_date) : '—'} · {formatEventTimeId(
								item.created_at
							)} · {item.status === 'reviewed' ? $i18n.t('All reviewed') : $i18n.t('Open')}
						</span>
						<button type="button" class="jlp-link" on:click={() => openBatch(item.id)}
							>{$i18n.t('Review candidates')}</button
						>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="jlp-meta mt-2">{$i18n.t('No candidate file has been uploaded yet.')}</p>
		{/if}
	{/if}

	<div aria-live="polite">
		{#if problem}
			<p class="jlp-notice jlp-notice-refused mt-2">{problem}</p>
		{/if}
	</div>

	{#if batch}
		<section class="mt-4" aria-labelledby="jlp-batch-title">
			<h4 class="jlp-surface-title" id="jlp-batch-title">{batch.source_filename}</h4>
			<ul class="jlp-mini-list">
				{#each batch.candidates as candidate (candidate.id)}
					<li class="jlp-mini">
						<strong>{candidate.payload.title}</strong>
						<span class="jlp-meta jlp-block">
							{$i18n.t('Slide {{slide}}', { slide: candidate.payload.slide })} ·
							{candidate.payload.external_id} ·
							{candidate.verification === 'verified' ? $i18n.t('Verified') : $i18n.t('Unverified')}
						</span>
						<span class="jlp-block">{MATCH[candidate.match_kind] ?? candidate.match_kind}</span>
						<dl class="jlp-dl mt-2">
							<dt>{$i18n.t('PIC')}</dt>
							<dd>
								{#if candidate.payload.owner_label}
									{candidate.payload.owner_label}
								{:else}
									<span class="jlp-meta"
										>{$i18n.t('Missing')}: {candidate.payload.missing.owner_label ?? '—'}</span
									>
								{/if}
							</dd>
							<dt>{$i18n.t('Target')}</dt>
							<dd>
								{#if candidate.payload.due}
									{recordedDueId(candidate.payload.due)}
								{:else}
									<span class="jlp-meta"
										>{$i18n.t('Missing')}: {candidate.payload.missing.due ?? '—'}</span
									>
								{/if}
							</dd>
							<dt>{$i18n.t('Progress reported')}</dt>
							<dd>
								{#if candidate.payload.progress_summary}
									{candidate.payload.progress_summary}
								{:else}
									<span class="jlp-meta"
										>{$i18n.t('Missing')}: {candidate.payload.missing.progress_summary ?? '—'}</span
									>
								{/if}
							</dd>
						</dl>
						{#if candidate.conflict}
							<details class="mt-2">
								<summary class="jlp-link">{$i18n.t('What conflicts')}</summary>
								<pre class="jlp-meta">{JSON.stringify(candidate.conflict, null, 2)}</pre>
							</details>
						{/if}
						<span class="jlp-status jlp-block"
							>{REVIEW[candidate.review_state] ?? candidate.review_state}</span
						>
						{#if candidate.review_state === 'pending'}
							<span class="jlp-row-buttons">
								{#if candidate.match_kind !== 'new' || candidate.payload.owner_label}
									<button
										type="button"
										class="jlp-link"
										disabled={busy}
										on:click={() => review(candidate, 'accept')}
										>{candidate.match_kind === 'conflict'
											? $i18n.t('Acknowledge')
											: $i18n.t('Accept')}</button
									>
								{/if}
								<button
									type="button"
									class="jlp-link"
									disabled={busy}
									on:click={() => review(candidate, 'reject')}>{$i18n.t('Reject')}</button
								>
							</span>
							{#if candidate.match_kind !== 'external_ref'}
								<span class="jlp-row-buttons">
									<input
										type="text"
										maxlength="64"
										placeholder="act-…"
										aria-label={$i18n.t('Recorded action id to link')}
										bind:value={linkTo[candidate.id]}
									/>
									<button
										type="button"
										class="jlp-link"
										disabled={busy}
										on:click={() => review(candidate, 'link')}>{$i18n.t('Link')}</button
									>
								</span>
							{/if}
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</section>
