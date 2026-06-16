"""Shared fixtures for Grid Gauntlet scenario tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure tests/ is importable for mocks module
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mocks import MockGridContext


@pytest.fixture
def mock_ctx() -> MockGridContext:
    """Provides a mock grid context for attack execution."""
    return MockGridContext()


@pytest.fixture
def sentinel_checker():
    """Provides a fresh InvariantChecker instance."""
    from invariants import InvariantChecker
    return InvariantChecker()
