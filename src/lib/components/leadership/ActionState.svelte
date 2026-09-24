<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let state: string;
	// `records` is the records store's register: its states are the lifecycle's, not the deck's.
	export let source: 'sample' | 'records';

	// The deck reports a state; it is not a live status check. Closure is BOD's decision.
	$: SAMPLE_STATE = {
		in_progress: $i18n.t('Ongoing according to the source'),
		completion_submitted: $i18n.t('Completion submitted, awaiting BOD review'),
		closed: $i18n.t('Closed by BOD'),
		returned: $i18n.t('Returned by BOD for follow-up'),
		cancelled: $i18n.t('Cancelled')
	} as Record<string, string>;

	// The records store's lifecycle. Only a BOD decision reaches `closed`.
	$: RECORD_STATE = {
		not_started: $i18n.t('Not started'),
		in_progress: $i18n.t('In progress'),
		blocked: $i18n.t('Blocked'),
		awaiting_bod_closure: $i18n.t('Awaiting BOD closure'),
		closed: $i18n.t('Closed by BOD')
	} as Record<string, string>;

	$: STATE = source === 'records' ? RECORD_STATE : SAMPLE_STATE;
</script>

<span class="jlp-status">{STATE[state] ?? state}</span>
