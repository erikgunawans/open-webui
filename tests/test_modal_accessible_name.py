"""The shared Modal can be named, and Ruang Pimpinan's dialogs name themselves.

The vendor `Modal.svelte` renders `role="dialog"` with no accessible name, so a screen reader
announced the source details and the context preview as just "dialog" (found 2026-09-24). The
patch adds one optional prop, `ariaLabelledby`; our dialogs point it at their `<h2>`.

Nothing fails when this patch is lost: Svelte drops the unknown prop silently and the dialogs go
back to being unnamed. This test is what notices. See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

SRC = Path(__file__).parent.parent / 'src' / 'lib' / 'components'


def test_modal_accepts_and_renders_aria_labelledby() -> None:
    source = (SRC / 'common' / 'Modal.svelte').read_text(encoding='utf-8')
    assert 'export let ariaLabelledby' in source, 'the ariaLabelledby prop is gone'
    assert 'aria-labelledby={ariaLabelledby}' in source, 'the dialog no longer renders aria-labelledby'


def test_leadership_dialogs_point_at_their_heading() -> None:
    # Every Modal under leadership/, not a hand-kept list: the full register dialog was missed
    # by the list this replaced (found 2026-09-25).
    found = 0
    for path in sorted((SRC / 'leadership').glob('*.svelte')):
        source = path.read_text(encoding='utf-8')
        for opening in re.findall(r'<Modal\b[^>]*>', source):
            found += 1
            named = re.search(r'ariaLabelledby="([^"]+)"', opening)
            assert named, f'{path.name} has an unnamed dialog: {opening}'
            assert f'id="{named.group(1)}"' in source, f'{path.name} lost the heading its dialog points at'
    assert found >= 5, f'only {found} leadership dialogs found; the scan is not seeing them'
