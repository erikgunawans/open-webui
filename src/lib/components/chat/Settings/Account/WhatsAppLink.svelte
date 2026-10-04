<script lang="ts">
	// Settings → Akun: link a WhatsApp number to Asisten JUP (E9.2, #103; spec #101). Renders nothing
	// unless the server says the user holds `jup.channel.use` with Channels on. The code is sent from
	// WhatsApp; while it is live the status is polled, so the section turns to "linked" by itself.
	import { getContext, onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		getWhatsAppLink,
		issueWhatsAppLinkCode,
		unlinkWhatsApp,
		type WhatsAppLinkCode,
		type WhatsAppLinkStatus
	} from '$lib/apis/whatsapp-link';
	import UserSettingSection from '../UserSettingSection.svelte';
	import UserSettingRow from '../UserSettingRow.svelte';

	const i18n = getContext('i18n');

	const POLL_MS = 3000;
	const actionButtonClass =
		'text-xs text-gray-500 transition-colors hover:text-gray-900 dark:text-gray-500 dark:hover:text-white disabled:opacity-50';

	let status: WhatsAppLinkStatus | null = null;
	let issued: WhatsAppLinkCode | null = null;
	let now = Date.now();
	let busy = false;
	let timer: ReturnType<typeof setInterval> | null = null;
	let lastPoll = 0;

	$: remaining = issued ? Math.max(0, issued.expires_at - now) : 0;
	$: expired = !!issued && remaining === 0;
	$: countdown = `${Math.floor(remaining / 60000)}:${String(Math.floor((remaining % 60000) / 1000)).padStart(2, '0')}`;
	$: number = issued ? new URL(issued.wa_link).pathname.replace(/\D/g, '') : '';

	const refresh = async () => {
		status = await getWhatsAppLink(localStorage.token);
		if (status.available && status.linked) {
			issued = null;
			stop();
		}
	};

	const tick = async () => {
		now = Date.now();
		if (!issued || expired || now - lastPoll < POLL_MS) return;
		lastPoll = now;
		await refresh().catch(() => {});
	};

	const stop = () => {
		if (timer) clearInterval(timer);
		timer = null;
	};

	const issue = async () => {
		busy = true;
		try {
			issued = await issueWhatsAppLinkCode(localStorage.token);
			now = lastPoll = Date.now();
			stop();
			timer = setInterval(tick, 1000);
		} catch {
			toast.error($i18n.t('WhatsApp cannot be linked right now. Try again shortly.'));
		} finally {
			busy = false;
		}
	};

	const unlink = async () => {
		busy = true;
		try {
			await unlinkWhatsApp(localStorage.token);
			await refresh();
		} catch {
			toast.error($i18n.t('WhatsApp cannot be linked right now. Try again shortly.'));
		} finally {
			busy = false;
		}
	};

	const since = (ms: number) =>
		new Date(ms).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });

	onMount(() => {
		refresh().catch(() => (status = null));
	});
	onDestroy(stop);
</script>

{#if status?.available}
	<UserSettingSection title={$i18n.t('WhatsApp')}>
		{#if status.linked}
			<UserSettingRow
				description={$i18n.t(
					'Asisten JUP answers this number on WhatsApp, linked since {{date}}.',
					{
						date: since(status.since)
					}
				)}
			>
				<span slot="label" class="font-mono tracking-wider">•••• {status.hint}</span>
				<button class={actionButtonClass} type="button" disabled={busy} on:click={unlink}
					>{$i18n.t('Disconnect')}</button
				>
			</UserSettingRow>
		{:else if issued && !expired}
			<div class="flex flex-col gap-2 text-xs text-gray-600 dark:text-gray-400">
				<p>
					{$i18n.t('Send this code from your WhatsApp within {{time}}.', { time: countdown })}
				</p>
				<div class="font-mono text-2xl tracking-[0.3em] text-gray-900 dark:text-white">
					{issued.code}
				</div>
				<a
					class="w-fit rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-gray-700 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
					href={issued.wa_link}
					target="_blank"
					rel="noopener noreferrer">{$i18n.t('Open WhatsApp')}</a
				>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
					{$i18n.t('Or send "hubungkan {{code}}" to +{{number}}.', {
						code: issued.code,
						number
					})}
				</p>
			</div>
		{:else}
			<UserSettingRow
				description={issued
					? $i18n.t('The code has expired. Make a new one.')
					: $i18n.t('Ask Asisten JUP from WhatsApp, with the same answers as here.')}
			>
				<span slot="label">{$i18n.t('Not linked')}</span>
				<button class={actionButtonClass} type="button" disabled={busy} on:click={issue}
					>{issued ? $i18n.t('New code') : $i18n.t('Link WhatsApp')}</button
				>
			</UserSettingRow>
			<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
				{$i18n.t(
					'WhatsApp messages pass through Meta servers, including in the United States, before they reach Asisten JUP.'
				)}
			</p>
		{/if}
	</UserSettingSection>
{/if}
