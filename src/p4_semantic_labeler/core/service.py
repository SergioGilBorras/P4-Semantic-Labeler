"""Only business entry point: every interface delegates to Labeler."""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.context_builder import ContextBuilder
from p4_semantic_labeler.core.errors import (
    LabelerError,
    ProviderFailure,
    ProviderTimeout,
    RequestValueError,
)
from p4_semantic_labeler.core.models import (
    BatchItem,
    BatchRequest,
    BatchResult,
    ErrorDetail,
    LabelRequest,
    LabelResult,
)
from p4_semantic_labeler.core.output_validator import normalize_label, truncate_label
from p4_semantic_labeler.core.prompt_builder import PromptBuilder
from p4_semantic_labeler.providers.base import LabelProvider, ProviderPrompt
from p4_semantic_labeler.providers.factory import create_provider


class Labeler:
    def __init__(
        self, provider: LabelProvider | None = None, settings: Settings | None = None
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.provider = provider or create_provider(self.settings)
        self.context_builder = ContextBuilder(self.settings)
        self.prompt_builder = PromptBuilder()

    async def _call_provider(self, prompt: ProviderPrompt) -> str:
        try:
            response = await asyncio.wait_for(
                self.provider.generate(prompt), timeout=self.settings.provider_timeout_seconds
            )
            return normalize_label(response.text)
        except TimeoutError as exc:
            raise ProviderTimeout() from exc
        except LabelerError:
            raise
        except Exception as exc:
            # Keep sensitive provider traceback/data out of the public response.
            raise ProviderFailure() from exc

    async def agenerate(self, request: LabelRequest) -> LabelResult:
        if not self.settings.min_chars <= request.max_chars <= self.settings.max_chars:
            raise RequestValueError("max_chars outside configured range")
        built = self.context_builder.build(request)
        warnings = list(built.warnings)
        if self.provider.name == "mock":
            warnings.append("mock_provider: synthetic name formatting, not semantic AI")
        prompt = self.prompt_builder.build(request, built)
        label = await self._call_provider(prompt)
        if len(label) > request.max_chars:
            for _ in range(self.settings.reduction_attempts):
                prompt = self.prompt_builder.build(request, built, previous=label)
                label = await self._call_provider(prompt)
                if len(label) <= request.max_chars:
                    warnings.append("length_reduced_by_provider")
                    break
        if len(label) > request.max_chars:
            label = truncate_label(label, request.max_chars)
            warnings.append("output_truncated: meaning may be incomplete")
        return LabelResult(
            label=label,
            char_count=len(label),
            language=request.language,
            style=request.style,
            output_type=request.output_type,
            provider=self.provider.name,
            warnings=warnings,
        )

    def generate(self, request: LabelRequest) -> LabelResult:
        """Blocking library convenience method (outside an existing event loop)."""
        return asyncio.run(self.agenerate(request))

    async def agenerate_batch(self, request: BatchRequest) -> BatchResult:
        if len(request.items) > self.settings.max_batch_items:
            raise RequestValueError("too many batch items")
        semaphore = asyncio.Semaphore(self.settings.batch_concurrency)

        async def run_item(index: int, item: LabelRequest | dict) -> BatchItem:
            async with semaphore:
                try:
                    validated = LabelRequest.model_validate(item)
                    return BatchItem(index=index, result=await self.agenerate(validated))
                except LabelerError as exc:
                    return BatchItem(
                        index=index,
                        error=ErrorDetail(code=exc.code, message=exc.public_message),
                    )
                except ValidationError:
                    return BatchItem(
                        index=index,
                        error=ErrorDetail(code="validation_error", message="Invalid batch item"),
                    )

        items = await asyncio.gather(
            *(run_item(index, item) for index, item in enumerate(request.items))
        )
        ok = sum(item.result is not None for item in items)
        return BatchResult(items=items, success_count=ok, error_count=len(items) - ok)
