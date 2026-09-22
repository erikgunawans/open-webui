<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Chat from '$lib/components/chat/Chat.svelte';
	import { page } from '$app/stores';
	import { afterNavigate, goto } from '$app/navigation';
	import { user } from '$lib/stores';

	onMount(() => {
		if ($page.url.searchParams.get('error')) {
			toast.error($page.url.searchParams.get('error') || 'An unknown error occurred.');
		}
	});

	// JUP: the operating layer lands on the Portfolio, because gate state is the thing this
	// deployment exists to show and chat is one click away. Only the navigation that *enters*
	// the app redirects — New Chat is a client navigation to `/` and must still open a chat —
	// and any query string (a shared prompt, a model, an error) is left alone.
	afterNavigate((navigation) => {
		if (
			navigation.type === 'enter' &&
			$user?.role === 'admin' &&
			$page.url.pathname === '/' &&
			$page.url.search === ''
		) {
			goto('/portfolio', { replaceState: true });
		}
	});
</script>

<Chat />
