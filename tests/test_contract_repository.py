"""The contract repository and the run import, against a scratch SQLite migrated by the real graph.

Card records are synthetic: no contract data is ever in the repo. Needs the runtime (alembic,
sqlalchemy).
"""

import json
from pathlib import Path

import pytest

# A skip mark would not stop the imports below, and `jup.contracts.models` needs sqlalchemy, which
# CI's `--only-group dev` job does not install.
pytest.importorskip('sqlalchemy', reason='the runtime tree is not installed')
pytest.importorskip('alembic', reason='the runtime tree is not installed')

from jup.contracts import imports, migrate, repository  # noqa: E402
from jup.contracts.cards import FIELDS  # noqa: E402


def _field(text: str, pages: list[int] | None = None) -> dict:
    return {'isi': text, 'halaman': pages or [1]}


def card(**overrides) -> dict:
    value = {name: _field('tidak tercantum', []) for name in FIELDS}
    value.update(
        mitra=_field('PT Contoh Mitra'),
        nomor_pks=_field('001/PKS/JUP/2020'),
        judul=_field('Perjanjian Kerja Sama Contoh'),
        jenis_dokumen=_field('PKS'),
        nilai_dan_pembayaran=_field('Rp 1.000.000.000', [3]),
    )
    value['halaman_perlu_diperiksa_manual'] = []
    value['perorangan_non_penandatangan'] = []
    value.update(overrides)
    return value


def record(number: str, item: str, value: dict | None = None, **extra) -> dict:
    return {
        'n': number,
        'path': ['SCAN PERJANJIAN', 'PT Contoh Mitra'],
        'file': f'{number}.pdf',
        'bytes': 1000,
        'itemId': item,
        'webUrl': f'https://example.invalid/{item}',
        'gcs': f'gs://bucket/full/src/{number}.pdf',
        'pages': 4,
        'ocrChars': 5000,
        'ocrLowConfidencePages': [2],
        'model': 'gemini-2.5-flash',
        'draftedAt': '2026-10-02T00:00:00Z',
        'card': card() if value is None else value,
        **extra,
    }


@pytest.fixture
def engine(tmp_path: Path):
    from sqlalchemy import create_engine

    engine = create_engine(f'sqlite:///{tmp_path / "c.db"}')
    assert migrate.run_contract_migrations(engine)
    return engine


def _write_run(root: Path, run: str, records: list[dict]) -> None:
    cards = root / run / 'cards'
    cards.mkdir(parents=True)
    for rec in records:
        (cards / f'{rec["n"]}.json').write_text(json.dumps(rec), encoding='utf-8')


def test_a_new_record_is_created_as_a_draft_with_an_event(engine) -> None:
    assert repository.import_record(engine, record('0001', 'item-1'), run='full', actor='admin') == 'created'
    row = repository.get_contract(engine, run='full', number='0001')
    assert row['state'] == 'draft'
    assert row['partner'] == 'PT Contoh Mitra' and row['contract_number'] == '001/PKS/JUP/2020'
    assert json.loads(row['current_card']) == json.loads(row['draft_card'])
    assert json.loads(row['low_confidence_pages']) == [2]
    assert row['version'] == 1
    events = repository.events(engine, row['id'])
    assert [e['kind'] for e in events] == ['imported']


def test_the_same_record_again_changes_nothing(engine) -> None:
    repository.import_record(engine, record('0001', 'item-1'), run='full', actor='admin')
    assert repository.import_record(engine, record('0001', 'item-1'), run='full', actor='admin') == 'unchanged'


def test_a_redraft_replaces_an_untouched_draft(engine) -> None:
    repository.import_record(engine, record('0001', 'item-1'), run='full', actor='admin')
    changed = record('0001', 'item-1', card(judul=_field('Judul baru')))
    assert repository.import_record(engine, changed, run='full', actor='admin') == 'updated'
    row = repository.get_contract(engine, run='full', number='0001')
    assert row['title'] == 'Judul baru'
    assert [e['kind'] for e in repository.events(engine, row['id'])] == ['imported', 'redrafted']


def test_a_redraft_never_overwrites_legal_work(engine) -> None:
    repository.import_record(engine, record('0001', 'item-1'), run='full', actor='admin')
    row = repository.get_contract(engine, run='full', number='0001')
    repository.set_state(engine, row['id'], 'approved', actor='legal')
    changed = record('0001', 'item-1', card(judul=_field('Judul baru')))
    assert repository.import_record(engine, changed, run='full', actor='admin') == 'redraft_held'
    row = repository.get_contract(engine, run='full', number='0001')
    assert row['state'] == 'approved'
    assert row['title'] == 'Perjanjian Kerja Sama Contoh'
    assert json.loads(row['draft_card'])['judul']['isi'] == 'Judul baru'


