"""Text-only file handling with strict byte limits and opt-in MCP roots."""

from __future__ import annotations

from pathlib import Path

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import InputLimitError, RequestValueError

ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".rst", ".py", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".csv"})


def validate_filename(filename: str) -> str:
    if not filename or Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise RequestValueError("Unsupported file extension")
    return filename


def decode_text(data: bytes, filename: str, settings: Settings) -> str:
    validate_filename(filename)
    if len(data) > settings.max_file_bytes:
        raise InputLimitError()
    if b"\x00" in data:
        raise RequestValueError("Binary file not accepted")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RequestValueError("Only UTF-8 text files are accepted") from exc


def read_local_file(path: Path, settings: Settings) -> str:
    validate_filename(path.name)
    if not path.is_file():
        raise RequestValueError("File must exist and be a regular file")
    if path.stat().st_size > settings.max_file_bytes:
        raise InputLimitError()
    with path.open("rb") as handle:
        data = handle.read(settings.max_file_bytes + 1)
    return decode_text(data, path.name, settings)


def read_authorized_file(path: str, settings: Settings) -> tuple[str, str]:
    if not settings.mcp_roots:
        raise RequestValueError("MCP file access disabled: configure allowed roots")
    try:
        requested = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RequestValueError("Requested file is unavailable") from exc
    if not any(requested.is_relative_to(root) for root in settings.mcp_roots):
        raise RequestValueError("Requested file is outside authorized roots")
    return requested.name, read_local_file(requested, settings)
