"""The `jup_contracts` tool logic against a scratch SQLite, with synthetic cards and OCR pages.

The point of every test here: what the model would read. Money withheld without the grant, names
never present, pages only with full text, state always stated (D1, D2, D3).
"""

import asyncio
import datetime as dt
import json
from pathlib import Path

import pytest

# A skip mark would not stop the imports below, and `jup.contracts.models` needs sqlalchemy, which
# CI's `--only-group dev` job does not install.
pytest.importorskip('sqlalchemy', reason='the runtime tree is not installed')
pytest.importorskip('alembic', reason='the runtime tree is not installed')

from jup.contracts import access, migrate, repository, titles, tool  # noqa: E402
from tests.test_contract_repository import _field, card, record  # noqa: E402

USER = {'id': 'user-1', 'role': 'user'}


@pytest.fixture
def world(tmp_path: Path):
    from sqlalchemy import create_engine

    engine = create_engine(f'sqlite:///{tmp_path / "c.db"}')
    assert migrate.run_contract_migrations(engine)
    repository.import_record(
        engine,
        record(
            '0001',
            'item-1',
            card(
                mitra=_field('Budi Santoso'),
                judul=_field('Sewa lahan SPBG Rorotan'),
                perorangan_non_penandatangan=['Budi Santoso'],
            ),
        ),
        run='full',
        actor='admin',
    )
    repository.import_record(
        engine, record('0002', 'item-2', card(judul=_field('Jual beli gas PT Lain'))), run='full', actor='admin'
    )
    ocr = tmp_path / 'bucket' / 'full' / 'ocr-text'
    ocr.mkdir(parents=True)
    (ocr / '0001.json').write_text(
        json.dumps(
            [
                {'n': 1, 'text': 'Pihak kedua: Budi Santoso, Rorotan', 'conf': 0.95},
                {'n': 2, 'text': 'Pasal 2', 'conf': 0.5},
            ]
        ),
        encoding='utf-8',
    )
    grants: dict[str, dict] = {}

    def source(title: str | None = 'staff', ready: bool = True) -> tool.Source:
        grants['current'] = titles.grants(title) if title else {}
        return tool.Source(
            engine=engine,
            root=tmp_path / 'bucket',
            permissions=lambda _user: grants['current'],
            ready=lambda: ready,
            today=lambda: dt.date(2026, 10, 2),
        )

    return engine, source


def _run(coro):
    return asyncio.run(coro)


def test_without_a_title_nothing_is_returned(world) -> None:
    _, source = world
    assert _run(tool.search_contracts(USER, 'Rorotan', source=source(None))) == access.NO_CARDS


def test_schema_not_ready_is_said(world) -> None:
    _, source = world
    assert _run(tool.search_contracts(USER, 'x', source=source(ready=False))) == tool.UNAVAILABLE


def test_search_finds_by_visible_text_and_states_the_card_state(world) -> None:
    _, source = world
    text = _run(tool.search_contracts(USER, 'rorotan', source=source('staff')))
    assert '[0001]' in text and '[0002]' not in text
    assert 'draf, belum ditinjau Tim Legal' in text
    assert 'Budi' not in text and 'Perorangan A' in text


def test_a_staff_member_cannot_find_a_contract_by_an_individuals_name(world) -> None:
    _, source = world
    assert 'Tidak ada kartu' in _run(tool.search_contracts(USER, 'Budi', source=source('staff')))


def test_a_staff_member_cannot_search_money_they_cannot_see(world) -> None:
    _, source = world
    assert 'Tidak ada kartu' in _run(tool.search_contracts(USER, '1.000.000.000', source=source('staff')))
    assert '[0001]' in _run(tool.search_contracts(USER, '1.000.000.000', source=source('manager')))


def test_staff_card_withholds_money_and_never_names_the_person(world) -> None:
    _, source = world
    text = _run(tool.get_contract(USER, '0001', source=source('staff')))
    assert access.WITHHELD_MONEY in text
    assert 'Rp 1.000.000.000' not in text
    assert 'Budi' not in text
    assert '/pdf' not in text


def test_legal_card_has_money_and_the_pdf_link_but_still_no_name(world) -> None:
    _, source = world
    text = _run(tool.get_contract(USER, 'K0001', source=source('legal')))
    assert 'Rp 1.000.000.000' in text
    assert '/api/v1/contracts/0001/pdf' in text
    assert 'Budi' not in text


