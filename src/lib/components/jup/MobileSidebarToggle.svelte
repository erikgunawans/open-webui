<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { mobile, showSidebar } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// The fork's own pages have no vendor navbar, and on a phone the sidebar is a closed drawer, so
	// without this a reader has no way back to chat or to another section. Same control and labels
	// as the vendor's workspace and admin headers.
</script>

{#if $mobile}
	<div class="mb-3 flex">
		<Tooltip
			content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
			interactive={true}
		>
			<button
				type="button"
				class="flex cursor-pointer rounded-lg transition hover:bg-gray-100 dark:hover:bg-gray-850"
				aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
				aria-expanded={$showSidebar}
				on:click={() => showSidebar.set(!$showSidebar)}
			>
				<div class="self-center p-1.5">
					<Sidebar className="size-4" />
				</div>
			</button>
		</Tooltip>
	</div>
{/if}
