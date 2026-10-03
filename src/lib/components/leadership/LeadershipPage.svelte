<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { user } from '$lib/stores';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getOverview,
		LeadershipRequestError,
		type LeadershipView,
		type Overview
	} from '$lib/apis/leadership';
	import { awaitingReview, isOpenAction, isSampleRegister } from '$lib/leadership/actions';
	import { leadershipAccess } from '$lib/stores/leadership';
	import { SUPPORTED, validateContextQuery, type ContextProblem } from '$lib/leadership/context';
	import { barShare, formatDateId, formatValue } from '$lib/leadership/format';

	import MetricCard from './MetricCard.svelte';
	import ActionRegister from './ActionRegister.svelte';
	import ActionDetail from './ActionDetail.svelte';
	import MeetingHistory from './MeetingHistory.svelte';
	import MeetingChanges from './MeetingChanges.svelte';
	import RkaRecords from './RkaRecords.svelte';
	import ImportReview from './ImportReview.svelte';
	import SourceDetails from './SourceDetails.svelte';
	import ContextPreview from './ContextPreview.svelte';
	import { callButton } from '$lib/voice/call';
	import { refreshVoiceCapabilities, voiceCapabilities } from '$lib/voice/session';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// Voice from Ruang Pimpinan: the same start-call route as the main chat (`/?call=true`), so the
	// disclosure, mode choice (normal or GPT-Live) and grants are the chat's own. What the assistant
	// may say about this page is decided by the `jup_leadership` tool against the page's grants.
	onMount(() => {
		if (localStorage.token) refreshVoiceCapabilities(localStorage.token);
	});

	export let view: LeadershipView;

	type State =
		| { kind: 'loading' }
		| { kind: 'denied'; message: string }
		| { kind: 'unavailable'; message: string }
		| { kind: 'context'; problem: ContextProblem }
		| { kind: 'failed'; message: string }
		| { kind: 'ready'; overview: Overview };

	let state: State = { kind: 'loading' };
	let controller: AbortController | null = null;

	$: scopeId = SUPPORTED[view].scope;
	$: viewLabel = view === 'board' ? 'Direksi & Komisaris' : 'RKA & Realisasi';

	// The short list names what still needs attention: the sample's examples as they are, the
	// recorded register without what the BOD has closed.
	const shortList = (overview: Overview) =>
		isSampleRegister(overview)
			? overview.actions
			: overview.actions.filter((action) => isOpenAction(action.state));

	$: MINI_STATE = {
		not_started: $i18n.t('Not started'),
		in_progress: $i18n.t('In progress'),
		blocked: $i18n.t('Blocked'),
		awaiting_bod_closure: $i18n.t('Awaiting BOD closure'),
		closed: $i18n.t('Closed by BOD')
	} as Record<string, string>;

	// Reload whenever the view, the context identifiers or the signed-in account changes. A
	// response for an earlier request is dropped, so one reader's report never renders for the next.
	$: loadKey = `${view}|${$user?.id ?? ''}|${['scope', 'context', 'period']
		.map((key) => $page.url.searchParams.get(key) ?? '')
		.join('|')}`;
	$: load(loadKey);

	// `quiet` keeps the current report on screen while it refreshes, so a dialog open over it (an
	// action the reader just wrote to) stays open.
	const load = async (_key: string, quiet = false) => {
		controller?.abort();
		const own = new AbortController();
		controller = own;

		const problem = validateContextQuery($page.url.searchParams, view);
		if (problem) {
			state = { kind: 'context', problem };
			return;
		}

		if (!quiet || state.kind !== 'ready') state = { kind: 'loading' };
		try {
			const overview = await getOverview(localStorage.token, view, scopeId, own.signal);
			if (!own.signal.aborted) state = { kind: 'ready', overview };
		} catch (error) {
			if (own.signal.aborted) return;
			if (error instanceof LeadershipRequestError && error.isAccessDenied) {
				state = { kind: 'denied', message: error.message };
			} else if (error instanceof LeadershipRequestError && error.isUnavailable) {
				state = { kind: 'unavailable', message: error.message };
			} else {
				state = { kind: 'failed', message: `${error}` };
			}
		}
	};

	onDestroy(() => controller?.abort());

	// The selected record lives in the URL as an id only, so Back, refresh and a shared link keep
	// it, and no record value ever reaches the address bar.
	$: recordId = $page.url.searchParams.get('record');

	const select = (id: string) => {
		const url = new URL($page.url);
		url.searchParams.set('record', id);
		goto(url, { keepFocus: true, noScroll: true });
	};

	$: overview = state.kind === 'ready' ? state.overview : null;

	$: recordLabels = overview
		? new Map<string, string>([
				...overview.metrics.map((item) => [item.id, item.label] as [string, string]),
				...overview.actions.map((item) => [item.id, item.title] as [string, string]),
				...overview.assumptions.map((item) => [item.id, item.label] as [string, string])
			])
		: new Map<string, string>();

	$: recordLabel = recordId ? (recordLabels.get(recordId) ?? null) : null;
	$: recordMissing = overview !== null && recordId !== null && recordLabel === null;

	// The comparison bar: only for a like-for-like actual against budget, both positive.
	$: comparison = overview?.metrics.find(
		(metric) =>
			metric.variance !== null &&
			metric.baseline?.value &&
			metric.primary.value &&
			barShare(metric.primary.value, metric.baseline.value) !== null
	);

	let sourceOpen = false;
	let sourceId: string | null = null;
	const openSource = (id: string) => {
		sourceId = id;
		sourceOpen = true;
	};

	// A recorded action's detail and history. Sample actions have no record, so none is offered.
	let detailOpen = false;
	let detailId: string | null = null;
	const openDetail = (id: string) => {
		detailId = id;
		detailOpen = true;
	};

	let registerOpen = false;
	let previewOpen = false;

	$: CONTEXT_PROBLEM = {
		scope: $i18n.t('The requested scope is not available in this stage.'),
		context: $i18n.t('The requested reporting context is not available in this stage.'),
		period: $i18n.t('The requested period is not available in this stage.')
	} as Record<string, string>;

	// The server writes its refusals in English and stays their single source. They are translated
	// here, keyed by the sentence itself; one the server rewords misses the map and shows in English,
	// never as a stale translation.
	$: serverText = {
		'Ruang Pimpinan is restricted. This account is signed in but has no access to this view.':
			$i18n.t(
				'Ruang Pimpinan is restricted. This account is signed in but has no access to this view.'
			),
		'Ruang Pimpinan is not enabled on this server.': $i18n.t(
			'Ruang Pimpinan is not enabled on this server.'
		),
		'No action is recorded for this view yet.': $i18n.t('No action is recorded for this view yet.'),
		'No leadership dataset is configured on this server.': $i18n.t(
			'No leadership dataset is configured on this server.'
		),
		'The leadership dataset could not be read.': $i18n.t(
			'The leadership dataset could not be read.'
		),
		'The leadership dataset is not valid JSON.': $i18n.t(
			'The leadership dataset is not valid JSON.'
		),
		'The leadership dataset is malformed.': $i18n.t('The leadership dataset is malformed.'),
		'The leadership dataset failed validation.': $i18n.t(
			'The leadership dataset failed validation.'
		)
	} as Record<string, string>;

	// Set by the meeting comparison once two published meeting records exist.
	let changesAvailable = false;

	$: MODULE_STATE = {
		unavailable: $i18n.t('Not yet available'),
		suggested: $i18n.t('Suggestion'),
		source_example: $i18n.t('Example from the presentation'),
		available: $i18n.t('Available')
	} as Record<string, string>;
