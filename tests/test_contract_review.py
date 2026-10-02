"""Legal's review rules (`jup.contracts.review`) against a scratch SQLite migrated by the real graph.

Card records are synthetic: no contract data is ever in the repo. Needs the runtime (alembic,
sqlalchemy).
"""

import json
from pathlib import Path

import pytest

pytest.importorskip('sqlalchemy', reason='the runtime tree is not installed')
pytest.importorskip('alembic', reason='the runtime tree is not installed')

from jup.contracts import migrate, repository, review  # noqa: E402
from jup.contracts.cards import FIELDS  # noqa: E402


def _field(text: str, pages: list[int] | None = None) -> dict:
    return {'isi': text, 'halaman': pages or [1]}


def card(partner: str = 'PT Contoh Mitra', individuals: list[str] | None = None, manual: list[int] | None = None):
    value = {name: _field('tidak tercantum', []) for name in FIELDS}
    value.update(
        mitra=_field(partner),
        nomor_pks=_field('001/PKS/JUP/2020'),
        judul=_field('Perjanjian Kerja Sama Contoh'),
        hak_kewajiban_lingkup=_field('Pihak kedua, Budi Santoso, menyewa lahan.', [2]),
    )
    value['halaman_perlu_diperiksa_manual'] = manual or []
    value['perorangan_non_penandatangan'] = individuals or []
    return value


def record(number: str, value: dict, low: list[int] | None = None) -> dict:
    return {
        'n': number,
        'path': ['SCAN PERJANJIAN', 'Mitra'],
        'file': f'{number}.pdf',
        'itemId': f'item-{number}',
        'gcs': f'gs://bucket/full/src/{number}.pdf',
        'pages': 4,
        'ocrLowConfidencePages': low or [],
        'model': 'gemini-2.5-flash',
        'card': value,
    }


@pytest.fixture
def engine(tmp_path: Path):
    from sqlalchemy import create_engine

    engine = create_engine(f'sqlite:///{tmp_path / "c.db"}')
    assert migrate.run_contract_migrations(engine)
    repository.import_record(engine, record('0001', card()), run='full', actor='admin')
    repository.import_record(
        engine, record('0002', card('CV Lain', individuals=['Budi Santoso'])), run='full', actor='admin'
    )
    repository.import_record(engine, record('0003', card('PT Ketiga', manual=[3]), low=[2]), run='full', actor='admin')
    return engine


def _id(engine, number: str) -> str:
    return repository.get_contract(engine, run='full', number=number)['id']


def _row(engine, number: str) -> dict:
    return repository.get_contract(engine, run='full', number=number)


# --- Queue -----------------------------------------------------------------------------------------


def test_the_queue_puts_individual_parties_first_then_manual_checks(engine) -> None:
    page = review.queue(engine)
    assert [item['number'] for item in page['items']] == ['0002', '0003', '0001']
    assert page['total'] == 3
    assert page['counts'] == {'perorangan': 1, 'manual': 1, 'low_ocr': 1, 'draft': 3, 'approved': 0, 'returned': 0}
    assert page['items'][0]['individuals'] == 1


@pytest.mark.parametrize(
    ('filters', 'expected'),
    [
        ({'flag': 'perorangan'}, ['0002']),
        ({'flag': 'manual'}, ['0003']),
        ({'flag': 'low_ocr'}, ['0003']),
        ({'q': 'ketiga'}, ['0003']),
        ({'q': '0001'}, ['0001']),
        ({'state': 'approved'}, []),
    ],
)
def test_queue_filters(engine, filters: dict, expected: list[str]) -> None:
    assert [item['number'] for item in review.queue(engine, **filters)['items']] == expected


def test_queue_counts_ignore_the_filter_and_bad_filters_are_refused(engine) -> None:
    assert review.queue(engine, flag='manual')['counts']['perorangan'] == 1
    with pytest.raises(review.Invalid):
        review.queue(engine, flag='nope')
    with pytest.raises(review.Invalid):
        review.queue(engine, state='nope')


def test_queue_pages(engine) -> None:
    first = review.queue(engine, limit=2)
    second = review.queue(engine, limit=2, offset=2)
    assert [i['number'] for i in first['items'] + second['items']] == ['0002', '0003', '0001']
    assert review.queue(engine, limit=10_000)['limit'] == review.MAX_LIMIT


# --- Detail ----------------------------------------------------------------------------------------


def test_detail_carries_the_card_its_hash_parties_and_events(engine) -> None:
    found = review.detail(engine, _id(engine, '0002'))
    assert found['card']['mitra']['isi'] == 'CV Lain'
    assert found['card_sha256'] == review.card_sha256(_row(engine, '0002')['current_card'])
    assert found['parties'] == [{'code': 'Perorangan A', 'name': 'Budi Santoso'}]
    assert [e['kind'] for e in found['events']] == ['imported']
    assert found['draft_card'] is None
    assert review.detail(engine, 'missing') is None


