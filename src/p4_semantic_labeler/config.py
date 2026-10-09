"""Small, dependency-free configuration; no secrets are logged."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    provider: str = "disabled"
    min_chars: int = 1
    max_chars: int = 300
    max_request_bytes: int = 1_048_576
    max_file_bytes: int = 524_288
    max_subject_chars: int = 256
    max_context_chars: int = 12_000
    max_input_chars: int = 48_000
    max_prompt_tokens_estimate: int = 5_000
    max_batch_items: int = 30
    batch_concurrency: int = 4
    provider_timeout_seconds: float = 20.0
    reduction_attempts: int = 1
    api_key: str | None = None
    rate_limit_rpm: int = 60
    mcp_roots: tuple[Path, ...] = ()
    codex_workspace: Path | None = None

    def __post_init__(self) -> None:
        if self.codex_workspace is not None:
            if not self.codex_workspace.is_absolute() or not self.codex_workspace.is_dir():
                raise ValueError("codex_workspace must be an existing absolute directory")
        if self.provider not in {"disabled", "mock", "codex"}:
            raise ValueError("provider must be disabled, mock or codex")
        if not 1 <= self.min_chars <= self.max_chars <= 10_000:
            raise ValueError("invalid min/max character limits")
        if not 1 <= self.max_file_bytes < self.max_request_bytes:
            raise ValueError("max_file_bytes must be smaller than max_request_bytes")
        if min(self.max_subject_chars, self.max_context_chars, self.max_input_chars) < 1:
            raise ValueError("input limits must be positive")
        if self.max_prompt_tokens_estimate < 50:
            raise ValueError("max_prompt_tokens_estimate must be >= 50")
        if min(self.max_batch_items, self.batch_concurrency) < 1:
            raise ValueError("batch limits must be positive")
        if self.rate_limit_rpm < 1:
            raise ValueError("rate limit must be positive")
        if self.provider_timeout_seconds <= 0 or self.reduction_attempts < 0:
            raise ValueError("invalid provider timeouts / retries")

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        roots = tuple(
            Path(p).expanduser().resolve()
            for p in os.getenv("P4_LABELER_MCP_ROOTS", "").split(os.pathsep)
            if p.strip()
        )
        return cls(
            provider=os.getenv("P4_LABELER_PROVIDER", defaults.provider),
            min_chars=int(os.getenv("P4_LABELER_MIN_CHARS", defaults.min_chars)),
            max_subject_chars=int(
                os.getenv("P4_LABELER_MAX_SUBJECT_CHARS", defaults.max_subject_chars)
            ),
            max_chars=int(os.getenv("P4_LABELER_MAX_CHARS", defaults.max_chars)),
            max_request_bytes=int(os.getenv("P4_LABELER_MAX_REQUEST_BYTES", defaults.max_request_bytes)),
            max_file_bytes=int(os.getenv("P4_LABELER_MAX_FILE_BYTES", defaults.max_file_bytes)),
            max_context_chars=int(os.getenv("P4_LABELER_MAX_CONTEXT_CHARS", defaults.max_context_chars)),
            max_input_chars=int(os.getenv("P4_LABELER_MAX_INPUT_CHARS", defaults.max_input_chars)),
            max_prompt_tokens_estimate=int(
                os.getenv("P4_LABELER_MAX_PROMPT_TOKENS_ESTIMATE", defaults.max_prompt_tokens_estimate)
            ),
            max_batch_items=int(os.getenv("P4_LABELER_MAX_BATCH_ITEMS", defaults.max_batch_items)),
            batch_concurrency=int(
                os.getenv("P4_LABELER_BATCH_CONCURRENCY", defaults.batch_concurrency)
            ),
            provider_timeout_seconds=float(
                os.getenv("P4_LABELER_PROVIDER_TIMEOUT", defaults.provider_timeout_seconds)
            ),
            reduction_attempts=int(
                os.getenv("P4_LABELER_REDUCTION_ATTEMPTS", defaults.reduction_attempts)
            ),
            api_key=os.getenv("P4_LABELER_API_KEY") or None,
            rate_limit_rpm=int(os.getenv("P4_LABELER_RATE_LIMIT_RPM", defaults.rate_limit_rpm)),
            mcp_roots=roots,
            codex_workspace=(
                Path(os.environ["P4_LABELER_CODEX_WORKSPACE"]).expanduser().resolve()
                if os.getenv("P4_LABELER_CODEX_WORKSPACE") else None
            ),
        )
