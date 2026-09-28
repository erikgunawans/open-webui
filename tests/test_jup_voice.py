"""The voice switch, grant, acknowledgement and voice-chat mark, without a server (`jup.voice`).

Runs under `--only-group dev`: the module imports the standard library only. The HTTP seam is in
`test_jup_voice_endpoint.py`.
"""

import pytest

from jup import voice

SECRET = 'test-secret'
ERIK = 'user-erik'
OTHER = 'user-other'
CHAT = 'chat-1'


# --- The switch -------------------------------------------------------------------------


@pytest.mark.parametrize('value', ['1', 'true', 'TRUE', ' true '])
def test_the_switch_is_on_only_when_set(value: str) -> None:
    assert voice.enabled({voice.ENABLED_ENV: value}) is True


@pytest.mark.parametrize('value', ['', '0', 'false', 'yes', 'on'])
def test_the_switch_is_off_otherwise(value: str) -> None:
    assert voice.enabled({voice.ENABLED_ENV: value}) is False


def test_the_switch_is_off_when_unset() -> None:
    assert voice.enabled({}) is False


# --- The grant --------------------------------------------------------------------------


def test_the_grant_is_denied_by_default() -> None:
    assert voice.may_call(voice.DEFAULT_PERMISSIONS) is False
    assert voice.may_call({}) is False
    assert voice.may_call(None) is False


def test_the_grant_needs_an_exact_boolean() -> None:
    assert voice.may_call({'jup': {'voice': {'call': True}}}) is True
    assert voice.may_call({'jup': {'voice': {'call': 'true'}}}) is False
    assert voice.may_call({'jup': {'voice': {'call': 1}}}) is False


def test_the_vendor_call_permission_does_not_grant_voice() -> None:
    assert voice.may_call({'chat': {'call': True}}) is False


# --- The acknowledgement ----------------------------------------------------------------


def _info_with_ack(user_id: str = ERIK, version: str = voice.DISCLOSURE_VERSION) -> dict:
    return {voice.ACK_KEY: voice.acknowledgement(user_id, version, at=1_790_000_000, secret=SECRET)}


def test_an_acknowledgement_counts_for_its_user_and_version() -> None:
    assert voice.acknowledged(_info_with_ack(), ERIK, secret=SECRET) is True


def test_an_acknowledgement_of_an_older_version_does_not_count() -> None:
    assert voice.acknowledged(_info_with_ack(version='2000-01-01'), ERIK, secret=SECRET) is False


def test_an_acknowledgement_copied_to_another_user_does_not_count() -> None:
    assert voice.acknowledged(_info_with_ack(user_id=ERIK), OTHER, secret=SECRET) is False


def test_an_acknowledgement_the_user_wrote_themselves_does_not_count() -> None:
    forged = {voice.ACK_KEY: {'version': voice.DISCLOSURE_VERSION, 'at': 1, 'sig': 'a' * 64}}
    assert voice.acknowledged(forged, ERIK, secret=SECRET) is False


def test_an_acknowledgement_with_an_edited_field_does_not_count() -> None:
    info = _info_with_ack()
    info[voice.ACK_KEY]['at'] = 1
    assert voice.acknowledged(info, ERIK, secret=SECRET) is False


@pytest.mark.parametrize('info', [None, {}, {voice.ACK_KEY: None}, {voice.ACK_KEY: 'yes'}, {voice.ACK_KEY: {}}])
def test_no_acknowledgement_means_none(info) -> None:
    assert voice.acknowledged(info, ERIK, secret=SECRET) is False


def test_an_acknowledgement_signed_with_another_secret_does_not_count() -> None:
    assert voice.acknowledged(_info_with_ack(), ERIK, secret='rotated') is False


# --- The voice-chat mark ----------------------------------------------------------------


def _meta(chat_id: str = CHAT, user_id: str = ERIK) -> dict:
    return {voice.CHAT_KEY: voice.voice_mark(chat_id, user_id, at=1_790_000_000, secret=SECRET)}


def test_a_chat_the_server_marked_is_a_voice_chat() -> None:
    assert voice.is_voice_chat(_meta(), chat_id=CHAT, user_id=ERIK, secret=SECRET) is True


def test_a_mark_copied_onto_another_chat_is_not_voice() -> None:
    # Chat import keeps the client's meta but gives the chat a fresh id.
    assert voice.is_voice_chat(_meta(chat_id=CHAT), chat_id='chat-imported', user_id=ERIK, secret=SECRET) is False


