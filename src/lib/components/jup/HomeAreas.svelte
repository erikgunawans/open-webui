<script lang="ts">
	// The JUP areas below the composer on the chat home: one card per section the user can open,
	// gated exactly as the sidebar gates its entries (a card is presentation; each page's server
	// still refuses a reader without the grant). No card is shown when none applies.
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { user } from '$lib/stores';
	import { leadershipAccess, refreshLeadershipAccess } from '$lib/stores/leadership';
	import { kbReviewAccess, refreshKbReviewAccess } from '$lib/stores/kbReview';

	const i18n = getContext<Writable<i18nType>>('i18n');

	onMount(() => {
		refreshLeadershipAccess();
		refreshKbReviewAccess();
	});

	$: areas =
		$i18n &&
		[
			{
				id: 'leadership',
				href: '/ruang-pimpinan',
				title: 'Ruang Pimpinan',
				action: $i18n.t('Open'),
				show: $leadershipAccess.enabled && $leadershipAccess.views.length > 0
			},
			{
				id: 'review',
				href: '/kb-review',
				title: $i18n.t('Knowledge review'),
				action: $i18n.t('Open'),
				show: $kbReviewAccess.submit || $kbReviewAccess.contracts || $user?.role === 'admin'
			},
			{
				id: 'portfolio',
				href: '/portfolio',
				title: $i18n.t('Portfolio'),
				action: $i18n.t('Open'),
				show: $user?.role === 'admin'
			}
		].filter((area) => area.show);
</script>

{#if areas.length > 0}
	<nav class="jup-areas" aria-label={$i18n.t('JUP areas')} data-count={areas.length}>
		{#each areas as area (area.id)}
			<a class="jup-area" href={area.href}>
				<span class="jup-area-head">
					<span class="jup-area-mark jup-area-mark-{area.id}" aria-hidden="true">
						<span></span><span></span>
					</span>
					<span class="jup-area-title">{area.title}</span>
				</span>
				<span class="jup-area-foot">
					{area.action}
					<svg
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg
					>
				</span>
			</a>
		{/each}
	</nav>
{/if}
