"""#28: the audio boundary's rules, without a server (`jup.voice_audio`).

Runs under `--only-group dev`: the module imports the standard library only. The HTTP seam is in
`test_jup_voice_audio_endpoint.py`.
"""

import pytest

from jup import voice_audio

# --- Speech to text ---------------------------------------------------------------------


def test_openai_transcription_is_refused_when_voice_is_off() -> None:
    refusal = voice_audio.stt_refusal('openai', switched_on=False, granted=True)
    assert refusal is not None and refusal.status == 503


def test_openai_transcription_is_refused_without_the_grant() -> None:
    refusal = voice_audio.stt_refusal('openai', switched_on=True, granted=False)
    assert refusal is not None and (refusal.status, refusal.code) == (403, 'voice_not_granted')


def test_openai_transcription_is_allowed_with_the_grant() -> None:
    assert voice_audio.stt_refusal('openai', switched_on=True, granted=True) is None


@pytest.mark.parametrize('engine', ['', 'deepgram', 'azure', 'mistral', None])
def test_other_engines_are_left_to_the_vendors_own_permission(engine) -> None:
    """Only OpenAI sends speech abroad under D21; the local engine stays as the vendor gates it."""
    assert voice_audio.stt_refusal(engine, switched_on=False, granted=False) is None


@pytest.mark.parametrize(('engine', 'provider'), [('openai', 'openai'), ('', 'local'), ('azure', 'azure')])
def test_the_provider_is_named_for_the_audit_line(engine, provider) -> None:
    assert voice_audio.provider(engine) == provider


def test_the_detected_language_comes_from_the_first_chunk_that_names_one() -> None:
    assert voice_audio.detected_language([{'text': 'a'}, {'text': 'b', 'language': 'indonesian'}]) == 'indonesian'
    assert voice_audio.detected_language([{'text': 'a'}], requested='id') == 'id'
    assert voice_audio.detected_language([{'text': 'a'}]) is None


# --- Text to speech: the request --------------------------------------------------------


def test_a_speech_request_names_a_message_in_a_chat() -> None:
    assert voice_audio.speech_request({'chat_id': 'c', 'message_id': 'm'}) == ('c', 'm', 0)
    assert voice_audio.speech_request({'chat_id': 'c', 'message_id': 'm', 'part': 2}) == ('c', 'm', 2)


@pytest.mark.parametrize(
    'payload',
    [
        {'input': 'read this aloud'},
        {'input': 'x', 'voice': 'alloy'},
        {'chat_id': 'c'},
        {'message_id': 'm'},
        {'chat_id': '', 'message_id': 'm'},
        {'chat_id': 'c', 'message_id': 7},
        {'chat_id': 'c', 'message_id': 'm', 'part': -1},
        {'chat_id': 'c', 'message_id': 'm', 'part': 'one'},
        {'chat_id': 'c', 'message_id': 'm', 'part': True},
        [],
        None,
    ],
)
def test_free_text_or_a_malformed_request_is_refused(payload) -> None:
    refusal = voice_audio.speech_request(payload)
    assert isinstance(refusal, voice_audio.Refusal)
    assert refusal.status == 400


def test_free_text_sent_next_to_a_message_id_is_refused_rather_than_ignored() -> None:
    refusal = voice_audio.speech_request({'chat_id': 'c', 'message_id': 'm', 'input': 'something else'})
    assert isinstance(refusal, voice_audio.Refusal)


# --- Text to speech: the message --------------------------------------------------------


def test_only_an_assistant_message_is_read() -> None:
    assert voice_audio.message_refusal({'role': 'assistant', 'content': 'Halo.'}) is None
    for message in ({'role': 'user', 'content': 'Halo.'}, {}, None, {'role': 'assistant', 'content': ''}):
        refusal = voice_audio.message_refusal(message)
        assert refusal is not None and refusal.status == 404


