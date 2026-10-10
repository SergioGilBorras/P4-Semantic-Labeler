"""Application-specific compatibility facade for persistent Codex workspaces.

New run roots are created and self-checked by portable-tempdirs. The owner is
explicitly detached so existing run evidence is retained without leaking
Windows handles or POSIX descriptors. Historical run directories are untouched.
Only fixed, caller-authorized child paths use the compatibility mkdir helper.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from portable_tempdirs import (
    TemporaryDirectoryError as PortableTemporaryDirectoryError,
    temporary_directory,
)

TEMP_ROOT_NAME = "P4-Semantic-Labeler"


class TemporaryDirectoryError(RuntimeError):
    """Sanitized workspace error preserving the provider's legacy diagnostic flag."""

    def __init__(self, message: str, *, permission_denied: bool = False) -> None:
        super().__init__(message)
        self.permission_denied = permission_denied


def create_run_directory() -> Path:
    """Create a unique, persistent workspace run under the platform temp root.

    No automatic cleanup is performed. The portable-tempdirs owner is detached
    immediately so the run directory outlives this call without open handles.
    """
    try:
        return temporary_directory(TEMP_ROOT_NAME).detach()
    except PortableTemporaryDirectoryError as exc:
        denied = exc.code == "PERMISSION_DENIED" or (
            exc.diagnostic.get("category") == "PermissionError"
        )
        message = (
            "PermissionError while creating managed temporary directory"
            if denied else "Unable to create managed temporary directory"
        )
        raise TemporaryDirectoryError(message, permission_denied=denied) from None
    except PermissionError:
        raise TemporaryDirectoryError(
            "PermissionError while creating managed temporary directory", permission_denied=True
        ) from None
    except OSError:
        raise TemporaryDirectoryError("Unable to create managed temporary directory") from None


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
    if not isinstance(name, str) or not name or name in {".", ".."} or "/" in name or "\\\\" in name or Path(name).name != name:
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
