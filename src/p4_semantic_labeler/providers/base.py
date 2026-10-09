"""Provider-neutral contract. No dependency on any AI SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderPrompt:
    system: str
    user: str
    # This is mock/test-only data, not required by real provider implementations.
    subject_name: str
    output_type: str


@dataclass(frozen=True)
class ProviderResponse:
    text: str


class LabelProvider(Protocol):
    name: str

    async def generate(self, prompt: ProviderPrompt) -> ProviderResponse:
        """Call a real provider or explicit test double; propagate provider failures."""
        ...
