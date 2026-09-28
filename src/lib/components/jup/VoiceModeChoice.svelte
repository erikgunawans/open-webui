<script lang="ts">
	// The call-mode choice (#37, ADR-0018): only for callers with the GPT-Live grant. The governed
	// call comes first and is the default; GPT-Live says plainly that it paraphrases.
	import { getContext } from 'svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import type { CallMode } from '$lib/voice/live';
	import { modeRequest } from '$lib/voice/session';

	const i18n = getContext('i18n');

	let show = false;
	$: show = $modeRequest !== null;

	const answer = (mode: CallMode | null) => {
		const resolve = $modeRequest;
		modeRequest.set(null);
		resolve?.(mode);
	};

	// Closed any other way (Escape, the backdrop) counts as backing out.
	$: if (!show && $modeRequest) answer(null);
</script>

<Modal bind:show size="md" ariaLabelledby="jup-voice-mode-title">
	<div class="jup-voice-disclosure">
		<h2 id="jup-voice-mode-title">{$i18n.t('Choose how to call')}</h2>

		<div class="jup-voice-modes">
			<button type="button" class="jup-voice-mode" on:click={() => answer('governed')}>
				<span class="jup-voice-mode-name">{$i18n.t('Voice call')}</span>
				<span class="jup-voice-mode-note"
					>{$i18n.t('Answers are read word for word from the documents.')}</span
				>
			</button>
			<button type="button" class="jup-voice-mode" on:click={() => answer('live')}>
				<span class="jup-voice-mode-name">GPT-Live</span>
				<span class="jup-voice-mode-note"
					>{$i18n.t('A more natural conversation. The assistant paraphrases the answers.')}</span
				>
			</button>
		</div>

		<div class="jup-voice-disclosure-actions">
			<button type="button" class="jup-voice-decline" on:click={() => answer(null)}>
				{$i18n.t('Cancel')}
			</button>
		</div>
	</div>
</Modal>
