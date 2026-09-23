<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import type { Metric } from '$lib/apis/leadership';
	import { formatValue, formatVariance } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ source: string; select: string }>();

	export let metric: Metric;
	export let selected = false;

	$: KIND = {
		actual: $i18n.t('Actual'),
		budget: $i18n.t('Budget'),
		forecast: $i18n.t('Forecast'),
		scenario: $i18n.t('Scenario')
	} as Record<string, string>;

	$: primary = metric.primary;
	$: baseline = metric.baseline;
	$: negative = primary.value !== null && primary.value.startsWith('-');
	$: varianceNegative = metric.variance !== null && metric.variance.startsWith('-');
</script>

<article
	class="jlp-metric"
	class:jlp-metric-selected={selected}
	aria-labelledby="metric-{metric.id}"
>
	<div class="jlp-metric-head">
		<h3 id="metric-{metric.id}" class="jlp-metric-label">{metric.label}</h3>
		<span class="jlp-kind">{KIND[primary.kind] ?? primary.kind}</span>
	</div>

	{#if primary.value === null}
		<!-- Missing is not zero. The reason is the content. -->
		<p class="jlp-metric-missing">{$i18n.t('Unavailable')}</p>
		<p class="jlp-meta">{primary.missing_reason}</p>
	{:else}
		<p class="jlp-metric-value" class:jlp-negative={negative}>
			{formatValue(primary.value, primary.unit)}
		</p>
	{/if}

	{#if baseline}
		<p class="jlp-meta">
			{KIND[baseline.kind] ?? baseline.kind}:
			{baseline.value === null
				? $i18n.t('Unavailable')
				: formatValue(baseline.value, baseline.unit)}
		</p>
	{/if}

	{#if metric.variance !== null}
		<p class="jlp-variance" class:jlp-negative={varianceNegative}>
			{$i18n.t('Difference from budget')}: {formatVariance(metric.variance, primary.unit)}
		</p>
	{/if}

	{#if metric.comparison_note}
		<p class="jlp-meta">{metric.comparison_note}</p>
	{/if}

	<div class="jlp-metric-foot">
		<span class="jlp-status">
			{metric.verification_status === 'verified'
				? $i18n.t('Verified')
				: $i18n.t(
						'Unverified'
					)}{#if primary.definition_status === 'candidate'}&nbsp;·&nbsp;{$i18n.t(
					'Candidate definition'
				)}{/if}
		</span>
		<span class="jlp-metric-buttons">
			<button type="button" class="jlp-link" on:click={() => dispatch('select', metric.id)}
				>{$i18n.t('Select')}</button
			>
			{#each metric.source_ids as sourceId (sourceId)}
				<button type="button" class="jlp-link" on:click={() => dispatch('source', sourceId)}
					>{$i18n.t('Source')}</button
				>
			{/each}
		</span>
	</div>
</article>