def test_an_unfinished_answer_is_not_read_yet() -> None:
    refusal = voice_audio.message_refusal({'role': 'assistant', 'content': 'Hal', 'done': False})
    assert refusal is not None and refusal.status == 409


def test_what_is_spoken_is_the_answer_without_tool_and_reasoning_blocks() -> None:
    content = (
        '<details type="tool_calls" done="true">\n<summary>Tool</summary>\nsecret args\n</details>\n'
        'Strategi JUP ada tiga.\n'
        '<details type="reasoning"><summary>Thought</summary>thinking</details>'
    )
    assert voice_audio.speakable_text(content) == 'Strategi JUP ada tiga.'


def test_a_short_answer_is_one_part() -> None:
    assert voice_audio.speech_parts('Satu. Dua.') == ['Satu. Dua.']


def test_a_long_answer_is_split_at_sentence_ends_under_the_limit() -> None:
    sentence = 'Ini kalimat yang cukup panjang untuk diuji. '
    text = (sentence * 200).strip()
    parts = voice_audio.speech_parts(text, limit=500)
    assert all(len(part) <= 500 for part in parts)
    assert all(part.endswith('.') for part in parts)
    assert ' '.join(parts) == text


def test_a_sentence_longer_than_the_limit_is_cut_hard_rather_than_dropped() -> None:
    text = 'a' * 1200
    parts = voice_audio.speech_parts(text, limit=500)
    assert [len(part) for part in parts] == [500, 500, 200]
    assert ''.join(parts) == text


def test_the_default_limit_is_under_openais_4096() -> None:
    assert voice_audio.SPEECH_PART_LIMIT < 4096


# --- Text to speech: the answer ---------------------------------------------------------


def _answer(**overrides):
    fields = {'own_chat': True, 'voice_chat': True, 'message': {'role': 'assistant', 'content': 'x'}, 'sealed': True}
    return voice_audio.answer_refusal(**{**fields, **overrides})


def test_a_sealed_answer_in_the_callers_own_voice_chat_is_read() -> None:
    assert _answer() is None


def test_someone_elses_chat_reads_as_missing_so_it_cannot_be_probed() -> None:
    assert _answer(own_chat=False) is voice_audio.ANSWER_NOT_FOUND
    assert _answer(own_chat=False, voice_chat=False, sealed=False) is voice_audio.ANSWER_NOT_FOUND


def test_a_typed_chat_is_not_read_by_voice() -> None:
    assert _answer(voice_chat=False) is voice_audio.NOT_A_VOICE_CHAT


def test_a_question_or_a_missing_message_is_not_an_answer() -> None:
    assert _answer(message={'role': 'user', 'content': 'x'}) is voice_audio.ANSWER_NOT_FOUND
    assert _answer(message=None) is voice_audio.ANSWER_NOT_FOUND


def test_an_answer_the_assistant_did_not_write_is_not_read() -> None:
    """Edited after the turn, or added through the chat API: the seal does not verify."""
    assert _answer(sealed=False) is voice_audio.UNSEALED


def test_a_part_past_the_end_is_refused() -> None:
    assert voice_audio.part_refusal(0, 1) is None
    assert voice_audio.part_refusal(1, 1) is voice_audio.NO_SUCH_PART


# --- The OpenAI key (#30) ---------------------------------------------------------------
# The key lives in Secret Manager and reaches the service as an env var; the app DB holds
# only the (empty) vendor key rows, which would otherwise win over any env var.


def test_the_secret_key_is_used_for_openai() -> None:
    assert voice_audio.openai_api_key('', 'https://api.openai.com/v1', secret='sk-secret') == 'sk-secret'


def test_the_secret_key_wins_over_a_key_saved_in_the_app() -> None:
    assert voice_audio.openai_api_key('sk-db', 'https://api.openai.com/v1', secret='sk-secret') == 'sk-secret'


