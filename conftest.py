"""Shared, owned pytest workspaces without pytest's global tmp_path allocator."""

from __future__ import annotations

from pathlib import Path

import pytest

from portable_tempdirs import temporary_directory


@pytest.fixture(scope="session")
def _portable_test_parent():
    """Own a unique temporary parent, including its cleanup after all tests.

    Use a local explicit parent to avoid Windows global-temp ACL problems.
    Never touch old, unowned .portable-test-workspaces directories.
    """
    project_root = Path(__file__).resolve().parent
    with temporary_directory("SemanticTestSession", parent=project_root) as raw:
        yield Path(raw)


@pytest.fixture
def portable_tmp_path(_portable_test_parent):
    """Own and clean an isolated subtree for each test, even on exceptions."""
    with temporary_directory("SemanticTests", parent=_portable_test_parent) as raw:
        yield Path(raw)
