from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import ProviderUnavailable
from p4_semantic_labeler.providers.base import LabelProvider
from p4_semantic_labeler.providers.codex_bridge import CodexBridgeProvider
from p4_semantic_labeler.providers.mock import MockProvider


class DisabledProvider:
    name = "disabled"

    async def generate(self, prompt):  # type: ignore[no-untyped-def]
        raise ProviderUnavailable()


def create_provider(settings: Settings) -> LabelProvider:
    if settings.provider == "mock":
        return MockProvider()
    if settings.provider == "codex":
        return CodexBridgeProvider(settings)
    return DisabledProvider()
