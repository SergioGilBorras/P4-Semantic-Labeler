"""Per-request temporary Codex workspaces backed by portable-tempdirs.

The owned run directory is cleaned after each Codex request. Only files created
inside that run are eligible for deletion; external caller-configured workspaces
and historical runs are never removed. Cleanup failures remain visible.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from portable_tempdirs import temporary_directory

TEMP_ROOT_NAME = "P4-Semantic-Labeler"


class TemporaryDirectoryError(RuntimeError):
    """Sanitized workspace error preserving the provider's legacy diagnostic flag."""

    def __init__(self, message: str, *, permission_denied: bool = False) -> None:
        super().__init__(message)
        self.permission_denied = permission_denied


def _raise_safe_directory_error(exc: OSError) -> None:
    denied = (
        isinstance(exc, PermissionError)
        or getattr(exc, "code", None) == "PERMISSION_DENIED"
        or getattr(exc, "diagnostic", {}).get("category") == "PermissionError"
    )
    message = (
        "PermissionError while managing temporary Codex directory"
        if denied else "Unable to manage temporary Codex directory"
    )
    raise TemporaryDirectoryError(message, permission_denied=denied) from None


@contextmanager
def managed_run_directory() -> Iterator[Path]:
    """Create a unique run root and clean it after this request.

    The managed root contains the generated workspace and bridge state. The
    context manager never detaches ownership or reuses a previous run.
    """
    try:
        owner = temporary_directory(TEMP_ROOT_NAME)
    except OSError as exc:
        _raise_safe_directory_error(exc)
    try:
        with owner as name:
            yield Path(name)
    except OSError as exc:
        # Cleanups are identity-checked by portable-tempdirs. Never attempt a
        # fallback recursive deletion if a filesystem operation is denied.
        _raise_safe_directory_error(exc)


def _validate_directory(path: Path, description: str) -> None:
    try:
        metadata = path.stat()
    except PermissionError:
        raise TemporaryDirectoryError(
            f"PermissionError while validating {description}", permission_denied=True
        ) from None
    except FileNotFoundError:
        raise TemporaryDirectoryError(f"{description} does not exist") from None
    except OSError:
        raise TemporaryDirectoryError(f"{description} is unavailable") from None
    if not stat.S_ISDIR(metadata.st_mode):
        raise TemporaryDirectoryError(f"{description} is not a directory")


def create_run_subdirectory(parent: Path, name: str) -> Path:
    """Create one named child directory without reusing an existing child."""
    if not isinstance(name, str) or not name or name in {".", ".."} or "/" in name or "\\" in name or Path(name).name != name:
        raise ValueError("Temporary subdirectory name must be a single path component")
    _validate_directory(parent, "temporary run directory")
    destination = parent / name
    try:
        os.mkdir(destination)
    except FileExistsError:
        raise TemporaryDirectoryError("Temporary subdirectory already exists") from None
    except PermissionError:
        raise TemporaryDirectoryError(
            "PermissionError while creating temporary subdirectory", permission_denied=True
        ) from None
    except OSError:
        raise TemporaryDirectoryError("Unable to create temporary subdirectory") from None
    return destination
