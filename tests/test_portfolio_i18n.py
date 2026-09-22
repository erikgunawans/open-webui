"""The portfolio's served sentences have an Indonesian rendering.

The projection writes its labels and non-coverage statements in English and stays their single
source. The page translates them at render time, keyed by the English itself, so a sentence
reworded here silently misses the lookup and an Indonesian reader gets it in English. That is
safe, since it is never a stale translation, but it is a regression nobody would see. This test is
what sees it: reword a sentence and it fails until id-ID says the new thing too.
"""

import json
from pathlib import Path

import pytest

from jup.portfolio import (
    ENGAGEMENT_NON_COVERAGE,
    PORTFOLIO_NON_COVERAGE,
    STAGE_LABELS,
    TIER_LABELS,
    TIER_MEANINGS,
)

ROOT = Path(__file__).parent.parent
ID_LOCALE = ROOT / 'src' / 'lib' / 'i18n' / 'locales' / 'id-ID' / 'translation.json'
PAGE = ROOT / 'src' / 'routes' / '(app)' / 'portfolio' / '+page.svelte'

SERVED = (
    *STAGE_LABELS.values(),
    *TIER_LABELS.values(),
    *TIER_MEANINGS.values(),
    *PORTFOLIO_NON_COVERAGE,
    *ENGAGEMENT_NON_COVERAGE,
)


@pytest.mark.parametrize('sentence', SERVED)
def test_every_served_sentence_is_translated_to_indonesian(sentence: str) -> None:
    translations = json.loads(ID_LOCALE.read_text(encoding='utf-8'))
    assert translations.get(sentence), f'id-ID has no translation for {sentence!r}'


@pytest.mark.parametrize('sentence', SERVED)
def test_every_served_sentence_is_a_key_the_page_looks_up(sentence: str) -> None:
    # A translation the page never asks for is dead, and `i18n:parse` deletes it on the next run.
    assert sentence in PAGE.read_text(encoding='utf-8'), f'the portfolio page does not look up {sentence!r}'
