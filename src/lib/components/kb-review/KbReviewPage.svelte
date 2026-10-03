<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { WEBUI_NAME } from '$lib/stores';
	import { kbReviewAccess, refreshKbReviewAccess } from '$lib/stores/kbReview';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import MobileSidebarToggle from '$lib/components/jup/MobileSidebarToggle.svelte';
	import '$lib/components/leadership/leadership.css';
	import SubmitSection from './SubmitSection.svelte';
	import ReviewQueue from './ReviewQueue.svelte';
	import ContractReview from './ContractReview.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// Each section is offered only for a capability the server reported. That is presentation: a
	// direct request without the grant or the role is refused on the server either way.
	onMount(refreshKbReviewAccess);
</script>

<svelte:head>
	<title>{$i18n.t('Knowledge review')} / {$WEBUI_NAME}</title>
</svelte:head>

<div class="jlp-root jlp-section">
	<div class="jlp-scroll">
		<div class="jlp-container">
			<MobileSidebarToggle />
			<header class="jlp-header">
				<div>
					<p class="jup-eyebrow">{$i18n.t('Knowledge Base')}</p>
					<h1 class="jlp-title">{$i18n.t('Knowledge review')}</h1>
					<p class="jlp-subtitle">
						{$i18n.t(
							'Staff submit documents for the assistant. An admin reviews each one; approved documents go into the JUP Staff Contributions collection.'
						)}
					</p>
				</div>
			</header>

			{#if $kbReviewAccess.loading}
				<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
			{:else if !$kbReviewAccess.submit && !$kbReviewAccess.review && !$kbReviewAccess.contracts}
				<div class="jlp-notice mt-4">
					<p class="font-medium">{$i18n.t('You do not have access to the review queue')}</p>
					<p class="mt-1 text-sm">
						{$i18n.t(
							'Submitting documents is by grant, and reviewing them is for admins. Ask an admin if you need access.'
						)}
					</p>
				</div>
			{:else}
				{#if $kbReviewAccess.submit}
					<SubmitSection />
				{/if}
				{#if $kbReviewAccess.review}
					<ReviewQueue />
				{/if}
				{#if $kbReviewAccess.contracts}
					<ContractReview />
				{/if}
			{/if}
		</div>
	</div>
</div>
