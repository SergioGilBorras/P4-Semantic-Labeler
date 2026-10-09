from __future__ import annotations

import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from p4_semantic_labeler import temp_directories
from p4_semantic_labeler.temp_directories import (
    TEMP_ROOT_NAME,
    TemporaryDirectoryError,
    create_run_directory,
    create_run_subdirectory,
)


@pytest.mark.parametrize(
    ("system_name", "environment_key"),
    [("nt", "TEMP"), ("posix", "TMPDIR")],
)
def test_creates_managed_root_and_run_directory(tmp_path, system_name, environment_key):
    parent = tmp_path / "temp-root"
    parent.mkdir()
    result = create_run_directory(
        environ={environment_key: str(parent)},
        system_name=system_name,
        now=lambda: datetime(2026, 10, 9, 17, 25, tzinfo=timezone.utc),
        token_hex=lambda byte_count: "a7f3c92d" if byte_count == 4 else "invalid",
    )

    assert result == parent / TEMP_ROOT_NAME / "20261009T172500Z-a7f3c92d"
    assert result.is_dir()


def test_run_directories_are_unique_and_identifier_uses_utc_and_random_hex(tmp_path):
    parent = tmp_path / "temp-root"
    parent.mkdir()
    instant = datetime(
        2026, 10, 9, 19, 25, tzinfo=timezone(timedelta(hours=2))
    )
    values = iter(("81bd4e20", "f12a73bc"))

    def token_hex(byte_count):
        assert byte_count == 4
        return next(values)

    def create():
        return create_run_directory(
            environ={"TEMP": str(parent)},
            system_name="nt",
            now=lambda: instant,
            token_hex=token_hex,
        )

    first = create()
    second = create()

    assert first.name == "20261009T172500Z-81bd4e20"
    assert second.name == "20261009T172500Z-f12a73bc"
    assert first != second


def test_existing_managed_root_is_reused_without_changing_permissions_or_environment(
    tmp_path, monkeypatch
):
    parent = tmp_path / "temp-root"
    parent.mkdir()
    managed_root = parent / TEMP_ROOT_NAME
    managed_root.mkdir()
    previous_mode = stat.S_IMODE(managed_root.stat().st_mode)
    previous_environment = os.environ.copy()
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: pytest.fail("Path.mkdir used"))

    result = create_run_directory(
        environ={"TEMP": str(parent)},
        system_name="nt",
        now=lambda: datetime(2026, 10, 9, 17, 26, 45, tzinfo=timezone.utc),
        token_hex=lambda _: "deadbeef",
    )

    assert result.is_dir()
    assert stat.S_IMODE(managed_root.stat().st_mode) == previous_mode
    assert os.environ.copy() == previous_environment


def test_collision_retries_without_reusing_existing_execution(tmp_path):
    parent = tmp_path / "temp-root"
    parent.mkdir()
    managed_root = parent / TEMP_ROOT_NAME
    managed_root.mkdir()
    existing = managed_root / "20261009T173010Z-a7f3c92d"
    existing.mkdir()
    marker = existing / "historical.txt"
    marker.write_text("keep", encoding="utf-8")
    values = iter(("a7f3c92d", "b8e4d03a"))

    result = create_run_directory(
        environ={"TEMP": str(parent)},
        system_name="nt",
        now=lambda: datetime(2026, 10, 9, 17, 30, 10, tzinfo=timezone.utc),
        token_hex=lambda _: next(values),
    )

    assert result.name == "20261009T173010Z-b8e4d03a"
    assert result != existing
    assert marker.read_text(encoding="utf-8") == "keep"


def test_permission_error_is_safe_and_does_not_change_environment(tmp_path, monkeypatch):
    parent = tmp_path / "temp-root"
    parent.mkdir()
    previous_environment = os.environ.copy()

    def fail_mkdir(_path):
        raise PermissionError("private path detail")

    monkeypatch.setattr(temp_directories.os, "mkdir", fail_mkdir)
    with pytest.raises(TemporaryDirectoryError, match="PermissionError") as error:
        create_run_directory(environ={"TEMP": str(parent)}, system_name="nt")

    assert str(tmp_path) not in str(error.value)
    assert "private path detail" not in str(error.value)
    assert os.environ.copy() == previous_environment


def test_invalid_or_missing_temporary_root_is_rejected(tmp_path):
    with pytest.raises(TemporaryDirectoryError, match="TEMP is not configured"):
        create_run_directory(environ={}, system_name="nt")
    with pytest.raises(TemporaryDirectoryError, match="does not exist"):
        create_run_directory(environ={"TEMP": str(tmp_path / "missing")}, system_name="nt")
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("x", encoding="utf-8")
    with pytest.raises(TemporaryDirectoryError, match="not a directory"):
        create_run_directory(environ={"TEMP": str(not_a_directory)}, system_name="nt")


def test_directory_identifier_matches_contract(tmp_path):
    parent = tmp_path / "temp-root"
    parent.mkdir()
    result = create_run_directory(
        environ={"TMPDIR": str(parent)},
        system_name="posix",
        now=lambda: datetime(2026, 10, 9, 17, 30, 10, tzinfo=timezone.utc),
        token_hex=lambda _: "0123abcd",
    )
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", result.name)


def test_run_subdirectory_is_created_with_os_mkdir(tmp_path, monkeypatch):
    parent = tmp_path / "run"
    parent.mkdir()
    mkdir = os.mkdir
    created = []

    def record_mkdir(path):
        created.append(Path(path))
        mkdir(path)

    monkeypatch.setattr(temp_directories.os, "mkdir", record_mkdir)
    result = create_run_subdirectory(parent, "bridge-state")

    assert result == parent / "bridge-state"
    assert result.is_dir()
    assert created == [result]


def test_run_subdirectory_permission_error_is_safe(tmp_path, monkeypatch):
    parent = tmp_path / "run"
    parent.mkdir()

    def fail_mkdir(_path):
        raise PermissionError("private path detail")

    monkeypatch.setattr(temp_directories.os, "mkdir", fail_mkdir)
    with pytest.raises(TemporaryDirectoryError, match="PermissionError") as error:
        create_run_subdirectory(parent, "bridge-state")

    assert error.value.permission_denied
    assert "private path detail" not in str(error.value)
