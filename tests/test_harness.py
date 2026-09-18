"""Assertions about the harness itself — not about the application.

Ticket #2 deliberately stops here: it proves pytest collects, runs, supports async
tests and can find fixture data. Product assertions arrive with #3 and later.
"""

from collections.abc import Callable
from pathlib import Path

import pytest


def test_pytest_collects_and_runs() -> None:
    """The floor: a sync test is collected and executed."""
    assert True


async def test_async_tests_run_without_a_marker() -> None:
    """Load-bearing: an unmarked `async def` only runs under `asyncio_mode = auto`.

    Under strict mode pytest fails this outright, so the test guards the config
    rather than restating `True`.
    """
    assert True


def test_fixtures_dir_is_present(fixtures_dir: Path) -> None:
    """Later tickets write fixture data here, so the directory must be committed."""
    assert fixtures_dir.is_dir()


def test_fixture_path_rejects_a_missing_fixture(fixture_path: Callable[..., Path]) -> None:
    """The resolver fails loudly instead of handing back a non-existent path."""
    with pytest.raises(FileNotFoundError):
        fixture_path('definitely-not-a-real-fixture.json')
