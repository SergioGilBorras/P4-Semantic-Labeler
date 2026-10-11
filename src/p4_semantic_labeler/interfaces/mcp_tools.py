"""Testable SDK-independent MCP tool handlers; no arbitrary file access."""

from __future__ import annotations

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.file_utils import read_authorized_file
from p4_semantic_labeler.core.models import BatchRequest, Context, LabelRequest, Subject
from p4_semantic_labeler.core.service import Labeler


class MCPTools:
    def __init__(self, labeler: Labeler, settings: Settings) -> None:
        self.labeler = labeler
        self.settings = settings

    async def generate_label(
        self,
        name: str,
        kind: str = "concept",
        documentation: str = "",
        source_code: str = "",
        max_chars: int = 80,
        style: str = "neutral",
        language: str = "es",
        min_chars: int = 1,
    ) -> dict:
        req = LabelRequest(
            subject=Subject(name=name, kind=kind),
            context=Context(documentation=documentation, source_code=source_code),
            output_type="title", min_chars=min_chars,
            min_chars=min_chars, max_chars=max_chars, style=style, language=language,
        )
        return (await self.labeler.agenerate(req)).model_dump()

    async def generate_summary(
        self,
        name: str,
        text: str = "",
        max_chars: int = 160,
        style: str = "neutral",
        language: str = "es",
        min_chars: int = 1,
    ) -> dict:
        req = LabelRequest(
            subject=Subject(name=name, kind="document"),
            context=Context(text=text), output_type="summary",
            min_chars=min_chars, max_chars=max_chars, style=style, language=language,
        )
        return (await self.labeler.agenerate(req)).model_dump()

    async def generate_labels_batch(self, items: list[dict]) -> dict:
        req = BatchRequest(items=items)
        return (await self.labeler.agenerate_batch(req)).model_dump()

    async def summarize_file(
        self,
        path: str,
        name: str = "document",
        max_chars: int = 160,
        style: str = "neutral",
        language: str = "es",
        min_chars: int = 1,
    ) -> dict:
        filename, data = read_authorized_file(path, self.settings)
        context = Context(**({"source_code": data} if filename.endswith(".py") else {"text": data}))
        req = LabelRequest(
            subject=Subject(kind="document", name=name), context=context,
            output_type="summary", max_chars=max_chars, style=style, language=language,
        )
        return (await self.labeler.agenerate(req)).model_dump()
