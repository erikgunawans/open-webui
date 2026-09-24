<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getSource,
		LeadershipRequestError,
		type LeadershipView,
		type Source
	} from '$lib/apis/leadership';
	import { formatDateId } from '$lib/leadership/format';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let show = false;
	export let view: LeadershipView;
	export let scopeId: string;
	export let sourceId: string | null = null;

	let source: Source | null = null;
	let error: string | null = null;
	let loading = false;
	let controller: AbortController | null = null;

	// Fetched through the view the reader is in, so the server can refuse a source that belongs
	// only to the other view even when its id is known.
	const load = async (id: string) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		source = null;
		error = null;
		loading = true;
		try {
			const result = await getSource(localStorage.token, view, scopeId, id, own.signal);
			if (!own.signal.aborted) source = result;
		} catch (caught) {
			if (own.signal.aborted) return;
			error =
				caught instanceof LeadershipRequestError && caught.isNotFound
					? $i18n.t('This source is not part of this view.')
					: `${caught}`;
		} finally {
			if (!own.signal.aborted) loading = false;
		}
	};

	$: if (show && sourceId) load(sourceId);
	$: if (!show) controller?.abort();

	$: VISIBILITY = {
		visible: $i18n.t('Visible slide'),
		hidden: $i18n.t('Hidden slide')
	} as Record<string, string>;

	$: STATUS = {
		presented: $i18n.t('Presented in the meeting'),
		draft: $i18n.t('Draft'),
		approved: $i18n.t('Approved')
	} as Record<string, string>;
</script>

<Modal size="sm" bind:show ariaLabelledby="jlp-source-title">
	<div class="jlp-root jlp-dialog" role="document">
		<div class="jlp-dialog-head">
			<h2 class="jlp-dialog-title" id="jlp-source-title">{$i18n.t('Source details')}</h2>
			<button type="button" class="jlp-link" on:click={() => (show = false)}
				>{$i18n.t('Close')}</button
			>
		</div>

		{#if loading}
			<div class="flex justify-center py-6"><Spinner className="size-5" /></div>
		{:else if error}
			<p class="jlp-notice"><ServerText text={error} /></p>
		{:else if source}
			<dl class="jlp-dl">
				<dt>{$i18n.t('Document')}</dt>
				<dd>{source.filename}</dd>
				<dt>{$i18n.t('Document date')}</dt>
				<dd>{formatDateId(source.document_date)}</dd>
				<dt>{$i18n.t('Slides')}</dt>
				<dd>
					{source.physical_slides.join(', ')}
					<span class="jlp-meta jlp-block"
						>{VISIBILITY[source.visibility]} · {$i18n.t('Physical order in the PPTX file')}</span
					>
				</dd>
				<dt>{$i18n.t('Document status')}</dt>
				<dd>{STATUS[source.document_status] ?? source.document_status}</dd>
				<dt>{$i18n.t('Verification')}</dt>
				<dd>
					{source.verification_status === 'verified' ? $i18n.t('Verified') : $i18n.t('Unverified')}
				</dd>
			</dl>
			<p class="jlp-meta mt-3">
				{$i18n.t(
					'A presented slide is not an approved report. This is citation metadata only; no ERP or CRM is connected.'
				)}
			</p>
		{/if}
	</div>
</Modal>
