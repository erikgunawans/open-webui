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
	<!-- The usual cause is a deploy: this tab still names the previous build's files. A reload fixes
	     it, and the meeting itself is in the browser, so nothing typed is lost. -->
	<div class="jlp-notice jlp-notice-refused mt-4" role="alert">
		<p class="font-medium">Halaman Rapat Direksi tidak dapat dimuat</p>
		<p class="mt-1 text-sm">
			Biasanya karena aplikasi baru saja diperbarui. Muat ulang halaman; isian rapat tetap tersimpan
			di peramban ini.
		</p>
		<button type="button" class="jlp-button mt-3" on:click={() => location.reload()}>
			Muat ulang
		</button>
		<details class="mt-3 text-xs">
			<summary>Detail teknis</summary>
			<p class="mt-1 break-all">{failed}</p>
		</details>
	</div>
{/if}
<div bind:this={target}></div>