# --- Field edits -----------------------------------------------------------------------------------


def test_an_edit_lands_once_and_a_stale_version_conflicts(engine) -> None:
    contract_id = _id(engine, '0001')
    done = review.edit_field(
        engine, contract_id, 'mitra', text='PT Benar', pages=[1], expected_version=1, actor='legal'
    )
    assert done['version'] == 2 and done['changed'] is True
    row = _row(engine, '0001')
    assert row['partner'] == 'PT Benar'
    assert json.loads(row['current_card'])['mitra'] == {'isi': 'PT Benar', 'halaman': [1]}
    assert json.loads(row['draft_card'])['mitra']['isi'] == 'PT Contoh Mitra'
    with pytest.raises(review.Conflict):
        review.edit_field(engine, contract_id, 'mitra', text='PT Lain', pages=[1], expected_version=1, actor='legal')
    event = repository.events(engine, contract_id)[-1]
    assert event['kind'] == 'field_edited' and event['actor'] == 'legal'
    assert json.loads(event['payload'])['before']['isi'] == 'PT Contoh Mitra'


def test_editing_an_approved_card_puts_it_back_to_draft(engine) -> None:
    contract_id = _id(engine, '0001')
    sha = review.detail(engine, contract_id)['card_sha256']
    review.approve(engine, contract_id, card_sha256=sha, expected_version=1, actor='legal')
    done = review.edit_field(
        engine, contract_id, 'judul', text='Judul baru', pages=[1], expected_version=2, actor='legal'
    )
    assert done['state'] == 'draft' and _row(engine, '0001')['state'] == 'draft'


def test_an_unchanged_edit_writes_nothing(engine) -> None:
    contract_id = _id(engine, '0001')
    done = review.edit_field(
        engine, contract_id, 'mitra', text='PT Contoh Mitra', pages=[1], expected_version=1, actor='legal'
    )
    assert done['changed'] is False and _row(engine, '0001')['version'] == 1


@pytest.mark.parametrize(
    ('field', 'text', 'pages'),
    [
        ('bukan_field', 'x', [1]),
        ('mitra', '  ', [1]),
        ('mitra', 'x', [9]),
        ('mitra', 'x', [0]),
        ('mitra', 'x', ['1']),
        ('mitra', 'x' * (review.MAX_TEXT + 1), [1]),
    ],
)
def test_malformed_edits_are_refused(engine, field: str, text: str, pages: list) -> None:
    with pytest.raises(review.Invalid):
        review.edit_field(engine, _id(engine, '0001'), field, text=text, pages=pages, expected_version=1, actor='legal')
    assert _row(engine, '0001')['version'] == 1


# --- Approve and return ----------------------------------------------------------------------------


def test_approve_needs_the_hash_of_the_card_read(engine) -> None:
    contract_id = _id(engine, '0001')
    with pytest.raises(review.Conflict):
        review.approve(engine, contract_id, card_sha256='0' * 64, expected_version=1, actor='legal')
    sha = review.detail(engine, contract_id)['card_sha256']
    assert (
        review.approve(engine, contract_id, card_sha256=sha, expected_version=1, actor='legal')['state'] == 'approved'
    )
    event = repository.events(engine, contract_id)[-1]
    assert event['kind'] == 'approved' and json.loads(event['payload'])['card_sha256'] == sha


def test_approve_refuses_a_card_edited_since_it_was_read(engine) -> None:
    contract_id = _id(engine, '0001')
    sha = review.detail(engine, contract_id)['card_sha256']
    review.edit_field(engine, contract_id, 'judul', text='Diubah', pages=[1], expected_version=1, actor='other')
    with pytest.raises(review.Conflict):
        review.approve(engine, contract_id, card_sha256=sha, expected_version=2, actor='legal')


def test_return_needs_a_reason_and_keeps_it(engine) -> None:
    contract_id = _id(engine, '0001')
    with pytest.raises(review.Invalid):
        review.return_card(engine, contract_id, reason=' ', expected_version=1, actor='legal')
    review.return_card(engine, contract_id, reason='Halaman 3 terpotong', expected_version=1, actor='legal')
    assert _row(engine, '0001')['state'] == 'returned'
    assert repository.events(engine, contract_id)[-1]['reason'] == 'Halaman 3 terpotong'


def test_a_missing_contract_is_a_lookup_error(engine) -> None:
    with pytest.raises(LookupError):
        review.return_card(engine, 'missing', reason='x', expected_version=1, actor='legal')


# --- Units, dates, parties, links ------------------------------------------------------------------


