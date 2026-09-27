<script lang="ts">
	// The voice disclosure (#29, ADR-0017). Shown before the first call and again whenever its
	// version changes; the text itself lives beside that version in `$lib/voice/call`.
	import { getContext } from 'svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import { DISCLOSURE } from '$lib/voice/call';
	import { disclosureRequest } from '$lib/voice/session';

	const i18n = getContext('i18n');

	let show = false;
	$: show = $disclosureRequest !== null;

	const answer = (accepted: boolean) => {
		const resolve = $disclosureRequest;
		disclosureRequest.set(null);
		resolve?.(accepted);
	};

	// Closed any other way (Escape, the backdrop) counts as declined.
	$: if (!show && $disclosureRequest) answer(false);
</script>

<Modal bind:show size="md" ariaLabelledby="jup-voice-disclosure-title">
	<div class="jup-voice-disclosure">
		<h2 id="jup-voice-disclosure-title">{$i18n.t('Before your first voice call')}</h2>

		<div lang="id">
			{#each DISCLOSURE.id as line}
				<p>{line}</p>
			{/each}
		</div>
		<div lang="en" class="jup-voice-disclosure-en">
			{#each DISCLOSURE.en as line}
				<p>{line}</p>
			{/each}
		</div>

		<div class="jup-voice-disclosure-actions">
			<button type="button" class="jup-voice-decline" on:click={() => answer(false)}>
				{$i18n.t('Cancel')}
			</button>
			<button type="button" class="jup-voice-accept" on:click={() => answer(true)}>
				{$i18n.t('I understand, start the call')}
			</button>
		</div>
	</div>
</Modal>