</script>

{#if state.kind === 'loading'}
	<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{:else if state.kind === 'denied'}
	<div class="jlp-notice">
		<p class="font-medium">{$i18n.t('You do not have access to this view')}</p>
		<p class="mt-1 text-sm">{serverText[state.message] ?? state.message}</p>
	</div>
{:else if state.kind === 'unavailable'}
	<div class="jlp-notice">
		<p class="font-medium">{$i18n.t('Ruang Pimpinan is unavailable')}</p>
		<p class="mt-1 text-sm">{serverText[state.message] ?? state.message}</p>
	</div>
{:else if state.kind === 'context'}
	<!-- A link for another period is reported, never silently answered with this one. -->
	<div class="jlp-notice">
		<p class="font-medium">{$i18n.t('This selection is not available')}</p>
		<p class="mt-1 text-sm">{CONTEXT_PROBLEM[state.problem]}</p>
		<p class="mt-2 text-sm">
			<a class="jlp-link" href="/ruang-pimpinan/{view}">{$i18n.t('Open the available example')}</a>
		</p>
	</div>
{:else if state.kind === 'failed'}
	<div class="jlp-notice jlp-notice-refused">
		<p class="font-medium">{$i18n.t('The report could not be loaded')}</p>
		<p class="mt-1 text-sm"><ServerText text={state.message} /></p>
	</div>
{:else if overview}
	<div class="jlp-context-bar">
		<div class="jlp-context-main">
			<span class="jlp-context-label">{overview.context.label}</span>
			<span class="jlp-meta">
				{overview.context.scope_id} · {formatDateId(overview.context.period_start)} – {formatDateId(
					overview.context.period_end
				)}
			</span>
			<span class="jlp-badge">
				{overview.data_mode === 'illustrative'
					? $i18n.t('Illustrative · unverified · partial coverage')
					: overview.data_mode}
			</span>
		</div>
		<button type="button" class="jlp-button" on:click={() => (previewOpen = true)}>
			<svg
				viewBox="0 0 24 24"
				aria-hidden="true"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linejoin="round"
				><path
					d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H10l-4 3v-3H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"
				/></svg
			>
			{$i18n.t('Discuss with the Assistant')}
			<span class="jlp-meta">· {$i18n.t('Context preview')}</span>
		</button>
		{#if callButton($voiceCapabilities) !== 'hidden'}
			<button type="button" class="jlp-button" on:click={() => goto('/?call=true')}>
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
				{$i18n.t('Talk with the Assistant')}
			</button>
		{/if}
	</div>

	{#if recordMissing}
		<p class="jlp-notice mt-3 text-sm">
			{$i18n.t('The selected record is not part of this view.')}
		</p>
	{/if}

	<section aria-label={$i18n.t('Key figures')} class="jlp-metric-row">
		{#each overview.metrics as metric (metric.id)}
			<MetricCard
				{metric}
				selected={recordId === metric.id}
				on:source={(event) => openSource(event.detail)}
				on:select={(event) => select(event.detail)}
			/>
		{/each}
	</section>

	<div class="jlp-grid">
		<section class="jlp-surface" aria-labelledby="jlp-left-title">
			{#if view === 'board'}
				<h3 id="jlp-left-title" class="jlp-surface-title">{$i18n.t('Main attention')}</h3>
				{#if comparison && comparison.baseline && comparison.primary.value && comparison.baseline.value}
					{@const actualShare = barShare(comparison.primary.value, comparison.baseline.value)}
					{@const budgetShare = barShare(comparison.baseline.value, comparison.primary.value)}
					<p class="jlp-meta">{comparison.label} · {$i18n.t('same period')}</p>
					<div
						class="jlp-bars"
						role="img"
						aria-label="{comparison.label}: {$i18n.t('actual')} {formatValue(
							comparison.primary.value,
							comparison.primary.unit
						)}, {$i18n.t('budget')} {formatValue(
							comparison.baseline.value,
							comparison.baseline.unit
						)}"
					>
						<div class="jlp-bar-label">
							<span>{$i18n.t('Actual')}</span>
							<strong>{formatValue(comparison.primary.value, comparison.primary.unit)}</strong>
						</div>
						<div class="jlp-bar-track">
							<div class="jlp-bar-fill" style="width: {actualShare}%"></div>
						</div>
						<div class="jlp-bar-label">
							<span>{$i18n.t('Budget')}</span>
							<strong>{formatValue(comparison.baseline.value, comparison.baseline.unit)}</strong>
						</div>
						<div class="jlp-bar-track">
							<div class="jlp-bar-fill jlp-bar-target" style="width: {budgetShare}%"></div>
						</div>
					</div>
				{/if}
				<ul class="jlp-notes">
					{#each overview.metrics.filter((metric) => metric.comparison_note) as metric (metric.id)}
						<li><strong>{metric.label}.</strong> {metric.comparison_note}</li>
					{/each}
				</ul>
			{:else}
				<h3 id="jlp-left-title" class="jlp-surface-title">
					{$i18n.t('Assumptions behind the targets')}
				</h3>
				<!-- A region that scrolls sideways must be reachable by keyboard (WCAG 2.1.1). -->
				<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
				<div
					class="jlp-table-scroll"
					role="region"
					aria-label={$i18n.t('Assumptions')}
					tabindex="0"
				>
					<table class="jlp-table">
						<thead>
							<tr>
								<th scope="col">{$i18n.t('Driver')}</th>
								<th scope="col">{$i18n.t('In the draft')}</th>
								<th scope="col">{$i18n.t('Watch')}</th>
							</tr>
						</thead>
						<tbody>
							{#each overview.assumptions as assumption (assumption.id)}
								<tr class:jlp-row-selected={recordId === assumption.id}>
									<td>
										<strong id="assumption-{assumption.id}" class="jlp-cell-title"
											>{assumption.label}</strong
										>
										<span class="jlp-row-buttons">
											<button
												type="button"
												class="jlp-link"
												aria-pressed={recordId === assumption.id}
												aria-describedby="assumption-{assumption.id}"
												on:click={() => select(assumption.id)}>{$i18n.t('Select')}</button
											>
											{#each assumption.source_ids as id (id)}
												<button
													type="button"
													class="jlp-link"
													aria-describedby="assumption-{assumption.id}"
													on:click={() => openSource(id)}>{$i18n.t('Source')}</button
												>
											{/each}
										</span>
									</td>
									<td>{assumption.target_note}</td>
									<td>{assumption.watch_note}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<section class="jlp-surface" aria-labelledby="jlp-right-title">
			<div class="jlp-surface-head">
				<h3 id="jlp-right-title" class="jlp-surface-title">
					{view === 'board' ? $i18n.t('Follow-ups not yet closed') : $i18n.t('Related follow-ups')}
				</h3>
				<button type="button" class="jlp-link" on:click={() => (registerOpen = true)}
					>{$i18n.t('Open the register')}</button
				>
			</div>
			<p class="jlp-meta">
				{#if isSampleRegister(overview)}
					{$i18n.t('{{count}} examples from the presentation · not a total', {
						count: overview.actions.length
					})}
				{:else}
					{$i18n.t('{{count}} open of {{total}} recorded actions', {
						count: shortList(overview).length,
						total: overview.actions.length
					})}
				{/if}
			</p>
			{#if overview.actions_note}
				<p class="jlp-meta">{serverText[overview.actions_note] ?? overview.actions_note}</p>
			{/if}
			<ul class="jlp-mini-list">
				{#each shortList(overview) as action (action.id)}
					<li class="jlp-mini" class:jlp-row-selected={recordId === action.id}>
						<strong id="mini-action-{action.id}">{action.title}</strong>
						<span class="jlp-meta jlp-block">{action.owner_label}</span>
						<span class="jlp-meta jlp-block">
							{$i18n.t('Target')}: {action.due ? action.due.label : $i18n.t('No target recorded')} ·
							{isSampleRegister(overview)
								? $i18n.t('Ongoing according to the source')
								: (MINI_STATE[action.state] ?? action.state)}
						</span>
						{#if !isSampleRegister(overview)}
							<button
								type="button"
								class="jlp-link"
								aria-describedby="mini-action-{action.id}"
								on:click={() => openDetail(action.id)}>{$i18n.t('Details')}</button
							>
						{/if}
					</li>
				{/each}
			</ul>
			<p class="jlp-meta mt-2">
				{$i18n.t(
					'The PIC submits completion evidence; only the BOD closes an action or returns it. A finished ERP task or a missing slide does not close it.'
				)}
			</p>
		</section>
	</div>

	{#if !isSampleRegister(overview) && $leadershipAccess.operations.includes('bod.review')}
		<!-- The BOD's queue. Whether a reviewer may decide is still the server's call per action. -->
		<section class="jlp-surface mt-4" aria-labelledby="jlp-queue-title">
			<h3 id="jlp-queue-title" class="jlp-surface-title">
				{$i18n.t('Waiting for a BOD decision')}
			</h3>
			{#if awaitingReview(overview.actions).length === 0}
				<p class="jlp-meta">{$i18n.t('Nothing is waiting for a BOD decision.')}</p>
			{:else}
				<ul class="jlp-mini-list">
					{#each awaitingReview(overview.actions) as action (action.id)}
						<li class="jlp-mini">
							<strong>{action.title}</strong>
							<span class="jlp-meta jlp-block">{action.owner_label}</span>
							<button type="button" class="jlp-link" on:click={() => openDetail(action.id)}
								>{$i18n.t('Review')}</button
							>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}

	<MeetingChanges {view} {scopeId} bind:available={changesAvailable} />

	<MeetingHistory {view} {scopeId} />

	{#if view === 'rka'}
		<RkaRecords {scopeId} />
	{/if}

	{#if $leadershipAccess.operations.includes('imports.review')}
		<ImportReview {view} {scopeId} />
	{/if}

	<section class="jlp-surface mt-4" aria-labelledby="jlp-modules-title">
		<h3 id="jlp-modules-title" class="jlp-surface-title">{$i18n.t('Discussion modules')}</h3>
		<ul class="jlp-modules">
			{#each overview.module_states as module (module.id)}
				<li class="jlp-module">
					<span class="jlp-module-label">{module.label}</span>
					{#if module.id === 'prior-meeting-change' && changesAvailable}
						<!-- The dataset predates the meeting records; the comparison above is real data. -->
						<span class="jlp-status">{MODULE_STATE.available}</span>
						<span class="jlp-meta jlp-block"
							>{$i18n.t('Compared from the two latest published meeting records.')}</span
						>
					{:else}
						<span class="jlp-status">{MODULE_STATE[module.state] ?? module.state}</span>
						<span class="jlp-meta jlp-block">{module.reason}</span>
					{/if}
				</li>
			{/each}
		</ul>
	</section>

	<SourceDetails bind:show={sourceOpen} {view} {scopeId} {sourceId} />

	<ActionDetail
		bind:show={detailOpen}
		{view}
		{scopeId}
		actionId={detailId}
		on:changed={() => load(loadKey, true)}
	/>

	<ContextPreview bind:show={previewOpen} {viewLabel} context={overview.context} {recordLabel} />

	{#if registerOpen}
		<!-- The full register is a detail view: same records, every column. -->
		<Modal size="lg" bind:show={registerOpen} ariaLabelledby="jlp-register-title">
			<div class="jlp-root jlp-dialog" role="document">
				<div class="jlp-dialog-head">
					<h2 class="jlp-dialog-title" id="jlp-register-title">
						{$i18n.t('Follow-up register across meetings')}
					</h2>
					<button type="button" class="jlp-link" on:click={() => (registerOpen = false)}
						>{$i18n.t('Close')}</button
					>
				</div>
				<ActionRegister
					actions={overview.actions}
					selectedId={recordId}
					source={overview.actions_source}
					partial={isSampleRegister(overview) && overview.coverage === 'partial'}
					on:source={(event) => openSource(event.detail)}
					on:select={(event) => select(event.detail)}
					on:detail={(event) => openDetail(event.detail)}
				/>
				{#if isSampleRegister(overview)}
					<p class="jlp-meta mt-3">
						{$i18n.t(
							'Origin meetings, earlier updates and due-date history are not in this example. The full register arrives with the persistent action record.'
						)}
					</p>
				{/if}
			</div>
		</Modal>
	{/if}
{/if}
