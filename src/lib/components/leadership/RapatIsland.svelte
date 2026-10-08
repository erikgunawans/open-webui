<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import { goto } from '$app/navigation';
	import { LEADERSHIP_SCOPE } from '$lib/apis/leadership';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { user } from '$lib/stores';
	import { leadershipAccess } from '$lib/stores/leadership';
	import Spinner from '$lib/components/common/Spinner.svelte';

	// Hosts one Rapat Direksi screen, which is a React island built from @jup/ui. React and the
	// screens load only here (dynamic import), and the island is torn down with this component.
	// When the server keeps Ruang Pimpinan records, meetings are stored there (RapatGate has
	// already waited for the reader's capabilities); otherwise in this browser.
	export let surface: 'list' | 'notulen' | 'layar';
	export let meetingId = '';

	let target: HTMLDivElement;
	let island: { destroy: () => void } | null = null;
	let failed = '';
	let loading = true;
	let destroyed = false;
	const server = $leadershipAccess.records;

	onMount(async () => {
		try {
			const { mountRapat } = await import('$lib/notulen/react/entry');
			const mounted = await mountRapat(target, {
				surface,
				meetingId,
				userId: $user?.id ?? 'anonim',
				navigate: (href) => goto(href),
				server: server
					? { apiBase: WEBUI_API_BASE_URL, token: localStorage.token, scopeId: LEADERSHIP_SCOPE }
					: undefined
			});
			// Left before the meetings arrived: nothing to show any more.
			if (destroyed) mounted.destroy();
			else island = mounted;
		} catch (error) {
			failed = `${error}`;
		} finally {
			loading = false;
		}
	});

	onDestroy(() => {
		destroyed = true;
		island?.destroy();
	});
</script>

{#if loading}
	<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{/if}
{#if failed}
	<!-- The usual cause is a deploy: this tab still names the previous build's files, or (records on)
	     the server could not be reached. A reload fixes it, and the meeting itself is stored, in the
	     browser or on the server, so nothing typed is lost. -->
	<div class="jlp-notice jlp-notice-refused mt-4" role="alert">
		<p class="font-medium">Halaman Rapat Direksi tidak dapat dimuat</p>
		<p class="mt-1 text-sm">
			{server
				? 'Biasanya karena aplikasi baru saja diperbarui atau server sedang tidak terjangkau. Muat ulang halaman; isian rapat tetap tersimpan di server.'
				: 'Biasanya karena aplikasi baru saja diperbarui. Muat ulang halaman; isian rapat tetap tersimpan di peramban ini.'}
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
