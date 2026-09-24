// The server writes its refusals and flag reasons in English. They are recognised here and turned
// into codes so a component can show each as a literal `$i18n.t` key (the extractor never sees a
// computed key). Text that is not recognised is shown as the server sent it: a new server message
// reads in English until it is added here, never as nothing.

export type ServerTextCode =
	// Actions
	| 'due_unchanged'
	| 'due_invalid'
	| 'pic_locked'
	| 'pic_unchanged'
	| 'no_account'
	| 'action_closed'
	| 'owner_cannot_close'
	| 'owner_move_refused'
	| 'field_required'
	| 'key_reused'
	| 'not_the_pic'
	| 'pic_cannot_review'
	| 'pic_cannot_move_due'
	// Evidence and closure requests
	| 'link_not_https'
	| 'file_or_link'
	| 'file_empty'
	| 'file_type'
	| 'file_too_large'
	| 'file_mismatch'
	| 'replacement_unknown'
	| 'replacement_missing'
	| 'supersede_self'
	| 'completion_not_in_progress'
	| 'request_open'
	| 'reason_needed'
	// BOD decisions
	| 'already_voted'
	| 'no_request_open'
	| 'not_reopenable'
	// Meeting records
	| 'four_eyes'
	| 'already_published'
	| 'date_format'
	// Imports
	| 'several_matches'
	| 'already_matched'
	| 'link_needs_action'
	| 'external_id_taken'
	| 'recorded_since'
	| 'owner_label_missing'
	| 'already_reviewed'
	| 'invalid_file'
	// A request body the server could not read at all (FastAPI's validation list).
	| 'malformed'
	// Flag reasons
	| 'flag_closed'
	| 'flag_no_due'
	| 'flag_due_not_day'
	| 'flag_no_next_meeting'
	| 'flag_no_stale_policy'
	| 'flag_never_updated';

export type ServerText = { code: ServerTextCode; values: Record<string, string> };

const EXACT: Record<string, ServerTextCode> = {
	'the due date is unchanged; a revision must move it': 'due_unchanged',
	'the PIC cannot change while a closure request is with the BOD': 'pic_locked',
	'the PIC is unchanged; an assignment must change who or how they are named': 'pic_unchanged',
	'No account has that email.': 'no_account',
	'the action is closed; only a BOD decision can reopen it': 'action_closed',
	'This submission key was already used for a different change.': 'key_reused',
	"Only this action's recorded PIC can submit on it.": 'not_the_pic',
	"An action's PIC cannot review its closure.": 'pic_cannot_review',
	"An action's PIC cannot move its due date.": 'pic_cannot_move_due',
	'link evidence must be an https URL': 'link_not_https',
	'Send exactly one of a file or a link.': 'file_or_link',
	'the evidence file is empty': 'file_empty',
	'this file type is not accepted as evidence': 'file_type',
	'a supersession request, and only one, names its replacement action': 'replacement_missing',
	'an action cannot supersede itself': 'supersede_self',
	'a closure request is already open on this action': 'request_open',
	'this reviewer has already voted to close on this evidence': 'already_voted',
	'no closure request is open on this action': 'no_request_open',
	'this action has no recorded closure to reopen': 'not_reopenable',
	'four-eyes publication: the author of a draft cannot publish it': 'four_eyes',
	'only a draft is published; this version already is': 'already_published',
	'this candidate matches several actions; link it to the right one or reject it':
		'several_matches',
	'this candidate is already matched; accept or reject it': 'already_matched',
	'link names an existing action': 'link_needs_action',
	'This candidate was already reviewed.': 'already_reviewed',
	'the action is closed': 'flag_closed',
	'no due date is known': 'flag_no_due',
	'no next meeting is scheduled': 'flag_no_next_meeting',
	'no staleness policy is recorded': 'flag_no_stale_policy',
	'the owner has not updated this action': 'flag_never_updated'
};

// Messages the server builds around a value. Order matters only where two could match; the more
// specific pattern comes first.
const PATTERNS: [RegExp, ServerTextCode, string[]][] = [
	[/^an owner cannot move an action to '[^']+'; closure is requested/, 'owner_cannot_close', []],
	[/^an owner cannot move an action from '[^']+' to '[^']+'$/, 'owner_move_refused', []],
	[/^evidence files are limited to (\d+) bytes$/, 'file_too_large', ['bytes']],
	[
		/^the file was declared as (.+) but its content is (.+)$/,
		'file_mismatch',
		['declared', 'actual']
	],
	[/^no replacement action '([^']+)'$/, 'replacement_unknown', ['id']],
	[/^completion evidence is submitted on an action in progress/, 'completion_not_in_progress', []],
	[/^no closure request is open on an action that is '[^']+'$/, 'no_request_open', []],
	[/^only a closed action is reopened/, 'not_reopenable', []],
	[/^'.+' is not an? \w+ due date$/, 'due_invalid', []],
	[/^'.+' has no month \d+$/, 'due_invalid', []],
	[/^'.+' ends before it starts$/, 'due_invalid', []],
	[/^\w+ must be a YYYY-MM-DD date$/, 'date_format', []],
	[/^'([^']+)' already refers to another action$/, 'external_id_taken', ['id']],
	[
		/^'([^']+)' has been recorded against an action since this deck was imported/,
		'recorded_since',
		['id']
	],
	[/^a new action needs its owner label/, 'owner_label_missing', []],
	[/^the due date is (\w+)-precise, not a day$/, 'flag_due_not_day', ['precision']],
	[/^(\w+) is required$/, 'field_required', ['field']],
	[/^.+ needs a reason$/, 'reason_needed', []]
];

// `${error}` on an Error prepends its name; the message is what the server said.
const ERROR_PREFIX = /^\w*Error: /;

export const cleanServerText = (text: string): string => text.replace(ERROR_PREFIX, '');

export const recogniseServerText = (raw: string): ServerText | null => {
	const text = cleanServerText(raw.trim());
	const exact = EXACT[text];
	if (exact) return { code: exact, values: {} };
	for (const [pattern, code, names] of PATTERNS) {
		const match = pattern.exec(text);
		if (match) {
			const values: Record<string, string> = {};
			names.forEach((name, index) => (values[name] = match[index + 1]));
			if (code === 'file_too_large') values.size = megabytes(Number(values.bytes));
			return { code, values };
		}
	}
	// A candidate file's rule breaches name a JSON path ("$.candidates[0].due: ..."), and a body
	// FastAPI could not validate arrives as its error list. Both keep their detail for whoever fixes
	// the file; only the sentence around it is translated.
	if (text.startsWith('$') || text.startsWith('the file is not UTF-8 JSON')) {
		return { code: 'invalid_file', values: { detail: text } };
	}
	if (text.startsWith('[{')) return { code: 'malformed', values: {} };
	return null;
};

const megabytes = (bytes: number): string => {
	const mb = bytes / (1024 * 1024);
	return Number.isInteger(mb) ? `${mb} MB` : `${mb.toFixed(1)} MB`;
};
