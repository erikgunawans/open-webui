"""#35: the GPT-Live session our server mints, without a server (`jup.voice_live`).

Runs under `--only-group dev`: the module imports the standard library only. The HTTP seam is in
`test_jup_voice_endpoint.py`.
"""

import pytest

from jup import voice_live

OFFER = 'v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\n'


def test_the_session_is_gpt_live_with_client_delegation_and_nothing_stored() -> None:
    config = voice_live.session_config()
    assert config['model'] == 'gpt-live-1'
    assert config['delegation'] == {'type': 'client'}
    assert config['store'] is False
    assert config['instructions'] == voice_live.INSTRUCTIONS
    assert 'audio' not in config  # WebRTC negotiates the format; the default voice is kept for now


def test_the_request_carries_the_config_and_the_browsers_offer() -> None:
    assert voice_live.session_request(OFFER) == {
        'session': voice_live.session_config(),
        'transport': {'type': 'webrtc', 'sdp': OFFER},
    }


def test_the_session_goes_to_openai_only() -> None:
    assert voice_live.LIVE_URL == 'https://api.openai.com/v1/live/sessions'


@pytest.mark.parametrize('sdp', [None, '', '   ', 42, {'sdp': OFFER}, 'hello', 'v=0' + 'a' * 70_000])
def test_anything_but_a_plain_sdp_offer_is_refused(sdp) -> None:
    refusal = voice_live.offer_refusal(sdp)
    assert refusal is not None and (refusal.status, refusal.code) == (400, 'voice_live_bad_offer')


def test_a_plain_sdp_offer_passes() -> None:
    assert voice_live.offer_refusal(OFFER) is None


def test_the_answer_gives_the_session_id_and_the_sdp_answer() -> None:
    body = {'session': {'id': 'live_123'}, 'transport': {'type': 'webrtc', 'sdp': 'v=0\r\nanswer'}}
    assert voice_live.session_answer(body) == ('live_123', 'v=0\r\nanswer')


@pytest.mark.parametrize(
    'body',
    [
        None,
        {},
        {'session': {'id': 'live_1'}},
        {'session': {}, 'transport': {'sdp': 'v=0'}},
        {'session': {'id': 3}, 'transport': {'sdp': 'v=0'}},
    ],
)
def test_a_malformed_answer_is_refused(body) -> None:
    refusal = voice_live.session_answer(body)
    assert isinstance(refusal, voice_live.Refusal) and (refusal.status, refusal.code) == (502, 'voice_live_upstream')


# --- The instructions (ADR-0018 item 4) ---------------------------------------------------


def test_the_instructions_keep_openais_three_delegation_labels() -> None:
    for label in ('Backend tools:', 'Delegate to the backend when:', 'Do not delegate to the backend when:'):
        assert label in voice_live.INSTRUCTIONS


def test_the_instructions_are_indonesian_and_say_so() -> None:
    assert 'Selalu berbicara dalam bahasa Indonesia' in voice_live.INSTRUCTIONS


def test_the_instructions_send_every_substantive_question_to_the_backend() -> None:
    assert 'Jangan menjawab pertanyaan tentang JUP dari pengetahuan Anda sendiri' in voice_live.INSTRUCTIONS


def test_the_instructions_ask_for_every_figure_and_caveat_as_written() -> None:
    assert 'setiap angka' in voice_live.INSTRUCTIONS
    assert 'catatan kehati-hatian' in voice_live.INSTRUCTIONS


def test_the_instructions_fit_gpt_lives_limit() -> None:
    """16,384 tokens; a token is at least one byte, so bytes bound it from above."""
    assert len(voice_live.INSTRUCTIONS.encode('utf-8')) < 16_384
