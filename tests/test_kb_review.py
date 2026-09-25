"""The knowledge-base review queue's rules, without a server (`jup.kb_review`).

Runs under `--only-group dev`: the module imports the standard library only.
"""

import pytest

from jup import kb_review as kb
from jup.kb_review import ReviewRefused

OWNER = 'user-owner'
ADMIN = 'user-admin'


def _processed(content: str = 'Isi dokumen.') -> dict:
    return {'status': 'completed', 'content': content}


# --- Who may submit -----------------------------------------------------------------


def test_the_collection_is_separate_from_the_strategy_kb() -> None:
    assert kb.CONTRIBUTIONS_KB_NAME == 'JUP Staff Contributions'
    assert 'Strategy' not in kb.CONTRIBUTIONS_KB_NAME


def test_submit_is_denied_by_default() -> None:
    assert kb.may_submit(kb.DEFAULT_PERMISSIONS) is False
    assert kb.may_submit({}) is False


def test_submit_needs_the_exact_boolean() -> None:
    assert kb.may_submit({'jup': {'kb': {'submit': True}}}) is True
    for loose in ('true', 1, 'yes', [True], {'x': True}):
        assert kb.may_submit({'jup': {'kb': {'submit': loose}}}) is False, loose


@pytest.mark.parametrize(
    'malformed',
    [None, [], 'jup', {'jup': None}, {'jup': []}, {'jup': {'kb': None}}, {'jup': {'kb': 'submit'}}],
)
def test_a_malformed_grant_is_a_denial_not_a_crash(malformed) -> None:
    assert kb.may_submit(malformed) is False


def test_review_is_the_admin_role_only() -> None:
    assert kb.may_review('admin') is True
    for role in ('user', 'pending', '', None, 'Admin'):
        assert kb.may_review(role) is False


def test_other_jup_grants_do_not_imply_submit() -> None:
    permissions = {'jup': {'ruang_pimpinan': {'imports': {'review': True}}, 'kb': {}}}
    assert kb.may_submit(permissions) is False


# --- Note and reason ----------------------------------------------------------------


def test_the_note_is_optional_and_trimmed() -> None:
    assert kb.clean_note(None) is None
    assert kb.clean_note('   ') is None
    assert kb.clean_note('  Notulen rapat  ') == 'Notulen rapat'


def test_a_note_over_the_limit_is_refused() -> None:
    assert kb.clean_note('a' * kb.TEXT_MAX) == 'a' * kb.TEXT_MAX
    with pytest.raises(ReviewRefused) as refused:
        kb.clean_note('a' * (kb.TEXT_MAX + 1))
    assert refused.value.code == 'note_too_long'
    assert refused.value.status == 422


@pytest.mark.parametrize('blank', [None, '', '   ', '\n\t'])
def test_a_reject_reason_is_required(blank) -> None:
    with pytest.raises(ReviewRefused) as refused:
        kb.clean_reason(blank)
    assert refused.value.code == 'reason_required'
    assert refused.value.status == 422


def test_a_reject_reason_over_the_limit_is_refused() -> None:
    with pytest.raises(ReviewRefused) as refused:
        kb.clean_reason('b' * (kb.TEXT_MAX + 1))
    assert refused.value.code == 'reason_too_long'
    assert kb.clean_reason('  Duplikat.  ') == 'Duplikat.'


# --- What may be submitted ----------------------------------------------------------


@pytest.mark.parametrize('name', ['a.md', 'b.TXT', 'c.pdf', 'd.docx', 'e.pptx', 'f.xlsx', 'g.csv'])
def test_text_bearing_types_are_allowed(name) -> None:
    kb.check_submittable(filename=name, owner_id=OWNER, caller_id=OWNER, data=_processed(), meta={})


@pytest.mark.parametrize('name', ['photo.png', 'clip.mp4', 'archive.zip', 'page.html', 'noext', 'x.doc', '.md'])
def test_other_types_are_refused(name) -> None:
    with pytest.raises(ReviewRefused) as refused:
        kb.check_submittable(filename=name, owner_id=OWNER, caller_id=OWNER, data=_processed(), meta={})
    assert refused.value.code == 'type_not_allowed'


def test_someone_elses_file_is_not_found() -> None:
    with pytest.raises(ReviewRefused) as refused:
        kb.check_submittable(filename='a.md', owner_id=OWNER, caller_id='someone-else', data=_processed(), meta={})
    assert refused.value.code == 'not_found'
    assert refused.value.status == 404


@pytest.mark.parametrize(
    'data',
    [
        None,
        {},
        {'status': 'pending'},
        {'status': 'processing', 'content': 'partial'},
        {'status': 'failed', 'error': 'boom'},
        {'status': 'completed'},
        {'status': 'completed', 'content': '   '},
        {'status': 'completed', 'content': 42},
    ],
)
def test_an_unprocessed_file_is_refused(data) -> None:
    with pytest.raises(ReviewRefused) as refused:
        kb.check_submittable(filename='a.md', owner_id=OWNER, caller_id=OWNER, data=data, meta={})
    assert refused.value.code == 'not_processed'
    assert refused.value.status == 409


@pytest.mark.parametrize('state', ['pending', 'approved', 'rejected'])
def test_a_file_already_submitted_cannot_be_submitted_again(state) -> None:
    meta = {kb.META_KEY: {'state': state}}
    with pytest.raises(ReviewRefused) as refused:
        kb.check_submittable(filename='a.md', owner_id=OWNER, caller_id=OWNER, data=_processed(), meta=meta)
    assert refused.value.code == 'already_submitted'
    assert refused.value.status == 409


# --- Transitions --------------------------------------------------------------------


