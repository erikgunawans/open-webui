<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getSnapshot,
		postSnapshotPublish,
		LeadershipRequestError,
		type LeadershipView,
		type SnapshotDetail,
		type SnapshotWithContent
	} from '$lib/apis/leadership';
	import { formatDateId, formatEventTimeId, formatValue, shortHash } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ changed: void }>();

	export let show = false;
	export let view: LeadershipView;
	export let scopeId: string;
	export let snapshotId: string | null = null;
	// Offered to a `snapshots.publish` holder; the server checks the grant, the policy and
	// four-eyes again.
	export let canPublish = false;

	let detail: SnapshotDetail | null = null;
	let error: string | null = null;
	let loading = false;
	let busy = false;
	let publishProblem: string | null = null;
	let controller: AbortController | null = null;
	let showing: 'published' | 'latest' = 'published';

	const load = async (id: string) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		detail = null;
		error = null;
		publishProblem = null;
		showing = 'published';
		loading = true;
		try {
			const result = await getSnapshot(localStorage.token, view, scopeId, id, own.signal);
			if (!own.signal.aborted) detail = result;
		} catch (caught) {
			if (own.signal.aborted) return;
			if (caught instanceof LeadershipRequestError && caught.isNotFound) {
				error = $i18n.t('This meeting record is not part of this view.');
			} else if (caught instanceof LeadershipRequestError && caught.isAccessDenied) {
				error = $i18n.t('You do not have access to this view');
			} else if (caught instanceof LeadershipRequestError && caught.isUnavailable) {
				error = $i18n.t(
					'This meeting record cannot be served; it failed its integrity check or the store is unavailable.'
				);
			} else {
				error = `${caught}`;
			}
		} finally {
			if (!own.signal.aborted) loading = false;
		}
	};

	$: if (show && snapshotId) load(snapshotId);
	$: if (!show) controller?.abort();

	// The published record is the meeting record. A draft is shown only as a draft, labelled.
	$: if (detail && !detail.published) showing = 'latest';
	$: shown = detail
		? ((showing === 'published' ? detail.published : detail.latest) as SnapshotWithContent | null)
		: null;

	// The publisher approves exactly the draft they read, by its hash.
	const publish = async () => {
		if (!detail || detail.latest.state !== 'draft') return;
		publishProblem = null;
		busy = true;
		try {
			await postSnapshotPublish(localStorage.token, view, scopeId, detail.latest.snapshot_id, {
				expected_version: detail.latest.version,
				content_hash: detail.latest.content_hash
			});
			dispatch('changed');
			await load(detail.latest.snapshot_id);
			showing = 'published';
		} catch (caught) {
			if (caught instanceof LeadershipRequestError && caught.isConflict) {
				publishProblem = $i18n.t(
					'This snapshot changed since you reviewed it. Reload and try again.'
				);
			} else if (caught instanceof LeadershipRequestError && caught.isUnavailable) {
				publishProblem = $i18n.t(
					'Publication is not configured on this server; every snapshot stays a draft.'
				);
			} else {
				publishProblem = caught instanceof Error ? caught.message : `${caught}`;
			}
		} finally {
			busy = false;
		}
	};

	$: STATE = {
		draft: $i18n.t('Draft'),
		published: $i18n.t('Published')
	} as Record<string, string>;

	$: CHANGE = {
		draft: $i18n.t('Draft frozen'),
		publication: $i18n.t('Publication'),
		correction: $i18n.t('Correction')
	} as Record<string, string>;
</script>

