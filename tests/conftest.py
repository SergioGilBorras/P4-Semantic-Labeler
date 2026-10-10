from __future__ import annotations

from pathlib import Path

import pytest
from portable_tempdirs import temporary_directory

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



@pytest.fixture
def portable_tmp_path():
    """Owned, isolated fixture avoiding pytest's global tmp_path machinery."""
    project_root = Path(__file__).resolve().parents[1]
    fixture_root = project_root / ".portable-test-workspaces"
    fixture_root.mkdir(exist_ok=True)
    owner = temporary_directory("SemanticTests", parent=fixture_root)
    try:
        yield owner.path
    finally:
        owner.cleanup()
