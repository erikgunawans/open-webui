"""The KPI 2026 catalogue: its weights add up and every reference resolves.

A typo here does not fail loudly: a weight off by 0.05 scores every quarter wrong, and an item
whose perspective id is misspelt silently drops out of its perspective's card. Pure data, so
this runs under `--only-group dev`.
"""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).parent.parent / 'backend' / 'jup' / 'leadership' / 'kpi.py'
_spec = importlib.util.spec_from_file_location('jup_leadership_kpi', _PATH)
assert _spec and _spec.loader
kpi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kpi)


def test_the_perspective_weights_make_a_whole() -> None:
    assert sum(p['weight'] for p in kpi.PERSPECTIVES) == pytest.approx(1)


@pytest.mark.parametrize('perspective', [p['id'] for p in kpi.PERSPECTIVES])
def test_each_perspective_holds_its_own_weight_in_items(perspective: str) -> None:
    declared = next(p['weight'] for p in kpi.PERSPECTIVES if p['id'] == perspective)
    assert sum(k['weight'] for k in kpi.ITEMS if k['p'] == perspective) == pytest.approx(declared)


def test_the_sheet_has_fifteen_kpis_with_unique_ids() -> None:
    ids = [k['id'] for k in kpi.ITEMS]
    assert len(ids) == 15
    assert len(set(ids)) == 15


def test_every_item_names_a_known_perspective_and_unit() -> None:
    perspectives = {p['id'] for p in kpi.PERSPECTIVES}
    for item in kpi.ITEMS:
        assert item['p'] in perspectives, item['id']
        assert item['unit'] in ('rp', 'pct', 'count'), item['id']
        assert item['target'] > 0, item['id']


def test_the_sample_covers_every_item_for_four_quarters() -> None:
    assert set(kpi.SAMPLE) == {k['id'] for k in kpi.ITEMS}
    assert all(len(values) == 4 for values in kpi.SAMPLE.values())


def test_the_sample_says_it_is_illustrative() -> None:
    assert kpi.read_kpi()['sample_is_illustrative'] is True


def test_a_caller_cannot_change_the_catalogue() -> None:
    first = kpi.read_kpi()
    first['items'][0]['target'] = 0
    first['sample']['k1'][0] = 0
    again = kpi.read_kpi()
    assert again['items'][0]['target'] == kpi.ITEMS[0]['target']
    assert again['sample']['k1'][0] == kpi.SAMPLE['k1'][0]
