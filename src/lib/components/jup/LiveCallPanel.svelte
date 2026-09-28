<script lang="ts">
	// The GPT-Live call (#37, ADR-0018): opened for the voice chat in `liveCallChat`. Audio runs on
	// WebRTC; the server answers every delegation with the governed answer and keeps the record.
	// This panel only shows the state and captions, and hangs up.
	import { getContext, onDestroy } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { startLiveSession } from '$lib/apis/voice';
	import type { Caption } from '$lib/voice/live';
	import { startLiveCall, type LiveCall, type LiveState } from '$lib/voice/liveCall';
	import { liveCallChat } from '$lib/voice/session';

	const i18n = getContext('i18n');

	let state: LiveState | null = null;
	let captions: Caption[] = [];
	let call: LiveCall | null = null;
	let player: HTMLAudioElement;
	let openFor: string | null = null;

	const begin = async (chatId: string) => {
		openFor = chatId;
		captions = [];
		try {
			call = await startLiveCall(
				{
					getUserMedia: (constraints) => navigator.mediaDevices.getUserMedia(constraints),
					createPeer: () => new RTCPeerConnection(),
					startSession: (sdp) => startLiveSession(localStorage.token, chatId, sdp),
					playRemote: (stream) => {
						player.srcObject = stream;
						player.play().catch(() => {});
					}
				},
				{
					onState: (next) => {
						state = next;
						if (next === 'ended' || next === 'failed') finish();
					},
					onCaptions: (next) => (captions = next)
				}
			);
		} catch (error) {
			toast.error(
				(error as { message?: string })?.message ?? $i18n.t('The GPT-Live call could not start.')
			);
			finish();
		}
	};

	const finish = () => {
		call = null;
		openFor = null;
		liveCallChat.set(null);
	};

	const hangUp = async () => {
		if (call) await call.hangUp();
		else finish();
	};

	$: if ($liveCallChat && $liveCallChat !== openFor) begin($liveCallChat);

	onDestroy(() => {
		call?.hangUp();
	});

	const label = (s: LiveState | null) =>
		s === 'live'
			? $i18n.t('GPT-Live is listening')
			: s === 'ending'
				? $i18n.t('Ending the call…')
				: $i18n.t('Connecting…');
</script>

<audio bind:this={player} autoplay class="hidden"></audio>

{#if $liveCallChat}
	<div class="jup-live-call" role="dialog" aria-label="GPT-Live">
		<div class="jup-live-call-head">
			<span class="jup-live-call-dot" class:jup-live-call-dot-on={state === 'live'}></span>
			<span>{label(state)}</span>
		</div>

		<div class="jup-live-call-captions" aria-live="polite">
			{#each captions as caption}
				<p class="jup-live-caption jup-live-caption-{caption.who}">
					<span class="jup-live-caption-who"
						>{caption.who === 'caller' ? $i18n.t('You') : 'Asisten JUP'}</span
					>
					{caption.text}
				</p>
			{/each}
		</div>

		<p class="jup-live-call-note">
			{$i18n.t('GPT-Live paraphrases. The written answers are in this chat.')}
		</p>

		<button type="button" class="jup-live-hangup" on:click={hangUp} disabled={state === 'ending'}>
			{$i18n.t('Hang up')}
		</button>
	</div>
{/if}
