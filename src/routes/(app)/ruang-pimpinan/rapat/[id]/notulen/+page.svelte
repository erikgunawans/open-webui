<script lang="ts">
	import { page } from '$app/stores';
	import RapatGate from '$lib/components/leadership/RapatGate.svelte';
	import RapatIsland from '$lib/components/leadership/RapatIsland.svelte';
</script>

<RapatGate>
	{#key $page.params.id}
		<RapatIsland surface="notulen" meetingId={$page.params.id} />
	{/key}
</RapatGate>
