<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import { user } from '$lib/stores';
	import { leadershipAccess } from '$lib/stores/leadership';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getAction,
		getEvidence,
		LeadershipRequestError,
		type ActionRecord,
		type Evidence,
		type HistoryEvent,
		type LeadershipView
	} from '$lib/apis/leadership';
	import { formatEventTimeId, recordedDueId } from '$lib/leadership/format';

	import ActionSubmit from './ActionSubmit.svelte';
	import ClosureReview from './ClosureReview.svelte';
	import DueRevise from './DueRevise.svelte';
	import PicAssign from './PicAssign.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
	// A write changed the record: the page reloads its register too.
	const dispatch = createEventDispatcher<{ changed: void }>();

	export let show = false;
	export let view: LeadershipView;
	export let scopeId: string;
	export let actionId: string | null = null;

	let record: ActionRecord | null = null;
	let error: string | null = null;
	let loading = false;
	let downloadError: string | null = null;
	let controller: AbortController | null = null;

	// Fetched through the reader's view: the server rechecks the grant on every open, so a revoked
	// reader loses the history too.
	// `quiet` refreshes after a write without clearing the record, so the form that wrote keeps
	// its confirmation or refusal on screen.
	const load = async (id: string, quiet = false) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;
		if (!quiet || record?.action.id !== id) {
			record = null;
			loading = true;
		}
		error = null;
		downloadError = null;
		try {
			const result = await getAction(localStorage.token, view, scopeId, id, own.signal);
			if (!own.signal.aborted) record = result;
		} catch (caught) {
			if (own.signal.aborted) return;
			if (caught instanceof LeadershipRequestError && caught.isNotFound) {
				error = $i18n.t('This action has no record in the records store.');
			} else if (caught instanceof LeadershipRequestError && caught.isAccessDenied) {
				error = $i18n.t('You do not have access to this view');
			} else if (caught instanceof LeadershipRequestError && caught.isUnavailable) {
				error = $i18n.t('The records store is not available on this server.');
			} else {
				error = `${caught}`;
			}
		} finally {
			if (!own.signal.aborted) loading = false;
		}
	};

	$: if (show && actionId) load(actionId);

	// Offered to the recorded PIC holding `actions.submit`; the server decides either way.
	$: isPic =
		record !== null &&
		record.action.pic_user_id !== null &&
		record.action.pic_user_id === $user?.id &&
		$leadershipAccess.operations.includes('actions.submit');

	// A BOD reviewer who is not this action's PIC; the owner never closes their own action.
	$: isReviewer =
		record !== null &&
		record.action.pic_user_id !== $user?.id &&
		$leadershipAccess.operations.includes('bod.review');

	$: isAssigner = record !== null && $leadershipAccess.operations.includes('actions.assign');

	const saved = () => {
		dispatch('changed');
		if (actionId) load(actionId, true);
	};
	$: if (!show) controller?.abort();

	// A file revision is fetched with the reader's token and handed to the browser as a download;
	// the server rechecks access on every one.
	const download = async (item: Evidence) => {
		downloadError = null;
		try {
			const result = await getEvidence(localStorage.token, view, scopeId, item.id);
			if (result.kind === 'link') {
				window.open(result.evidence.url ?? '', '_blank', 'noopener,noreferrer');
				return;
			}
			const href = URL.createObjectURL(result.blob);
			const anchor = document.createElement('a');
			anchor.href = href;
			anchor.download = result.filename;
			anchor.click();
			setTimeout(() => URL.revokeObjectURL(href), 0);
		} catch (caught) {
			downloadError =
				caught instanceof LeadershipRequestError && caught.isAccessDenied
					? $i18n.t('You do not have access to this view')
					: $i18n.t('The evidence could not be opened.');
		}
	};

	const text = (value: unknown): string | null =>
		typeof value === 'string' && value.trim() ? value : null;

	// Newest first: the reader opens a record to see what happened last.
	$: history = record ? [...record.history].reverse() : [];

	$: STATE = {
		not_started: $i18n.t('Not started'),
		in_progress: $i18n.t('In progress'),
		blocked: $i18n.t('Blocked'),
		awaiting_bod_closure: $i18n.t('Awaiting BOD closure'),
		closed: $i18n.t('Closed by BOD')
	} as Record<string, string>;

	$: KIND = {
		created: $i18n.t('Action recorded'),
		state_changed: $i18n.t('State changed'),
		due_revised: $i18n.t('Target revised'),
		progress_submitted: $i18n.t('Progress update from the PIC'),
		evidence_submitted: $i18n.t('Evidence submitted'),
		bod_decision: $i18n.t('BOD decision'),
		pic_assigned: $i18n.t('PIC assigned')
	} as Record<string, string>;

	$: CLOSURE_KIND = {
		completed: $i18n.t('Completion, for BOD closure'),
		cancelled: $i18n.t('Cancellation request'),
		superseded: $i18n.t('Supersession request')
	} as Record<string, string>;

	$: OUTCOME = {
		closed: $i18n.t('Closed'),
		vote_recorded: $i18n.t('Vote recorded, quorum not yet reached'),
		returned: $i18n.t('Returned to the PIC'),
		reopened: $i18n.t('Reopened')
	} as Record<string, string>;

	$: PRECISION = {
		month: $i18n.t('Target month'),
		year: $i18n.t('Target year'),
		year_range: $i18n.t('Target range'),
		date: $i18n.t('Target date')
	} as Record<string, string>;

	const flag = (value: boolean | null): string =>
		value === null ? $i18n.t('Cannot say') : value ? $i18n.t('Yes') : $i18n.t('No');

	const stateChange = (entry: HistoryEvent): string | null =>
		entry.state_before !== entry.state_after && entry.state_after
			? `${entry.state_before ? (STATE[entry.state_before] ?? entry.state_before) : '—'} → ${STATE[entry.state_after] ?? entry.state_after}`
			: null;

	const dueChange = (entry: HistoryEvent): string | null =>
		entry.kind !== 'created' && JSON.stringify(entry.due_before) !== JSON.stringify(entry.due_after)
			? `${recordedDueId(entry.due_before) ?? '—'} → ${recordedDueId(entry.due_after) ?? '—'}`
			: null;
