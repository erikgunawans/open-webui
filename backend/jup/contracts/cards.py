"""The contract card: its fields, which of them are money, and how to read one.

The field list is the drafting schema in `deploy/gcp/legal-kb/lib.ts` (FAQ Kontrak topics); each field
is `{"isi": text, "halaman": [page, …]}`. A test holds the two lists equal.
"""

from typing import Any

FIELDS: tuple[str, ...] = (
    'mitra',
    'nomor_pks',
    'judul',
    'tanggal_tanda_tangan',
    'jenis_dokumen',
    'hak_kewajiban_lingkup',
    'nilai_dan_pembayaran',
    'jangka_waktu_perpanjangan',
    'pengakhiran',
    'wanprestasi_ganti_rugi',
    'kerahasiaan_hki',
    'keadaan_kahar',
    'penyelesaian_sengketa',
    'keabsahan',
    'hubungan_dokumen',
)

# Withheld without the `money` grant: value and payment, and penalties and damages caps.
MONEY_FIELDS: frozenset[str] = frozenset({'nilai_dan_pembayaran', 'wanprestasi_ganti_rugi'})

MANUAL_PAGES = 'halaman_perlu_diperiksa_manual'
INDIVIDUALS = 'perorangan_non_penandatangan'


def text(card: dict[str, Any] | None, name: str) -> str | None:
    """A field's text, or None when the card or the field is missing or says nothing."""
    if not isinstance(card, dict):
        return None
    value = card.get(name)
    if not isinstance(value, dict):
        return None
    content = value.get('isi')
    if not isinstance(content, str) or not content.strip() or content.strip().lower() == 'tidak tercantum':
        return None
    return content.strip()


def individuals(card: dict[str, Any] | None) -> list[str]:
    """The individual parties the draft listed, stripped and without blanks."""
    if not isinstance(card, dict):
        return []
    names = card.get(INDIVIDUALS) or []
    return [name.strip() for name in names if isinstance(name, str) and name.strip()]
