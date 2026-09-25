<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { page } from '$app/stores';
	import { WEBUI_NAME } from '$lib/stores';
	import { leadershipAccess, refreshLeadershipAccess } from '$lib/stores/leadership';
	import '$lib/components/leadership/leadership.css';
	import MobileSidebarToggle from '$lib/components/jup/MobileSidebarToggle.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The section frame: title, the two local views, and a scroll region. The app shell's inset
	// panel owns the size; this fills it and never measures itself against the viewport.
	const TABS = [
		{ view: 'board', href: '/ruang-pimpinan/board', label: 'Direksi & Komisaris' },
		{ view: 'rka', href: '/ruang-pimpinan/rka', label: 'RKA & Realisasi' }
	] as const;

	// A tab is offered only for a view the reader holds. That is presentation: a direct URL still
	// reaches the page, and the server refuses it there.
	$: tabs = TABS.filter((tab) => $leadershipAccess.views.includes(tab.view));

	$: active = (href: string) =>
		$page.url.pathname === href || $page.url.pathname.startsWith(`${href}/`);

	onMount(refreshLeadershipAccess);
</script>

<svelte:head>
	<title>Ruang Pimpinan / {$WEBUI_NAME}</title>
</svelte:head>

<div class="jlp-root jlp-section">
	<div class="jlp-scroll">
		<div class="jlp-container">
			<MobileSidebarToggle />
			<header class="jlp-header">
				<div>
					<h1 class="jlp-title">Ruang Pimpinan</h1>
					<p class="jlp-subtitle">
						{$i18n.t('Performance, direction and follow-up in one room.')}
					</p>
				</div>
			</header>

			{#if tabs.length > 0}
				<nav class="jlp-tabs jup-seg" aria-label={$i18n.t('Ruang Pimpinan views')}>
					{#each tabs as tab (tab.view)}
						<a class="jlp-tab" href={tab.href} aria-current={active(tab.href) ? 'page' : undefined}
							>{tab.label}</a
						>
					{/each}
				</nav>
			{/if}

			<slot />
		</div>
	</div>
</div>
