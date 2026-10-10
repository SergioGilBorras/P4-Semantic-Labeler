"""Offline contract tests for the portable persistent-workspace facade."""
from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from portable_tempdirs import TemporaryDirectoryError as PortableTemporaryDirectoryError

from p4_semantic_labeler import temp_directories
from p4_semantic_labeler.temp_directories import (
    TEMP_ROOT_NAME,
    TemporaryDirectoryError,
    create_run_directory,
    create_run_subdirectory,
)


def test_creates_distinct_persistent_run_directories_without_changing_environment():
    before = dict(os.environ)
    first = create_run_directory()
    second = create_run_directory()
    try:
        assert first != second
        assert first.parent == second.parent
        assert first.parent.name == TEMP_ROOT_NAME
        assert re.fullmatch(r"\d{8}T\d{12}Z-[0-9a-f]{24}", first.name)
        assert first.is_dir() and second.is_dir()
        assert os.environ == before
    finally:
        # Test-owned, empty run folders only. Do not touch historical workspaces.
        os.rmdir(first)
        os.rmdir(second)


def test_run_directory_relinquishes_cleanup_ownership(monkeypatch, portable_tmp_path):
    parent = portable_tmp_path
    fake_owner = Mock()
    fake_owner.detach.return_value = parent
    allocate = Mock(return_value=fake_owner)
    monkeypatch.setattr(temp_directories, "temporary_directory", allocate)
    assert create_run_directory() == parent
    allocate.assert_called_once_with(TEMP_ROOT_NAME)
    fake_owner.detach.assert_called_once_with()
    fake_owner.cleanup.assert_not_called()


def test_run_permission_error_is_sanitized(monkeypatch):
    def refuse(_namespace):
        raise PortableTemporaryDirectoryError(
            "secret path inside filesystem", code="PERMISSION_DENIED"
        )

    monkeypatch.setattr(temp_directories, "temporary_directory", refuse)
    with pytest.raises(TemporaryDirectoryError, match="PermissionError") as raised:
        create_run_directory()
    assert raised.value.permission_denied
    assert "secret path" not in str(raised.value)


def test_unclassified_run_error_does_not_expose_paths(monkeypatch):
    def refuse(_namespace):
        raise PortableTemporaryDirectoryError(
            "secret directory detail", code="CREATE_OR_SELF_CHECK_FAILED"
        )

    monkeypatch.setattr(temp_directories, "temporary_directory", refuse)
    with pytest.raises(TemporaryDirectoryError, match="Unable to create") as raised:
        create_run_directory()
    assert not raised.value.permission_denied
    assert "secret" not in str(raised.value)


def test_run_creation_does_not_fall_back_to_os_mkdir(monkeypatch):
    def refuse(_namespace):
        raise PortableTemporaryDirectoryError("denied", code="PERMISSION_DENIED")

    monkeypatch.setattr(temp_directories, "temporary_directory", refuse)
    with pytest.raises(TemporaryDirectoryError):
        create_run_directory()


def test_named_children_are_unique_and_workspace_and_state_remain_separate(portable_tmp_path):
    run = portable_tmp_path
    workspace = create_run_subdirectory(run, "workspace")
    state = create_run_subdirectory(run, "bridge-state")
    assert workspace.is_dir() and state.is_dir()
    assert workspace != state
    with pytest.raises(TemporaryDirectoryError, match="already exists"):
        create_run_subdirectory(run, "workspace")


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "a\\b"])
def test_invalid_child_name_is_rejected_without_creating_paths(portable_tmp_path, name):
    with pytest.raises(ValueError, match="single path component"):
        create_run_subdirectory(portable_tmp_path, name)


def test_named_child_creation_propagates_safe_permission_diagnostic(
    portable_tmp_path, monkeypatch
):
    def reject(_path):
        raise PermissionError("sensitive path detail")

    monkeypatch.setattr(temp_directories.os, "mkdir", reject)
    with pytest.raises(TemporaryDirectoryError, match="PermissionError") as raised:
        create_run_subdirectory(portable_tmp_path, "bridge-state")
    assert raised.value.permission_denied
    assert "sensitive path detail" not in str(raised.value)
