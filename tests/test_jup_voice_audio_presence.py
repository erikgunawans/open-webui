"""#28: the vendor inserts that make the audio endpoints the edge of the voice boundary.

Losing one fails nothing visible: speech still transcribes and answers are still read aloud, just
to OpenAI without the grant, or from free text. So a lost patch must break this test instead
(ADR-0007, `deploy/gcp/VENDOR-PATCHES.md`).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_PY = ROOT / 'backend' / 'open_webui' / 'routers' / 'audio.py'
OPENAI_PY = ROOT / 'backend' / 'open_webui' / 'routers' / 'openai.py'
MIDDLEWARE_PY = ROOT / 'backend' / 'open_webui' / 'utils' / 'middleware.py'
JUP_VOICE_PY = ROOT / 'backend' / 'open_webui' / 'routers' / 'jup_voice.py'
RESPONSE_MESSAGE = ROOT / 'src' / 'lib' / 'components' / 'chat' / 'Messages' / 'ResponseMessage.svelte'
PATCHES = ROOT / 'deploy' / 'gcp' / 'VENDOR-PATCHES.md'


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def test_every_transcription_is_admitted_before_any_audio_is_touched():
    body = _between(AUDIO_PY.read_text(encoding='utf-8'), 'async def transcribe(', '\ndef compress_audio(')
    admit = body.index('jup_stt = await jup_voice.stt_admit(request, user, file_path, metadata)')
    assert admit < body.index('convert_audio_to_mp3')
    assert admit < body.index('transcription_handler(request, chunk_path, metadata, user)')


def test_every_transcription_is_audited_before_it_returns():
    body = _between(AUDIO_PY.read_text(encoding='utf-8'), 'async def transcribe(', '\ndef compress_audio(')
    audit = body.index('jup_voice.stt_audit(jup_stt, results)')
    assert body.index('results = await asyncio.gather(*tasks)') < audit < body.index("'text': ' '.join(")


def test_the_transcription_route_and_file_uploads_both_go_through_transcribe():
    """The gate sits in `transcribe`, so it covers every caller; none may call the handler directly."""
    source = AUDIO_PY.read_text(encoding='utf-8')
    # The definition and one call each: the handler only from `transcribe`, OpenAI only from the handler.
    assert source.count('transcription_handler(') == 2
    assert source.count('_transcribe_openai(') == 2
    files = (ROOT / 'backend' / 'open_webui' / 'routers' / 'files.py').read_text(encoding='utf-8')
    assert 'transcription_handler' not in files and '_transcribe_openai' not in files


def test_speech_takes_its_body_from_the_boundary_before_it_hashes_or_sends_it():
    body = _between(AUDIO_PY.read_text(encoding='utf-8'), "@router.post('/speech')", 'async def _transcribe_whisper(')
    swap = body.index('body = await jup_voice.speech_body(request, user, engine)')
    assert 'await request.body()' not in body
    assert swap < body.index('name = hashlib.sha256(') < body.index('handler(request, payload,')


def test_every_finished_voice_answer_is_sealed_after_it_is_saved():
    source = MIDDLEWARE_PY.read_text(encoding='utf-8')
    assert 'from open_webui.routers import jup_voice' in source
    body = _between(source, 'async def publish_chat_finished_event(', '\n\n\n')
    seal = body.index('await jup_voice.seal_answer(metadata)')
    assert body.index("if getattr(request.state, 'internal', False) is True") < seal < body.index('publish_event(')
    # Both finish paths save the answer, then publish: the seal reads what was saved.
    for finish in (
        'await publish_chat_finished_event(request, user, metadata, title, content, response_output)',
        'await publish_chat_finished_event(\n',
    ):
        at = source.index(finish)
        assert source.rindex('await Chats.upsert_message_to_chat_by_id_and_message_id(', 0, at) > at - 1200


def test_the_audit_mirrors_the_vendors_speech_cache_name():
    """`speech_cached` recomputes the vendor's cache name; if upstream changes it, `cached` lies."""
    vendor = "body + str(engine).encode('utf-8') + str(await Config.get('audio.tts.model')).encode('utf-8')"
    assert vendor in AUDIO_PY.read_text(encoding='utf-8')
    ours = "body + str(engine).encode('utf-8') + str(model).encode('utf-8')"
    assert ours in JUP_VOICE_PY.read_text(encoding='utf-8')
    assert "model = await _vendor_config('audio.tts.model')" in JUP_VOICE_PY.read_text(encoding='utf-8')


def test_the_raw_openai_speech_proxy_refuses_first():
    body = _between(OPENAI_PY.read_text(encoding='utf-8'), "@router.post('/audio/speech')", '\n@router.')
    refuse = body.index('jup_voice.refuse_speech_passthrough(user)')
    assert refuse < body.index('await request.body()')


def test_both_routers_import_the_boundary():
    for path in (AUDIO_PY, OPENAI_PY):
        assert 'from open_webui.routers import jup_voice' in path.read_text(encoding='utf-8'), path.name


def test_read_aloud_on_a_typed_answer_uses_the_browser_when_openai_is_the_engine():
    source = RESPONSE_MESSAGE.read_text(encoding='utf-8')
    assert "import { readAloudUsesBrowser } from '$lib/voice/readAloud';" in source
    speak = _between(source, 'const speak = async () => {', 'let preprocessedDetailsCache')
    branch = speak.index('if (readAloudUsesBrowser($config.audio.tts.engine)) {')
    assert branch < speak.index('new SpeechSynthesisUtterance(content)') < speak.index('synthesizeOpenAISpeech(')
    assert "$config.audio.tts.engine === ''" not in speak


def test_every_insert_has_a_vendor_patches_entry():
    patches = PATCHES.read_text(encoding='utf-8')
    for needle in (
        'stt_admit',
        'stt_audit',
        'speech_body',
        'seal_answer',
        'refuse_speech_passthrough',
        'readAloudUsesBrowser',
    ):
        assert needle in patches, needle
    assert 'test_jup_voice_audio_presence.py' in patches
