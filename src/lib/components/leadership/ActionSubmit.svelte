<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import {
		postEvidence,
		postProgress,
		postState,
		LeadershipRequestError,
		type ActionRecord,
		type LeadershipView
	} from '$lib/apis/leadership';
	import {
		allowedPurposes,
		evidenceProblem,
		newIdempotencyKey,
		ownerMoves,
		type EvidencePurpose,
		type OwnerMove
	} from '$lib/leadership/submit';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ saved: void }>();

	// Shown only to the action's recorded PIC holding `actions.submit`. The server checks both
	// again on every write; this form never decides whether a submission is accepted.
	export let record: ActionRecord;
	export let view: LeadershipView;
	export let scopeId: string;

	let tab: 'progress' | 'evidence' = 'progress';
	let busy = false;
	let problem: string | null = null;
	let done: string | null = null;

	// Progress
	let narrative = '';
	let blocker = '';
	let nextStep = '';
	let remainingWork = '';
	let progressKey = newIdempotencyKey();

	// State: the PIC's start, block and unblock
	let blockReason = '';
	let stateKey = newIdempotencyKey();
	$: moves = ownerMoves(record.action.state);

	// Evidence
	let purpose: EvidencePurpose = 'evidence';
	let mode: 'file' | 'link' = 'file';
	let files: FileList | null = null;
	let url = '';
	let reason = '';
	let replacementActionId = '';
	let note = '';
	let evidenceKey = newIdempotencyKey();

	$: purposes = allowedPurposes(record.action.state);
	$: if (!purposes.includes(purpose)) purpose = 'evidence';

	$: PURPOSE = {
		evidence: $i18n.t('Evidence only; the action stays open'),
		completed: $i18n.t('Completion: ask the BOD to close'),
		cancelled: $i18n.t('Cancellation: ask the BOD to close as cancelled'),
		superseded: $i18n.t('Supersession: ask the BOD to close in favour of another action')
	} as Record<string, string>;

	$: PROBLEM = {
		file_missing: $i18n.t('Choose a file.'),
		link_not_https: $i18n.t('The link must be an https address.'),
		reason_missing: $i18n.t('A cancellation needs its reason.'),
		replacement_missing: $i18n.t('Name the action that replaces this one.'),
		not_in_progress: $i18n.t('Completion can be submitted only while the action is in progress.'),
		request_open: $i18n.t('A closure request is already waiting for the BOD.')
	} as Record<string, string>;

	const refused = (caught: unknown): string => {
		if (caught instanceof LeadershipRequestError) {
			if (caught.isConflict && caught.conflict?.version !== undefined) {
				return $i18n.t('This action changed since you opened it. Reload and try again.');
			}
			if (caught.isAccessDenied) {
				return $i18n.t("Only this action's recorded PIC can submit on it.");
			}
			if (caught.isUnavailable)
				return $i18n.t('Evidence storage is not configured on this server.');
			// A 422 names the rule the server applied, in its own words.
			return caught.message;
		}
		return `${caught}`;
	};

	const submitProgress = async () => {
		problem = null;
		done = null;
		if (!narrative.trim()) {
			problem = $i18n.t('Write what happened since the last update.');
			return;
		}
		busy = true;
		try {
			await postProgress(localStorage.token, view, scopeId, record.action.id, {
				expected_version: record.action.version,
				narrative: narrative.trim(),
				blocker: blocker.trim() || null,
				next_step: nextStep.trim() || null,
				remaining_work: remainingWork.trim() || null,
				idempotency_key: progressKey
			});
			narrative = blocker = nextStep = remainingWork = '';
			progressKey = newIdempotencyKey();
			done = $i18n.t('Progress recorded.');
			dispatch('saved');
		} catch (caught) {
			problem = refused(caught);
		} finally {
			busy = false;
		}
	};

	const moveTo = async (to: OwnerMove) => {
		problem = null;
		done = null;
		if (to === 'blocked' && !blockReason.trim()) {
			problem = $i18n.t('Say what blocks the action.');
			return;
		}
		busy = true;
		try {
			await postState(localStorage.token, view, scopeId, record.action.id, {
				expected_version: record.action.version,
				to_state: to,
				reason: to === 'blocked' ? blockReason.trim() : null,
				idempotency_key: stateKey
			});
			blockReason = '';
			stateKey = newIdempotencyKey();
			done = $i18n.t('State changed.');
			dispatch('saved');
		} catch (caught) {
			problem = refused(caught);
		} finally {
			busy = false;
		}
	};

	const submitEvidence = async () => {
		problem = null;
		done = null;
		const file = files?.[0] ?? null;
		const found = evidenceProblem(
			{ purpose, mode, file, url, reason, replacementActionId },
			record.action.state
		);
		if (found) {
			problem = PROBLEM[found];
			return;
		}
		busy = true;
		try {
			const common = {
				expected_version: record.action.version,
				closure_kind: purpose === 'evidence' ? null : purpose,
				reason: purpose === 'cancelled' ? reason.trim() : null,
				replacement_action_id: purpose === 'superseded' ? replacementActionId.trim() : null,
				note: note.trim() || null,
				idempotency_key: evidenceKey
			};
			const result = await postEvidence(
				localStorage.token,
				view,
				scopeId,
				record.action.id,
				mode === 'file' && file ? { ...common, file } : { ...common, url: url.trim() }
			);
			files = null;
			url = reason = replacementActionId = note = '';
			purpose = 'evidence';
			evidenceKey = newIdempotencyKey();
			done = result.closure_request_id
				? $i18n.t('Evidence recorded. The BOD now reviews the closure request.')
				: $i18n.t('Evidence recorded.');
			dispatch('saved');
		} catch (caught) {
			problem = refused(caught);
		} finally {
			busy = false;
		}
	};
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-submit-title">
	<h3 class="jlp-surface-title" id="jlp-submit-title">{$i18n.t('Your update as PIC')}</h3>
	<div class="jlp-row-buttons" role="group" aria-label={$i18n.t('Update type')}>
		<button
			type="button"
			class="jlp-link"
			aria-pressed={tab === 'progress'}
			on:click={() => (tab = 'progress')}>{$i18n.t('Progress')}</button
		>
		<button
			type="button"
			class="jlp-link"
			aria-pressed={tab === 'evidence'}
			on:click={() => (tab = 'evidence')}>{$i18n.t('Evidence')}</button
		>
	</div>

	{#if record.action.state === 'closed'}
		<p class="jlp-meta mt-2">
			{$i18n.t('This action is closed. Only a BOD reopening makes it editable again.')}
		</p>
	{:else if tab === 'progress'}
		{#if moves.length > 0}
			<div class="jlp-form" role="group" aria-label={$i18n.t('Action state')}>
				{#if moves.includes('blocked')}
					<label class="jlp-field">
						<span>{$i18n.t('What blocks the action')}</span>
						<textarea bind:value={blockReason} rows="2" maxlength="10000"></textarea>
					</label>
				{/if}
				<div class="jlp-row-buttons">
					{#if moves.includes('in_progress')}
						<button
							type="button"
							class="jlp-button"
							disabled={busy}
							on:click={() => moveTo('in_progress')}
							>{record.action.state === 'blocked'
								? $i18n.t('Resume work')
								: $i18n.t('Start work')}</button
						>
					{/if}
					{#if moves.includes('blocked')}
						<button
							type="button"
							class="jlp-button"
							disabled={busy}
							on:click={() => moveTo('blocked')}>{$i18n.t('Mark blocked')}</button
						>
					{/if}
				</div>
				<p class="jlp-meta">
					{$i18n.t('Completion can be submitted as evidence once the action is in progress.')}
				</p>
			</div>
		{/if}
		<form class="jlp-form" on:submit|preventDefault={submitProgress}>
			<label class="jlp-field">
				<span>{$i18n.t('What happened since the last update')}</span>
				<textarea bind:value={narrative} rows="3" maxlength="10000" required></textarea>
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('Remaining work')}</span>
				<textarea bind:value={remainingWork} rows="2" maxlength="10000"></textarea>
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('Blocker')}</span>
				<textarea bind:value={blocker} rows="2" maxlength="10000"></textarea>
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('Next step')}</span>
				<textarea bind:value={nextStep} rows="2" maxlength="10000"></textarea>
			</label>
			<button type="submit" class="jlp-button" disabled={busy}>{$i18n.t('Record progress')}</button>
			<p class="jlp-meta">{$i18n.t('A progress update never changes the state.')}</p>
		</form>
	{:else}
		<form class="jlp-form" on:submit|preventDefault={submitEvidence}>
			<fieldset class="jlp-field">
				<legend>{$i18n.t('What this evidence is for')}</legend>
				{#each purposes as option (option)}
					<label class="jlp-choice">
						<input type="radio" bind:group={purpose} value={option} />
						{PURPOSE[option]}
					</label>
				{/each}
			</fieldset>
			<fieldset class="jlp-field">
				<legend>{$i18n.t('Evidence')}</legend>
				<label class="jlp-choice">
					<input type="radio" bind:group={mode} value="file" />
					{$i18n.t('File')}
				</label>
				<label class="jlp-choice">
					<input type="radio" bind:group={mode} value="link" />
					{$i18n.t('Link')}
				</label>
				{#if mode === 'file'}
					<input type="file" bind:files aria-label={$i18n.t('Evidence file')} />
				{:else}
					<input
						type="url"
						bind:value={url}
						placeholder="https://"
						maxlength="2000"
						aria-label={$i18n.t('Evidence link')}
					/>
				{/if}
			</fieldset>
			{#if purpose === 'cancelled'}
				<label class="jlp-field">
					<span>{$i18n.t('Reason for cancellation')}</span>
					<textarea bind:value={reason} rows="2" maxlength="10000"></textarea>
				</label>
			{:else if purpose === 'superseded'}
				<label class="jlp-field">
					<span>{$i18n.t('Id of the replacing action')}</span>
					<input type="text" bind:value={replacementActionId} maxlength="64" />
				</label>
			{/if}
			<label class="jlp-field">
				<span>{$i18n.t('Note')}</span>
				<textarea bind:value={note} rows="2" maxlength="10000"></textarea>
			</label>
			<button type="submit" class="jlp-button" disabled={busy}>{$i18n.t('Submit evidence')}</button>
			<p class="jlp-meta">
				{$i18n.t('Only the BOD closes an action. A request waits for their decision.')}
			</p>
		</form>
	{/if}

	<div aria-live="polite">
		{#if problem}
			<p class="jlp-notice jlp-notice-refused mt-2"><ServerText text={problem} /></p>
		{:else if done}
			<p class="jlp-notice mt-2">{done}</p>
		{/if}
	</div>
</section>
