"""The sidebar's knowledge-review entry, in both the collapsed rail and the expanded list.

`Sidebar.svelte` is vendor code. A rebase (ADR-0007) that takes upstream's side of a conflict drops
the entry silently: the page still works at /kb-review, and nobody can find it. A source read
catches it under `--only-group dev`. See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDEBAR = ROOT / 'src' / 'lib' / 'components' / 'layout' / 'Sidebar.svelte'
KB_REVIEW = ROOT / 'src' / 'lib' / 'components' / 'kb-review'


def _source() -> str:
    return SIDEBAR.read_text(encoding='utf-8')


def test_the_entry_is_shown_to_a_submitter_or_an_admin() -> None:
    source = _source()
    assert "import { kbReviewAccess } from '$lib/stores/kbReview';" in source
    assert "$: showKbReview = $kbReviewAccess.submit || $user?.role === 'admin';" in source


def test_the_entry_is_in_both_the_rail_and_the_list() -> None:
    blocks = re.findall(r'\{#if showKbReview\}(.*?)\{/if\}', _source(), flags=re.S)
    assert len(blocks) == 2, f'expected the rail and the expanded list, found {len(blocks)}'
    for block in blocks:
        assert 'href="/kb-review"' in block
        assert "aria-label={$i18n.t('Knowledge review')}" in block
        assert "aria-current={kbReviewActive ? 'page' : undefined}" in block
        # Prettier puts the attribute on its own line when the tag grows; either layout counts.
        assert re.search(r"<Tooltip\s+content=\{\$i18n\.t\('Knowledge review'\)\}", block)
        assert '<DocumentArrowUpIcon' in block


def test_the_review_dialog_is_named_by_its_heading() -> None:
    found = 0
    for path in sorted(KB_REVIEW.glob('*.svelte')):
        source = path.read_text(encoding='utf-8')
        for opening in re.findall(r'<Modal\b[^>]*>', source):
            found += 1
            named = re.search(r'ariaLabelledby="([^"]+)"', opening)
            assert named, f'{path.name} has an unnamed dialog: {opening}'
            assert f'id="{named.group(1)}"' in source, f'{path.name} lost the heading its dialog points at'
    assert found >= 1, 'the review dialog is gone, or the scan is not seeing it'
