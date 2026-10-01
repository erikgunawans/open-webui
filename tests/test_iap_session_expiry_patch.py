"""IAP session expiry is told apart from app-session expiry and unsticks the chat (#47).

The IAP/GCIP session ends about an hour after sign-in. `+layout.svelte` sends the AJAX hint so
IAP answers 401 instead of a 302 that `fetch` cannot follow, and checks for IAP's own 401 BEFORE
the vendor's 401 handler: that handler signs the user out and wipes the token, which would turn
every hourly IAP expiry into a forced app sign-out. `Chat.svelte` marks the cut answer interrupted
so later messages are not queued behind it.

Nothing fails loudly when these hooks are lost. This test is what notices. See
`deploy/gcp/VENDOR-PATCHES.md`.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent
LAYOUT = ROOT / 'src' / 'routes' / '+layout.svelte'
CHAT = ROOT / 'src' / 'lib' / 'components' / 'chat' / 'Chat.svelte'


def test_layout_fetch_wrapper_checks_iap_before_the_vendor_sign_out() -> None:
    source = LAYOUT.read_text(encoding='utf-8')
    wrapper = source[source.index('window.fetch = async (input, init) => {') :]
    hint = wrapper.index('withIapAjaxHeader(input, init, window.location.origin)')
    fetch = wrapper.index('await originalFetch(input, init)')
    iap = wrapper.index('if (isIapExpiry(response))')
    sign_out = wrapper.index('clearExpiredSession()')
    assert hint < fetch, 'the AJAX hint must be added before the request goes out'
    assert fetch < iap < sign_out, "IAP's 401 must be handled before the vendor signs the user out"


def test_failed_socket_reconnect_probes_the_iap_session() -> None:
    source = LAYOUT.read_text(encoding='utf-8')
    handler = source[source.index("_socket.on('connect_error'") :]
    assert 'probeIapSession();' in handler[: handler.index('});')]


def test_chat_interrupts_the_cut_answer_and_refuses_to_queue() -> None:
    source = CHAT.read_text(encoding='utf-8')
    assert '$: if ($iapSessionExpired) interruptForIapExpiry();' in source
    submit = source[source.index('const submitHandler = async (userPrompt') :]
    guard = submit.index('if ($iapSessionExpired) {')
    queue = submit.index('chatRequestQueues.update(')
    assert guard < queue, 'an expired session must stop the send before anything is queued'
