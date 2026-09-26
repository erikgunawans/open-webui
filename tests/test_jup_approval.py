"""A5+E5 #21: an attended External Call waits for the asking user, who approves or rejects that call.

Behaviour of `jup.approval` and `jup.tool_policy.decide` through their public interfaces:

- a gated call is armed when its card is shown, and only then does its 10-minute clock start;
- approve signs the approval to exactly that call and that user, and `decide` runs it only then;
- reject and timeout each end in a refusal the model can explain, with who decided and the wait;
- the timeout holds server-side: a late approve is a timeout, and the timer itself times it out.

The vendor inserts that call these are guarded in `test_jup_tool_gate_presence.py`.
"""

import json

import pytest

from jup import approval
from jup.tool_policy import AUTOMATION, CHAT, SUBAGENT, decide, must_pause, preapprove_ungated

SECRET = 'test-secret'
CHAT_ID = 'chat-1'
MESSAGE_ID = 'msg-1'
OWNER = 'user-owner'
T0 = 1_000_000
MINUTE = 60_000

GATE_PROBE = {'tool_id': 'gate_probe', 'spec': {'name': 'gate_probe'}, 'risk_class': 'external'}
PORTFOLIO = {'tool_id': 'portfolio_status', 'spec': {'name': 'portfolio_status'}, 'risk_class': 'read'}
TOOLS = {'gate_probe': GATE_PROBE, 'portfolio_status': PORTFOLIO}


def call(name='gate_probe', call_id='call-1', arguments=None, **fields) -> dict:
    return {
        'type': 'function_call',
        'id': call_id,
        'call_id': call_id,
        'name': name,
        'arguments': arguments if arguments is not None else json.dumps({'text': 'halo'}),
        'status': 'pending',
        **fields,
    }


def armed(**fields) -> dict:
    item = call(**fields)
    assert approval.arm(item, TOOLS.get(item['name']), now_ms=T0)
    return item


def resolve(item, action, *, user_id=OWNER, now_ms=T0 + MINUTE):
    return approval.resolve(
        item, action, chat_id=CHAT_ID, message_id=MESSAGE_ID, user_id=user_id, now_ms=now_ms, secret=SECRET
    )


def verified(item, *, user_id=OWNER, chat_id=CHAT_ID, message_id=MESSAGE_ID, secret=SECRET):
    return approval.verified(item, chat_id=chat_id, message_id=message_id, user_id=user_id, secret=secret)


# --- when a call pauses -----------------------------------------------------------------------------


@pytest.mark.parametrize('mode', ['ask', 'full', None])
def test_an_external_call_in_a_chat_pauses_whatever_the_mode(mode):
    assert must_pause('gate_probe', GATE_PROBE, mode=mode, path=CHAT)


def test_a_read_call_in_full_mode_does_not_pause():
    assert not must_pause('portfolio_status', PORTFOLIO, mode='full', path=CHAT)


def test_ask_mode_still_pauses_ungated_calls_as_the_vendor_does_except_ask_user():
    assert must_pause('portfolio_status', PORTFOLIO, mode='ask', path=CHAT)
    assert not must_pause('ask_user', {'tool_id': 'builtin:ask_user'}, mode='ask', path=CHAT)


@pytest.mark.parametrize('path', [AUTOMATION, SUBAGENT])
def test_an_unattended_external_call_is_not_paused_it_is_refused(path):
    """Nobody is there to see a card; #20's refusal handles it at dispatch."""
    assert not must_pause('gate_probe', GATE_PROBE, mode='full', path=path)


def test_in_full_mode_only_the_gated_calls_wait_the_rest_are_preapproved():
    output = [
        call('portfolio_status', 'c-read', status='in_progress'),
        call('gate_probe', 'c-ext', status='in_progress'),
    ]
    preapprove_ungated(output, ['c-read', 'c-ext'], TOOLS, path=CHAT)
    read_item, ext_item = output
    assert read_item['approved'] is True and read_item['status'] == 'queued'
    assert 'approved' not in ext_item


def test_preapproval_touches_only_this_batches_calls():
    older = call('portfolio_status', 'c-old', status='queued')
    preapprove_ungated([older], ['c-new'], TOOLS, path=CHAT)
    assert 'approved' not in older


# --- arming: the clock starts when the card is shown --------------------------------------------------


def test_arming_marks_an_external_call_with_when_it_was_shown_and_its_tool():
    item = armed()
    assert approval.is_gated(item)
    assert item[approval.GATE_KEY]['paused_at'] == T0
    assert item[approval.GATE_KEY]['tool_id'] == 'gate_probe'


def test_an_ungated_call_is_never_armed():
    item = call('portfolio_status')
    assert not approval.arm(item, PORTFOLIO, now_ms=T0)
    assert not approval.is_gated(item)


def test_arming_twice_keeps_the_first_clock():
    """The vendor re-pauses a message after each drain; a re-pause must not restart the timeout."""
    item = armed()
    assert not approval.arm(item, GATE_PROBE, now_ms=T0 + 5 * MINUTE)
    assert item[approval.GATE_KEY]['paused_at'] == T0


# --- approve ----------------------------------------------------------------------------------------


def test_approving_queues_the_call_for_the_drain_and_says_who_and_how_long():
    item = armed()
    result = resolve(item, 'approve')
    assert result.approval == 'approved'
    assert result.approved_by == OWNER
    assert result.wait_ms == MINUTE
    assert item['status'] == 'queued' and item['approved'] is True


