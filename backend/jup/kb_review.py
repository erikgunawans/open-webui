"""The knowledge-base review queue: who may submit, who may decide, and what each step allows.

Staff contribute documents to the assistant's knowledge through a review, never directly (ADR-0015).
A submission is an ordinary vendor file uploaded through `POST /api/v1/files/`; its review state is
one key in that file's `meta`, `jup_kb_review`, so the queue needs no table and no migration. An
approved file is added to its own collection, **JUP Staff Contributions**, never to the Strategy
KB: `deploy/gcp/sync-kb.ts` runs a cleanup that deletes anything in that collection it did not put
there itself, so a hand-added file would vanish on the next sync.

Two authorities, decided by Erik on 2026-09-25:

- **Submitting** is a group grant, `permissions['jup']['kb']['submit'] is True`: an exact boolean,
  denied by default, held by nobody until an admin grants it. Same shape as
  `jup.leadership.policy.may_read`: a malformed grant is a denial, never a crash, and `"true"` or
  `1` in a group row does not count.
- **Reviewing** is the `admin` role, the same line Portfolio draws for the operating layer.

This module is pure: plain dicts in, plain dicts out, the standard library only, so
`uv run --only-group dev pytest` covers it without sqlalchemy or the vendor tree.
"""

import hashlib
from collections.abc import Iterable
from typing import Any

CONTRIBUTIONS_KB_NAME = 'JUP Staff Contributions'

CONTRIBUTIONS_KB_DESCRIPTION = (
    'Staff submissions that an admin reviewed and approved. Managed by the knowledge-base review '
    'queue (/kb-review); do not add or remove files here by hand.'
)

#: The key in `file.meta` that holds a submission's review. Its presence is what makes a file a
#: submission; a file without it has never been submitted.
META_KEY = 'jup_kb_review'

STATES: tuple[str, ...] = ('pending', 'approved', 'rejected')

#: The role that reviews. Portfolio's operating layer (`jup.portfolio.OPERATING_LAYER_ROLE`) is the
#: same answer; it is spelled out here so this module keeps its no-runtime-import promise.
REVIEW_ROLE = 'admin'

#: The note on a submission and the reason on a rejection share one ceiling.
TEXT_MAX = 1000

#: How much extracted text the reviewer's preview carries.
PREVIEW_CHARS = 20_000

#: File types whose text the vendor loader (`retrieval/loaders/main.py`, default engine) extracts:
#: markdown and plain text through the text loader, pdf, docx, pptx and xlsx through their own
#: loaders, csv through the CSV loader. Images and media are left out on purpose: their "content"
#: is OCR or a transcript at best, which is not a document a reviewer can read and vouch for.
ALLOWED_EXTENSIONS = frozenset({'md', 'txt', 'pdf', 'docx', 'pptx', 'xlsx', 'csv'})

DEFAULT_PERMISSIONS: dict[str, Any] = {'jup': {'kb': {'submit': False}}}


class ReviewRefused(Exception):
    """A request the rules refuse. Carries a stable `code` the frontend translates, and an HTTP status."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def may_submit(permissions: Any) -> bool:
    """True only for an exact boolean `jup.kb.submit` grant."""
    try:
        return permissions['jup']['kb']['submit'] is True
    except (KeyError, TypeError, IndexError):
        return False


def may_review(role: Any) -> bool:
    return role == REVIEW_ROLE


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ''


def clean_note(note: Any) -> str | None:
    """The submitter's optional note, trimmed; blank is no note."""
    text = _text(note)
    if len(text) > TEXT_MAX:
        raise ReviewRefused('note_too_long', f'The note is longer than {TEXT_MAX} characters.', 422)
    return text or None


def clean_reason(reason: Any) -> str:
    """A rejection's reason: required, because the submitter is owed an explanation."""
    text = _text(reason)
    if not text:
        raise ReviewRefused('reason_required', 'A rejection needs a reason.', 422)
    if len(text) > TEXT_MAX:
        raise ReviewRefused('reason_too_long', f'The reason is longer than {TEXT_MAX} characters.', 422)
    return text


def extension(filename: str) -> str:
    """The lower-cased extension, or '' when there is none (a dotfile has none either)."""
    stem, dot, ext = (filename or '').rpartition('.')
    return ext.lower() if dot and stem else ''


def content_of(data: Any) -> str:
    """The extracted text the vendor stored on the file, or ''."""
    content = data.get('content') if isinstance(data, dict) else None
    return content if isinstance(content, str) else ''


def review_of(meta: Any) -> dict[str, Any] | None:
    """The file's review, when it carries a well-formed one."""
    review = meta.get(META_KEY) if isinstance(meta, dict) else None
    if isinstance(review, dict) and review.get('state') in STATES:
        return review
    return None


