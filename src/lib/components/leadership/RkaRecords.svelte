<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getBaselines, LeadershipRequestError, type RkaRecord } from '$lib/apis/leadership';
	import { formatDateId, formatEventTimeId, rkaEntry, shortHash } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let scopeId: string;

	let records: RkaRecord[] = [];
	let loading = true;
	let unavailable: string | null = null;
	let controller: AbortController | null = null;

	const load = async (scope: string) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		unavailable = null;
		try {
			const result = await getBaselines(localStorage.token, scope, own.signal);
			if (!own.signal.aborted) records = result.records;
		} catch (caught) {
			if (own.signal.aborted) return;
			records = [];
			unavailable =
				caught instanceof LeadershipRequestError && caught.isUnavailable
					? $i18n.t('RKA records are not available on this server yet.')
					: caught instanceof LeadershipRequestError && caught.isAccessDenied
						? $i18n.t('You do not have access to this view')
						: `${caught}`;
		} finally {
			if (!own.signal.aborted) loading = false;
		}
	};

	$: load(scopeId);
	onDestroy(() => controller?.abort());

	// Newest first; each record is immutable, and a later figure is a new record that supersedes.
	$: newest = [...records].reverse();
	$: labels = new Map(records.map((record) => [record.id, record.label]));

	// Only scalar content is shown here; a record's structure is the importer's, not this view's.
	const scalars = (content: Record<string, unknown>): [string, string][] =>
		Object.entries(content)
			.filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
			.map(([key, value]) => [key, String(value)]);

	$: KIND = {
		baseline: $i18n.t('Approved RKA baseline'),
		revision: $i18n.t('Approved RKA revision'),
		forecast: $i18n.t('Forecast · never approved RKA')
	} as Record<string, string>;
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-rka-records-title">
	<h3 id="jlp-rka-records-title" class="jlp-surface-title">{$i18n.t('RKA records')}</h3>
	<p class="jlp-meta">
		{$i18n.t('An approved baseline never changes; a revision or a forecast is a new record.')}
	</p>

	{#if loading}
		<div class="flex justify-center py-4"><Spinner className="size-5" /></div>
	{:else if unavailable}
		<p class="jlp-meta"><ServerText text={unavailable} /></p>
	{:else if newest.length === 0}
		<p class="jlp-meta">{$i18n.t('No RKA record has been entered yet.')}</p>
	{:else}
		<ul class="jlp-mini-list">
			{#each newest as record (record.id)}
				<li class="jlp-mini">
					<strong>{record.label}</strong>
					<span class="jlp-block">{KIND[record.record_kind] ?? record.record_kind}</span>
					<span class="jlp-meta jlp-block">
						{formatDateId(record.period_start)} – {formatDateId(record.period_end)}
						{#if record.approved_at}
							· {$i18n.t('approved {{at}}', { at: formatEventTimeId(record.approved_at) })}
						{/if}
						· <code title={record.content_hash}>{shortHash(record.content_hash)}</code>
					</span>
					{#if record.supersedes_id}
						<span class="jlp-meta jlp-block">
							{$i18n.t('Supersedes: {{label}}', {
								label: labels.get(record.supersedes_id) ?? record.supersedes_id
							})}
						</span>
					{/if}
					{#if scalars(record.content).length}
						<dl class="jlp-dl mt-2">
							{#each scalars(record.content) as [key, value] (key)}
								{@const entry = rkaEntry(key, value)}
								<dt title={key}>{entry.label}</dt>
								<dd>{entry.value}</dd>
							{/each}
						</dl>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>
