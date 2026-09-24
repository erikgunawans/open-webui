<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import {
		postClosureDecision,
		LeadershipRequestError,
		type ActionRecord,
		type LeadershipView
	} from '$lib/apis/leadership';
	import { formatEventTimeId } from '$lib/leadership/format';
	import { newIdempotencyKey, reviewProblem } from '$lib/leadership/submit';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ saved: void }>();

	// Shown to a holder of `bod.review` who is not the action's PIC. The server checks the grant,
	// the configured policy, the PIC rule and the evidence revision again on every decision.
	export let record: ActionRecord;
	export let view: LeadershipView;
	export let scopeId: string;

	let decision: 'close' | 'return' = 'close';
	let reason = '';
	let returnTo: 'in_progress' | 'blocked' | null = null;
	let busy = false;
	let problem: string | null = null;
	let done: string | null = null;
	let key = newIdempotencyKey();

	// The revision under review is always the latest: a newer one makes a decision on an older
	// one stale, and the server answers 409 naming the latest.
	$: latest = record.evidence.length ? record.evidence[record.evidence.length - 1] : null;
	$: awaiting = record.action.state === 'awaiting_bod_closure';
	$: closed = record.action.state === 'closed';

	$: PROBLEM = {
		reason_missing: $i18n.t('Give the reason for this decision.'),
		return_to_missing: $i18n.t('Choose where the action goes back to.'),
		no_evidence: $i18n.t('There is no evidence revision to decide on.')
	} as Record<string, string>;

	$: OUTCOME = {
		closed: $i18n.t('The action is closed.'),
		vote_recorded: $i18n.t('Your vote to close is recorded; the quorum is not yet reached.'),
		returned: $i18n.t('The action is returned to the PIC.'),
		reopened: $i18n.t('The action is reopened.')
	} as Record<string, string>;

	const refused = (caught: unknown): string => {
		if (caught instanceof LeadershipRequestError) {
			if (caught.isConflict && caught.conflict?.evidence_id) {
				return $i18n.t(
					'The evidence changed since you reviewed it. The latest revision is now shown; review it before deciding.'
				);
			}
			if (caught.isConflict) {
				return $i18n.t('This action changed since you opened it. Reload and try again.');
			}
			if (caught.isAccessDenied) return $i18n.t("An action's PIC cannot review its closure.");
			if (caught.isUnavailable) return $i18n.t('BOD closure is not configured on this server.');
			return caught.message;
		}
		return `${caught}`;
	};

	const submit = async (chosen: 'close' | 'return' | 'reopen') => {
		problem = null;
		done = null;
		const found = reviewProblem({
			decision: chosen,
			reason,
			returnTo,
			evidenceId: chosen === 'reopen' ? null : (latest?.id ?? null)
		});
		if (found) {
			problem = PROBLEM[found];
			return;
		}
		busy = true;
		try {
			const result = await postClosureDecision(
				localStorage.token,
				view,
				scopeId,
				record.action.id,
				{
					expected_version: record.action.version,
					decision: chosen,
					evidence_id: chosen === 'reopen' ? null : latest?.id,
					reason: reason.trim() || null,
					return_to: chosen === 'return' ? returnTo : null,
					idempotency_key: key
				}
			);
			reason = '';
			returnTo = null;
			key = newIdempotencyKey();
			done =
				result.outcome === 'vote_recorded'
					? $i18n.t('Your vote to close is recorded ({{votes}} of {{quorum}}).', {
							votes: result.close_votes,
							quorum: result.quorum
						})
					: OUTCOME[result.outcome];
			dispatch('saved');
		} catch (caught) {
			problem = refused(caught);
			// A stale revision or version: reload so the reviewer sees what is current now.
			if (caught instanceof LeadershipRequestError && caught.isConflict) dispatch('saved');
		} finally {
			busy = false;
		}
	};
</script>

{#if awaiting || closed}
	<section class="jlp-surface mt-4" aria-labelledby="jlp-review-title">
		<h3 class="jlp-surface-title" id="jlp-review-title">{$i18n.t('BOD decision')}</h3>

		{#if awaiting}
			{#if latest}
				<p class="jlp-meta">
					{$i18n.t('You are deciding on evidence revision {{revision}}, submitted {{at}}.', {
						revision: latest.revision,
						at: formatEventTimeId(latest.created_at)
					})}
				</p>
			{/if}
			<form class="jlp-form" on:submit|preventDefault={() => submit(decision)}>
				<fieldset class="jlp-field">
					<legend>{$i18n.t('Decision')}</legend>
					<label class="jlp-choice">
						<input type="radio" bind:group={decision} value="close" />
						{$i18n.t('Close the action')}
					</label>
					<label class="jlp-choice">
						<input type="radio" bind:group={decision} value="return" />
						{$i18n.t('Return it to the PIC')}
					</label>
				</fieldset>
				{#if decision === 'return'}
					<fieldset class="jlp-field">
						<legend>{$i18n.t('Goes back to')}</legend>
						<label class="jlp-choice">
							<input type="radio" bind:group={returnTo} value="in_progress" />
							{$i18n.t('In progress')}
						</label>
						<label class="jlp-choice">
							<input type="radio" bind:group={returnTo} value="blocked" />
							{$i18n.t('Blocked')}
						</label>
					</fieldset>
				{/if}
				<label class="jlp-field">
					<span
						>{decision === 'return'
							? $i18n.t('Reason (required)')
							: $i18n.t('Reason (optional)')}</span
					>
					<textarea bind:value={reason} rows="2" maxlength="10000"></textarea>
				</label>
				<button type="submit" class="jlp-button" disabled={busy || !latest}
					>{decision === 'close'
						? $i18n.t('Record the closure')
						: $i18n.t('Record the return')}</button
				>
			</form>
		{:else}
			<form class="jlp-form" on:submit|preventDefault={() => submit('reopen')}>
				<p class="jlp-meta">
					{$i18n.t('Reopening keeps the earlier closure in the history.')}
				</p>
				<label class="jlp-field">
					<span>{$i18n.t('Reason (required)')}</span>
					<textarea bind:value={reason} rows="2" maxlength="10000"></textarea>
				</label>
				<button type="submit" class="jlp-button" disabled={busy}
					>{$i18n.t('Reopen the action')}</button
				>
			</form>
		{/if}

		<div aria-live="polite">
			{#if problem}
				<p class="jlp-notice jlp-notice-refused mt-2">{problem}</p>
			{:else if done}
				<p class="jlp-notice mt-2">{done}</p>
			{/if}
		</div>
	</section>
{/if}
