<script lang="ts">
	// The chip row above the composer on the chat home. Each chip starts a question about one JUP
	// area by writing its opening words into the composer, never sending them, so the user finishes
	// the question. Ruang Pimpinan is offered only to a reader who holds one of its views; what the
	// assistant may answer is still decided by each tool against the user's grants.
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { leadershipAccess } from '$lib/stores/leadership';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let onInsert: (text: string) => void;
	export let onMore: () => void;
	export let moreOpen = false;

	$: showLeadership = $leadershipAccess.enabled && $leadershipAccess.views.length > 0;

	// Literal t() calls, so the extractor sees every key.
	$: chips = $i18n && [
		{
			id: 'kb',
			label: $i18n.t('JUP knowledge'),
			text: $i18n.t('What does the JUP knowledge base say about '),
			show: true
		},
		{
			id: 'contracts',
			label: $i18n.t('Contracts'),
			text: $i18n.t('Find the contract card for '),
			show: true
		},
		{
			id: 'leadership',
			label: 'Ruang Pimpinan',
			text: $i18n.t('From Ruang Pimpinan, summarise '),
			show: showLeadership
		}
	];
</script>

<div class="jup-shortcuts" role="group" aria-label={$i18n.t('Start a question')}>
	{#each chips.filter((c) => c.show) as chip (chip.id)}
		<button type="button" class="jup-chip" on:click={() => onInsert(chip.text)}>
			{#if chip.id === 'kb'}
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H19v14H5.5A1.5 1.5 0 0 0 4 19.5v-14Z" /><path
						d="M4 19.5A1.5 1.5 0 0 0 5.5 21H19v-3"
					/><path d="M8 8h7M8 11.5h5" /></svg
				>
			{:else if chip.id === 'contracts'}
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><path d="M7 3h7l4 4v14H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M14 3v4h4" /><path
						d="M9.5 12h5M9.5 15.5h5"
					/></svg
				>
			{:else}
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg
				>
			{/if}
			{chip.label}
		</button>
	{/each}
	<button
		type="button"
		class="jup-chip"
		aria-expanded={moreOpen}
		aria-controls="jup-home-more"
		on:click={onMore}
	>
		<svg viewBox="0 0 24 24" aria-hidden="true"
			><rect x="4" y="4" width="6" height="6" rx="1.5" /><rect
				x="14"
				y="4"
				width="6"
				height="6"
				rx="1.5"
			/><rect x="4" y="14" width="6" height="6" rx="1.5" /><path d="M17 14v6M14 17h6" /></svg
		>
		{$i18n.t('More')}
	</button>
</div>
