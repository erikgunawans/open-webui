<script lang="ts">
	// The GPT-Live disclosure (#34, #37, ADR-0018), acknowledged apart from the governed call's.
	// The text lives beside its version in `$lib/voice/live`.
	import { getContext } from 'svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import { LIVE_DISCLOSURE } from '$lib/voice/live';
	import { liveDisclosureRequest } from '$lib/voice/session';

	const i18n = getContext('i18n');

	let show = false;
	$: show = $liveDisclosureRequest !== null;

	const answer = (accepted: boolean) => {
		const resolve = $liveDisclosureRequest;
		liveDisclosureRequest.set(null);
		resolve?.(accepted);
	};

	$: if (!show && $liveDisclosureRequest) answer(false);
</script>

<Modal bind:show size="md" ariaLabelledby="jup-live-disclosure-title">
	<div class="jup-voice-disclosure">
		<h2 id="jup-live-disclosure-title">{$i18n.t('Before your first GPT-Live call')}</h2>

		<div lang="id">
			{#each LIVE_DISCLOSURE.id as line}
				<p>{line}</p>
			{/each}
		</div>
		<div lang="en" class="jup-voice-disclosure-en">
			{#each LIVE_DISCLOSURE.en as line}
				<p>{line}</p>
			{/each}
		</div>

		<div class="jup-voice-disclosure-actions">
			<button type="button" class="jup-voice-decline" on:click={() => answer(false)}>
				{$i18n.t('Cancel')}
			</button>
			<button type="button" class="jup-voice-accept" on:click={() => answer(true)}>
				{$i18n.t('I understand, start GPT-Live')}
			</button>
		</div>
	</div>
</Modal>
