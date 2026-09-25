<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import type { SubmissionState } from '$lib/apis/kb-review';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let state: SubmissionState;

	let LABEL: Record<string, string>;
	$: LABEL = {
		pending: $i18n.t('Waiting for review'),
		approved: $i18n.t('Approved'),
		rejected: $i18n.t('Rejected')
	};
</script>

<span class="jlp-status">{LABEL[state] ?? state}</span>
