"""Ruang Pimpinan's repeated row buttons say what they act on, and Select says whether it is on.

Every metric card, assumption row and action row carries the same "Select", "Source" and
"Details" buttons. A screen reader tabbing through the board heard "Select, button" and
"Source, button" three times over with nothing to tell them apart, and nothing announced which
record was selected: the choice showed only as a card outline (found by the keyboard pass,
2026-09-25). Each button now points `aria-describedby` at its record's title, and Select carries
`aria-pressed`.
"""

import re
from pathlib import Path

LEADERSHIP = Path(__file__).parent.parent / 'src' / 'lib' / 'components' / 'leadership'
LABELS = ('Select', 'Source', 'Details')
# A label may sit behind a count ternary: `{ids.length > 1 ? $i18n.t('Source {{n}}', …) : …}`.
BUTTON = re.compile(
    r"<button\b((?:=>|[^>])*?)>\s*\{(?:[^{}?]*\?\s*)?\$i18n\.t\('(" + '|'.join(LABELS) + r")(?: \{\{n\}\})?'",
    re.S,
)


def test_row_buttons_name_their_record() -> None:
    found = 0
    for path in sorted(LEADERSHIP.glob('*.svelte')):
        source = path.read_text(encoding='utf-8')
        for attrs, label in BUTTON.findall(source):
            if 'jlp-link' not in attrs:
                continue
            found += 1
            described = re.search(r'aria-describedby="([^"]+)"', attrs)
            assert described, f'{path.name}: a "{label}" button does not say which record it acts on'
            assert f'id="{described.group(1)}"' in source, (
                f'{path.name}: "{label}" points at {described.group(1)}, which no element carries'
            )
            if label == 'Select':
                assert 'aria-pressed=' in attrs, f'{path.name}: Select does not announce whether it is on'
    assert found >= 8, f'only {found} row buttons found; the scan is not seeing them'
