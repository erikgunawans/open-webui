<script context="module" lang="ts">
	// JUP: whether this page load *entered* the app at a bare `/`. Read from the document's own
	// navigation entry rather than from SvelteKit's `afterNavigate`, which only reports later
	// navigations to a component that mounts after the layout's async load, as this one does.
	// Consumed once per load, so New Chat, a client navigation back to `/`, still opens a chat.
	let entryConsumed = false;

	const enteredAtRoot = (): boolean => {
		if (entryConsumed) return false;
		entryConsumed = true;
		const entry = performance.getEntriesByType('navigation')[0];
		if (!entry) return false;
		const url = new URL(entry.name);
		return url.pathname === '/' && url.search === '';
	};
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Chat from '$lib/components/chat/Chat.svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';

	// JUP: the operating layer lands on the Portfolio, because gate state is the thing this
	// deployment exists to show and chat is one click away.
	const landOnPortfolio = enteredAtRoot() && $user?.role === 'admin';

	onMount(() => {
		if (landOnPortfolio) {
			goto('/portfolio', { replaceState: true });
			return;
		}
		if ($page.url.searchParams.get('error')) {
			toast.error($page.url.searchParams.get('error') || 'An unknown error occurred.');
		}
	});
</script>

{#if !landOnPortfolio}
	<Chat />
{/if}
