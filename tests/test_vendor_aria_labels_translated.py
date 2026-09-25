"""Everyday vendor controls announce their name through i18n, not as hardcoded English.

Open WebUI wrote these `aria-label`s as string literals, so no translation could reach them: under
id-ID a screen reader still said "New Chat", "Chat Menu", "Voice Input" (found 2026-09-25). The
update toast's close button had no name at all; it was the third tab stop on every page.

A rebase that takes the vendor's version back loses the fix silently. This test is what notices.
See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

SRC = Path(__file__).parent.parent / 'src' / 'lib' / 'components'

TRANSLATED = {
    'chat/Navbar.svelte': ['New Chat', 'Controls'],
    'chat/MessageInput.svelte': ['Available Tools', 'Voice Input', 'Expand input'],
    'channel/MessageInput.svelte': ['Voice Input'],
    'chat/Messages/ResponseMessage.svelte': ['Fork chat'],
    'layout/Sidebar/ChatItem.svelte': ['Chat Menu'],
    'layout/SearchModal.svelte': ['Chat Menu'],
    'layout/UpdateInfoToast.svelte': ['Close'],
    'common/InputModal.svelte': ['Close'],
    'common/CodeEditorModal.svelte': ['Close'],
    'common/PDFViewer.svelte': ['Zoom out', 'Zoom in', 'Reset zoom'],
    'common/PptxPreview.svelte': ['Zoom out', 'Zoom in', 'Reset zoom'],
    'common/DocxPreview.svelte': ['Zoom out', 'Zoom in', 'Reset zoom'],
}


def test_labels_go_through_i18n() -> None:
    for name, labels in TRANSLATED.items():
        source = (SRC / name).read_text(encoding='utf-8')
        assert re.search(r"i18n = getContext(<[^>]*>+)?\('i18n'\)", source), f'{name} lost its i18n context'
        for label in labels:
            assert f'aria-label="{label}"' not in source, f'{name}: "{label}" is hardcoded English again'
            assert f"aria-label={{$i18n.t('{label}')}}" in source, f'{name}: "{label}" is not translated'


def test_update_toast_close_button_is_named() -> None:
    source = (SRC / 'layout' / 'UpdateInfoToast.svelte').read_text(encoding='utf-8')
    buttons = re.findall(r'<button\b[^>]*>', source)
    assert buttons, 'the scan found no button in the update toast'
    for opening in buttons:
        assert 'aria-label=' in opening, f'unnamed button in the update toast: {opening}'
