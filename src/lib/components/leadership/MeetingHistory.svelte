<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getSnapshots,
		postSnapshotDraft,
		LeadershipRequestError,
		type LeadershipView,
		type SnapshotListItem
	} from '$lib/apis/leadership';
	import { meetingRecordState } from '$lib/leadership/actions';
	import { formatDateId, shortHash } from '$lib/leadership/format';
	import { leadershipAccess } from '$lib/stores/leadership';

	import SnapshotViewer from './SnapshotViewer.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let view: LeadershipView;
	export let scopeId: string;

	let items: SnapshotListItem[] = [];
	let loading = true;
	let unavailable: string | null = null;
	let controller: AbortController | null = null;

	const load = async (key: string) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		unavailable = null;
		try {
			const result = await getSnapshots(localStorage.token, view, scopeId, own.signal);
			if (!own.signal.aborted) items = result.snapshots;
		} catch (caught) {
			if (own.signal.aborted) return;
			items = [];
			unavailable =
				caught instanceof LeadershipRequestError && caught.isUnavailable
					? $i18n.t('Meeting records are not available on this server yet.')
					: caught instanceof LeadershipRequestError && caught.isAccessDenied
						? $i18n.t('You do not have access to this view')
						: `${caught}`;
		} finally {
			if (!own.signal.aborted) loading = false;
		}
		return key;
	};

	$: load(`${view}|${scopeId}`);
	onDestroy(() => controller?.abort());

	// Freezing a draft needs `snapshots.publish`; the server checks it and the records store.
	$: canPublish = $leadershipAccess.operations.includes('snapshots.publish');

	let meetingLabel = '';
	let meetingDate = '';
	let busy = false;
	let draftProblem: string | null = null;

	const freeze = async () => {
		draftProblem = null;
		if (!meetingLabel.trim()) {
			draftProblem = $i18n.t('Name the meeting.');
			return;
		}
		busy = true;
		try {
			const draft = await postSnapshotDraft(localStorage.token, view, scopeId, {
				meeting_label: meetingLabel.trim(),
				meeting_date: meetingDate || null
			});
			meetingLabel = meetingDate = '';
			await load(`${view}|${scopeId}`);
			open(draft.snapshot_id);
		} catch (caught) {
			draftProblem = caught instanceof Error ? caught.message : `${caught}`;
		} finally {
			busy = false;
		}
	};

	let viewerOpen = false;
	let viewerId: string | null = null;
	const open = (id: string) => {
		viewerId = id;
		viewerOpen = true;
	};

	$: RECORD_STATE = {
		published: $i18n.t('Published'),
		draft_only: $i18n.t('Draft only · not a meeting record'),
		draft_after_published: $i18n.t('Published · a newer draft exists')
	} as Record<string, string>;
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-meetings-title">
	<h3 id="jlp-meetings-title" class="jlp-surface-title">{$i18n.t('Meeting history')}</h3>

	{#if loading}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if unavailable}
		<p class="jlp-meta">{unavailable}</p>
	{:else if items.length === 0}
		<p class="jlp-meta">{$i18n.t('No meeting has been frozen for this view yet.')}</p>
	{:else}
		<ul class="jlp-mini-list">
			{#each items as item (item.latest.snapshot_id)}
				<li class="jlp-mini">
					<strong>{item.latest.meeting_label}</strong>
					<span class="jlp-meta jlp-block">
						{item.latest.meeting_date ? formatDateId(item.latest.meeting_date) : '—'} ·
						{RECORD_STATE[meetingRecordState(item)]} ·
						<code title={(item.published ?? item.latest).content_hash}
							>{shortHash((item.published ?? item.latest).content_hash)}</code
						>
					</span>
					<button type="button" class="jlp-link" on:click={() => open(item.latest.snapshot_id)}
						>{$i18n.t('Open')}</button
					>
				</li>
			{/each}
		</ul>
	{/if}

	{#if canPublish && !unavailable}
		<form class="jlp-form" on:submit|preventDefault={freeze}>
			<label class="jlp-field">
				<span>{$i18n.t('Meeting')}</span>
				<input type="text" bind:value={meetingLabel} maxlength="500" />
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('Meeting date')}</span>
				<input type="date" bind:value={meetingDate} />
			</label>
			<button type="submit" class="jlp-button" disabled={busy}
				>{$i18n.t('Freeze this view as a draft')}</button
			>
			<p class="jlp-meta">
				{$i18n.t(
					'A draft is frozen now and published separately; it is never a meeting record by itself.'
				)}
			</p>
		</form>
		<div aria-live="polite">
			{#if draftProblem}
				<p class="jlp-notice jlp-notice-refused mt-2">{draftProblem}</p>
			{/if}
		</div>
	{/if}
</section>

<SnapshotViewer
	bind:show={viewerOpen}
	{view}
	{scopeId}
	snapshotId={viewerId}
	{canPublish}
	on:changed={() => load(`${view}|${scopeId}`)}
/>