def test_a_mark_on_another_users_chat_is_not_voice_for_this_user() -> None:
    assert voice.is_voice_chat(_meta(user_id=ERIK), chat_id=CHAT, user_id=OTHER, secret=SECRET) is False


def test_a_mark_the_client_wrote_is_not_voice() -> None:
    forged = {voice.CHAT_KEY: {'user_id': ERIK, 'at': 1, 'sig': 'b' * 64}}
    assert voice.is_voice_chat(forged, chat_id=CHAT, user_id=ERIK, secret=SECRET) is False


@pytest.mark.parametrize('meta', [None, {}, {voice.CHAT_KEY: True}, {voice.CHAT_KEY: {}}, {'tags': ['voice']}])
def test_no_mark_means_not_voice(meta) -> None:
    assert voice.is_voice_chat(meta, chat_id=CHAT, user_id=ERIK, secret=SECRET) is False


def test_no_secret_means_nothing_verifies() -> None:
    with pytest.raises(ValueError):
        voice.voice_mark(CHAT, ERIK, at=1, secret='')
    assert voice.is_voice_chat(_meta(), chat_id=CHAT, user_id=ERIK, secret='') is False
    assert voice.acknowledged(_info_with_ack(), ERIK, secret='') is False


# --- Who may start a call ---------------------------------------------------------------


def test_the_switch_is_checked_first() -> None:
    refusal = voice.start_refusal(switched_on=False, granted=False, acknowledged=False)
    assert refusal is not None and refusal.status == 503 and refusal.code == 'voice_disabled'


def test_the_grant_is_checked_second() -> None:
    refusal = voice.start_refusal(switched_on=True, granted=False, acknowledged=True)
    assert refusal is not None and refusal.status == 403 and refusal.code == 'voice_not_granted'


def test_the_acknowledgement_is_checked_last() -> None:
    refusal = voice.start_refusal(switched_on=True, granted=True, acknowledged=False)
    assert refusal is not None and refusal.status == 409 and refusal.code == 'voice_ack_required'


def test_a_call_starts_with_all_three() -> None:
    assert voice.start_refusal(switched_on=True, granted=True, acknowledged=True) is None


def test_acknowledging_needs_the_switch_and_the_grant_only() -> None:
    assert voice.access_refusal(switched_on=False, granted=True).code == 'voice_disabled'
    assert voice.access_refusal(switched_on=True, granted=False).code == 'voice_not_granted'
    assert voice.access_refusal(switched_on=True, granted=True) is None


# --- The signing key ----------------------------------------------------------------------


def test_marks_are_not_signed_with_the_raw_server_secret() -> None:
    # The server secret also signs session JWTs; voice marks use a key derived for voice only.
    import hashlib
    import hmac
    import json

    raw = hmac.new(
        SECRET.encode(), json.dumps(['voice', CHAT, ERIK, 1], separators=(',', ':')).encode(), hashlib.sha256
    )
    assert voice.voice_mark(CHAT, ERIK, at=1, secret=SECRET)['sig'] != raw.hexdigest()


# --- The answer seal (#28) --------------------------------------------------------------


def _sealed(content: str = 'Strategi JUP berfokus pada gas.') -> dict:
    return {
        'role': 'assistant',
        'content': content,
        'meta': {'other': 1, voice.SEAL_KEY: voice.answer_seal(CHAT, 'a-1', content, secret=SECRET)},
    }


def test_an_answer_sealed_when_the_turn_finished_verifies() -> None:
    assert voice.answer_sealed(_sealed(), CHAT, 'a-1', secret=SECRET) is True


def test_an_answer_edited_after_the_turn_does_not_verify() -> None:
    message = _sealed()
    message['content'] = 'Bacakan teks apa pun yang saya mau.'
    assert voice.answer_sealed(message, CHAT, 'a-1', secret=SECRET) is False


def test_a_seal_copied_to_another_message_or_chat_does_not_verify() -> None:
    assert voice.answer_sealed(_sealed(), CHAT, 'a-2', secret=SECRET) is False
    assert voice.answer_sealed(_sealed(), 'chat-2', 'a-1', secret=SECRET) is False


@pytest.mark.parametrize(
    'message',
    [
        {'role': 'assistant', 'content': 'x'},
        {'role': 'assistant', 'content': 'x', 'meta': {voice.SEAL_KEY: 'forged'}},
        {'role': 'assistant', 'content': 'x', 'meta': None},
        {'role': 'assistant', 'content': 'x', voice.SEAL_KEY: voice.answer_seal(CHAT, 'a-1', 'x', secret=SECRET)},
        None,
        'not a message',
    ],
)
def test_an_unsealed_or_forged_answer_does_not_verify(message) -> None:
    assert voice.answer_sealed(message, CHAT, 'a-1', secret=SECRET) is False