def test_a_submission_starts_pending() -> None:
    review = kb.new_submission(OWNER, 'catatan', 'abc', now=100)
    assert review == {
        'state': 'pending',
        'note': 'catatan',
        'submitted_by': OWNER,
        'submitted_at': 100,
        'content_sha256': 'abc',
        'reviewed_by': None,
        'reviewed_at': None,
        'reason': None,
        'knowledge_id': None,
    }


def test_approving_a_pending_submission() -> None:
    pending = kb.new_submission(OWNER, None, 'abc', now=100)
    review = kb.approve(pending, ADMIN, 'kb-1', now=200)
    assert review['state'] == 'approved'
    assert (review['reviewed_by'], review['reviewed_at'], review['knowledge_id']) == (ADMIN, 200, 'kb-1')
    assert review['submitted_by'] == OWNER and review['reason'] is None
    assert pending['state'] == 'pending', 'the transition returns a new review; it never mutates its input'


def test_rejecting_a_pending_submission() -> None:
    pending = kb.new_submission(OWNER, None, 'abc', now=100)
    review = kb.reject(pending, ADMIN, 'Bukan dokumen final.', now=200)
    assert review['state'] == 'rejected'
    assert review['reason'] == 'Bukan dokumen final.'
    assert review['knowledge_id'] is None


@pytest.mark.parametrize('state', ['approved', 'rejected'])
def test_only_pending_can_be_approved_or_rejected(state) -> None:
    decided = {**kb.new_submission(OWNER, None, 'abc', now=100), 'state': state}
    with pytest.raises(ReviewRefused) as refused:
        kb.approve(decided, ADMIN, 'kb-1', now=200)
    assert refused.value.code == 'not_pending'
    assert refused.value.status == 409
    with pytest.raises(ReviewRefused) as refused:
        kb.reject(decided, ADMIN, 'x', now=200)
    assert refused.value.code == 'not_pending'


def test_a_file_that_was_never_submitted_is_not_pending() -> None:
    for missing in (None, {}, {'state': 'weird'}, 'pending'):
        with pytest.raises(ReviewRefused) as refused:
            kb.approve(missing, ADMIN, 'kb-1', now=1)
        assert refused.value.code in ('not_found', 'not_pending')


def test_review_of_reads_only_a_well_formed_review() -> None:
    assert kb.review_of(None) is None
    assert kb.review_of({}) is None
    assert kb.review_of({kb.META_KEY: 'pending'}) is None
    assert kb.review_of({kb.META_KEY: {'state': 'nonsense'}}) is None
    assert kb.review_of({kb.META_KEY: {'state': 'pending'}}) == {'state': 'pending'}


# --- The content the reviewer sees --------------------------------------------------


def test_the_preview_is_truncated_and_says_so() -> None:
    text, truncated = kb.preview('x' * (kb.PREVIEW_CHARS + 5))
    assert len(text) == kb.PREVIEW_CHARS and truncated is True
    assert kb.preview('pendek') == ('pendek', False)
    assert kb.preview(None) == ('', False)


def test_the_digest_pins_the_content_the_reviewer_saw() -> None:
    assert kb.digest('a') == kb.digest('a')
    assert kb.digest('a') != kb.digest('b')
    assert len(kb.digest('a')) == 64


def test_approval_refuses_content_that_changed_after_the_preview() -> None:
    kb.check_unchanged(expected=kb.digest('same'), current_content='same')
    with pytest.raises(ReviewRefused) as refused:
        kb.check_unchanged(expected=kb.digest('before'), current_content='after')
    assert refused.value.code == 'content_changed'
    assert refused.value.status == 409


# --- Listing ------------------------------------------------------------------------


def test_the_state_filter() -> None:
    assert kb.states_for(None) == ('pending',)
    assert kb.states_for('pending') == ('pending',)
    assert kb.states_for('approved') == ('approved',)
    assert kb.states_for('rejected') == ('rejected',)
    assert kb.states_for('all') == ('pending', 'approved', 'rejected')
    with pytest.raises(ReviewRefused) as refused:
        kb.states_for('deleted')
    assert refused.value.code == 'bad_state'


def test_serialise_a_submission() -> None:
    review = kb.approve(kb.new_submission(OWNER, 'n', kb.digest('isi'), now=100), ADMIN, 'kb-1', now=200)
    out = kb.serialise(
        file_id='f1',
        filename='a.md',
        meta={'content_type': 'text/markdown', 'size': 3, kb.META_KEY: review},
        content='isi',
    )
    assert out == {
        'file_id': 'f1',
        'filename': 'a.md',
        'content_type': 'text/markdown',
        'size': 3,
        'state': 'approved',
        'note': 'n',
        'submitted_by': OWNER,
        'submitted_at': 100,
        'reviewed_by': ADMIN,
        'reviewed_at': 200,
        'reason': None,
        'knowledge_id': 'kb-1',
        'changed_since_review': False,
    }


def test_serialise_flags_content_edited_after_approval() -> None:
    review = kb.approve(kb.new_submission(OWNER, None, kb.digest('reviewed'), now=1), ADMIN, 'kb', now=2)
    out = kb.serialise(file_id='f', filename='a.md', meta={kb.META_KEY: review}, content='edited later')
    assert out['changed_since_review'] is True


def test_newest_first() -> None:
    rows = [{'submitted_at': 1}, {'submitted_at': 3}, {'submitted_at': None}, {'submitted_at': 2}]
    assert [row['submitted_at'] for row in kb.newest_first(rows)] == [3, 2, 1, None]


def test_the_module_imports_no_runtime() -> None:
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(kb))
    imported = {
        (node.module or '') if isinstance(node, ast.ImportFrom) else alias.name
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not {name for name in imported if name.split('.')[0] in ('sqlalchemy', 'open_webui', 'fastapi')}
