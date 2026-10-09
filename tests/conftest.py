from __future__ import annotations

import pytest

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.service import Labeler
from p4_semantic_labeler.providers.base import ProviderResponse


class StubProvider:
    name = "stub"

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts = []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        return ProviderResponse(self.responses.pop(0) if self.responses else "Generated")


@pytest.fixture
def settings():
    return Settings(provider="mock", provider_timeout_seconds=0.2)


@pytest.fixture
def labeler(settings):
    return Labeler(settings=settings)


@pytest.fixture
def stub_class():
    return StubProvider
