<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ServerText from './ServerText.svelte';

	import {
		postPicAssignment,
		LeadershipRequestError,
		type ActionRecord,
		type LeadershipView
	} from '$lib/apis/leadership';
	import { newIdempotencyKey } from '$lib/leadership/submit';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ saved: void }>();

	// Shown to an `actions.assign` holder. The server checks the grant, the person and the
	// action's state again; the PIC it names is the only one who can submit evidence.
	export let record: ActionRecord;
	export let view: LeadershipView;
	export let scopeId: string;

	let email = '';
	let label = '';
	let reason = '';
	let busy = false;
	let problem: string | null = null;
	let done: string | null = null;
	let key = newIdempotencyKey();

	$: replacing = record.action.pic_user_id !== null;
	$: locked = record.action.state === 'closed' || record.action.state === 'awaiting_bod_closure';

	const submit = async () => {
		problem = null;
		done = null;
		if (!email.trim()) {
			problem = $i18n.t('Enter the email the PIC signs in with.');
			return;
		}
		if (replacing && !reason.trim()) {
			problem = $i18n.t('Replacing a PIC needs a reason.');
			return;
		}
		busy = true;
		try {
			await postPicAssignment(localStorage.token, view, scopeId, record.action.id, {
				expected_version: record.action.version,
				pic_email: email.trim(),
				pic_label: label.trim() || null,
				reason: reason.trim() || null,
				idempotency_key: key
			});
			email = label = reason = '';
			key = newIdempotencyKey();
			done = $i18n.t('PIC assigned.');
			dispatch('saved');
		} catch (caught) {
			if (caught instanceof LeadershipRequestError && caught.isConflict) {
				problem = $i18n.t('This action changed since you opened it. Reload and try again.');
				dispatch('saved');
			} else {
				problem = caught instanceof Error ? caught.message : `${caught}`;
			}
		} finally {
			busy = false;
		}
	};
</script>

<section class="jlp-surface mt-4" aria-labelledby="jlp-pic-title">
	<h3 class="jlp-surface-title" id="jlp-pic-title">
		{replacing ? $i18n.t('Replace the PIC') : $i18n.t('Assign the PIC')}
	</h3>
	{#if locked}
		<p class="jlp-meta">
			{$i18n.t(
				'The PIC cannot change on a closed action or while a closure request is with the BOD.'
			)}
		</p>
	{:else}
		<form class="jlp-form" on:submit|preventDefault={submit}>
			<label class="jlp-field">
				<span>{$i18n.t('Email the PIC signs in with')}</span>
				<input
					type="text"
					inputmode="email"
					autocomplete="off"
					bind:value={email}
					maxlength="320"
				/>
			</label>
			<label class="jlp-field">
				<span>{$i18n.t('Label shown for the PIC (optional)')}</span>
				<input
					type="text"
					bind:value={label}
					maxlength="500"
					placeholder={record.action.pic_label}
				/>
			</label>
			<label class="jlp-field">
				<span>{replacing ? $i18n.t('Reason (required)') : $i18n.t('Reason (optional)')}</span>
				<textarea bind:value={reason} rows="2" maxlength="10000"></textarea>
			</label>
			<button type="submit" class="jlp-button" disabled={busy}>{$i18n.t('Record the PIC')}</button>
			<p class="jlp-meta">{$i18n.t('Only the recorded PIC can submit progress and evidence.')}</p>
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
