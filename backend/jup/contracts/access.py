"""What a reader may see of a contract, decided in code before anything reaches the model.

Grants come from the reader's title group (D3), resolved by the host's `get_permissions`, and count
only as an exact boolean `True`: the host merges group grants with `or`, so a `"true"` typed into a
group editor arrives here unchanged and must open nothing.

- `cards`: a card, with the money fields withheld unless `money` is held too.
- `fulltext`: OCR pages and the PDF (Legal, Direksi; D4's per-unit grants come later).
- `names`: individual parties' real names, shown on display after the answer (D2). The model never
  reads a name: every card and page it receives is masked for every reader, Legal included.

D1: drafts answer too. Every view carries the card's state, so the answer can say whether Legal has
approved it.
"""

import re
from dataclasses import dataclass
from typing import Any, Iterable

from jup.contracts import cards
from jup.contracts.titles import CONTRACT_GRANTS

WITHHELD_MONEY = 'Ditahan: nilai, pembayaran, denda dan batas ganti rugi memerlukan akses nilai kontrak.'
WITHHELD_FULLTEXT = 'Ditahan: teks lengkap dan PDF kontrak memerlukan akses teks lengkap (Tim Legal atau Direksi).'
NO_CARDS = (
    'Akses kartu kontrak belum diberikan untuk akun ini. Admin menetapkannya lewat kolom Jabatan di Admin → Pengguna.'
)

STATE_LABELS: dict[str, str] = {
    'draft': 'draf, belum ditinjau Tim Legal',
    'approved': 'disetujui Tim Legal',
    'returned': 'dikembalikan Tim Legal untuk diperbaiki',
}


class Withheld(Exception):
    """The reader lacks the grant for what was asked. The message says which, in Indonesian."""


@dataclass(frozen=True)
class Access:
    cards: bool = False
    money: bool = False
    fulltext: bool = False
    names: bool = False
    review: bool = False

    @classmethod
    def from_permissions(cls, permissions: Any) -> 'Access':
        try:
            grants = permissions['jup']['contracts']
        except (KeyError, TypeError):
            return cls()
        if not isinstance(grants, dict):
            return cls()
        return cls(**{grant: grants.get(grant) is True for grant in CONTRACT_GRANTS})


def _pattern(name: str) -> re.Pattern[str]:
    words = [re.escape(word) for word in name.split()]
    return re.compile(r'(?<!\w)' + r'\s+'.join(words) + r'(?!\w)', flags=re.IGNORECASE)


def mask(text: str, parties: Iterable[dict[str, str]]) -> str:
    """Every individual party's name in `text` replaced by their code; longest names first."""
    for found in sorted(parties, key=lambda p: len(p['name']), reverse=True):
        if found['name'].strip():
            text = _pattern(found['name']).sub(found['code'], text)
    return text


def _masked_field(value: Any, parties: list[dict[str, str]]) -> Any:
    if isinstance(value, dict) and isinstance(value.get('isi'), str):
        return {**value, 'isi': mask(value['isi'], parties)}
    return value


def card_view(card: dict[str, Any] | None, reader: Access, parties: list[dict[str, str]]) -> dict[str, Any] | None:
    """The card as this reader may see it: money withheld without `money`, names always masked."""
    if not reader.cards:
        raise Withheld(NO_CARDS)
    if card is None:
        return None
    view: dict[str, Any] = {}
    for name in cards.FIELDS:
        if name in cards.MONEY_FIELDS and not reader.money:
            view[name] = {'isi': WITHHELD_MONEY, 'halaman': []}
        else:
            view[name] = _masked_field(card.get(name), parties)
    view[cards.MANUAL_PAGES] = list(card.get(cards.MANUAL_PAGES) or [])
    codes = {p['name']: p['code'] for p in parties}
    view[cards.INDIVIDUALS] = [codes.get(name, mask(name, parties)) for name in cards.individuals(card)]
    return view


def withheld_notes(reader: Access) -> list[str]:
    """What this reader cannot see, said plainly so the answer can name it."""
    notes = []
    if not reader.money:
        notes.append(WITHHELD_MONEY)
    if not reader.fulltext:
        notes.append(WITHHELD_FULLTEXT)
    return notes


def pages_view(
    pages: list[dict[str, Any]], wanted: Iterable[int], reader: Access, parties: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """The requested OCR pages, masked, for a reader with `fulltext`. Unknown page numbers are skipped."""
    if not reader.fulltext:
        raise Withheld(WITHHELD_FULLTEXT)
    wanted = set(wanted)
    return [
        {
            'halaman': page['n'],
            'teks': mask(page.get('text') or '', parties),
            'ocr_rendah': (page.get('conf') or 0) < 0.8,
        }
        for page in pages
        if page.get('n') in wanted
    ]


def resolve_codes(codes: Iterable[str], reader: Access, parties: list[dict[str, str]]) -> dict[str, str]:
    """Code → name for display after an answer, only for a reader holding `names` (D2)."""
    if not reader.names:
        return {}
    known = {p['code']: p['name'] for p in parties}
    return {code: known[code] for code in codes if code in known}