def test_without_the_secret_the_saved_key_stays() -> None:
    assert voice_audio.openai_api_key('sk-db', 'https://api.openai.com/v1', secret='') == 'sk-db'
    assert voice_audio.openai_api_key('sk-db', 'https://api.openai.com/v1', secret=None) == 'sk-db'


@pytest.mark.parametrize(
    'base_url',
    [
        'https://openrouter.ai/api/v1',
        'http://api.openai.com/v1',
        'https://api.openai.com.evil.example/v1',
        'https://evil.example/api.openai.com/v1',
        'https://user@api.openai.com.evil.example/v1',
        '',
        None,
    ],
)
def test_the_secret_key_never_goes_anywhere_but_openai(base_url) -> None:
    assert voice_audio.openai_api_key('sk-db', base_url, secret='sk-secret') == 'sk-db'


def test_openai_with_or_without_a_trailing_slash_or_path_is_openai() -> None:
    for base_url in ('https://api.openai.com', 'https://api.openai.com/', 'https://api.openai.com/v1/'):
        assert voice_audio.openai_api_key('', base_url, secret='sk-secret') == 'sk-secret'


def test_the_secret_key_is_trimmed_of_the_newlines_a_pasted_secret_carries() -> None:
    """`openai-live-key` was stored with two trailing newlines; aiohttp refuses them in a header."""
    assert voice_audio.openai_api_key('', 'https://api.openai.com/v1', secret='sk-secret\n\n') == 'sk-secret'
    assert voice_audio.openai_api_key('', 'https://api.openai.com/v1', secret='  sk-secret\r\n') == 'sk-secret'


def test_a_secret_of_only_whitespace_counts_as_no_secret() -> None:
    assert voice_audio.openai_api_key('sk-db', 'https://api.openai.com/v1', secret='\n\n') == 'sk-db'


# --- Google speech (#32, D23) -------------------------------------------------------------


@pytest.mark.parametrize('engine', ['openai', 'google'])
def test_the_engines_that_read_only_sealed_answers(engine) -> None:
    assert voice_audio.reads_sealed_answers(engine) is True


@pytest.mark.parametrize('engine', ['', None, 'transformers', 'elevenlabs', 'azure', 'mistral', 'Google'])
def test_every_other_engine_reads_what_the_vendor_always_read(engine) -> None:
    assert voice_audio.reads_sealed_answers(engine) is False


def test_google_speaks_with_kore_by_default() -> None:
    assert voice_audio.GOOGLE_VOICE == 'id-ID-Chirp3-HD-Kore'
    for configured in ('', None, 'nova', 'alloy', 'id-ID', 'Kore'):
        assert voice_audio.google_voice(configured) == 'id-ID-Chirp3-HD-Kore'


def test_google_speaks_with_the_configured_google_voice() -> None:
    assert voice_audio.google_voice('id-ID-Chirp3-HD-Puck') == 'id-ID-Chirp3-HD-Puck'
    assert voice_audio.google_voice(' en-US-Chirp3-HD-Charon ') == 'en-US-Chirp3-HD-Charon'


def test_the_google_request_names_the_voice_its_language_and_mp3() -> None:
    assert voice_audio.google_speech_request('Selamat pagi, Pak.', 'id-ID-Chirp3-HD-Kore') == {
        'input': {'text': 'Selamat pagi, Pak.'},
        'voice': {'languageCode': 'id-ID', 'name': 'id-ID-Chirp3-HD-Kore'},
        'audioConfig': {'audioEncoding': 'MP3'},
    }


def test_google_speech_goes_to_google_only() -> None:
    assert voice_audio.GOOGLE_SPEECH_URL == 'https://texttospeech.googleapis.com/v1/text:synthesize'


def test_a_speech_part_fits_googles_request_limit() -> None:
    """Google takes at most 5000 bytes of text; a part is 4000 characters, so multibyte text is cut."""
    text = 'é' * 4000
    for part in voice_audio.speech_parts(text):
        assert len(part.encode('utf-8')) <= voice_audio.GOOGLE_TEXT_BYTES