def check_submittable(*, filename: str, owner_id: str, caller_id: str, data: Any, meta: Any) -> None:
    """Refuse a file that is not the caller's, not yet processed, of the wrong type, or already in the queue.

    Someone else's file answers `not_found`, the same as a file that does not exist, so the endpoint
    cannot be used to learn which file ids are real.

    "Processed" is stricter than the vendor's own `if not file.data` check: an upload is stored with
    `data = {'status': 'pending'}`, which is truthy, so that check passes a file the loader has not
    read yet. Here processing must have finished and left text behind.
    """
    if owner_id != caller_id:
        raise ReviewRefused('not_found', 'No such file.', 404)
    if meta is not None and isinstance(meta, dict) and META_KEY in meta:
        raise ReviewRefused('already_submitted', 'This file has already been submitted for review.', 409)
    if extension(filename) not in ALLOWED_EXTENSIONS:
        raise ReviewRefused(
            'type_not_allowed',
            'Only documents with readable text can be submitted: ' + ', '.join(sorted(ALLOWED_EXTENSIONS)) + '.',
            422,
        )
    status = data.get('status') if isinstance(data, dict) else None
    if status != 'completed' or not content_of(data).strip():
        raise ReviewRefused('not_processed', 'The file has not finished processing, or no text was found in it.', 409)


def digest(content: str | None) -> str:
    return hashlib.sha256((content or '').encode('utf-8')).hexdigest()


def new_submission(user_id: str, note: str | None, content_sha256: str, *, now: int) -> dict[str, Any]:
    return {
        'state': 'pending',
        'note': note,
        'submitted_by': user_id,
        'submitted_at': now,
        # The text as submitted. The owner can still edit a file's content through the vendor API,
        # so this is what lets a reviewer, or a later reader, see that it changed.
        'content_sha256': content_sha256,
        'reviewed_by': None,
        'reviewed_at': None,
        'reason': None,
        'knowledge_id': None,
    }


def check_pending(review: Any) -> dict[str, Any]:
    if not isinstance(review, dict) or not review:
        raise ReviewRefused('not_found', 'No such submission.', 404)
    if review.get('state') != 'pending':
        raise ReviewRefused('not_pending', 'Only a pending submission can be approved or rejected.', 409)
    return review


def approve(review: Any, reviewer_id: str, knowledge_id: str, *, now: int) -> dict[str, Any]:
    pending = check_pending(review)
    return {
        **pending,
        'state': 'approved',
        'reviewed_by': reviewer_id,
        'reviewed_at': now,
        'knowledge_id': knowledge_id,
    }


def reject(review: Any, reviewer_id: str, reason: str, *, now: int) -> dict[str, Any]:
    pending = check_pending(review)
    return {**pending, 'state': 'rejected', 'reviewed_by': reviewer_id, 'reviewed_at': now, 'reason': reason}


def check_unchanged(*, expected: str, current_content: str | None) -> None:
    """Refuse an approval when the text is no longer the text the reviewer's preview showed."""
    if not isinstance(expected, str) or expected != digest(current_content):
        raise ReviewRefused(
            'content_changed',
            'The document changed after it was opened for review. Open it again before deciding.',
            409,
        )


def preview(content: str | None, limit: int = PREVIEW_CHARS) -> tuple[str, bool]:
    text = content or ''
    return (text[:limit], True) if len(text) > limit else (text, False)


def states_for(value: str | None) -> tuple[str, ...]:
    """The states a queue filter selects: pending by default, `all` for every state."""
    if value is None or value == '':
        return ('pending',)
    if value == 'all':
        return STATES
    if value in STATES:
        return (value,)
    raise ReviewRefused('bad_state', 'Unknown state filter.', 422)


def serialise(*, file_id: str, filename: str, meta: Any, content: str | None = None) -> dict[str, Any]:
    """A submission as the API serves it. Ids only: display names are resolved by the router."""
    meta = meta if isinstance(meta, dict) else {}
    review = review_of(meta) or {}
    recorded = review.get('content_sha256')
    return {
        'file_id': file_id,
        'filename': filename,
        'content_type': meta.get('content_type'),
        'size': meta.get('size'),
        'state': review.get('state'),
        'note': review.get('note'),
        'submitted_by': review.get('submitted_by'),
        'submitted_at': review.get('submitted_at'),
        'reviewed_by': review.get('reviewed_by'),
        'reviewed_at': review.get('reviewed_at'),
        'reason': review.get('reason'),
        'knowledge_id': review.get('knowledge_id'),
        'changed_since_review': (
            None if content is None or not isinstance(recorded, str) else digest(content) != recorded
        ),
    }


def newest_first(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """By submission time, newest first; a row without one sorts last."""
    return sorted(rows, key=lambda row: row.get('submitted_at') or 0, reverse=True)
