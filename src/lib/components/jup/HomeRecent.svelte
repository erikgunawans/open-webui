<script lang="ts">
	// The latest conversations on the chat home, from the sidebar's own chat list (no new request).
	// "See more" opens the sidebar, where the whole history and its search already live.
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { showSidebar } from '$lib/stores';
	import { chats } from '$lib/stores/chatList';
	import { relativeTime } from './homeTime';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let limit = 3;

	$: recent = ($chats ?? []).slice(0, limit) as {
		id: string;
		title?: string;
		updated_at?: number;
	}[];
</script>

{#if recent.length > 0}
	<section class="jup-recent" aria-labelledby="jup-recent-title">
		<h2 id="jup-recent-title" class="jup-recent-title">
			<svg
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg
			>
			{$i18n.t('Recent conversations')}
		</h2>
		<ul class="jup-recent-list">
			{#each recent as chat (chat.id)}
				<li>
					<a class="jup-recent-item" href="/c/{chat.id}">
						<span class="jup-recent-name">{chat.title || $i18n.t('New Chat')}</span>
						{#if chat.updated_at}
							<span class="jup-recent-when">{relativeTime(chat.updated_at, $i18n.language)}</span>
						{/if}
					</a>
				</li>
			{/each}
		</ul>
		<button type="button" class="jup-recent-more" on:click={() => showSidebar.set(true)}>
			{$i18n.t('See more')}
		</button>
	</section>
{/if}
