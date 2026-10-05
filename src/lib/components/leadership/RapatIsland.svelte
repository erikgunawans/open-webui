<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';
	import Spinner from '$lib/components/common/Spinner.svelte';

	// Hosts one Rapat Direksi screen, which is a React island built from @jup/ui. React and the
	// screens load only here (dynamic import), and the island is torn down with this component.
	export let surface: 'list' | 'notulen' | 'layar';
	export let meetingId = '';

	let target: HTMLDivElement;
	let island: { destroy: () => void } | null = null;
	let failed = '';
	let loading = true;

	onMount(async () => {
		try {
			const { mountRapat } = await import('$lib/notulen/react/entry');
			island = mountRapat(target, {
				surface,
				meetingId,
				userId: $user?.id ?? 'anonim',
				navigate: (href) => goto(href)
			});
		} catch (error) {
			failed = `${error}`;
		} finally {
			loading = false;
		}
	});

	onDestroy(() => island?.destroy());
</script>

{#if loading}
	<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{/if}
{#if failed}
	<div class="jlp-notice jlp-notice-refused mt-4">
		<p class="font-medium">Layar rapat tidak dapat dimuat</p>
		<p class="mt-1 text-sm">{failed}</p>
	</div>
{/if}
<div bind:this={target} class:rapat-island-full={surface === 'layar'}></div>
