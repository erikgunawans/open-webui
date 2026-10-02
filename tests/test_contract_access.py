"""Who sees what of a contract card, and masking of individual parties (D1, D2, D3). Pure; no server."""

import pytest

from jup.contracts import access, titles
from jup.contracts.cards import FIELDS

PARTIES = [{'code': 'Perorangan A', 'name': 'Budi Santoso'}, {'code': 'Perorangan B', 'name': 'Siti'}]


def _card() -> dict:
    value = {name: {'isi': f'isi {name}', 'halaman': [1]} for name in FIELDS}
    value['mitra'] = {'isi': 'Budi  Santoso dan PT Contoh', 'halaman': [1]}
    value['nilai_dan_pembayaran'] = {'isi': 'Rp 5 miliar dibayar oleh BUDI SANTOSO', 'halaman': [3]}
    value['perorangan_non_penandatangan'] = ['Budi Santoso']
    value['halaman_perlu_diperiksa_manual'] = [4]
    return value


def _access(title: str | None) -> access.Access:
    return access.Access.from_permissions(titles.grants(title) if title else {})


def test_grants_must_be_exact_true() -> None:
    loose = {'jup': {'contracts': {'cards': 'true', 'money': 1, 'fulltext': True}}}
    got = access.Access.from_permissions(loose)
    assert (got.cards, got.money, got.fulltext) == (False, False, True)
    assert access.Access.from_permissions(None) == access.Access()


@pytest.mark.parametrize(
    ('title', 'cards', 'money', 'fulltext', 'names'),
    [
        (None, False, False, False, False),
        ('staff', True, False, False, False),
        ('manager', True, True, False, False),
        ('legal', True, True, True, True),
        ('direksi', True, True, True, True),
    ],
)
def test_titles_map_to_access(title, cards, money, fulltext, names) -> None:
    got = _access(title)
    assert (got.cards, got.money, got.fulltext, got.names) == (cards, money, fulltext, names)


def test_masking_replaces_names_whatever_their_case_or_spacing() -> None:
    masked = access.mask('Budi  Santoso, budi santoso dan SITI; Sitinah tetap', PARTIES)
    assert masked == 'Perorangan A, Perorangan A dan Perorangan B; Sitinah tetap'


def test_masking_longest_name_first() -> None:
    parties = [{'code': 'Perorangan A', 'name': 'Budi'}, {'code': 'Perorangan B', 'name': 'Budi Santoso'}]
    assert access.mask('Budi Santoso dan Budi', parties) == 'Perorangan B dan Perorangan A'


def test_staff_card_withholds_money_and_masks_names() -> None:
    view = access.card_view(_card(), _access('staff'), PARTIES)
    assert view['nilai_dan_pembayaran'] == {'isi': access.WITHHELD_MONEY, 'halaman': []}
    assert view['wanprestasi_ganti_rugi']['isi'] == access.WITHHELD_MONEY
    assert view['mitra']['isi'] == 'Perorangan A dan PT Contoh'
    assert view['perorangan_non_penandatangan'] == ['Perorangan A']
    assert 'Budi' not in repr(view)


def test_manager_card_keeps_money_but_masks_names_in_it() -> None:
    view = access.card_view(_card(), _access('manager'), PARTIES)
    assert view['nilai_dan_pembayaran']['isi'] == 'Rp 5 miliar dibayar oleh Perorangan A'
    assert 'Budi' not in repr(view)


def test_even_legal_gets_masked_text_for_the_model() -> None:
    # D2 unmasks for Legal and Direksi after the answer, on display, never in what the model reads.
    assert 'Budi' not in repr(access.card_view(_card(), _access('legal'), PARTIES))


def test_no_cards_grant_means_no_view() -> None:
    with pytest.raises(access.Withheld):
        access.card_view(_card(), _access(None), PARTIES)


def test_withheld_lists_name_what_is_missing() -> None:
    assert access.withheld_notes(_access('staff')) == [access.WITHHELD_MONEY, access.WITHHELD_FULLTEXT]
    assert access.withheld_notes(_access('legal')) == []


@pytest.mark.parametrize(
    ('state', 'label'),
    [
        ('draft', 'draf, belum ditinjau Tim Legal'),
        ('approved', 'disetujui Tim Legal'),
        ('returned', 'dikembalikan Tim Legal untuk diperbaiki'),
    ],
)
def test_every_state_has_a_label(state: str, label: str) -> None:
    assert access.STATE_LABELS[state] == label


def test_pages_need_fulltext_and_come_back_masked() -> None:
    pages = [{'n': 1, 'text': 'Pihak pertama Budi Santoso', 'conf': 0.9}, {'n': 2, 'text': 'x', 'conf': 0.5}]
    with pytest.raises(access.Withheld):
        access.pages_view(pages, [1], _access('manager'), PARTIES)
    got = access.pages_view(pages, [1, 2, 9], _access('direksi'), PARTIES)
    assert got == [
        {'halaman': 1, 'teks': 'Pihak pertama Perorangan A', 'ocr_rendah': False},
        {'halaman': 2, 'teks': 'x', 'ocr_rendah': True},
    ]


def test_unmask_only_with_the_names_grant() -> None:
    assert access.resolve_codes(['Perorangan A', 'Perorangan Z'], _access('legal'), PARTIES) == {
        'Perorangan A': 'Budi Santoso'
    }
    assert access.resolve_codes(['Perorangan A'], _access('manager'), PARTIES) == {}
