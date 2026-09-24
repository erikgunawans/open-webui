<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getMeetingChanges,
		LeadershipRequestError,
		type LeadershipView,
		type MeetingChanges,
		type MetricChange,
		type Reading
	} from '$lib/apis/leadership';
	import { formatDateId, formatValue, formatVariance, shortHash } from '$lib/leadership/format';

	import ActionState from './ActionState.svelte';
	import ServerText from './ServerText.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let view: LeadershipView;
	export let scopeId: string;
	// Whether two meeting records were compared, for the page's module list.
	export let available = false;

	let changes: MeetingChanges | null = null;
	let loading = true;
	let unavailable: string | null = null;
	let controller: AbortController | null = null;

	const load = async (key: string) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		unavailable = null;
		try {
			const result = await getMeetingChanges(localStorage.token, view, scopeId, own.signal);
			if (!own.signal.aborted) changes = result;
		} catch (caught) {
			if (own.signal.aborted) return;
			changes = null;
			unavailable =
				caught instanceof LeadershipRequestError && caught.isUnavailable
					? $i18n.t('Meeting records are not available on this server yet.')
					: caught instanceof LeadershipRequestError && caught.isAccessDenied
						? $i18n.t('You do not have access to this view')
						: caught instanceof Error
							? caught.message
							: `${caught}`;
		} finally {
			if (!own.signal.aborted) loading = false;
		}
		return key;
	};

	$: load(`${view}|${scopeId}`);
	onDestroy(() => controller?.abort());

	$: available = changes?.available === true;
	$: movedMetrics = changes?.available
		? changes.metrics.filter((metric) => metric.change !== 'unchanged')
		: [];
	$: unchangedCount = changes?.available
		? changes.metrics.filter((metric) => metric.change === 'unchanged').length
		: 0;
	$: actionCount = changes?.available
		? changes.actions.added.length + changes.actions.removed.length + changes.actions.changed.length
		: 0;

	const shown = (reading: Reading | null): string =>
		reading === null
			? '—'
			: reading.value === null
				? $i18n.t('Unavailable')
				: formatValue(reading.value, reading.unit);

	const period = (reading: Reading): string =>
		`${formatDateId(reading.period_start)} – ${formatDateId(reading.period_end)}`;

	const periodMoved = (metric: MetricChange): boolean =>
		metric.before !== null &&
		metric.after !== null &&
		(metric.before.period_start !== metric.after.period_start ||
			metric.before.period_end !== metric.after.period_end);

	$: NOTE = {
		missing: $i18n.t('No difference: a reading is unavailable.'),
		unit: $i18n.t('No difference: the units differ.'),
		kind: $i18n.t('No difference: one is an actual and the other is not.'),
		scope: $i18n.t('No difference: the scopes differ.')
	} as Record<string, string>;

	$: CHANGE = {
		added: $i18n.t('New since the last meeting'),
		removed: $i18n.t('No longer reported')
	} as Record<string, string>;
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-changes-title">
	<h3 class="jlp-surface-title" id="jlp-changes-title">
		{$i18n.t('Changes since the last meeting')}
	</h3>

	{#if loading}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if unavailable}
		<p class="jlp-meta"><ServerText text={unavailable} /></p>
	{:else if changes && !changes.available}
		<p class="jlp-meta">
			{$i18n.t(
				'Needs two published meeting records of this view; {{count}} published so far. A draft is never compared.',
				{ count: changes.published_meetings }
			)}
		</p>
	{:else if changes && changes.available}
		<p class="jlp-meta">
			{$i18n.t('{{before}} against {{after}}, both as published.', {
				before: changes.before.meeting_label,
				after: changes.after.meeting_label
			})}
			<code title={changes.before.content_hash}>{shortHash(changes.before.content_hash)}</code>
			→ <code title={changes.after.content_hash}>{shortHash(changes.after.content_hash)}</code>
		</p>

		<h4 class="jlp-group-title mt-3">{$i18n.t('Metrics')}</h4>
		{#if movedMetrics.length === 0}
			<p class="jlp-meta">{$i18n.t('No metric moved between the two meetings.')}</p>
		{:else}
			<ul class="jlp-mini-list">
				{#each movedMetrics as metric (metric.id)}
					<li class="jlp-mini">
						<strong>{metric.label}</strong>
						{#if metric.change === 'added' || metric.change === 'removed'}
							<span class="jlp-meta jlp-block">{CHANGE[metric.change]}</span>
							<span class="jlp-block">{shown(metric.after ?? metric.before)}</span>
						{:else}
							<span class="jlp-block">
								{shown(metric.before)} → {shown(metric.after)}
								{#if metric.difference !== null && metric.after}
									· {formatVariance(metric.difference, metric.after.unit)}
								{/if}
							</span>
							{#if metric.difference_note}
								<span class="jlp-meta jlp-block">{NOTE[metric.difference_note]}</span>
							{/if}
							{#if periodMoved(metric) && metric.before && metric.after}
								<span class="jlp-meta jlp-block">
									{$i18n.t('Period {{before}} → {{after}}', {
										before: period(metric.before),
										after: period(metric.after)
									})}
								</span>
							{/if}
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
		{#if unchangedCount}
			<p class="jlp-meta mt-1">
				{$i18n.t('{{count}} metrics unchanged.', { count: unchangedCount })}
			</p>
		{/if}

		<h4 class="jlp-group-title mt-3">{$i18n.t('Follow-up actions')}</h4>
		{#if !changes.actions_comparable}
			<p class="jlp-meta">
				{$i18n.t(
					'The two meetings froze actions from different sources, so their states are not compared.'
				)}
			</p>
		{:else if actionCount === 0}
			<p class="jlp-meta">{$i18n.t('No action changed between the two meetings.')}</p>
		{:else}
			<ul class="jlp-mini-list">
				{#each changes.actions.changed as action (action.id)}
					<li class="jlp-mini">
						<strong>{action.title}</strong>
						{#if action.state_before !== action.state_after}
							<span class="jlp-block">
								<ActionState state={action.state_before} source={changes.actions_source} />
								→
								<ActionState state={action.state_after} source={changes.actions_source} />
							</span>
						{/if}
						{#if action.due_before !== action.due_after}
							<span class="jlp-meta jlp-block">
								{$i18n.t('Target {{before}} → {{after}}', {
									before: action.due_before ?? $i18n.t('No target recorded'),
									after: action.due_after ?? $i18n.t('No target recorded')
								})}
							</span>
						{/if}
					</li>
				{/each}
				{#each changes.actions.added as action (action.id)}
					<li class="jlp-mini">
						<strong>{action.title}</strong>
						<span class="jlp-meta jlp-block">{$i18n.t('New since the last meeting')}</span>
						<ActionState state={action.state} source={changes.actions_source} />
					</li>
				{/each}
				{#each changes.actions.removed as action (action.id)}
					<li class="jlp-mini">
						<strong>{action.title}</strong>
						<span class="jlp-meta jlp-block">{$i18n.t('No longer in the register')}</span>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</section>
