"""Create unique, persistent temporary workspaces without changing permissions."""

from __future__ import annotations

import os
import re
import secrets
import stat
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

TEMP_ROOT_NAME = "P4-Planning-Agent"
RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
MAX_COLLISION_ATTEMPTS = 100


class TemporaryDirectoryError(RuntimeError):
    """A safe diagnostic for a failure to create a managed temporary directory."""

    def __init__(self, message: str, *, permission_denied: bool = False) -> None:
        super().__init__(message)
        self.permission_denied = permission_denied


def _system_temp_root(system_name: str, environ: Mapping[str, str]) -> Path:
    if system_name == "nt":
        configured_root = environ.get("TEMP")
        if not configured_root:
            raise TemporaryDirectoryError("TEMP is not configured")
        return Path(configured_root)

    configured_root = environ.get("TMPDIR")
    return Path(configured_root) if configured_root else Path(tempfile.gettempdir())


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


def create_run_directory(
    *,
    environ: Mapping[str, str] | None = None,
    system_name: str | None = None,
    now: Callable[[], datetime] | None = None,
    token_hex: Callable[[int], str] | None = None,
) -> Path:
    """Create and return a unique directory under the platform temporary root.

    Directories are intentionally not deleted or reused. Each level is created
    with a single atomic ``os.mkdir`` operation, and collisions retry with a
    fresh random component.
    """
    environment = os.environ if environ is None else environ
    platform_name = os.name if system_name is None else system_name
    root = _system_temp_root(platform_name, environment)
    _validate_directory(root, "configured temporary root")

    managed_root = root / TEMP_ROOT_NAME
    try:
        os.mkdir(managed_root)
    except FileExistsError:
        _validate_directory(managed_root, "managed temporary root")
    except PermissionError:
        raise TemporaryDirectoryError(
            "PermissionError while creating managed temporary root", permission_denied=True
        ) from None
    except OSError:
        raise TemporaryDirectoryError(
            "Unable to create managed temporary root"
        ) from None

    clock = now or (lambda: datetime.now(timezone.utc))
    random_hex = token_hex or secrets.token_hex
    for _ in range(MAX_COLLISION_ATTEMPTS):
        timestamp = clock()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Temporary directory clock must return a timezone-aware datetime")
        run_id = f"{timestamp.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-{random_hex(4)}"
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Temporary directory identifier is invalid")
        destination = managed_root / run_id
        try:
            os.mkdir(destination)
            return destination
        except FileExistsError:
            continue
        except PermissionError:
            raise TemporaryDirectoryError(
                "PermissionError while creating temporary run directory",
                permission_denied=True,
            ) from None
        except OSError:
            raise TemporaryDirectoryError(
                "Unable to create temporary run directory"
            ) from None

    raise TemporaryDirectoryError("Unable to allocate a unique temporary run directory")
