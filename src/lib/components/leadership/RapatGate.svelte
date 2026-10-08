<script lang="ts">
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { leadershipAccess } from '$lib/stores/leadership';

	// Rapat Direksi is offered to readers holding the Direksi & Komisaris view. This gate is
	// presentation, like the section's tabs: when meetings are kept on the server (records on), the
	// server checks the grant on every request; otherwise they never leave this browser.
</script>

{#if $leadershipAccess.loading}
	<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{:else if !$leadershipAccess.enabled}
	<div class="jlp-notice mt-4">
		<p class="font-medium">Ruang Pimpinan tidak tersedia</p>
		<p class="mt-1 text-sm">Ruang Pimpinan belum diaktifkan di server ini.</p>
	</div>
{:else if !$leadershipAccess.views.includes('board')}
	<div class="jlp-notice mt-4">
		<p class="font-medium">Anda tidak memiliki akses ke tampilan ini</p>
		<p class="mt-1 text-sm">Rapat Direksi tersedia untuk pemegang akses Direksi &amp; Komisaris.</p>
	</div>
{:else}
	<slot />
{/if}
