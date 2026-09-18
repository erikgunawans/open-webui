"""Root pytest configuration for the ent-os backend suite.

This directory sits outside `backend/` on purpose: the quarterly upstream rebase
(ADR-0007) should never have to merge our tests against open-webui's own tree, and
the vendor tree already owns `test/` (singular) for its image-generation fixtures.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='session')
def fixtures_dir() -> Path:
    """Absolute path to `tests/fixtures/` — the shared home for fixture data."""
    return FIXTURES_DIR


@pytest.fixture
def fixture_path(fixtures_dir: Path) -> Callable[..., Path]:
    """Resolve a path under `tests/fixtures/`, failing loudly when it is missing.

    A missing fixture raises here rather than surfacing as a confusing assertion
    failure deeper inside the test.
    """

    def _resolve(*parts: str) -> Path:
        path = fixtures_dir.joinpath(*parts)
        if not path.exists():
            raise FileNotFoundError(f'fixture not found: {path}')
        return path

    return _resolve