def test_a_skipped_scan_is_kept_without_a_card(engine) -> None:
    rec = record('0002', 'item-2', value=None)
    rec['card'] = None
    rec['skipped'] = 'no-ocr-text'
    assert repository.import_record(engine, rec, run='full', actor='admin') == 'created'
    row = repository.get_contract(engine, run='full', number='0002')
    assert row['draft_card'] is None and row['partner'] is None


def test_individual_parties_get_global_codes_shared_across_contracts(engine) -> None:
    repository.import_record(
        engine,
        record('0001', 'item-1', card(perorangan_non_penandatangan=['Budi Santoso', 'Siti Aminah'])),
        run='full',
        actor='admin',
    )
    repository.import_record(
        engine,
        record('0002', 'item-2', card(perorangan_non_penandatangan=['  budi   SANTOSO ', 'Agus'])),
        run='full',
        actor='admin',
    )
    one = repository.get_contract(engine, run='full', number='0001')
    two = repository.get_contract(engine, run='full', number='0002')
    first = {p['name']: p['code'] for p in repository.parties(engine, one['id'])}
    second = {p['code'] for p in repository.parties(engine, two['id'])}
    assert first == {'Budi Santoso': 'Perorangan A', 'Siti Aminah': 'Perorangan B'}
    assert second == {'Perorangan A', 'Perorangan C'}


@pytest.mark.parametrize(('index', 'code'), [(0, 'A'), (25, 'Z'), (26, 'AA'), (27, 'AB'), (701, 'ZZ'), (702, 'AAA')])
def test_codes_count_like_spreadsheet_columns(index: int, code: str) -> None:
    assert repository.party_code(index) == f'Perorangan {code}'


def test_a_run_import_counts_and_skips_unreadable_files(engine, tmp_path: Path) -> None:
    root = tmp_path / 'bucket'
    _write_run(root, 'full', [record('0001', 'item-1'), record('0002', 'item-2')])
    (root / 'full' / 'cards' / '0003.json').write_text('{not json', encoding='utf-8')
    (root / 'full' / 'cards' / 'summary.txt').write_text('x', encoding='utf-8')
    result = imports.import_run(engine, root, 'full', actor='admin')
    assert result == {'created': 2, 'updated': 0, 'unchanged': 0, 'redraft_held': 0, 'unreadable': 1, 'dated': 0}
    again = imports.import_run(engine, root, 'full', actor='admin')
    assert again['unchanged'] == 2 and again['created'] == 0


def test_a_run_name_cannot_leave_the_root(engine, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        imports.import_run(engine, tmp_path, '../etc', actor='admin')


def _dates(root: Path, run: str, number: str, **values) -> None:
    folder = root / run / 'dates'
    folder.mkdir(parents=True, exist_ok=True)
    body = {'n': number, 'tanggal_mulai': '', 'tanggal_berakhir': '', 'perpanjangan_otomatis': 'tidak jelas', **values}
    (folder / f'{number}.json').write_text(json.dumps(body), encoding='utf-8')


def test_dates_are_imported_and_counted(engine, tmp_path: Path) -> None:
    root = tmp_path / 'bucket'
    _write_run(root, 'full', [record('0001', 'item-1'), record('0002', 'item-2')])
    _dates(root, 'full', '0001', tanggal_mulai='2020-01-01', tanggal_berakhir='2025-01-01', perpanjangan_otomatis='ya')
    _dates(root, 'full', '0002', tanggal_berakhir='not a date')
    result = imports.import_run(engine, root, 'full', actor='admin')
    assert result['dated'] == 1
    row = repository.get_contract(engine, run='full', number='0001')
    assert (row['start_date'], row['end_date'], row['auto_renewal']) == ('2020-01-01', '2025-01-01', True)
    assert repository.get_contract(engine, run='full', number='0002')['end_date'] is None
    assert [e['kind'] for e in repository.events(engine, row['id'])] == ['imported', 'dates_set']
    # Same dates again: no new event.
    assert imports.import_run(engine, root, 'full', actor='admin')['dated'] == 0


def test_dates_edited_by_legal_are_kept(engine, tmp_path: Path) -> None:
    root = tmp_path / 'bucket'
    _write_run(root, 'full', [record('0001', 'item-1')])
    imports.import_run(engine, root, 'full', actor='admin')
    row = repository.get_contract(engine, run='full', number='0001')
    repository.set_dates(
        engine, row['id'], start='2021-01-01', end='2026-01-01', auto_renewal=False, actor='legal', kind='dates_edited'
    )
    _dates(root, 'full', '0001', tanggal_berakhir='2030-01-01')
    assert imports.import_run(engine, root, 'full', actor='admin')['dated'] == 0
    assert repository.get_contract(engine, run='full', number='0001')['end_date'] == '2026-01-01'