</script>

<Modal size="lg" bind:show ariaLabelledby="jlp-action-title">
	<div class="jlp-root jlp-dialog" role="document">
		<div class="jlp-dialog-head">
			<h2 class="jlp-dialog-title" id="jlp-action-title">
				{record ? record.action.title : $i18n.t('Action record')}
			</h2>
			<button type="button" class="jlp-link" on:click={() => (show = false)}
				>{$i18n.t('Close')}</button
			>
		</div>

		{#if loading}
			<div class="flex justify-center py-6"><Spinner className="size-5" /></div>
		{:else if error}
			<p class="jlp-notice"><ServerText text={error} /></p>
		{:else if record}
			<dl class="jlp-dl">
				<dt>{$i18n.t('PIC')}</dt>
				<dd>
					{record.action.pic_label}
					{#if record.action.pic_user_id === null}
						<span class="jlp-meta jlp-block"
							>{$i18n.t('No PIC account assigned yet; nobody can submit on this action.')}</span
						>
					{/if}
				</dd>
				<dt>{$i18n.t('Status')}</dt>
				<dd>
					<span class="jlp-status">{STATE[record.action.state] ?? record.action.state}</span>
					<span class="jlp-meta jlp-block"
						>{$i18n.t('Record version {{version}}', { version: record.action.version })}</span
					>
				</dd>
				<dt>{$i18n.t('Current target')}</dt>
				<dd>
					{#if record.action.current_due}
						{recordedDueId(record.action.current_due)}
						<span class="jlp-meta jlp-block">{PRECISION[record.action.current_due.precision]}</span>
					{:else}
						<span class="jlp-meta">{$i18n.t('No target recorded')}</span>
					{/if}
				</dd>
				{#if JSON.stringify(record.action.original_due) !== JSON.stringify(record.action.current_due)}
					<dt>{$i18n.t('Original target')}</dt>
					<dd>{recordedDueId(record.action.original_due) ?? '—'}</dd>
				{/if}
				<dt>{$i18n.t('Overdue')}</dt>
				<dd>
					{flag(record.flags.overdue)}{#if record.flags.days_overdue}&nbsp;·&nbsp;{$i18n.t(
							'{{count}} days',
							{ count: record.flags.days_overdue }
						)}{/if}
					{#if record.flags.overdue === null && record.flags.reasons.overdue}
						<span class="jlp-meta jlp-block"
							><ServerText text={record.flags.reasons.overdue} /></span
						>
					{/if}
				</dd>
				<dt>{$i18n.t('Stale')}</dt>
				<dd>
					{flag(record.flags.stale)}
					{#if record.flags.stale === null && record.flags.reasons.stale}
						<span class="jlp-meta jlp-block"><ServerText text={record.flags.reasons.stale} /></span>
					{/if}
				</dd>
			</dl>

			{#if isPic}
				<ActionSubmit {record} {view} {scopeId} on:saved={saved} />
			{/if}
			{#if isAssigner}
				<PicAssign {record} {view} {scopeId} on:saved={saved} />
			{/if}
			{#if isReviewer}
				<ClosureReview {record} {view} {scopeId} on:saved={saved} />
				<DueRevise {record} {view} {scopeId} on:saved={saved} />
			{/if}

			<section class="mt-4" aria-labelledby="jlp-evidence-title">
				<h3 class="jlp-surface-title" id="jlp-evidence-title">{$i18n.t('Evidence')}</h3>
				{#if record.evidence.length === 0}
					<p class="jlp-meta">{$i18n.t('No evidence submitted yet')}</p>
				{:else}
					<ul class="jlp-mini-list">
						{#each [...record.evidence].reverse() as item (item.id)}
							<li class="jlp-mini">
								<strong>{$i18n.t('Revision {{revision}}', { revision: item.revision })}</strong>
								<span class="jlp-meta jlp-block">
									{item.kind === 'file'
										? (item.filename ?? $i18n.t('File'))
										: (item.url ?? $i18n.t('Link'))} · {formatEventTimeId(item.created_at)}
								</span>
								<button type="button" class="jlp-link" on:click={() => download(item)}
									>{item.kind === 'file' ? $i18n.t('Download') : $i18n.t('Open link')}</button
								>
							</li>
						{/each}
					</ul>
					{#if downloadError}
						<p class="jlp-notice mt-2">{downloadError}</p>
					{/if}
				{/if}
			</section>

			<section class="mt-4" aria-labelledby="jlp-history-title">
				<h3 class="jlp-surface-title" id="jlp-history-title">{$i18n.t('History')}</h3>
				<p class="jlp-meta">
					{$i18n.t('Every change is an event; nothing is edited in place.')}
				</p>
				<ol class="jlp-mini-list">
					{#each history as entry (entry.version)}
						<li class="jlp-mini">
							<strong>{KIND[entry.kind] ?? entry.kind}</strong>
							<span class="jlp-meta jlp-block">
								{$i18n.t('Version {{version}}', { version: entry.version })} · {formatEventTimeId(
									entry.at
								)} · {$i18n.t('by {{author}}', {
									author: entry.author_name ?? entry.author
								})}
							</span>
							{#if stateChange(entry)}
								<span class="jlp-block">{stateChange(entry)}</span>
							{/if}
							{#if dueChange(entry)}
								<span class="jlp-block">{$i18n.t('Target')}: {dueChange(entry)}</span>
							{/if}
							{#if entry.kind === 'progress_submitted'}
								{#if text(entry.payload.narrative)}
									<span class="jlp-block">{entry.payload.narrative}</span>
								{/if}
								{#if text(entry.payload.blocker)}
									<span class="jlp-block">{$i18n.t('Blocker')}: {entry.payload.blocker}</span>
								{/if}
								{#if text(entry.payload.next_step)}
									<span class="jlp-block">{$i18n.t('Next step')}: {entry.payload.next_step}</span>
								{/if}
							{:else if entry.kind === 'evidence_submitted'}
								{#if text(entry.payload.closure_kind)}
									<span class="jlp-block"
										>{CLOSURE_KIND[String(entry.payload.closure_kind)] ??
											entry.payload.closure_kind}</span
									>
								{/if}
								{#if text(entry.payload.note)}
									<span class="jlp-block">{entry.payload.note}</span>
								{/if}
							{:else if entry.kind === 'pic_assigned'}
								<span class="jlp-block">{entry.payload.pic_label}</span>
							{:else if entry.kind === 'bod_decision'}
								<span class="jlp-block"
									>{OUTCOME[String(entry.payload.outcome)] ?? entry.payload.outcome}</span
								>
							{/if}
							{#if entry.reason}
								<span class="jlp-meta jlp-block">{$i18n.t('Reason')}: {entry.reason}</span>
							{/if}
						</li>
					{/each}
				</ol>
			</section>
		{/if}
	</div>
</Modal>
