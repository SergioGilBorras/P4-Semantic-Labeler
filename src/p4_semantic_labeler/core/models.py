"""Public wire models shared by Python, HTTP, CLI and MCP."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Subject(StrictModel):
    kind: str = Field(default="concept", min_length=1, max_length=64, pattern=r"^[\w.-]+$")
    name: str = Field(min_length=1, max_length=256)
    module: str | None = Field(default=None, max_length=256)
    class_name: str | None = Field(default=None, max_length=256)
    signature: str | None = Field(default=None, max_length=1_024)


class Context(StrictModel):
    documentation: str | None = None
    source_code: str | None = None
    text: str | None = None
    before: str | None = None
    after: str | None = None
    purpose: str | None = None
    title: str | None = None
    document_type: str | None = None


class LabelRequest(StrictModel):
    subject: Subject
    context: Context | None = None
    output_type: Literal["title", "summary"] = "title"
    min_chars: int = Field(default=1, ge=1, le=10_000)  # Preferred only; not a hard output bound.
    max_chars: int = Field(default=80, ge=1, le=10_000)
    style: str = Field(default="neutral", min_length=1, max_length=64, pattern=r"^[\w-]+$")
    language: str = Field(default="es", min_length=2, max_length=35)

    @model_validator(mode="after")
    def valid_preferred_range(self) -> "LabelRequest":
        if self.min_chars > self.max_chars:
            raise ValueError("min_chars must not exceed max_chars")
        return self

    @field_validator("language")
    @classmethod
    def language_code(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value):
            raise ValueError("language must be a valid-looking BCP 47 language tag")
        return value


class LabelResult(StrictModel):
    label: str
    char_count: int
    language: str
    style: str
    output_type: Literal["title", "summary"]
    provider: str
    warnings: list[str] = Field(default_factory=list)


class BatchRequest(StrictModel):
    # Admit dict payloads so invalid items do not poison an entire batch.
    items: list[LabelRequest | dict[str, Any]] = Field(min_length=1)


class ErrorDetail(StrictModel):
    code: str
    message: str


class BatchItem(StrictModel):
    index: int
    result: LabelResult | None = None
    error: ErrorDetail | None = None


class BatchResult(StrictModel):
    items: list[BatchItem]
    success_count: int
    error_count: int