def test_an_approved_call_verifies_for_its_own_user_and_runs():
    item = armed()
    resolve(item, 'approve')
    granted = verified(item)
    assert granted is not None
    ruling = decide('gate_probe', GATE_PROBE, path=CHAT, approval=granted)
    assert ruling.runs
    assert ruling.approval == 'approved'
    assert ruling.approved_by == OWNER
    assert ruling.approval_wait_ms == MINUTE


def test_without_an_approval_an_attended_external_call_is_refused():
    ruling = decide('gate_probe', GATE_PROBE, path=CHAT)
    assert not ruling.runs
    assert ruling.approval == 'rejected'
    assert 'did not run' in ruling.message


def test_an_approval_does_not_open_an_unattended_path():
    item = armed()
    resolve(item, 'approve')
    ruling = decide('gate_probe', GATE_PROBE, path=AUTOMATION, approval=verified(item))
    assert not ruling.runs
    assert ruling.approval == 'rejected_unattended'


def test_an_approval_is_only_good_for_the_user_who_gave_it():
    item = armed()
    resolve(item, 'approve')
    assert verified(item, user_id='someone-else') is None


def test_an_approval_is_bound_to_the_arguments_that_were_shown():
    """Editing the stored call after approving must not run a different call under the same approval."""
    item = armed()
    resolve(item, 'approve')
    item['arguments'] = json.dumps({'text': 'something else'})
    assert verified(item) is None


@pytest.mark.parametrize(
    'tamper',
    [
        lambda item: item.update(name='fetch_url'),
        lambda item: item.update(call_id='call-2'),
        lambda item: item[approval.GATE_KEY].update(approved_by='user-other'),
        lambda item: item[approval.GATE_KEY].update(paused_at=T0 + 9 * MINUTE),
    ],
)
def test_any_edit_to_the_approved_call_voids_the_approval(tamper):
    item = armed()
    resolve(item, 'approve')
    tamper(item)
    assert verified(item) is None


@pytest.mark.parametrize('where', [{'chat_id': 'chat-2'}, {'message_id': 'msg-2'}, {'secret': 'other-secret'}])
def test_an_approval_does_not_transfer_to_another_message_or_server(where):
    item = armed()
    resolve(item, 'approve')
    assert verified(item, **where) is None


def test_an_approval_nobody_gave_does_not_verify():
    """A call marked approved by hand, not through `resolve`, carries no signature."""
    item = armed()
    item['approved'] = True
    item['status'] = 'queued'
    assert verified(item) is None
    assert verified(call()) is None
    assert verified(None) is None


# --- reject -----------------------------------------------------------------------------------------


def test_rejecting_refuses_the_call_and_tells_the_model():
    item = armed()
    result = resolve(item, 'reject', now_ms=T0 + 2 * MINUTE)
    assert result.approval == 'rejected'
    assert result.approved_by == OWNER
    assert result.wait_ms == 2 * MINUTE
    assert item['status'] == 'rejected'
    assert 'approved' not in item
    assert 'rejected' in result.message and 'did not run' in result.message
    assert verified(item) is None


# --- timeout ----------------------------------------------------------------------------------------


def test_the_timeout_is_ten_minutes():
    assert approval.TIMEOUT_MS == 10 * MINUTE


def test_an_approve_after_ten_minutes_is_a_timeout_not_an_approval():
    item = armed()
    result = resolve(item, 'approve', now_ms=T0 + approval.TIMEOUT_MS + 1)
    assert result.approval == 'timed_out'
    assert result.approved_by is None
    assert item['status'] == 'rejected'
    assert 'approved' not in item
    assert verified(item) is None
    assert 'timed_out' in result.message and 'did not run' in result.message


def test_a_reject_after_ten_minutes_is_also_recorded_as_a_timeout():
    item = armed()
    assert resolve(item, 'reject', now_ms=T0 + approval.TIMEOUT_MS + 1).approval == 'timed_out'


def test_the_server_side_timer_times_out_an_unanswered_call():
    """What runs when nobody answers, a closed tab included."""
    item = armed()
    result = approval.time_out(item, now_ms=T0 + approval.TIMEOUT_MS)
    assert result is not None
    assert result.approval == 'timed_out'
    assert result.wait_ms == approval.TIMEOUT_MS
    assert item['status'] == 'rejected'


def test_the_timer_leaves_a_call_alone_before_its_deadline():
    item = armed()
    assert approval.time_out(item, now_ms=T0 + approval.TIMEOUT_MS - 1) is None
    assert item['status'] == 'pending'


def test_the_timer_leaves_an_answered_call_alone():
    item = armed()
    resolve(item, 'approve')
    assert approval.time_out(item, now_ms=T0 + approval.TIMEOUT_MS + 1) is None
    assert item['status'] == 'queued'


def test_the_timer_ignores_a_call_that_was_never_gated():
    item = call('portfolio_status')
    assert approval.time_out(item, now_ms=T0 + approval.TIMEOUT_MS + 1) is None


# --- an approval is spent by one run ------------------------------------------------------------------


def test_resolving_a_gated_call_twice_is_refused():
    item = armed()
    resolve(item, 'approve')
    with pytest.raises(approval.AlreadyResolved):
        resolve(item, 'approve')


def test_an_unknown_action_is_refused():
    item = armed()
    with pytest.raises(ValueError):
        resolve(item, 'answer')
