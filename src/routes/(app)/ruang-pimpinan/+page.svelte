<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { defaultView } from '$lib/leadership/context';
	import { leadershipAccess } from '$lib/stores/leadership';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The section root: wait for the reader's views, then open Board if granted, otherwise RKA.
	// With neither, say so here; nothing is fetched and no view is guessed.
	$: target = $leadershipAccess.loading ? undefined : defaultView($leadershipAccess.views);

	$: if (target) {
		goto(`/ruang-pimpinan/${target}${$page.url.search}`, { replaceState: true });
	}
</script>

{#if target === undefined || target}
	<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{:else if !$leadershipAccess.enabled}
	<div class="jlp-notice mt-4">
		<p class="font-medium">{$i18n.t('Ruang Pimpinan is unavailable')}</p>
		<p class="mt-1 text-sm">{$i18n.t('Ruang Pimpinan is not enabled on this server.')}</p>
	</div>
{:else}
	<div class="jlp-notice mt-4">
		<p class="font-medium">{$i18n.t('You do not have access to this view')}</p>
		<p class="mt-1 text-sm">
			{$i18n.t(
				'This account has no Ruang Pimpinan view. Access is granted per view by the company.'
			)}
		</p>
	</div>
{/if}