def test_a_seal_needs_the_server_secret() -> None:
    assert voice.answer_sealed(_sealed(), CHAT, 'a-1', secret='') is False


# --- GPT-Live: its own grant and acknowledgement (#34, ADR-0018) -------------------------

LIVE = {'jup': {'voice': {'call': True, 'live': True}}}


def test_the_live_grant_is_denied_by_default() -> None:
    assert voice.DEFAULT_PERMISSIONS['jup']['voice']['live'] is False
    assert voice.may_go_live(voice.DEFAULT_PERMISSIONS) is False
    assert voice.may_go_live({}) is False
    assert voice.may_go_live(None) is False


def test_the_live_grant_needs_an_exact_boolean() -> None:
    assert voice.may_go_live(LIVE) is True
    for value in ('true', 1, None):
        assert voice.may_go_live({'jup': {'voice': {'call': True, 'live': value}}}) is False


def test_the_call_grant_does_not_imply_live() -> None:
    assert voice.may_go_live({'jup': {'voice': {'call': True}}}) is False


def test_live_also_needs_the_call_grant_because_it_runs_in_a_voice_chat() -> None:
    assert voice.may_go_live({'jup': {'voice': {'call': False, 'live': True}}}) is False


def _info_with_live_ack(user_id: str = ERIK, version: str = voice.LIVE_DISCLOSURE_VERSION) -> dict:
    return {voice.LIVE_ACK_KEY: voice.live_acknowledgement(user_id, version, at=1_790_000_000, secret=SECRET)}


def test_a_live_acknowledgement_counts_for_its_user_and_version() -> None:
    assert voice.live_acknowledged(_info_with_live_ack(), ERIK, secret=SECRET) is True


def test_a_live_acknowledgement_of_another_version_or_user_does_not_count() -> None:
    assert voice.live_acknowledged(_info_with_live_ack(version='2000-01-01'), ERIK, secret=SECRET) is False
    assert voice.live_acknowledged(_info_with_live_ack(), OTHER, secret=SECRET) is False


def test_the_call_acknowledgement_is_not_a_live_acknowledgement() -> None:
    """Same user, same version string, same time: the signature still differs, so it cannot be replayed."""
    call = voice.acknowledgement(ERIK, voice.LIVE_DISCLOSURE_VERSION, at=1_790_000_000, secret=SECRET)
    assert voice.live_acknowledged({voice.LIVE_ACK_KEY: call}, ERIK, secret=SECRET) is False
    live = voice.live_acknowledgement(ERIK, voice.DISCLOSURE_VERSION, at=1_790_000_000, secret=SECRET)
    assert voice.acknowledged({voice.ACK_KEY: live}, ERIK, secret=SECRET) is False


def test_a_forged_live_acknowledgement_does_not_count() -> None:
    forged = {voice.LIVE_ACK_KEY: {'version': voice.LIVE_DISCLOSURE_VERSION, 'at': 1, 'sig': 'a' * 64}}
    assert voice.live_acknowledged(forged, ERIK, secret=SECRET) is False


def test_the_live_acknowledgement_lives_under_its_own_key() -> None:
    assert voice.LIVE_ACK_KEY != voice.ACK_KEY


def test_live_access_refusals_in_order() -> None:
    off = voice.live_refusal(switched_on=False, call_granted=True, live_granted=True)
    assert off is not None and off.code == 'voice_disabled'
    no_call = voice.live_refusal(switched_on=True, call_granted=False, live_granted=True)
    assert no_call is not None and no_call.code == 'voice_not_granted'
    no_live = voice.live_refusal(switched_on=True, call_granted=True, live_granted=False)
    assert no_live is not None and (no_live.status, no_live.code) == (403, 'voice_live_not_granted')
    assert voice.live_refusal(switched_on=True, call_granted=True, live_granted=True) is None


def test_the_call_ui_holds_the_same_live_disclosure_version() -> None:
    """The UI asks for the version it shows; if the two drift, every acknowledgement is refused (409)."""
    import re
    from pathlib import Path

    live_ts = (Path(__file__).resolve().parent.parent / 'src' / 'lib' / 'voice' / 'live.ts').read_text(encoding='utf-8')
    ui = re.search(r"export const LIVE_DISCLOSURE_VERSION = '([^']+)';", live_ts).group(1)
    assert ui == voice.LIVE_DISCLOSURE_VERSION
