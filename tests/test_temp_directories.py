"""Offline tests for one-request, auto-cleaned portable workspaces."""
from __future__ import annotations

import os
import re
from unittest.mock import Mock

import pytest
from portable_tempdirs import TemporaryDirectoryError as PortableTemporaryDirectoryError

from p4_semantic_labeler import temp_directories
from p4_semantic_labeler.temp_directories import (
    TEMP_ROOT_NAME,
    TemporaryDirectoryError,
    create_run_subdirectory,
    managed_run_directory,
)


def test_unique_run_roots_are_cleaned_after_each_context():
    before = dict(os.environ)
    with managed_run_directory() as first:
        assert first.is_dir()
        assert first.parent.name == TEMP_ROOT_NAME
        assert re.fullmatch(r"\d{8}T\d{12}Z-[0-9a-f]{24}", first.name)
        with managed_run_directory() as second:
            assert first != second
            assert first.is_dir() and second.is_dir()
            (second / "nested").mkdir()
            (second / "nested" / "data.txt").write_text("ephemeral", encoding="utf-8")
        assert not second.exists()
        assert first.exists()
    assert not first.exists()
    assert os.environ == before


def test_managed_run_context_does_not_detach_owner(monkeypatch, portable_tmp_path):
    events = []

    class FakeOwner:
        def __enter__(self):
            events.append("enter")
            return str(portable_tmp_path)

        def __exit__(self, exc_type, exc, tb):
            events.append("cleanup")
            return False

        def detach(self):
            raise AssertionError("one-shot callers must not detach")

    allocate = Mock(return_value=FakeOwner())
    monkeypatch.setattr(temp_directories, "temporary_directory", allocate)
    with managed_run_directory() as root:
        assert root == portable_tmp_path
    allocate.assert_called_once_with(TEMP_ROOT_NAME)
    assert events == ["enter", "cleanup"]


def test_context_cleans_after_body_failure():
    with pytest.raises(RuntimeError, match="expected"):
        with managed_run_directory() as root:
            (root / "note.txt").write_text("discard", encoding="utf-8")
            raise RuntimeError("expected")
    assert not root.exists()


def test_run_permission_error_is_sanitized(monkeypatch):
    def refuse(_namespace):
        raise PortableTemporaryDirectoryError(
            "secret path inside filesystem", code="PERMISSION_DENIED"
        )

    monkeypatch.setattr(temp_directories, "temporary_directory", refuse)
    with pytest.raises(TemporaryDirectoryError, match="PermissionError") as raised:
        with managed_run_directory():
            pytest.fail("context should not start")
    assert raised.value.permission_denied
    assert "secret path" not in str(raised.value)


def test_unclassified_run_error_does_not_expose_paths(monkeypatch):
    def refuse(_namespace):
        raise PortableTemporaryDirectoryError(
            "secret directory detail", code="CREATE_OR_SELF_CHECK_FAILED"
        )

    monkeypatch.setattr(temp_directories, "temporary_directory", refuse)
    with pytest.raises(TemporaryDirectoryError, match="Unable to manage") as raised:
        with managed_run_directory():
            pytest.fail("context should not start")
    assert not raised.value.permission_denied
    assert "secret" not in str(raised.value)


def test_cleanup_denial_is_reported_without_fallback(monkeypatch, portable_tmp_path):
    class FakeOwner:
        def __enter__(self):
            return str(portable_tmp_path)

        def __exit__(self, exc_type, exc, tb):
            raise PortableTemporaryDirectoryError(
                "sensitive cleanup path", code="CLEANUP_INCOMPLETE",
                diagnostic={"category": "PermissionError"},
            )

    monkeypatch.setattr(temp_directories, "temporary_directory", lambda namespace: FakeOwner())
    with pytest.raises(TemporaryDirectoryError, match="PermissionError") as raised:
        with managed_run_directory():
            pass
    assert raised.value.permission_denied
    assert "sensitive cleanup path" not in str(raised.value)


def test_run_creation_does_not_fall_back_to_os_mkdir(monkeypatch):
    def refuse(_namespace):
        raise PortableTemporaryDirectoryError("denied", code="PERMISSION_DENIED")

    monkeypatch.setattr(temp_directories, "temporary_directory", refuse)
    mkdir = Mock(side_effect=AssertionError("fallback mkdir must not run"))
    monkeypatch.setattr(temp_directories.os, "mkdir", mkdir)
    with pytest.raises(TemporaryDirectoryError):
        with managed_run_directory():
            pytest.fail("context should not start")
    mkdir.assert_not_called()


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
