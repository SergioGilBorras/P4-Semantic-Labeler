"""Deterministic *non-AI* demonstration provider; never a semantic oracle."""

from __future__ import annotations

import re

from p4_semantic_labeler.providers.base import ProviderPrompt, ProviderResponse


class MockProvider:
    name = "mock"

    async def generate(self, prompt: ProviderPrompt) -> ProviderResponse:
        name = prompt.subject_name
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
        spaced = re.sub(r"[_\-.]+", " ", spaced).strip()
        return ProviderResponse(text=spaced or name)
