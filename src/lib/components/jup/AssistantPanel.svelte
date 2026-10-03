<script lang="ts">
	// The Ruang Pimpinan assistant panel (`$lib/voice/panel`): mounted by the section layout so the
	// call survives Board ↔ RKA, it pushes the page narrower on a desktop and is a bottom sheet on a
	// phone. The voice orb sits on top, the conversation below, a text box at the foot. Every
	// question — typed, spoken in a normal call, or delegated by GPT-Live — runs on the server as a
	// governed turn in the caller's own voice chat; this component only records, shows and plays.
	import { getContext, onDestroy, tick } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { toast } from 'svelte-sonner';

	import { page } from '$app/stores';
	import { settings } from '$lib/stores';
	import { blobToFile } from '$lib/utils';
	import { transcribeAudio } from '$lib/apis/audio';
	import {
		acknowledgeVoice,
		acknowledgeVoiceLive,
		askInCall,
		getAnswerSpeechParts,
		setCallContext,
		startLiveSession,
		startVoiceCall,
		synthesizeAnswerPart
	} from '$lib/apis/voice';
	import { startLiveCall, type LiveCall, type LiveState } from '$lib/voice/liveCall';
	import type { Caption, CallMode } from '$lib/voice/live';
	import {
		addTurn,
		assistantPanelOpen,
		panelModes,
		speakSealedAnswer,
		startPanelCall,
		viewFromPath,
		type LeadershipTab,
		type PanelCall,
		type Turn
	} from '$lib/voice/panel';
	import {
		disclosureRequest,
		liveDisclosureRequest,
		refreshVoiceCapabilities,
		voiceCapabilities
	} from '$lib/voice/session';

	const i18n = getContext<Writable<i18nType>>('i18n');

	const TAB_NAMES: Record<LeadershipTab, string> = {
		board: 'Direksi & Komisaris',
		rka: 'RKA & Realisasi'
	};

	type Timed = Turn & { at: number };
	type Phase = 'idle' | 'starting' | 'ready' | 'recording' | 'thinking' | 'speaking';

	let call: PanelCall | null = null;
	let phase: Phase = 'idle';
	let turns: Timed[] = [];
	let draft = '';
	let asking = false;
	let list: HTMLElement;

	// GPT-Live
	let live: LiveCall | null = null;
	let liveState: LiveState | null = null;
	let liveSince = 0;
	let captions: Caption[] = [];
	let player: HTMLAudioElement;

	// A normal call: push-to-talk recording, then the sealed answer read aloud.
	let recorder: MediaRecorder | null = null;
	let chunks: Blob[] = [];
	let speech: AbortController | null = null;
	let voicePlayer: HTMLAudioElement | null = null;

	$: view = viewFromPath($page.url.pathname);
	$: modes = panelModes($voiceCapabilities);

	if (localStorage.token) refreshVoiceCapabilities(localStorage.token);

	// Each tab switch is told to the server, which checks the caller's grant before recording it.
	let toldView: string | null = null;
	$: if (call && view && `${call.chat_id}:${view}` !== toldView) tellView(call.chat_id, view);
	const tellView = (chatId: string, next: LeadershipTab) => {
		toldView = `${chatId}:${next}`;
		setCallContext(localStorage.token, chatId, next).catch(() => null);
	};

	// The conversation: typed and normal-call turns, plus GPT-Live's captions in time order.
	$: shown = [
		...turns,
		...captions.map((c) => ({ who: c.who, text: c.text, at: liveSince + c.start }))
	].sort((a, b) => a.at - b.at) as Timed[];
	$: if (shown.length) tick().then(() => list?.scrollTo({ top: list.scrollHeight }));

	const push = (turn: Turn) => {
		turns = addTurn(turns, { ...turn, at: Date.now() } as Timed) as Timed[];
	};

	const errorText = (error: unknown): string =>
		(error as { message?: string } | null)?.message ?? (typeof error === 'string' ? error : '');

	const begin = async (mode: CallMode): Promise<PanelCall | null> => {
		if (call) return call;
		phase = 'starting';
		const token = localStorage.token;
		try {
			call = await startPanelCall(
				{
					capabilities: () => refreshVoiceCapabilities(token),
					disclose: () => new Promise((resolve) => disclosureRequest.set(resolve)),
					acknowledge: (version) => acknowledgeVoice(token, version),
					discloseLive: () => new Promise((resolve) => liveDisclosureRequest.set(resolve)),
					acknowledgeLive: (version) => acknowledgeVoiceLive(token, version),
					startCall: () => startVoiceCall(token),
					setContext: (chatId, tab) => {
						toldView = `${chatId}:${tab}`;
						return setCallContext(token, chatId, tab);
					}
				},
				mode,
				view
			);
		} catch (error) {
			toast.error(errorText(error) || $i18n.t('The call could not start.'));
			call = null;
		}
		phase = call ? 'ready' : 'idle';
		if (call?.mode === 'live') await goLive(call.chat_id);
		return call;
	};

	const goLive = async (chatId: string) => {
		captions = [];
		try {
			live = await startLiveCall(
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
						liveState = next;
						if (next === 'live' && !liveSince) liveSince = Date.now();
						if (next === 'ended' || next === 'failed') endLive();
					},
					onCaptions: (next) => (captions = next)
				}
			);
		} catch (error) {
			toast.error(errorText(error) || $i18n.t('The GPT-Live call could not start.'));
			endLive();
		}
	};

	// GPT-Live's captions stay in the conversation once the call is over.
	const endLive = () => {
		const base = liveSince;
		turns = [...turns, ...captions.map((c) => ({ who: c.who, text: c.text, at: base + c.start }))];
		captions = [];
		live = null;
		liveState = null;
		liveSince = 0;
		if (call?.mode === 'live') {
			call = null;
			phase = 'idle';
		}
	};

	const stopSpeech = () => {
		speech?.abort();
		speech = null;
		voicePlayer?.pause();
		voicePlayer = null;
	};

	const playBlob = (blob: Blob, signal: AbortSignal) =>
		new Promise<void>((resolve) => {
			const url = URL.createObjectURL(blob);
			const audio = new Audio(url);
			voicePlayer = audio;
			const done = () => {
				URL.revokeObjectURL(url);
				resolve();
			};
			audio.addEventListener('ended', done, { once: true });
			audio.addEventListener('error', done, { once: true });
			signal.addEventListener('abort', done, { once: true });
			audio.play().catch(done);
		});

	const speak = async (chatId: string, messageId: string) => {
		stopSpeech();
		const controller = new AbortController();
		speech = controller;
		phase = 'speaking';
		try {
			await speakSealedAnswer(
				{
					parts: () => getAnswerSpeechParts(localStorage.token, chatId, messageId),
					part: (n) => synthesizeAnswerPart(localStorage.token, chatId, messageId, n),
					play: (blob) => playBlob(blob, controller.signal)
				},
				controller.signal
			);
		} catch (error) {
			if (!controller.signal.aborted) toast.error(errorText(error));
		}
		if (speech === controller) {
			speech = null;
			if (call) phase = 'ready';
		}
	};

	/** One question in the call; spoken back only in a normal call the caller is talking in. */
	const ask = async (text: string, { aloud }: { aloud: boolean }) => {
		const question = text.trim();
		if (!question || asking) return;
		const current = call ?? (await begin('governed'));
		if (!current) return;
		asking = true;
		stopSpeech();
		push({ who: 'caller', text: question });
		if (current.mode === 'governed') phase = 'thinking';
		try {
			const answer = await askInCall(localStorage.token, current.chat_id, question);
			push({ who: 'assistant', text: answer.content });
			if (aloud && call?.mode === 'governed') {
				asking = false;
				await speak(current.chat_id, answer.message_id);
			}
		} catch (error) {
			toast.error(errorText(error) || $i18n.t('The answer could not be fetched.'));
		} finally {
			asking = false;
			if (call?.mode === 'governed' && phase === 'thinking') phase = 'ready';
		}
	};

	const send = () => {
		const text = draft;
		draft = '';
		ask(text, { aloud: false });
	};

	const onKey = (event: KeyboardEvent) => {
		if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
			event.preventDefault();
			send();
		}
	};

	const startRecording = async () => {
		stopSpeech();
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			chunks = [];
			recorder = new MediaRecorder(stream);
			recorder.addEventListener('dataavailable', (event) => chunks.push(event.data));
			recorder.addEventListener('stop', async () => {
				stream.getTracks().forEach((track) => track.stop());
				const blob = new Blob(chunks, { type: recorder?.mimeType || 'audio/webm' });
				recorder = null;
				await transcribeAndAsk(blob);
			});
			recorder.start();
			phase = 'recording';
		} catch {
			toast.error($i18n.t('The microphone could not start.'));
			phase = 'ready';
		}
	};

	const transcribeAndAsk = async (blob: Blob) => {
		if (!call || blob.size < 100) {
			phase = call ? 'ready' : 'idle';
			return;
		}
		phase = 'thinking';
		const result = await transcribeAudio(
			localStorage.token,
			blobToFile(blob, 'recording.webm'),
			$settings?.audio?.stt?.language,
			call.chat_id
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		const text = (result?.text ?? '').trim();
		if (text) await ask(text, { aloud: true });
		else phase = call ? 'ready' : 'idle';
	};

	const talk = () => {
		if (phase === 'recording') recorder?.stop();
		else if (phase === 'speaking') stopSpeech();
		else if (phase === 'ready') startRecording();
	};

	// The voice button in the composer: starts a normal call if none is open, then talks.
	const voiceFromComposer = async () => {
		if (!call) {
			if (!(await begin('governed'))) return;
		}
		if (call?.mode === 'governed') talk();
	};

	const hangUp = async () => {
		stopSpeech();
		if (recorder && recorder.state !== 'inactive') {
			recorder.onstop = null;
			recorder.stream.getTracks().forEach((track) => track.stop());
		}
		recorder = null;
		if (live) await live.hangUp();
		call = null;
		phase = 'idle';
	};

	const close = async () => {
		await hangUp();
		assistantPanelOpen.set(false);
	};

	onDestroy(() => {
		stopSpeech();
		recorder?.stream.getTracks().forEach((track) => track.stop());
		live?.hangUp();
	});

	$: orbState =
		call?.mode === 'live'
			? liveState === 'live'
				? 'live'
				: 'busy'
			: phase === 'recording'
				? 'listening'
				: phase === 'speaking'
					? 'speaking'
					: phase === 'thinking' || phase === 'starting'
						? 'busy'
						: call
							? 'ready'
							: 'idle';

	$: status =
		call?.mode === 'live'
			? liveState === 'live'
				? $i18n.t('GPT-Live is listening')
				: liveState === 'ending'
					? $i18n.t('Ending the call…')
					: $i18n.t('Connecting…')
			: phase === 'starting'
				? $i18n.t('Connecting…')
				: phase === 'recording'
					? $i18n.t('Listening… tap to send')
					: phase === 'thinking'
						? $i18n.t('Preparing the answer…')
						: phase === 'speaking'
							? $i18n.t('Speaking… tap to stop')
							: call
								? $i18n.t('Tap to speak')
								: $i18n.t('Ask a question about this page, by voice or by typing.');
</script>

<audio bind:this={player} autoplay class="hidden"></audio>

<aside class="jup-ap" aria-labelledby="jup-ap-title">
	<header class="jup-ap-head">
		<div class="jup-ap-heading">
			<h2 id="jup-ap-title" class="jup-ap-title">Asisten JUP</h2>
			{#if view}
				<p class="jup-ap-viewing">
					{$i18n.t('Viewing: {{tab}}', { tab: TAB_NAMES[view] })}
				</p>
			{/if}
		</div>
		<button
			type="button"
			class="jup-ap-icon"
			on:click={close}
			aria-label={$i18n.t('Close the assistant')}
		>
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"
				><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg
			>
		</button>
	</header>

	<section class="jup-ap-voice" aria-label={$i18n.t('Voice')}>
		{#if call?.mode === 'governed'}
			<button
				type="button"
				class="jup-ap-orb jup-ap-orb-{orbState}"
				on:click={talk}
				disabled={phase === 'thinking' || phase === 'starting'}
				aria-label={status}
			>
				<svg
					viewBox="0 0 24 24"
					aria-hidden="true"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					><rect x="9" y="3" width="6" height="11" rx="3" /><path
						d="M5 11a7 7 0 0 0 14 0M12 18v3"
					/></svg
				>
			</button>
		{:else}
			<div class="jup-ap-orb jup-ap-orb-{orbState}" aria-hidden="true">
				<svg
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					><rect x="9" y="3" width="6" height="11" rx="3" /><path
						d="M5 11a7 7 0 0 0 14 0M12 18v3"
					/></svg
				>
			</div>
		{/if}
		<p class="jup-ap-status" role="status">{status}</p>

		{#if !call && phase === 'idle'}
			{#if modes.length > 0}
				<div class="jup-ap-modes">
					<button type="button" class="jup-ap-mode" on:click={() => begin('governed')}>
						{$i18n.t('Normal call')}
					</button>
					{#if modes.includes('live')}
						<button type="button" class="jup-ap-mode" on:click={() => begin('live')}
							>GPT-Live</button
						>
					{/if}
				</div>
			{/if}
		{:else if call}
			<button type="button" class="jup-ap-end" on:click={hangUp} disabled={liveState === 'ending'}>
				{$i18n.t('End call')}
			</button>
		{/if}
	</section>

	<div class="jup-ap-list" bind:this={list} aria-live="polite">
		{#each shown as turn}
			<p class="jup-ap-turn jup-ap-turn-{turn.who}">
				<span class="jup-ap-who">{turn.who === 'caller' ? $i18n.t('You') : 'Asisten JUP'}</span>
				<span class="jup-ap-text">{turn.text}</span>
			</p>
		{:else}
			<p class="jup-ap-empty">
				{$i18n.t(
					'Answers come from what you may see in Ruang Pimpinan and the JUP knowledge base.'
				)}
			</p>
		{/each}
		{#if asking}
			<p class="jup-ap-turn jup-ap-turn-assistant jup-ap-pending">
				<span class="jup-ap-who">Asisten JUP</span>
				<span class="jup-ap-text">{$i18n.t('Preparing the answer…')}</span>
			</p>
		{/if}
	</div>

	{#if call}
		<a class="jup-ap-record" href="/c/{call.chat_id}">{$i18n.t('Open the written record')}</a>
	{/if}

	<div class="jup-ap-compose">
		<form class="jup-ap-input" on:submit|preventDefault={send}>
			<textarea
				bind:value={draft}
				on:keydown={onKey}
				rows="2"
				maxlength="2000"
				placeholder={$i18n.t('Ask about this page…')}
				aria-label={$i18n.t('Ask about this page…')}
				disabled={modes.length === 0}
			></textarea>
			<div class="jup-ap-input-row">
				{#if call?.mode !== 'live'}
					<button
						type="button"
						class="jup-ap-voice-btn"
						class:jup-ap-voice-on={phase === 'recording'}
						on:click={voiceFromComposer}
						disabled={modes.length === 0 || phase === 'thinking' || phase === 'starting'}
						aria-label={phase === 'recording'
							? $i18n.t('Listening… tap to send')
							: $i18n.t('Tap to speak')}
					>
						<svg
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							aria-hidden="true"><path d="M6 10v4M10 7v10M14 9v6M18 11v2" /></svg
						>
					</button>
				{/if}
				<button
					type="submit"
					class="jup-ap-send"
					disabled={!draft.trim() || asking || modes.length === 0}
					aria-label={$i18n.t('Send')}
				>
					<svg
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg
					>
				</button>
			</div>
		</form>
	</div>
</aside>

<style>
	.jup-ap {
		display: flex;
		flex-direction: column;
		width: 24rem;
		flex: 0 0 24rem;
		height: 100%;
		min-height: 0;
		background: var(--jup-ui-paper);
		border-left: 1px solid var(--jup-ui-hairline);
		color: var(--jup-ui-ink);
	}

	.jup-ap-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 1rem 1rem 0.5rem 1.25rem;
	}

	.jup-ap-title {
		font-size: 1rem;
		font-weight: 600;
		letter-spacing: var(--jup-ui-tracking-heading);
	}

	.jup-ap-viewing {
		margin-top: 0.125rem;
		font-size: 0.8125rem;
		color: var(--jup-ui-muted);
	}

	.jup-ap-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border-radius: var(--jup-ui-radius-control);
		color: var(--jup-ui-muted);
	}

	.jup-ap-icon svg {
		width: 1.125rem;
		height: 1.125rem;
	}

	.jup-ap-icon:hover {
		background: var(--jup-ui-fill);
		color: var(--jup-ui-ink);
	}

	.jup-ap-voice {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem 1.25rem 1.25rem;
		border-bottom: 1px solid var(--jup-ui-hairline);
	}

	.jup-ap-orb {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 5.5rem;
		height: 5.5rem;
		border-radius: 999px;
		background: var(--jup-ui-fill);
		color: var(--jup-ui-muted);
		transition: var(--jup-ui-transition);
	}

	.jup-ap-orb svg {
		width: 2rem;
		height: 2rem;
	}

	.jup-ap-orb-ready {
		background: var(--jup-ui-ink);
		color: var(--jup-ui-on-ink);
	}

	button.jup-ap-orb-ready:hover {
		background: var(--jup-ui-ink-hover);
	}

	.jup-ap-orb-listening,
	.jup-ap-orb-live,
	.jup-ap-orb-speaking {
		background: var(--jup-brand);
		color: #011627; /* Rich Black on JUP green: 5.67:1 */
		box-shadow: var(--jup-ui-ring-brand);
		animation: jup-ap-pulse 1.6s ease-in-out infinite;
	}

	.jup-ap-orb-busy {
		background: var(--jup-ui-fill-hover);
		color: var(--jup-ui-ink);
		animation: jup-ap-pulse 2.4s ease-in-out infinite;
	}

	.jup-ap-orb:focus-visible {
		outline: 2px solid var(--jup-ring);
		outline-offset: 3px;
	}

	@keyframes jup-ap-pulse {
		0%,
		100% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.06);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.jup-ap-orb {
			animation: none !important;
		}
	}

	.jup-ap-status {
		min-height: 1.25rem;
		font-size: 0.875rem;
		text-align: center;
		color: var(--jup-ui-muted);
	}

	.jup-ap-modes {
		display: flex;
		gap: 0.5rem;
	}

	.jup-ap-mode,
	.jup-ap-end {
		min-height: 2.25rem;
		padding: 0.4rem 1rem;
		border-radius: var(--jup-ui-radius-control);
		font-size: 0.875rem;
		font-weight: 500;
	}

	.jup-ap-mode {
		background: var(--jup-ui-ink);
		color: var(--jup-ui-on-ink);
	}

	.jup-ap-mode:hover {
		background: var(--jup-ui-ink-hover);
	}

	.jup-ap-end {
		background: var(--jup-ui-fill);
		color: var(--jup-ui-destructive);
	}

	.jup-ap-end:hover {
		background: var(--jup-ui-fill-hover);
	}

	.jup-ap-mode:focus-visible,
	.jup-ap-end:focus-visible,
	.jup-ap-icon:focus-visible,
	.jup-ap-send:focus-visible,
	.jup-ap-record:focus-visible {
		outline: 2px solid var(--jup-ring);
		outline-offset: 2px;
	}

	.jup-ap-list {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 1rem 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.jup-ap-turn {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		font-size: 0.875rem;
		line-height: 1.5;
	}

	.jup-ap-turn-caller {
		align-self: flex-end;
		max-width: 85%;
		padding: 0.5rem 0.75rem;
		border-radius: var(--jup-ui-radius-nested);
		background: var(--jup-ui-fill);
	}

	.jup-ap-who {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--jup-ui-muted);
	}

	.jup-ap-text {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.jup-ap-pending .jup-ap-text,
	.jup-ap-empty {
		color: var(--jup-ui-muted);
	}

	.jup-ap-empty {
		font-size: 0.875rem;
	}

	.jup-ap-record {
		margin: 0 1.25rem 0.5rem;
		font-size: 0.8125rem;
		color: var(--jup-ui-muted);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	/* The same composer as the chat home: a paper card inside a soft tray, controls on its foot. */
	.jup-ap-compose {
		margin: 0 0.75rem 0.75rem;
		padding: 0.375rem;
		border-radius: calc(var(--jup-ui-radius-nested) + 0.375rem);
		background: var(--jup-ui-surface-alt);
		box-shadow: 0 0 0 1px var(--jup-ui-hairline);
	}

	.jup-ap-input {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.5rem 0.5rem 0.5rem 0.75rem;
		border-radius: var(--jup-ui-radius-nested);
		background: var(--jup-ui-paper);
		box-shadow: 0 0 0 1px var(--jup-ui-hairline);
	}

	.jup-ap-input:focus-within {
		box-shadow: 0 0 0 1px var(--jup-ui-hairline-strong);
	}

	.jup-ap-input textarea {
		resize: none;
		padding: 0.25rem 0;
		background: transparent;
		color: var(--jup-ui-ink);
		font-size: 0.875rem;
	}

	.jup-ap-input textarea::placeholder {
		color: var(--jup-ui-muted);
	}

	/* The card's edge shows focus; the field itself needs no second ring. */
	.jup-ap-input textarea:focus-visible {
		outline: none;
	}

	.jup-ap-input-row {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}

	.jup-ap-voice-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border-radius: 999px;
		box-shadow: 0 0 0 1px var(--jup-ui-hairline-strong);
		color: var(--jup-ui-ink);
	}

	.jup-ap-voice-btn svg {
		width: 1.125rem;
		height: 1.125rem;
	}

	.jup-ap-voice-btn:hover {
		background: var(--jup-ui-fill);
	}

	.jup-ap-voice-on {
		background: var(--jup-brand);
		color: #011627;
		box-shadow: none;
	}

	.jup-ap-voice-btn:disabled {
		opacity: 0.4;
	}

	.jup-ap-voice-btn:focus-visible {
		outline: 2px solid var(--jup-ring);
		outline-offset: 2px;
	}

	.jup-ap-send {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border-radius: 999px;
		background: var(--jup-ui-ink);
		color: var(--jup-ui-on-ink);
	}

	.jup-ap-send svg {
		width: 1.125rem;
		height: 1.125rem;
	}

	.jup-ap-send:disabled {
		opacity: 0.4;
	}

	/* A phone: a bottom sheet over the page rather than a column beside it. */
	@media (max-width: 767px) {
		.jup-ap {
			position: fixed;
			inset: auto 0 0 0;
			z-index: 40;
			width: 100%;
			height: 72dvh;
			border-left: 0;
			border-radius: var(--jup-ui-radius-card) var(--jup-ui-radius-card) 0 0;
			box-shadow: var(--jup-ui-shadow-pop);
		}
	}
</style>
