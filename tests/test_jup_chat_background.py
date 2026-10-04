"""The JUP chat background: Settings → Antarmuka → Latar Obrolan, Putih Polos or Pola JUP.

`Chat.svelte` and `InterfaceSettings.svelte` are vendor code. A rebase (ADR-0007) that takes
upstream's side drops the choice silently: the setting stays saved and nothing draws it. The pattern
must also stay out from under the vendor's white wash, which is what made Erik's upload of the same
image invisible (2026-10-05). See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAT = ROOT / 'src' / 'lib' / 'components' / 'chat' / 'Chat.svelte'
SETTINGS = ROOT / 'src' / 'lib' / 'components' / 'common' / 'InterfaceSettings.svelte'
ID_ID = ROOT / 'src' / 'lib' / 'i18n' / 'locales' / 'id-ID' / 'translation.json'


def _pattern_branch() -> str:
    match = re.search(
        r"\{:else if !embedded && \$settings\?\.jupChatBackground === 'jup'\}(.*?)\{:else if",
        CHAT.read_text(encoding='utf-8'),
        flags=re.S,
    )
    assert match, 'the JUP pattern branch is gone from Chat.svelte'
    return match.group(1)


def test_the_pattern_is_drawn_whole_and_without_the_white_wash() -> None:
    branch = _pattern_branch()
    assert '/static/jup-chat-pattern.png' in branch
    # contain, not cover: cover crops the logos off both bottom corners on a normal window.
    assert 'bg-contain' in branch and 'bg-bottom' in branch
    assert 'from-white' not in branch, 'the vendor wash hides the pale pattern entirely'
    assert 'dark:hidden' in branch


def test_the_pattern_wins_over_an_uploaded_image_but_not_a_folder_background() -> None:
    source = CHAT.read_text(encoding='utf-8')
    folder = source.index('$selectedFolder?.meta?.background_image_url}')
    pattern = source.index("$settings?.jupChatBackground === 'jup'")
    upload = source.index('$settings?.backgroundImageUrl ??')
    assert folder < pattern < upload


def test_the_setting_toggles_and_saves() -> None:
    source = SETTINGS.read_text(encoding='utf-8')
    assert "jupChatBackground = currentSettings?.jupChatBackground === 'jup' ? 'jup' : 'plain';" in source
    assert "jupChatBackground = jupChatBackground === 'jup' ? 'plain' : 'jup';" in source
    assert 'saveSettings({ jupChatBackground });' in source


def test_the_image_ships_in_both_static_trees() -> None:
    for tree in (ROOT / 'static' / 'static', ROOT / 'backend' / 'open_webui' / 'static'):
        assert (tree / 'jup-chat-pattern.png').stat().st_size > 0


def test_every_string_has_an_indonesian_value() -> None:
    source = ID_ID.read_text(encoding='utf-8')
    for key in (
        'Chat Background',
        'JUP Pattern',
        'Plain White',
        'Show the JUP pattern behind the chat, or keep it plain white.',
    ):
        assert re.search(rf'"{re.escape(key)}": "[^"]+"', source), key
