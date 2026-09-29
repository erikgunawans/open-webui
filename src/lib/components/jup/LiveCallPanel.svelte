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
	import Headphone from '$lib/components/icons/Headphone.svelte';

	const i18n = getContext('i18n');

	let state: LiveState | null = null;
	let captions: Caption[] = [];
	let call: LiveCall | null = null;
	let player: HTMLAudioElement;
	let openFor: string | null = null;

	// Elapsed time on the call, counted from the moment it went live. The server caps a call at
	// 60 minutes, so the clock shows the cap once the last five minutes begin.
	const CAP_S = 3600;
	let liveSince: number | null = null;
	let elapsed = 0;
	let tick: ReturnType<typeof setInterval> | null = null;

	const startClock = () => {
		if (tick) return;
		liveSince = Date.now();
		elapsed = 0;
		tick = setInterval(
			() => (elapsed = Math.floor((Date.now() - (liveSince ?? Date.now())) / 1000)),
			1000
		);
	};

	const stopClock = () => {
		if (tick) clearInterval(tick);
		tick = null;
		liveSince = null;
	};

	const clock = (s: number) =>
		`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

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
						if (next === 'live') startClock();
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
		stopClock();
		state = null;
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
		stopClock();
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
	<div class="jup-live-call" role="dialog" aria-labelledby="jup-live-call-title">
		<div class="jup-live-call-head">
			<span class="jup-live-call-badge" class:jup-live-call-badge-on={state === 'live'}>
				<Headphone className="size-5" />
			</span>
			<div class="jup-live-call-title">
				<span id="jup-live-call-title">GPT-Live</span>
				<span class="jup-live-call-state" role="status">
					<span class="jup-live-call-dot" class:jup-live-call-dot-on={state === 'live'}></span>
					{label(state)}
				</span>
			</div>
			{#if liveSince}
				<span
					class="jup-live-call-clock"
					class:jup-live-call-clock-late={elapsed >= CAP_S - 300}
					aria-label={$i18n.t('Call time')}
					>{clock(elapsed)}{#if elapsed >= CAP_S - 300}<span> / {clock(CAP_S)}</span>{/if}</span
				>
			{/if}
		</div>

		<div class="jup-live-call-captions" aria-live="polite">
			{#each captions as caption}
				<p class="jup-live-caption jup-live-caption-{caption.who}">
					<span class="jup-live-caption-who"
						>{caption.who === 'caller' ? $i18n.t('You') : 'Asisten JUP'}</span
					>
					{caption.text}
				</p>
			{:else}
				<p class="jup-live-call-empty">
					{state === 'live'
						? $i18n.t('Start speaking. What you and the assistant say appears here.')
						: $i18n.t('Connecting…')}
				</p>
			{/each}
		</div>

		<p class="jup-live-call-note">
			{$i18n.t('GPT-Live paraphrases. The written answers are in this chat.')}
		</p>

		<button type="button" class="jup-live-hangup" on:click={hangUp} disabled={state === 'ending'}>
			<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" class="size-5"
				><path
					d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08a.956.956 0 0 1-.29-.7c0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.53-.29.71l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28a11.27 11.27 0 0 0-2.67-1.85.996.996 0 0 1-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z"
				/></svg
			>
			{state === 'ending' ? $i18n.t('Ending the call…') : $i18n.t('Hang up')}
		</button>
	</div>
{/if}
