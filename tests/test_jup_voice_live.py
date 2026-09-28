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


# --- The ledger: questions from the transcript, speech against answers (#36) -------------


def _ledger():
    return voice_live.LiveLedger()


def test_the_question_is_what_the_caller_said_up_to_the_delegation() -> None:
    ledger = _ledger()
    ledger.heard(100, 900, 'Apa status ')
    ledger.heard(900, 1600, 'proyek SPBG?')
    assert ledger.question('d1', 1700) == 'Apa status proyek SPBG?'


def test_each_question_starts_after_the_previous_one() -> None:
    ledger = _ledger()
    ledger.heard(100, 900, 'Apa status SPBG?')
    assert ledger.question('d1', 1000) == 'Apa status SPBG?'
    ledger.heard(5000, 6000, 'Dan G1-nya?')
    assert ledger.question('d2', 6100) == 'Dan G1-nya?'


def test_a_fragment_that_arrives_late_still_joins_its_question() -> None:
    """Transcript delivery is uneven; timing, not arrival order, decides."""
    ledger = _ledger()
    ledger.heard(900, 1600, 'proyek SPBG?')
    ledger.heard(100, 900, 'Apa status ')
    assert ledger.question('d1', 1700) == 'Apa status proyek SPBG?'


def test_speech_after_the_delegation_belongs_to_the_next_question() -> None:
    ledger = _ledger()
    ledger.heard(100, 900, 'Apa status SPBG?')
    ledger.heard(2000, 2500, 'Terima kasih.')
    assert ledger.question('d1', 1000) == 'Apa status SPBG?'


def test_no_speech_makes_no_question() -> None:
    assert _ledger().question('d1', 1000) == ''


def test_speech_after_a_relayed_delegation_is_recorded_against_it() -> None:
    ledger = _ledger()
    ledger.heard(100, 900, 'Apa status SPBG?')
    ledger.question('d1', 1000)
    ledger.relayed('d1', 'm-1')
    ledger.said(1500, 2500, 'Menurut dokumen, ')
    ledger.said(2500, 4000, 'proyek masih di G1.')
    assert ledger.turns() == [
        {'kind': 'relayed', 'delegation': 'd1', 'message_id': 'm-1', 'spoken': 'Menurut dokumen, proyek masih di G1.'}
    ]


def test_speech_with_no_delegation_since_the_caller_spoke_is_self_answered() -> None:
    ledger = _ledger()
    ledger.said(0, 800, 'Halo, selamat pagi.')
    ledger.heard(1000, 2000, 'Berapa kapasitas SPBG?')
    ledger.said(2200, 3000, 'Sekitar lima mmscfd.')
    assert ledger.turns() == [
        {'kind': 'self_answered', 'delegation': None, 'message_id': None, 'spoken': 'Halo, selamat pagi.'},
        {'kind': 'self_answered', 'delegation': None, 'message_id': None, 'spoken': 'Sekitar lima mmscfd.'},
    ]


def test_a_delegation_with_no_answer_yet_is_not_relayed() -> None:
    ledger = _ledger()
    ledger.heard(100, 900, 'Apa status SPBG?')
    ledger.question('d1', 1000)
    ledger.said(1100, 1800, 'Sebentar, saya periksa.')
    assert ledger.turns() == [
        {'kind': 'pending', 'delegation': 'd1', 'message_id': None, 'spoken': 'Sebentar, saya periksa.'}
    ]


def test_a_new_question_ends_the_previous_turn() -> None:
    ledger = _ledger()
    ledger.heard(100, 900, 'Apa status SPBG?')
    ledger.question('d1', 1000)
    ledger.relayed('d1', 'm-1')
    ledger.said(1500, 2500, 'Masih di G1.')
    ledger.heard(3000, 3500, 'Siapa mitranya?')
    ledger.said(3600, 4200, 'Itu belum pasti.')
    assert [turn['kind'] for turn in ledger.turns()] == ['relayed', 'self_answered']


def test_a_long_answer_is_sent_in_parts_under_gpt_lives_limit() -> None:
    answer = ('Kalimat yang cukup panjang untuk diuji di sini. ' * 120).strip()
    parts = voice_live.commentary_parts(answer)
    assert len(parts) > 1
    assert all(len(part.encode('utf-8')) <= voice_live.COMMENTARY_BYTES for part in parts)
    assert ' '.join(parts) == answer


def test_tool_and_reasoning_blocks_are_not_relayed() -> None:
    answer = '<details type="tool_calls">x</details>Proyek masih di G1.'
    assert voice_live.commentary_parts(answer) == ['Proyek masih di G1.']
