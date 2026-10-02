"""The card fields in Python are the drafting schema in `deploy/gcp/legal-kb/lib.ts`, read from source."""

import re
from pathlib import Path

from jup.contracts import cards

LIB_TS = Path(__file__).resolve().parent.parent / 'deploy' / 'gcp' / 'legal-kb' / 'lib.ts'


def test_the_fields_match_the_drafting_schema() -> None:
    block = re.search(r'export const FIELDS = \[(.*?)\];', LIB_TS.read_text(encoding='utf-8'), flags=re.S)
    assert block, 'lib.ts no longer declares FIELDS'
    assert tuple(re.findall(r'"([a-z_]+)"', block.group(1))) == cards.FIELDS


def test_money_fields_are_card_fields() -> None:
    assert cards.MONEY_FIELDS <= set(cards.FIELDS)


def test_text_treats_not_stated_as_missing() -> None:
    card = {'judul': {'isi': ' Tidak tercantum ', 'halaman': []}, 'mitra': {'isi': ' PT A ', 'halaman': [1]}}
    assert cards.text(card, 'judul') is None
    assert cards.text(card, 'mitra') == 'PT A'
    assert cards.text(None, 'mitra') is None


def test_the_stored_tool_wrapper_holds_no_logic_of_its_own() -> None:
    """The DB copy is exec'd untested, so it may only delegate. A rule added there escapes CI."""
    import ast

    source = (Path(__file__).resolve().parent.parent / 'tools' / 'jup_contracts.py').read_text(encoding='utf-8')
    assert 'risk_class: read\n' in source
    tools = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Tools')
    methods = [n for n in tools.body if isinstance(n, ast.AsyncFunctionDef)]
    assert [m.name for m in methods] == ['search_contracts', 'get_contract', 'read_contract_pages']
    assert not [n for n in tools.body if isinstance(n, ast.FunctionDef)]
    for method in methods:
        body = [n for n in method.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        assert len(body) == 1 and isinstance(body[0], ast.Return)
        assert f'_{method.name}(__user__' in ast.unparse(body[0])
        doc = (ast.get_docstring(method) or '').lower()
        # Access is decided in code; a docstring that names roles makes the model refuse on its own.
        for word in ('admin', 'legal team only', 'direksi', 'manager', 'staff'):
            assert word not in doc
