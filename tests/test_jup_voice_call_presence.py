"""#29: the vendor inserts that put the call UI behind the start-call route and sealed answers.

Losing one fails nothing visible: the call button still shows and calls still work, just in the
chat at hand rather than a voice chat, or reading streamed text that the server now refuses. So a
lost patch must break this test instead (ADR-0007, `deploy/gcp/VENDOR-PATCHES.md`).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAT = ROOT / 'src' / 'lib' / 'components' / 'chat'
MESSAGE_INPUT = CHAT / 'MessageInput.svelte'
CHAT_SVELTE = CHAT / 'Chat.svelte'
CALL_OVERLAY = CHAT / 'MessageInput' / 'CallOverlay.svelte'
AUDIO_API = ROOT / 'src' / 'lib' / 'apis' / 'audio' / 'index.ts'
PATCHES = ROOT / 'deploy' / 'gcp' / 'VENDOR-PATCHES.md'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def test_the_call_button_shows_only_with_the_switch_and_the_grant():
    source = _read(MESSAGE_INPUT)
    assert "callButton($voiceCapabilities) !== 'hidden'" in source
    # The vendor `chat.call` defaults on for everyone; it is not the gate (ADR-0017).
    assert 'permissions?.chat?.call' not in source


def test_the_call_button_starts_a_call_through_the_route_not_the_overlay():
    source = _read(MESSAGE_INPUT)
    handler = _between(source, 'class="jup-voice ', "aria-label={$i18n.t('Voice mode')}")
    assert 'await runVoiceCall(localStorage.token)' in handler
    assert 'await goto(`/c/${started.chat_id}`)' in handler
    assert 'showCallOverlay.set(true)' not in handler


def test_every_other_way_in_goes_through_the_route_and_the_voice_chat_opens_its_call():
    source = _read(CHAT_SVELTE)
    assert 'refreshVoiceCapabilities(localStorage.token)' in source
    assert '<VoiceDisclosure />' in source
    # `?call=true` and the desktop shortcut start a call; only a just-started voice chat opens one.
    assert source.count('startVoiceCall();') == 2
    assert source.count('openCallOverlay();') == 1
    loaded = _between(source, 'const navigateHandler = async', 'const initEmbeddedDraft')
    assert 'get(pendingVoiceCall) === chatIdProp' in loaded
    assert loaded.index('get(pendingVoiceCall) === chatIdProp') < loaded.index('openCallOverlay();')


def test_the_overlay_names_its_voice_chat_when_it_transcribes():
    source = _read(CALL_OVERLAY)
    call = _between(source, 'await transcribeAudio(', ').catch(')
    assert 'chatId' in call
    assert '`${AUDIO_API_BASE_URL}/transcriptions${query}`' in _read(AUDIO_API)


def test_the_overlay_reads_only_the_sealed_answer_with_openai_speech():
    source = _read(CALL_OVERLAY)
    streamed = _between(source, 'const chatEventHandler = async', 'const chatFinishHandler')
    assert 'if (sealedSpeech()) return;' in streamed
    finished = _between(source, 'const chatFinishHandler = async', 'const toggleMute')
    queued = finished.index('await queueSealedAnswer(id, signal)')
    assert queued < finished.index('finishedMessages[id] = true;')
    assert 'synthesizeAnswerPart(localStorage.token, chatId, id, part)' in source
    assert "speaksSealedAnswers($config?.audio?.tts?.engine)" in source


def test_every_call_shows_the_reminder():
    assert 'class="jup-voice-reminder' in _read(CALL_OVERLAY)


def test_the_patch_is_registered():
    patches = _read(PATCHES)
    assert '## The call UI starts voice chats through the route' in patches
    assert 'tests/test_jup_voice_call_presence.py' in patches


def test_a_call_ends_when_the_page_moves_to_another_chat():
    assert '$: if (callChatId && chatId !== callChatId) showCallOverlay.set(false);' in _read(CALL_OVERLAY)


def test_an_interrupt_or_hang_up_stops_the_sealed_parts():
    source = _read(CALL_OVERLAY)
    stop = _between(source, 'const stopAllAudio = async', 'let audioAbortController')
    assert 'if (sealedSpeech()) audioAbortController.abort();' in stop
    fetches = _between(source, 'const queueSealedAnswer = async (id, signal)', 'const monitorAndPlayAudio')
    assert 'if (signal.aborted) return;' in fetches
    finished = _between(source, 'const chatFinishHandler = async', 'const toggleMute')
    assert finished.index('const signal = audioAbortController.signal;') < finished.index('await queueSealedAnswer(id, signal)')
