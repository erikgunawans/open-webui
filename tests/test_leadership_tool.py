"""The `jup_leadership` assistant tool (P3): the page's grants, the page's data, as text.

The stored wrapper is exec'd from the DB where nothing tests it, so every rule lives in
`jup.leadership.tool` and is tested here without a server.
"""

import ast
import asyncio
import copy
import json
import logging
from pathlib import Path

import pytest

from jup.leadership import policy
from jup.leadership.reader import DatasetUnavailable
from jup.leadership.tool import NO_ACCESS, UNAVAILABLE, UNKNOWN_USER, Source, read_leadership

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / 'tests' / 'fixtures' / 'leadership' / 'illustrative-seed.json'
TOOL_SOURCE = ROOT / 'tools' / 'jup_leadership.py'
USER = {'id': 'u-1', 'role': 'user'}


def _grants(board: object = False, rka: object = False, scope: object = True) -> dict:
    permissions = copy.deepcopy(policy.DEFAULT_PERMISSIONS)
    grants = permissions['jup']['ruang_pimpinan']
    grants['board']['view'], grants['rka']['view'], grants['scopes']['jup_consolidated'] = board, rka, scope
    return permissions


def _source(permissions: dict, dataset=None, recorded=None) -> Source:
    return Source(
        dataset=dataset or (lambda: json.loads(SEED.read_text(encoding='utf-8'))),
        permissions=lambda _user_id: permissions,
        recorded=recorded or (lambda: None),
    )


def _read(permissions: dict, view: str = '', user=USER, **kwargs) -> str:
    return asyncio.run(read_leadership(user, view, _source(permissions, **kwargs)))


def _audit(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if 'leadership_read' in r.getMessage()]


def test_without_a_user_nothing_is_read() -> None:
    assert _read(_grants(True, True), user=None) == UNKNOWN_USER


def test_a_reader_without_a_grant_is_refused_and_audited(caplog) -> None:
    caplog.set_level(logging.INFO)
    assert _read(_grants()) == NO_ACCESS
    assert "'result': 'refused'" in _audit(caplog)[-1]
    assert "'surface': 'assistant'" in _audit(caplog)[-1]


def test_a_view_grant_without_the_scope_grant_is_refused() -> None:
    assert _read(_grants(True, True, scope=False)) == NO_ACCESS


def test_a_truthy_grant_that_is_not_exactly_true_is_refused() -> None:
    assert _read(_grants(board=1, rka='true')) == NO_ACCESS


def test_the_rka_reader_hears_the_rka_view_only() -> None:
    text = _read(_grants(rka=True))
    assert 'RKA & Realisasi' in text
    assert 'Direksi & Komisaris' not in text
    assert 'Rp347,17 miliar' in text
    assert '"20261001 - RKA 2027 - DRAFT - Jakpro Final.pptx" slide 2, 3' in text


def test_asking_for_a_view_the_reader_lacks_is_refused_even_with_another_grant() -> None:
    assert _read(_grants(rka=True), view='board') == NO_ACCESS


def test_with_both_grants_and_no_view_both_views_are_read() -> None:
    text = _read(_grants(True, True))
    assert text.index('Direksi & Komisaris') < text.index('RKA & Realisasi')


def test_an_unknown_view_is_named_not_guessed() -> None:
    assert 'tidak dikenal' in _read(_grants(True, True), view='keuangan')


def test_board_figures_carry_their_comparison_and_variance() -> None:
    text = _read(_grants(board=True))
    assert 'Pendapatan usaha: Rp144,47 miliar (realisasi' in text
    assert 'pembanding Rp158,47 miliar (anggaran/target' in text
    assert 'selisih -14,00' in text


def test_assumptions_and_follow_ups_are_read_with_their_sources() -> None:
    text = _read(_grants(rka=True))
    assert 'Tarif dan mutu WTP KBB' in text and 'Pantau:' in text
    assert '### Tindak lanjut' in text


def test_recorded_actions_replace_the_sample_ones_when_the_server_reads_records() -> None:
    recorded = [
        {
            'id': 'example-action-water',
            'title': 'Uji mutu air WTP KBB',
            'owner_label': 'Divisi Air',
            'due': {'label': 'Desember 2026'},
            'state': 'completion_submitted',
            'progress_summary': None,
        }
    ]
    text = _read(_grants(rka=True), recorded=lambda: recorded)
    assert 'Uji mutu air WTP KBB — Divisi Air, tenggat Desember 2026, penyelesaian diajukan.' in text


def test_the_answer_says_the_figures_are_a_draft_and_unverified() -> None:
    text = _read(_grants(rka=True))
    assert 'belum terverifikasi' in text
    assert 'Jangan menambah angka' in text


def test_an_untrusted_dataset_is_unavailable_never_read_around(caplog) -> None:
    caplog.set_level(logging.INFO)

    def broken() -> dict:
        raise DatasetUnavailable('The leadership dataset failed validation.')

    assert _read(_grants(True, True), dataset=broken) == UNAVAILABLE
    assert "'result': 'unavailable'" in _audit(caplog)[-1]


def test_a_served_read_is_audited_with_its_views_and_no_figures(caplog) -> None:
    caplog.set_level(logging.INFO)
    _read(_grants(True, True))
    line = _audit(caplog)[-1]
    assert "'views': ['board', 'rka']" in line and "'result': 'served'" in line
    assert '347' not in line


@pytest.mark.parametrize('env', [{}, {'JUP_LEADERSHIP_ENABLED': 'true'}])
def test_the_production_source_refuses_an_unconfigured_server(env, monkeypatch) -> None:
    for key in ('JUP_LEADERSHIP_ENABLED', 'JUP_LEADERSHIP_SAMPLE_FILE'):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(DatasetUnavailable):
        Source().dataset()


def test_the_production_source_reads_the_configured_file(monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_ENABLED', 'true')
    monkeypatch.setenv('JUP_LEADERSHIP_SAMPLE_FILE', str(SEED))
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'sample')
    assert Source().dataset()['views']['rka']['metrics']
    assert Source().recorded() is None


def test_a_misconfigured_actions_source_is_refused(monkeypatch) -> None:
    monkeypatch.setenv('JUP_LEADERSHIP_ACTIONS_SOURCE', 'everything')
    with pytest.raises(DatasetUnavailable):
        Source().recorded()


def test_the_stored_wrapper_holds_no_logic_of_its_own() -> None:
    """The DB copy is exec'd untested, so it may only delegate. A rule added there escapes CI."""
    tree = ast.parse(TOOL_SOURCE.read_text())
    tools = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Tools')
    methods = [n for n in tools.body if isinstance(n, ast.AsyncFunctionDef)]
    assert [m.name for m in methods] == ['read_ruang_pimpinan']
    body = [n for n in methods[0].body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert len(body) == 1 and isinstance(body[0], ast.Return)
    assert '_read_leadership(' in ast.unparse(body[0])


def test_the_stored_wrapper_declares_a_read_risk_class() -> None:
    assert 'risk_class: read' in TOOL_SOURCE.read_text()
