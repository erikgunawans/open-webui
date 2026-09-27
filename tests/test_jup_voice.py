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
