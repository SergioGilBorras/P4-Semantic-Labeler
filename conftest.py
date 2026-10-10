"""Shared, owned test workspaces without pytest's global tmp_path allocator."""

from __future__ import annotations

from pathlib import Path

import pytest

from portable_tempdirs import temporary_directory


@pytest.fixture(scope="session")
def _portable_test_parent():
    root = Path(__file__).resolve().parent / ".portable-test-workspaces"
    # An existing parent (including leftovers from previous failed sessions) is
    # not owned by this session. Never sweep it or other concurrent tests.
    try:
        root.mkdir()
    except FileExistsError:
        created = False
    else:
        created = True
    if root.is_symlink() or not root.is_dir():
        raise OSError("Test workspace parent must be an ordinary directory")
    try:
        yield root
    finally:
        # Remove only a parent created by this session, and only when empty.
        # The managed children are cleaned separately by their owners.
        if created and root.is_dir() and not root.is_symlink():
            if not any(root.iterdir()):
                root.rmdir()


@pytest.fixture
def portable_tmp_path(_portable_test_parent):
    """Create and clean a new portable-tempdirs tree for each test."""
    with temporary_directory("SemanticTests", parent=_portable_test_parent) as raw:
        yield Path(raw)
