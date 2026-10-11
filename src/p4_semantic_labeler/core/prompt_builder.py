"""Prompt construction using separately versioned UTF-8 runtime templates."""

from functools import lru_cache
import json
from pathlib import Path
from string import Template

from p4_semantic_labeler.core.context_builder import BuiltContext
from p4_semantic_labeler.core.models import LabelRequest
from p4_semantic_labeler.providers.base import ProviderPrompt


@lru_cache(maxsize=4)
def read_prompt(name: str) -> str:
    if name not in {"label_system.txt", "label_reduction.txt", "codex_data_delimiter.txt"}:
        raise ValueError("unsupported prompt template")
    text = (Path(__file__).resolve().parents[1] / "prompts" / name).read_text(encoding="utf-8")
    if not text.strip():
        raise RuntimeError("prompt template is empty")
    return text.strip()


class PromptBuilder:
    def build(
        self, request: LabelRequest, context: BuiltContext, *, previous: str | None = None
    ) -> ProviderPrompt:
        instruction = Template(read_prompt("label_system.txt")).substitute(
            output_type=request.output_type,
            style=request.style,
            language=request.language,
            min_chars=request.min_chars,
            max_chars=request.max_chars,
        )
        data: dict[str, object] = {"reference_data": context.fields}
        if previous is not None:
            instruction += " " + read_prompt("label_reduction.txt")
            data["previous_candidate_untrusted"] = previous
        return ProviderPrompt(
            system=instruction,
            user=json.dumps(data, ensure_ascii=False),
            subject_name=request.subject.name,
            output_type=request.output_type,
        )
