"""The review routes' HTTP seam (`routers/jup_contracts.py`, `/review/…`).

Faked: who is signed in and what they hold (`contract_reader`). The real routes, the real review rules
and a scratch SQLite migrated by the real graph run on every request. Card data is synthetic.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

for _module in ('fastapi', 'httpx', 'jwt', 'sqlalchemy', 'alembic', 'aiosqlite'):
    pytest.importorskip(_module, reason='the runtime tree is not installed')

from jup.contracts import migrate, repository  # noqa: E402
from jup.contracts.access import Access  # noqa: E402
from jup.contracts.cards import FIELDS  # noqa: E402

BASE = '/api/v1/contracts'
LEGAL = Access(cards=True, money=True, fulltext=True, names=True, review=True)
REVIEW_NO_NAMES = Access(cards=True, money=True, fulltext=True, review=True)
DIREKSI = Access(cards=True, money=True, fulltext=True, names=True)


@dataclass(frozen=True)
class _Account:
    role: str
    id: str


def _card(individuals: list[str]) -> dict:
    value = {name: {'isi': 'tidak tercantum', 'halaman': []} for name in FIELDS}
    value['mitra'] = {'isi': 'PT Contoh', 'halaman': [1]}
    value['hak_kewajiban_lingkup'] = {'isi': 'Penyewa: Budi Santoso.', 'halaman': [2]}
    value['halaman_perlu_diperiksa_manual'] = []
    value['perorangan_non_penandatangan'] = individuals
    return value


@pytest.fixture
def engine(tmp_path: Path):
    from sqlalchemy import create_engine

    engine = create_engine(f'sqlite:///{tmp_path / "c.db"}')
    assert migrate.run_contract_migrations(engine)
    for number, people in (('0001', ['Budi Santoso']), ('0002', [])):
        repository.import_record(
            engine,
            {
                'n': number,
                'itemId': f'item-{number}',
                'gcs': f'gs://b/full/src/{number}.pdf',
                'file': f'{number}.pdf',
                'pages': 3,
                'card': _card(people),
            },
            run='full',
            actor='admin',
        )
    return engine


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / 'mount' / 'full' / 'ocr-text'
    folder.mkdir(parents=True)
    pages = [{'n': 1, 'text': 'Halaman satu', 'conf': 0.95}, {'n': 2, 'text': 'Penyewa Budi Santoso', 'conf': 0.5}]
    (folder / '0001.json').write_text(json.dumps(pages), encoding='utf-8')
    return tmp_path / 'mount'


@pytest.fixture
def client(engine, root, caplog) -> Iterator[Any]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from open_webui.routers import jup_contracts
    from open_webui.utils.auth import get_current_user

    app = FastAPI()
    app.include_router(jup_contracts.router, prefix=BASE)
    app.dependency_overrides[jup_contracts.contracts_engine] = lambda: engine
    app.dependency_overrides[jup_contracts.contracts_root] = lambda: root
    app.dependency_overrides[get_current_user] = lambda: _Account(role='user', id='user-legal')
    app.dependency_overrides[jup_contracts.contract_reader] = lambda: LEGAL
    caplog.set_level('INFO', logger='jup.governance')
    jup_contracts_schema = jup_contracts.schema_ready
    jup_contracts.schema_ready = lambda: True
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            test_client.app = app  # type: ignore[attr-defined]
            yield test_client
    finally:
        jup_contracts.schema_ready = jup_contracts_schema


def _reader(client, reader: Access) -> None:
    from open_webui.routers import jup_contracts

    client.app.dependency_overrides[jup_contracts.contract_reader] = lambda: reader


def _first(client) -> dict:
    return client.get(f'{BASE}/review/queue').json()['items'][0]


def _review_audit(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "'event': 'contract_review'" in r.getMessage()]


def test_without_the_review_grant_every_route_is_403(client, caplog) -> None:
    _reader(client, DIREKSI)
    calls = [
        client.get(f'{BASE}/review/queue'),
        client.get(f'{BASE}/review/x'),
        client.get(f'{BASE}/review/x/pages'),
        client.patch(f'{BASE}/review/x/field', json={'version': 1, 'field': 'mitra', 'text': 'a'}),
        client.post(f'{BASE}/review/x/approve', json={'version': 1, 'card_sha256': 'a'}),
        client.post(f'{BASE}/review/x/return', json={'version': 1, 'reason': 'a'}),
        client.put(f'{BASE}/review/x/units', json={'version': 1, 'units': []}),
        client.put(f'{BASE}/review/x/dates', json={'version': 1}),
        client.post(f'{BASE}/review/x/links', json={'version': 1, 'related_id': 'y'}),
        client.delete(f'{BASE}/review/x/links/y?version=1'),
    ]
    assert [c.status_code for c in calls] == [403] * len(calls)
    assert all(c.json()['detail']['code'] == 'review_required' for c in calls)
    assert all("'result': 'refused'" in line for line in _review_audit(caplog))


def test_the_queue_and_detail_for_legal_show_names(client) -> None:
    first = _first(client)
    assert first['number'] == '0001' and first['individuals'] == 1
    body = client.get(f'{BASE}/review/{first["id"]}').json()
    assert body['parties'] == [{'code': 'Perorangan A', 'name': 'Budi Santoso'}]
    assert 'Budi Santoso' in body['card']['hak_kewajiban_lingkup']['isi']
    pages = client.get(f'{BASE}/review/{first["id"]}/pages').json()['pages']
    assert pages[1] == {'halaman': 2, 'teks': 'Penyewa Budi Santoso', 'ocr_rendah': True}


def test_a_reviewer_without_names_sees_codes_and_cannot_set_names(client) -> None:
    _reader(client, REVIEW_NO_NAMES)
    first = _first(client)
    body = client.get(f'{BASE}/review/{first["id"]}').json()
    assert body['parties'] == [{'code': 'Perorangan A', 'name': None}]
    assert body['card']['hak_kewajiban_lingkup']['isi'] == 'Penyewa: Perorangan A.'
    assert 'Budi' not in json.dumps(body)
    pages = client.get(f'{BASE}/review/{first["id"]}/pages').json()['pages']
    assert pages[1]['teks'] == 'Penyewa Perorangan A'
    refused = client.put(f'{BASE}/review/{first["id"]}/parties', json={'version': 1, 'names': []})
    assert refused.status_code == 403 and refused.json()['detail']['code'] == 'names_required'


def test_edit_then_approve_with_the_new_hash(client, caplog) -> None:
    first = _first(client)
    edited = client.patch(
        f'{BASE}/review/{first["id"]}/field', json={'version': 1, 'field': 'judul', 'text': 'Sewa lahan', 'pages': [1]}
    )
    assert edited.status_code == 200, edited.text
    stale = client.post(
        f'{BASE}/review/{first["id"]}/approve', json={'version': 1, 'card_sha256': edited.json()['card_sha256']}
    )
    assert stale.status_code == 409 and stale.json()['detail']['code'] == 'conflict'
    approved = client.post(
        f'{BASE}/review/{first["id"]}/approve', json={'version': 2, 'card_sha256': edited.json()['card_sha256']}
    )
    assert approved.json() == {'version': 3, 'state': 'approved'}
    lines = _review_audit(caplog)
    assert "'action': 'approve'" in lines[-1] and "'result': 'recorded'" in lines[-1]
    # Audit lines carry ids and versions, never card text.
    assert not any('Sewa lahan' in line for line in lines)


def test_malformed_writes_are_422_and_missing_contracts_404(client) -> None:
    first = _first(client)
    bad = client.patch(f'{BASE}/review/{first["id"]}/field', json={'version': 1, 'field': 'nope', 'text': 'a'})
    assert bad.status_code == 422 and bad.json()['detail']['code'] == 'invalid'
    assert client.post(f'{BASE}/review/missing/return', json={'version': 1, 'reason': 'a'}).status_code == 404
    assert client.get(f'{BASE}/review/missing').status_code == 404
    assert client.get(f'{BASE}/review/queue?flag=nope').status_code == 422


def test_links_round_trip(client) -> None:
    items = client.get(f'{BASE}/review/queue').json()['items']
    main, other = items[0]['id'], items[1]['id']
    assert client.post(f'{BASE}/review/{main}/links', json={'version': 1, 'related_id': other}).status_code == 200
    assert [l['id'] for l in client.get(f'{BASE}/review/{main}').json()['links']] == [other]
    assert client.delete(f'{BASE}/review/{main}/links/{other}?version=2').status_code == 200


def test_pages_missing_from_the_mount_are_404(client) -> None:
    second = client.get(f'{BASE}/review/queue').json()['items'][1]
    response = client.get(f'{BASE}/review/{second["id"]}/pages')
    assert response.status_code == 404 and response.json()['detail']['code'] == 'pages_not_found'
