<script lang="ts">
	import { onMount } from 'svelte';

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { user, WEBUI_NAME } from '$lib/stores';
	import { refreshLeadershipAccess } from '$lib/stores/leadership';
	import RapatGate from '$lib/components/leadership/RapatGate.svelte';
	import RapatIsland from '$lib/components/leadership/RapatIsland.svelte';
	import '$lib/components/leadership/leadership.css';

	// The boardroom display: full window, outside the app shell (the `@` resets to the root
	// layout), so the 1920×1080 stage gets the whole screen. Signed-out readers go to sign-in.
	onMount(() => {
		if (!localStorage.token) {
			goto(`/auth?redirect=${encodeURIComponent($page.url.pathname)}`);
			return;
		}
		refreshLeadershipAccess();
	});
</script>

<svelte:head>
	<title>Layar Rapat Direksi / {$WEBUI_NAME}</title>
</svelte:head>

{#if $user}
	<div class="jlp-root">
		<RapatGate>
			{#key $page.params.id}
				<RapatIsland surface="layar" meetingId={$page.params.id} />
			{/key}
		</RapatGate>
	</div>
{/if}
