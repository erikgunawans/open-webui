<script lang="ts">
	import { page } from '$app/stores';
	import { WEBUI_NAME } from '$lib/stores';
	import RapatGate from '$lib/components/leadership/RapatGate.svelte';
	import RapatIsland from '$lib/components/leadership/RapatIsland.svelte';

	// The boardroom display, inside the Ruang Pimpinan inner layer like the other tabs: the
	// 1920×1080 stage scales to the panel's width. "Layar penuh" (or F) gives it the whole screen
	// for the projector.
</script>

<svelte:head>
	<title>Layar Rapat Direksi / {$WEBUI_NAME}</title>
</svelte:head>

<RapatGate>
	{#key $page.params.id}
		<RapatIsland surface="layar" meetingId={$page.params.id} />
	{/key}
</RapatGate>