def test_units_are_codes_and_leave_the_state_alone(engine) -> None:
    contract_id = _id(engine, '0001')
    sha = review.detail(engine, contract_id)['card_sha256']
    review.approve(engine, contract_id, card_sha256=sha, expected_version=1, actor='legal')
    assert review.set_units(engine, contract_id, ['umum', 'air-bersih', 'umum'], expected_version=2, actor='legal') == {
        'version': 3,
        'units': ['air-bersih', 'umum'],
    }
    assert _row(engine, '0001')['state'] == 'approved'
    with pytest.raises(review.Invalid):
        review.set_units(engine, contract_id, ['Air Bersih'], expected_version=3, actor='legal')


def test_dates_edited_by_legal_survive_the_dates_pass(engine) -> None:
    contract_id = _id(engine, '0001')
    review.set_dates(
        engine, contract_id, start='2024-01-01', end='2026-12-31', auto_renewal=False, expected_version=1, actor='legal'
    )
    record_ = {'tanggal_mulai': '2020-01-01', 'tanggal_berakhir': '2021-01-01', 'perpanjangan_otomatis': 'ya'}
    assert repository.apply_dates_record(engine, run='full', number='0001', record=record_, actor='pass') is False
    row = _row(engine, '0001')
    assert (row['start_date'], row['end_date'], row['auto_renewal']) == ('2024-01-01', '2026-12-31', False)


@pytest.mark.parametrize(
    ('start', 'end', 'renewal'),
    [('2024-13-01', None, None), ('2024/01/01', None, None), ('2025-01-01', '2024-01-01', None), (None, None, 'ya')],
)
def test_malformed_dates_are_refused(engine, start, end, renewal) -> None:
    with pytest.raises(review.Invalid):
        review.set_dates(
            engine, _id(engine, '0001'), start=start, end=end, auto_renewal=renewal, expected_version=1, actor='legal'
        )


def test_fixing_the_party_list_relinks_and_never_logs_a_name(engine) -> None:
    contract_id = _id(engine, '0001')
    done = review.set_parties(
        engine, contract_id, ['Budi  Santoso', 'Siti Aminah', 'budi santoso'], expected_version=1, actor='legal'
    )
    # Budi already holds A from contract 0002: one person, one code across contracts.
    assert done['codes'] == ['Perorangan A', 'Perorangan B']
    assert {p['name'] for p in repository.parties(engine, contract_id)} == {'Budi Santoso', 'Siti Aminah'}
    assert json.loads(_row(engine, '0001')['current_card'])['perorangan_non_penandatangan'] == [
        'Budi Santoso',
        'Siti Aminah',
    ]
    payload = repository.events(engine, contract_id)[-1]['payload']
    assert 'Budi' not in payload and 'Siti' not in payload

    review.set_parties(engine, contract_id, [], expected_version=2, actor='legal')
    assert repository.parties(engine, contract_id) == []
    # Contract 0002 keeps its own link.
    assert repository.parties(engine, _id(engine, '0002')) == [{'code': 'Perorangan A', 'name': 'Budi Santoso'}]


def test_an_addendum_link_shows_on_both_cards_and_cannot_repeat(engine) -> None:
    main, addendum = _id(engine, '0001'), _id(engine, '0003')
    review.link(engine, main, addendum, kind='addendum', expected_version=1, actor='legal')
    assert [(l['number'], l['direction'], l['kind']) for l in review.links(engine, main)] == [
        ('0003', 'related', 'addendum')
    ]
    assert [(l['number'], l['direction']) for l in review.links(engine, addendum)] == [('0001', 'main')]
    with pytest.raises(review.Invalid):
        review.link(engine, addendum, main, kind='addendum', expected_version=1, actor='legal')
    with pytest.raises(review.Invalid):
        review.link(engine, main, main, kind='addendum', expected_version=2, actor='legal')
    with pytest.raises(review.Invalid):
        review.link(engine, main, 'missing', kind='addendum', expected_version=2, actor='legal')
    review.unlink(engine, main, addendum, expected_version=2, actor='legal')
    assert review.links(engine, main) == []
    assert [e['kind'] for e in repository.events(engine, main)][-2:] == ['link_added', 'link_removed']


def test_every_change_writes_one_event_with_the_new_version(engine) -> None:
    contract_id = _id(engine, '0001')
    review.edit_field(engine, contract_id, 'judul', text='A', pages=[1], expected_version=1, actor='legal')
    review.set_units(engine, contract_id, ['umum'], expected_version=2, actor='legal')
    review.return_card(engine, contract_id, reason='cek', expected_version=3, actor='legal')
    versions = [e['version'] for e in repository.events(engine, contract_id)]
    assert versions == [1, 2, 3, 4] and _row(engine, '0001')['version'] == 4
