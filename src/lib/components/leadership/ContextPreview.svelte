<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Modal from '$lib/components/common/Modal.svelte';
	import type { ReportingContext } from '$lib/apis/leadership';
	import { formatDateId } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// P1 shows what the assistant WOULD be given. It sends nothing: no chat is created, no message
	// is posted, and no record value goes into a URL. Wiring it to a real discussion is P3, and
	// that stage re-checks access on the server and the conversation's audience first.
	export let show = false;
	export let viewLabel: string;
	export let context: ReportingContext;
	export let recordLabel: string | null = null;
</script>

<Modal size="sm" bind:show>
	<div class="jlp-root jlp-dialog" role="document">
		<div class="jlp-dialog-head">
			<h2 class="jlp-dialog-title">{$i18n.t('Context preview for the Assistant')}</h2>
			<button type="button" class="jlp-link" on:click={() => (show = false)}
				>{$i18n.t('Close')}</button
			>
		</div>

		<p class="jlp-notice">
			{$i18n.t('Discussion is not connected at this stage. No message or data is sent.')}
		</p>

		<dl class="jlp-dl mt-3">
			<dt>{$i18n.t('View')}</dt>
			<dd>{viewLabel}</dd>
			<dt>{$i18n.t('Scope')}</dt>
			<dd>{context.scope_id}</dd>
			<dt>{$i18n.t('Period')}</dt>
			<dd>{formatDateId(context.period_start)} – {formatDateId(context.period_end)}</dd>
			<dt>{$i18n.t('Reporting context')}</dt>
			<dd>
				{context.label}
				<span class="jlp-meta jlp-block"
					>{context.kind === 'source_example'
						? $i18n.t('Illustrative example from a presentation, not a meeting record')
						: context.kind}</span
				>
			</dd>
			<dt>{$i18n.t('Selected record')}</dt>
			<dd>{recordLabel ?? $i18n.t('None selected')}</dd>
		</dl>

		<p class="jlp-meta mt-3">
			{$i18n.t(
				'When connected, the discussion stays inside Ruang Pimpinan, access is checked again, and any change the Assistant prepares needs confirmation from an authorised person.'
			)}
		</p>
	</div>
</Modal>
