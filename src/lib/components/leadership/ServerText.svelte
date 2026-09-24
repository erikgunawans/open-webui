<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import {
		cleanServerText,
		recogniseServerText,
		type ServerTextCode
	} from '$lib/leadership/refusals';

	const i18n: Writable<i18nType> = getContext('i18n');

	// Text that may have come from the server: a refusal, a flag reason, or a message the caller
	// already translated. Recognised server text is shown in the reader's language; anything else
	// as it is.
	export let text: string;

	$: found = recogniseServerText(text);
	$: values = found?.values ?? {};

	let TEXT: Record<ServerTextCode, string>;
	$: TEXT = {
		due_unchanged: $i18n.t('The due date is unchanged. A revision must move it.'),
		due_invalid: $i18n.t('That due date is not valid for its precision.'),
		pic_locked: $i18n.t('The PIC cannot change while a closure request is with the BOD.'),
		pic_unchanged: $i18n.t(
			'The PIC is unchanged. An assignment must change who or how they are named.'
		),
		no_account: $i18n.t('No account has that email.'),
		action_closed: $i18n.t('The action is closed. Only a BOD decision can reopen it.'),
		owner_cannot_close: $i18n.t(
			'The PIC cannot close an action. Closure is requested with evidence and decided by the BOD.'
		),
		owner_move_refused: $i18n.t('The action cannot move to that state from its current one.'),
		field_required: $i18n.t('A required field is empty: {{field}}.', { field: values.field }),
		key_reused: $i18n.t('This submission key was already used for a different change.'),
		not_the_pic: $i18n.t("Only this action's recorded PIC can submit on it."),
		pic_cannot_review: $i18n.t("An action's PIC cannot review its closure."),
		pic_cannot_move_due: $i18n.t("An action's PIC cannot move its due date."),
		link_not_https: $i18n.t('Link evidence must be an https:// address.'),
		file_or_link: $i18n.t('Send either a file or a link, not both.'),
		file_empty: $i18n.t('The evidence file is empty.'),
		file_type: $i18n.t('This file type is not accepted as evidence.'),
		file_too_large: $i18n.t('Evidence files are limited to {{size}}.', { size: values.size }),
		file_mismatch: $i18n.t('The file was declared as {{declared}} but its content is {{actual}}.', {
			declared: values.declared,
			actual: values.actual
		}),
		replacement_unknown: $i18n.t('There is no replacement action {{id}}.', { id: values.id }),
		replacement_missing: $i18n.t('A supersession request names its one replacement action.'),
		supersede_self: $i18n.t('An action cannot supersede itself.'),
		completion_not_in_progress: $i18n.t('Completion is requested only on an action in progress.'),
		request_open: $i18n.t('A closure request is already open on this action.'),
		reason_needed: $i18n.t('This needs a reason.'),
		already_voted: $i18n.t('You have already voted to close on this evidence.'),
		no_request_open: $i18n.t('No closure request is open on this action.'),
		not_reopenable: $i18n.t('Only a closed action with a recorded closure can be reopened.'),
		four_eyes: $i18n.t('Four-eyes publication: the author of a draft cannot publish it.'),
		already_published: $i18n.t('Only a draft is published. This version already is.'),
		date_format: $i18n.t('Write the date as YYYY-MM-DD.'),
		several_matches: $i18n.t(
			'This candidate matches several actions. Link it to the right one or reject it.'
		),
		already_matched: $i18n.t('This candidate is already matched. Accept or reject it.'),
		link_needs_action: $i18n.t('A link names an existing action.'),
		external_id_taken: $i18n.t('{{id}} already refers to another action.', { id: values.id }),
		recorded_since: $i18n.t(
			'{{id}} was recorded against an action after this file was imported. Link it instead.',
			{ id: values.id }
		),
		owner_label_missing: $i18n.t(
			'A new action needs its owner label, and this candidate has none. Link or reject it.'
		),
		already_reviewed: $i18n.t('This candidate was already reviewed.'),
		invalid_file: $i18n.t('The candidate file was refused: {{detail}}', { detail: values.detail }),
		malformed: $i18n.t('The server could not read this request. Reload the page and try again.'),
		flag_closed: $i18n.t('The action is closed.'),
		flag_no_due: $i18n.t('No due date is known.'),
		flag_due_not_day: $i18n.t('The due date is not a single day.'),
		flag_no_next_meeting: $i18n.t('No next meeting is scheduled.'),
		flag_no_stale_policy: $i18n.t('No staleness policy is recorded.'),
		flag_never_updated: $i18n.t('The PIC has not updated this action.')
	};
</script>

{found ? TEXT[found.code] : cleanServerText(text)}
