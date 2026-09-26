"""`gate_probe` (A5+E5 #18), and the Risk Class every stored tool declares in its own source.

`gate_probe` exists to prove the approval gate in production: it is admin-only, it is `external`,
and it does nothing but echo its arguments, so exercising the gate with it can never have an
effect. Its rules live in `jup.gate_probe`; the stored file may only delegate.
"""

import ast
import re
from pathlib import Path

import pytest

from jup.gate_probe import REFUSAL, gate_probe
from jup.tool_policy import CHAT, EXTERNAL, READ, RISK_CLASSES, classify, decide

TOOLS_DIR = Path(__file__).resolve().parent.parent / 'tools'


def _frontmatter(path: Path) -> dict[str, str]:
    """The same parse as `deploy/gcp/sync-tools.ts` and the vendor's `extract_frontmatter`."""
    header = re.match(r'^"""\n(.*?)\n"""', path.read_text(), re.S)
    assert header, f'{path.name}: no frontmatter docstring'
    fields = {}
    for line in header.group(1).splitlines():
        key, sep, value = line.partition(':')
        if sep:
            fields[key.strip()] = value.strip()
    return fields


# --- the probe's behaviour ------------------------------------------------------------------------


def test_the_probe_echoes_its_arguments_for_an_admin():
    out = gate_probe('admin', message='halo', token='sk-not-a-real-secret')
    assert 'halo' in out and 'sk-not-a-real-secret' in out


def test_the_probe_echoes_empty_arguments_without_failing():
    assert 'message' in gate_probe('admin')


@pytest.mark.parametrize('role', ['user', 'pending', None, ''])
def test_anyone_but_an_admin_is_refused(role):
    assert gate_probe(role, message='halo') == REFUSAL


# --- every stored tool declares its class --------------------------------------------------------


@pytest.mark.parametrize('path', sorted(TOOLS_DIR.glob('*.py')), ids=lambda p: p.stem)
def test_every_stored_tool_declares_a_risk_class(path: Path):
    assert _frontmatter(path).get('risk_class') in RISK_CLASSES


def test_portfolio_status_declares_read_and_gate_probe_declares_external():
    assert _frontmatter(TOOLS_DIR / 'portfolio_status.py')['risk_class'] == READ
    assert _frontmatter(TOOLS_DIR / 'gate_probe.py')['risk_class'] == EXTERNAL


def test_the_probe_as_stored_is_refused_by_the_gate():
    """The entry `get_tools` builds from the stored probe: the declared class is what gates it."""
    entry = {'tool_id': 'gate_probe', 'risk_class': _frontmatter(TOOLS_DIR / 'gate_probe.py')['risk_class']}
    assert classify(entry) == EXTERNAL
    assert decide('gate_probe', entry, path=CHAT).approval == 'rejected'


def test_the_stored_probe_holds_no_logic_of_its_own():
    tree = ast.parse((TOOLS_DIR / 'gate_probe.py').read_text())
    tools = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Tools')
    methods = [n for n in tools.body if isinstance(n, ast.FunctionDef)]
    assert [m.name for m in methods] == ['gate_probe']
    body = [n for n in methods[0].body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert len(body) == 1 and isinstance(body[0], ast.Return)
    assert '_gate_probe(' in ast.unparse(body[0])
