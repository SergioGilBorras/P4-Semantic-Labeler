"""Budgeted contextual extraction. Parsing Python AST never executes user code."""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import InputLimitError
from p4_semantic_labeler.core.models import LabelRequest


@dataclass(frozen=True)
class BuiltContext:
    fields: dict[str, str]
    warnings: list[str]


def _python_facts(source: str, name: str) -> str:
    try:
        tree = ast.parse(textwrap.dedent(source))
    except (SyntaxError, ValueError, RecursionError):
        return source
    last_name = name.rsplit(".", 1)[-1]
    selected = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == last_name
        ),
        None,
    )
    if selected is None:
        return source
    lines: list[str] = []
    if isinstance(selected, (ast.FunctionDef, ast.AsyncFunctionDef)):
        first_line = source.splitlines()[selected.lineno - 1].strip()
        lines.append(f"Signature or declaration: {first_line}")
    else:
        lines.append(f"Class: {selected.name}")
    docstring = ast.get_docstring(selected)
    if docstring:
        lines.append(f"Docstring: {docstring}")
    calls = []
    for node in ast.walk(selected):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    if calls:
        lines.append("Calls: " + ", ".join(dict.fromkeys(calls[:20])))
    segment = ast.get_source_segment(textwrap.dedent(source), selected)
    if segment:
        lines.append("Code excerpt:\n" + segment)
    return "\n".join(lines) or source


class ContextBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, request: LabelRequest) -> BuiltContext:
        if len(request.subject.name) > self.settings.max_subject_chars:
            raise InputLimitError()
        context = request.context
        fields = request.subject.model_dump(exclude_none=True)
        raw = context.model_dump(exclude_none=True) if context else {}
        total_chars = len(request.subject.model_dump_json()) + sum(len(str(v)) for v in raw.values())
        if total_chars > self.settings.max_input_chars:
            raise InputLimitError()
        out: dict[str, str] = {"subject_" + k: str(v) for k, v in fields.items()}
        warnings: list[str] = []
        if not any(raw.values()):
            warnings.append("context_missing: only the subject is available")
        budgets = {
            "purpose": 450,
            "title": 300,
            "document_type": 150,
            "documentation": 3_500,
            "text": 3_500,
            "source_code": 6_000,
            "before": 1_000,
            "after": 1_000,
        }
        remaining = self.settings.max_context_chars
        for field in (
            "purpose", "title", "document_type", "documentation", "text",
            "source_code", "before", "after",
        ):
            value = raw.get(field)
            if not value:
                continue
            if field == "source_code" and request.subject.kind in {"function", "method", "class"}:
                value = _python_facts(str(value), request.subject.name)
            limit = min(budgets[field], remaining)
            if limit == 0:
                warnings.append(f"context_omitted: {field}")
                continue
            clipped = str(value)[:limit]
            if len(clipped) < len(value):
                warnings.append(f"context_trimmed: {field}")
            out[field] = clipped
            remaining -= len(clipped)
        # Approximation, not an actual tokenizer. Fail closed instead of overfilling.
        token_estimate = (sum(len(k) + len(v) for k, v in out.items()) + 2) // 3
        if token_estimate > self.settings.max_prompt_tokens_estimate:
            raise InputLimitError()
        return BuiltContext(fields=out, warnings=warnings)
