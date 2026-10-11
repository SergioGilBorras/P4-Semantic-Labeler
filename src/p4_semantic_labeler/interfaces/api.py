"""FastAPI facade with capped bodies, optional auth and sanitized errors."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections import defaultdict, deque
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import InputLimitError, LabelerError, RequestValueError
from p4_semantic_labeler.core.file_utils import decode_text, validate_filename
from p4_semantic_labeler.core.models import (
    BatchRequest,
    BatchResult,
    Context,
    LabelRequest,
    LabelResult,
    Subject,
)
from p4_semantic_labeler.core.service import Labeler


class BodyLimitMiddleware:
    """ASGI-layer limit, independent of a possibly false Content-Length header."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > self.max_bytes:
                await self._too_large(send)
                return
        except ValueError:
            await self._too_large(send)
            return
        buffer = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            chunk = event.get("body", b"")
            if len(buffer) + len(chunk) > self.max_bytes:
                await self._too_large(send)
                return
            buffer.extend(chunk)
            if not event.get("more_body", False):
                break
        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(buffer), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _too_large(send: Any) -> None:
        body = b'{"error":{"code":"input_limit_exceeded","message":"Input exceeds configured limits"}}'
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})


def create_app(labeler: Labeler | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or (labeler.settings if labeler is not None else Settings.from_env())
    labeler = labeler or Labeler(settings=settings)
    app = FastAPI(
        title="P4 Semantic Labeler", version="0.1.0",
        description="Contextual label generation; mock mode is NOT a semantic AI provider.",
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.state.labeler = labeler
    app.state.rate_buckets = defaultdict(deque)
    app.state.rate_lock = asyncio.Lock()

    @app.exception_handler(LabelerError)
    async def labeler_error(_request: Request, exc: LabelerError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.public_message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default body could echo confidential context/source_code.
        fields = [
            {"loc": [str(part) for part in e.get("loc", ())], "type": e.get("type", "invalid")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Invalid request", "fields": fields}},
        )

    async def require_key(
        request: Request, authorization: str | None = Header(default=None)
    ) -> None:
        if settings.api_key:
            expected = "Bearer " + settings.api_key
            if authorization is None or not secrets.compare_digest(authorization, expected):
                from fastapi import HTTPException

                raise HTTPException(status_code=401, detail="Unauthorized")
        # Per-IP, per-process rolling window. Put a distributed gateway in front of production.
        addr = request.client.host if request.client else "unknown"
        async with app.state.rate_lock:
            now = time.monotonic()
            bucket = app.state.rate_buckets[addr]
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            if len(bucket) >= settings.rate_limit_rpm:
                from fastapi import HTTPException

                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            bucket.append(now)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "provider": labeler.provider.name}

    @app.post("/v1/labels", response_model=LabelResult, dependencies=[Depends(require_key)])
    async def label(request: LabelRequest) -> LabelResult:
        return await labeler.agenerate(request)

    @app.post("/v1/labels/batch", response_model=BatchResult, dependencies=[Depends(require_key)])
    async def batch(request: BatchRequest) -> BatchResult:
        return await labeler.agenerate_batch(request)

    @app.post("/v1/labels/file", response_model=LabelResult, dependencies=[Depends(require_key)])
    async def label_file(
        file: Annotated[UploadFile, File()],
        name: str = Form(...),
        kind: str = Form("document"),
        output_type: str = Form("summary"),
        min_chars: int = Form(1),
        max_chars: int = Form(160),
        style: str = Form("neutral"),
        language: str = Form("es"),
        purpose: str = Form(""),
        before: str = Form(""),
        after: str = Form(""),
    ) -> LabelResult:
        filename = file.filename or ""
        validate_filename(filename)
        data = bytearray()
        while chunk := await file.read(64 * 1024):
            data.extend(chunk)
            if len(data) > settings.max_file_bytes:
                raise InputLimitError()
        content = decode_text(bytes(data), filename, settings)
        fields = {"source_code": content} if filename.lower().endswith(".py") else {"text": content}
        fields.update({"purpose": purpose, "before": before, "after": after})
        try:
            context = Context(**fields)
            label_request = LabelRequest(
                subject=Subject(kind=kind, name=name), context=context,
                output_type=output_type, min_chars=min_chars,
                max_chars=max_chars, style=style, language=language,
            )
        except ValidationError as exc:
            raise RequestValueError() from exc
        return await labeler.agenerate(label_request)

    return app


app = create_app()
