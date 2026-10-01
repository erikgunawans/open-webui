"""Knowledge grep treats inline-flag and word-boundary patterns as regex.

`is_regex_pattern` in `tools/knowledge_fs.py` decides between regex and literal substring matching.
It missed `(?i)` and `\\b`, so Asisten JUP's `grep_knowledge_files` call with `(?i)direktur` searched
for the literal text "(?i)direktur" and answered "No matches" across a KB full of "Direktur"
(live, 2026-10-02). See `deploy/gcp/VENDOR-PATCHES.md`.

Needs the vendor runtime, so it skips under CI's `--only-group dev` job. A skip here is not a pass.
"""

import importlib.util

import pytest

_RUNTIME_MODULES = ('fastapi', 'regex', 'sqlalchemy')
_MISSING_RUNTIME = tuple(name for name in _RUNTIME_MODULES if importlib.util.find_spec(name) is None)
pytestmark = pytest.mark.skipif(
    bool(_MISSING_RUNTIME),
    reason=f'the runtime tree is not installed ({", ".join(_MISSING_RUNTIME)} missing) — expected under --only-group dev',
)


@pytest.mark.parametrize('pattern', ['(?i)direktur', r'\bJUP\b', '(?i)direktur utama'])
def test_inline_flags_and_word_boundaries_are_regex(pattern: str) -> None:
    from open_webui.tools.knowledge_fs import is_regex_pattern

    assert is_regex_pattern(pattern)


def test_inline_case_flag_matches_the_word() -> None:
    from open_webui.tools.knowledge_fs import build_matcher

    matches, err = build_matcher('(?i)direktur')
    assert err is None
    assert matches('| Direksi | Direktur Utama | Astar Simorangkir |')
    assert not matches('| Dewan Komisaris | Komisaris Utama |')


def test_plain_words_stay_literal() -> None:
    from open_webui.tools.knowledge_fs import is_regex_pattern

    assert not is_regex_pattern('PAM Jaya')
    assert not is_regex_pattern('Rp 1.000.000')