def test_an_approved_card_says_so(world) -> None:
    engine, source = world
    row = repository.get_contract(engine, run='full', number='0001')
    repository.set_state(engine, row['id'], 'approved', actor='legal')
    assert 'disetujui Tim Legal' in _run(tool.get_contract(USER, '1', source=source('staff')))


def test_pages_need_full_text(world) -> None:
    _, source = world
    assert _run(tool.read_contract_pages(USER, '0001', '1', source=source('manager'))) == access.WITHHELD_FULLTEXT


def test_pages_come_back_masked_with_low_confidence_flagged(world) -> None:
    _, source = world
    text = _run(tool.read_contract_pages(USER, '0001', '1-2', source=source('direksi')))
    assert 'Pihak kedua: Perorangan A, Rorotan' in text
    assert 'Halaman 2 (OCR berkeyakinan rendah' in text
    assert 'Budi' not in text


def test_ends_within_days_says_dates_are_not_extracted_yet(world) -> None:
    _, source = world
    text = _run(tool.search_contracts(USER, '', ends_within_days=180, source=source('staff')))
    assert 'belum diekstrak' in text


def test_ends_within_days_uses_structured_dates(world) -> None:
    engine, source = world
    from sqlalchemy import update

    from jup.contracts.models import contract

    with engine.begin() as connection:
        connection.execute(update(contract).where(contract.c.number == '0002').values(end_date='2027-01-31'))
        connection.execute(update(contract).where(contract.c.number == '0001').values(end_date='2030-01-01'))
    text = _run(tool.search_contracts(USER, '', ends_within_days=180, source=source('staff')))
    assert '[0002]' in text and '[0001]' not in text and 'berakhir: 2027-01-31' in text


def test_an_unknown_reference_is_said(world) -> None:
    _, source = world
    assert 'tidak ditemukan' in _run(tool.get_contract(USER, '9999', source=source('staff')))


def test_the_card_carries_structured_dates_when_known(world) -> None:
    engine, source = world
    row = repository.get_contract(engine, run='full', number='0002')
    repository.set_dates(engine, row['id'], start='2020-01-01', end='2027-01-31', auto_renewal=False, actor='t')
    text = _run(tool.get_contract(USER, '0002', source=source('staff')))
    assert 'mulai 2020-01-01, berakhir 2027-01-31, perpanjangan otomatis: tidak' in text


# -- restricted reads mark the chat (O2: the files' classification floor) ----------------------


class Marks:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, chat_id: str, source: str) -> None:
        if self.fail:
            raise RuntimeError('database unavailable')
        self.calls.append((chat_id, source))


def test_a_card_with_money_marks_the_chat(world) -> None:
    _, source = world
    marks = Marks()
    text = _run(tool.get_contract(USER, '0001', source=source('legal'), chat_id='chat-1', marker=marks))
    assert 'Kartu kontrak [0001]' in text
    assert marks.calls == [('chat-1', 'contracts')]


def test_a_card_without_money_does_not_mark_the_chat(world) -> None:
    _, source = world
    marks = Marks()
    _run(tool.get_contract(USER, '0001', source=source('staff'), chat_id='chat-1', marker=marks))
    assert marks.calls == []


def test_page_text_marks_the_chat(world) -> None:
    _, source = world
    marks = Marks()
    _run(tool.read_contract_pages(USER, '0001', '1', source=source('direksi'), chat_id='chat-1', marker=marks))
    assert marks.calls == [('chat-1', 'contracts')]


def test_searches_refusals_and_misses_do_not_mark(world) -> None:
    _, source = world
    marks = Marks()
    _run(tool.search_contracts(USER, 'Rorotan', source=source('legal')))
    _run(tool.read_contract_pages(USER, '0001', '1', source=source('manager'), chat_id='chat-1', marker=marks))
    _run(tool.get_contract(USER, '9999', source=source('legal'), chat_id='chat-1', marker=marks))
    assert marks.calls == []


def test_restricted_text_is_withheld_when_the_mark_cannot_be_written(world) -> None:
    _, source = world
    text = _run(tool.get_contract(USER, '0001', source=source('legal'), chat_id='chat-1', marker=Marks(fail=True)))
    assert text == tool.MARK_FAILED


def test_the_stored_wrapper_passes_the_chat_through() -> None:
    wrapper = (Path(__file__).resolve().parent.parent / 'tools' / 'jup_contracts.py').read_text(encoding='utf-8')
    assert '_get_contract(__user__, ref, chat_id=__chat_id__)' in wrapper
    assert '_read_contract_pages(__user__, ref, pages, chat_id=__chat_id__)' in wrapper
