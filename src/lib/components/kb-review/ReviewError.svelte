<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { KbReviewRequestError } from '$lib/apis/kb-review';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// A failure from the review API or the upload, in the reader's language. Refusals carry a stable
	// code (jup/kb_review.py); an unknown code, or an error from the vendor's upload, shows as sent.
	export let error: unknown;

	let TEXT: Record<string, string>;
	$: TEXT = {
		submit_forbidden: $i18n.t(
			'Submitting to the knowledge base is by grant. This account does not hold it.'
		),
		review_forbidden: $i18n.t('The review queue is restricted to admins.'),
		not_found: $i18n.t('The document was not found, or it is not yours.'),
		already_submitted: $i18n.t('This document has already been submitted for review.'),
		type_not_allowed: $i18n.t(
			'Only documents with readable text can be submitted: md, txt, pdf, docx, pptx, xlsx, csv.'
		),
		not_processed: $i18n.t('The document has not finished processing, or no text was found in it.'),
		note_too_long: $i18n.t('The note is longer than 1000 characters.'),
		reason_required: $i18n.t('A rejection needs a reason.'),
		reason_too_long: $i18n.t('The reason is longer than 1000 characters.'),
		not_pending: $i18n.t('This submission has already been decided.'),
		content_changed: $i18n.t(
			'The document changed after it was opened for review. Open it again before deciding.'
		),
		bad_state: $i18n.t('Unknown state filter.'),
		collection_unavailable: $i18n.t('The JUP Staff Contributions collection could not be created.'),
		attach_failed: $i18n.t(
			'The document could not be added to the knowledge base. It is still pending.'
		),
		record_failed: $i18n.t('The change could not be recorded. Try again.')
	};

	$: known = error instanceof KbReviewRequestError && error.code ? TEXT[error.code] : undefined;
	$: detail =
		error instanceof KbReviewRequestError && error.code === 'attach_failed' ? error.message : null;
	$: fallback = error instanceof Error ? error.message : `${error ?? ''}`;
</script>

{#if known}
	{known}
	{#if detail}<span class="jlp-meta jlp-block">{detail}</span>{/if}
{:else}
	{fallback}
{/if}
