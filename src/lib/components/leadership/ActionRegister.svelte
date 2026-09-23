<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import type { Action } from '$lib/apis/leadership';
	import { formatDateId } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ source: string; select: string }>();

	export let actions: Action[];
	export let selectedId: string | null = null;
	// P1 serves a partial example, never a register. The caption says so every time it renders.
	export let partial = true;

	// The deck reports a state; it is not a live status check. Closure is BOD's decision (P2).
	$: STATE = {
		in_progress: $i18n.t('Ongoing according to the source'),
		completion_submitted: $i18n.t('Completion submitted, awaiting BOD review'),
		closed: $i18n.t('Closed by BOD'),
		returned: $i18n.t('Returned by BOD for follow-up'),
		cancelled: $i18n.t('Cancelled')
	} as Record<string, string>;

	// Month, year and year-range targets carry no day, so no overdue count can be computed.
	$: PRECISION = {
		month: $i18n.t('Target month'),
		year: $i18n.t('Target year'),
		year_range: $i18n.t('Target range'),
		date: $i18n.t('Target date')
	} as Record<string, string>;
</script>

<p class="jlp-meta jlp-caption">
	{#if partial}
		{$i18n.t('{{count}} examples from the presentation · not a complete register', {
			count: actions.length
		})}
	{:else}
		{$i18n.t('{{count}} actions', { count: actions.length })}
	{/if}
</p>

<!-- A region that scrolls sideways must be reachable by keyboard (WCAG 2.1.1). -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="jlp-table-scroll" role="region" aria-label={$i18n.t('Action register')} tabindex="0">
	<table class="jlp-table">
		<thead>
			<tr>
				<th scope="col">{$i18n.t('Action / PIC')}</th>
				<th scope="col">{$i18n.t('Progress reported')}</th>
				<th scope="col">{$i18n.t('Target')}</th>
				<th scope="col">{$i18n.t('Status')}</th>
			</tr>
		</thead>
		<tbody>
			{#each actions as action (action.id)}
				<tr class:jlp-row-selected={selectedId === action.id}>
					<td>
						<strong class="jlp-cell-title">{action.title}</strong>
						<span class="jlp-meta jlp-block">{action.owner_label}</span>
					</td>
					<td>
						{action.progress_summary}
						<span class="jlp-meta jlp-block">
							{$i18n.t('As of {{date}}', {
								date: formatDateId(action.source_as_of)
							})}{#if !action.history_complete}&nbsp;·&nbsp;{$i18n.t('History incomplete')}{/if}
						</span>
					</td>
					<td>
						{action.due.label}
						<span class="jlp-meta jlp-block">{PRECISION[action.due.precision]}</span>
					</td>
					<td>
						<span class="jlp-status">{STATE[action.state] ?? action.state}</span>
						<span class="jlp-meta jlp-block">
							{action.closure ? $i18n.t('Closure recorded') : $i18n.t('Not closed by BOD')}
						</span>
						<span class="jlp-row-buttons">
							<button type="button" class="jlp-link" on:click={() => dispatch('select', action.id)}
								>{$i18n.t('Select')}</button
							>
							{#each action.source_ids as sourceId (sourceId)}
								<button type="button" class="jlp-link" on:click={() => dispatch('source', sourceId)}
									>{$i18n.t('Source')}</button
								>
							{/each}
						</span>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
