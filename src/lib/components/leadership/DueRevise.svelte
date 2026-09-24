<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import {
		postDueRevision,
		LeadershipRequestError,
		type ActionRecord,
		type LeadershipView
	} from '$lib/apis/leadership';
	import { dueProblem, newIdempotencyKey, type DuePrecision } from '$lib/leadership/submit';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ saved: void }>();

	// Shown to a `bod.review` holder who is not this action's PIC (Erik, 2026-09-24: a due date
	// is the BOD's to move). The server checks the grant, the owner and the rules again.
	export let record: ActionRecord;
	export let view: LeadershipView;
	export let scopeId: string;

	let precision: DuePrecision = 'month';
	let value = '';
	let reason = '';
	let busy = false;
	let problem: string | null = null;
	let done: string | null = null;
	let key = newIdempotencyKey();

	$: PLACEHOLDER = {
		date: '2026-11-30',
		month: '2026-11',
		year: '2027',
		year_range: '2026/2027'
	} as Record<DuePrecision, string>;

	const submit = async () => {
		problem = null;
		done = null;
		const found = dueProblem(precision, value);
		if (found === 'value_missing') {
			problem = $i18n.t('Enter the new due date.');
			return;
		}
		if (found === 'value_shape') {
			problem = $i18n.t('Write the date as {{example}}.', { example: PLACEHOLDER[precision] });
			return;
		}
		if (!reason.trim()) {
			problem = $i18n.t('Moving a due date needs a reason.');
			return;
		}
		busy = true;
		try {
			await postDueRevision(localStorage.token, view, scopeId, record.action.id, {
				expected_version: record.action.version,
				due: { precision, value: value.trim() },
				reason: reason.trim(),
				idempotency_key: key
			});
			value = reason = '';
			key = newIdempotencyKey();
			done = $i18n.t('Due date revised. The original stays on record.');
			dispatch('saved');
		} catch (caught) {
			if (caught instanceof LeadershipRequestError && caught.isConflict) {
				problem = $i18n.t('This action changed since you opened it. Reload and try again.');
				dispatch('saved');
			} else {
				// A 422 names the rule the server applied, in its own words.
				problem = caught instanceof Error ? caught.message : `${caught}`;
			}
		} finally {
			busy = false;
		}
	};
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-due-title">
	<h3 class="jlp-surface-title" id="jlp-due-title">{$i18n.t('Revise the due date')}</h3>
	{#if record.action.state === 'closed'}
		<p class="jlp-meta">{$i18n.t('A closed action keeps its due date.')}</p>
	{:else}
		<form class="jlp-form" on:submit|preventDefault={submit}>
			<label class="jlp-field">
				<span>{$i18n.t('Precision')}</span>
				<select bind:value={precision}>
					<option value="date">{$i18n.t('Day')}</option>
					<option value="month">{$i18n.t('Month')}</option>
					<option value="year">{$i18n.t('Year')}</option>
					<option value="year_range">{$i18n.t('Year range')}</option>
				</select>
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('New due date')}</span>
				<input
					type="text"
					bind:value
					maxlength="16"
					autocomplete="off"
					placeholder={PLACEHOLDER[precision]}
				/>
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('Reason (required)')}</span>
				<textarea bind:value={reason} rows="2" maxlength="10000"></textarea>
			</label>
			<button type="submit" class="jlp-button" disabled={busy}
				>{$i18n.t('Record the new date')}</button
			>
			<p class="jlp-meta">
				{$i18n.t(
					'The original due date is never changed; each revision is recorded with its reason.'
				)}
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
