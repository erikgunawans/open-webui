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

	{#if baseline || metric.variance !== null}
		<!-- JUP: the comparison reads as label/value pairs; the variance is a pill whose arrow and
		     sign carry the direction, so colour is never the only signal. -->
		<div class="jlp-compare">
			{#if baseline}
				<span>
					{KIND[baseline.kind] ?? baseline.kind}
					<strong
						>{baseline.value === null
							? $i18n.t('Unavailable')
							: formatValue(baseline.value, baseline.unit)}</strong
					>
				</span>
			{/if}
			{#if metric.variance !== null}
				<span>
					{$i18n.t('Difference from budget')}
					<span class="jlp-variance" class:jlp-negative={varianceNegative}>
						<svg viewBox="0 0 12 12" aria-hidden="true" fill="currentColor"
							>{#if varianceNegative}<path d="M6 10 1.5 4h9z" />{:else}<path
									d="M6 2l4.5 6h-9z"
								/>{/if}</svg
						>
						{formatVariance(metric.variance, primary.unit)}
					</span>
				</span>
			{/if}
		</div>
	{/if}

	{#if metric.comparison_note}
		<p class="jlp-meta jlp-metric-note">{metric.comparison_note}</p>
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
			<button
				type="button"
				class="jlp-link"
				aria-pressed={selected}
				aria-describedby="metric-{metric.id}"
				on:click={() => dispatch('select', metric.id)}>{$i18n.t('Select')}</button
			>
			{#each metric.source_ids as sourceId (sourceId)}
				<button
					type="button"
					class="jlp-link"
					aria-describedby="metric-{metric.id}"
					on:click={() => dispatch('source', sourceId)}
					>{$i18n.t('Source')}<svg
						viewBox="0 0 16 16"
						width="12"
						height="12"
						aria-hidden="true"
						fill="none"
						stroke="currentColor"
						stroke-width="1.6"
						><path d="M4 2.5h5.5L12 5v8.5H4z" /><path d="M6.5 8h3M6.5 10.5h3" /></svg
					></button
				>
			{/each}
		</span>
	</div>
</article>
