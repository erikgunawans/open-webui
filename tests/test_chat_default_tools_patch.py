"""A `?q=` auto-submit waits for the model's default tools before it sends.

`Chat.svelte`'s `setDefaults()` copies the selected model's `meta.toolIds` into the composer. On a
fresh load it first awaits the tool list, and the vendor guarded re-entry with an early return, so
a second caller came back at once while the first was still waiting. `initNewChat` is that second
caller, and it auto-submits `?q=` straight after, so the turn went out with no `tool_ids` and the
model was never offered `portfolio_status` (reproduced live 2026-09-23; a typed chat was
unaffected, because a person types slower than three fetches).

Nothing fails when this patch is lost: the chat still answers, just without the tool. This test is
what notices. See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

CHAT = Path(__file__).parent.parent / 'src' / 'lib' / 'components' / 'chat' / 'Chat.svelte'


def _source() -> str:
    return CHAT.read_text(encoding='utf-8')


def test_set_defaults_waits_for_an_in_flight_run_instead_of_returning() -> None:
    source = _source()
    assert 'if (settingDefaults) return;' not in source, 'the vendor early return is back'
    body = re.search(r'const setDefaults = async \(\) => \{(.*?)\n\t\};', source, re.S)
    assert body, 'setDefaults() not found'
    assert 'await defaultsSettled();' in body.group(1)


def test_q_auto_submit_waits_for_defaults_before_submitting() -> None:
    source = _source()
    branch = source[source.index("$page.url.searchParams.get('q')") :]
    settled = branch.index('await defaultsSettled();')
    submit = branch.index('submitHandler(q);')
    assert settled < submit, '?q= submits before the default tools are selected'