<Modal size="lg" bind:show ariaLabelledby="jlp-snapshot-title">
	<div class="jlp-root jlp-dialog" role="document">
		<div class="jlp-dialog-head">
			<h2 class="jlp-dialog-title" id="jlp-snapshot-title">
				{detail ? detail.latest.meeting_label : $i18n.t('Meeting record')}
			</h2>
			<button type="button" class="jlp-link" on:click={() => (show = false)}
				>{$i18n.t('Close')}</button
			>
		</div>

		{#if loading}
			<div class="flex justify-center py-6"><Spinner className="size-5" /></div>
		{:else if error}
			<p class="jlp-notice">{error}</p>
		{:else if detail}
			{#if detail.published && detail.latest.state === 'draft'}
				<div class="jlp-row-buttons" role="group" aria-label={$i18n.t('Version shown')}>
					<button
						type="button"
						class="jlp-link"
						aria-pressed={showing === 'published'}
						on:click={() => (showing = 'published')}>{$i18n.t('Published record')}</button
					>
					<button
						type="button"
						class="jlp-link"
						aria-pressed={showing === 'latest'}
						on:click={() => (showing = 'latest')}>{$i18n.t('Newer draft')}</button
					>
				</div>
			{/if}

			{#if shown}
				{#if shown.state === 'draft'}
					<p class="jlp-notice mt-2">
						{$i18n.t('Draft: not an approved meeting record.')}
					</p>
				{/if}
				<dl class="jlp-dl mt-2">
					<dt>{$i18n.t('Status')}</dt>
					<dd>
						{STATE[shown.state]} · {$i18n.t('Version {{version}}', { version: shown.version })}
					</dd>
					{#if shown.meeting_date}
						<dt>{$i18n.t('Meeting date')}</dt>
						<dd>{formatDateId(shown.meeting_date)}</dd>
					{/if}
					<dt>{$i18n.t('Frozen')}</dt>
					<dd>{formatEventTimeId(shown.created_at)}</dd>
					<dt>{$i18n.t('Content hash')}</dt>
					<dd><code title={shown.content_hash}>{shortHash(shown.content_hash)}</code></dd>
					<dt>{$i18n.t('Actions source')}</dt>
					<dd>
						{shown.content.actions_source === 'records'
							? $i18n.t('Recorded register')
							: $i18n.t('Illustrative sample')}
					</dd>
				</dl>

				<section class="mt-4" aria-labelledby="jlp-snapshot-metrics">
					<h3 class="jlp-surface-title" id="jlp-snapshot-metrics">
						{$i18n.t('Metrics as frozen')}
					</h3>
					<ul class="jlp-mini-list">
						{#each shown.content.metrics as metric (metric.id)}
							<li class="jlp-mini">
								<strong>{metric.label}</strong>
								<span class="jlp-block">
									{metric.primary.value === null
										? $i18n.t('Unavailable')
										: formatValue(metric.primary.value, metric.primary.unit)}
								</span>
							</li>
						{/each}
					</ul>
				</section>

				<section class="mt-4" aria-labelledby="jlp-snapshot-actions">
					<h3 class="jlp-surface-title" id="jlp-snapshot-actions">
						{$i18n.t('Actions as frozen')}
					</h3>
					{#if shown.content.actions.length === 0}
						<p class="jlp-meta">{$i18n.t('No action was recorded for this view.')}</p>
					{:else}
						<ul class="jlp-mini-list">
							{#each shown.content.actions as action (action.id)}
								<li class="jlp-mini">
									<strong>{action.title}</strong>
									<span class="jlp-meta jlp-block"
										>{action.owner_label} · {action.due
											? action.due.label
											: $i18n.t('No target recorded')}</span
									>
								</li>
							{/each}
						</ul>
					{/if}
				</section>
			{/if}

			<section class="mt-4" aria-labelledby="jlp-snapshot-versions">
				<h3 class="jlp-surface-title" id="jlp-snapshot-versions">{$i18n.t('Versions')}</h3>
				<p class="jlp-meta">
					{$i18n.t('Versions are never edited. A correction is a new, linked version.')}
				</p>
				<ol class="jlp-mini-list">
					{#each [...detail.versions].reverse() as version (version.id)}
						<li class="jlp-mini">
							<strong>{$i18n.t('Version {{version}}', { version: version.version })}</strong>
							· {CHANGE[version.change_kind] ?? version.change_kind} · {STATE[version.state]}
							<span class="jlp-meta jlp-block">
								{formatEventTimeId(version.created_at)} ·
								<code title={version.content_hash}>{shortHash(version.content_hash)}</code>
								{#if version.previous_version_id}
									· {$i18n.t('follows version {{version}}', {
										version:
											detail.versions.find((item) => item.id === version.previous_version_id)
												?.version ?? '?'
									})}
								{/if}
							</span>
						</li>
					{/each}
				</ol>
			</section>

			{#if canPublish && detail.latest.state === 'draft'}
				<section class="jlp-surface mt-4" aria-labelledby="jlp-publish-title">
					<h3 class="jlp-surface-title" id="jlp-publish-title">{$i18n.t('Publish this draft')}</h3>
					<p class="jlp-meta">
						{$i18n.t('Publishing approves exactly the draft shown, by its content hash {{hash}}.', {
							hash: shortHash(detail.latest.content_hash)
						})}
					</p>
					<button type="button" class="jlp-button mt-2" disabled={busy} on:click={publish}
						>{$i18n.t('Publish as the meeting record')}</button
					>
					<div aria-live="polite">
						{#if publishProblem}
							<p class="jlp-notice jlp-notice-refused mt-2">{publishProblem}</p>
						{/if}
					</div>
				</section>
			{/if}
		{/if}
	</div>
</Modal>
