from __future__ import annotations

from fastapi.testclient import TestClient

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.service import Labeler
from p4_semantic_labeler.interfaces.api import create_app


def payload():
    return {"subject": {"kind": "function", "name": "calculate_total"},
            "context": {"documentation": "Calculates total from line items."},
            "max_chars": 20, "language": "en", "style": "neutral"}


def test_http_contract_health_openapi(settings):
    with TestClient(create_app(Labeler(settings=settings), settings)) as client:
        assert client.get("/health").json()["provider"] == "mock"
        response = client.post("/v1/labels", json=payload())
        assert response.status_code == 200
        assert response.json()["label"] == "calculate total"
        schema = client.get("/openapi.json").json()
        assert "/v1/labels/batch" in schema["paths"]
        assert "/v1/labels/file" in schema["paths"]


def test_http_validation_not_leaking_input(settings):
    with TestClient(create_app(settings=settings)) as client:
        response = client.post("/v1/labels", json={"subject": {"name": "PRIVATE", "oops": "SECRETDATA"}})
        assert response.status_code == 422
        assert "SECRETDATA" not in response.text
        assert "PRIVATE" not in response.text


def test_http_file_and_rejection(settings):
    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/v1/labels/file", data={"name": "Example", "max_chars": "25"},
            files={"file": ("file.md", b"# Docs\nMeaningful description", "text/markdown")})
        assert response.status_code == 200
        assert response.json()["provider"] == "mock"
        rejected = client.post(
            "/v1/labels/file", data={"name": "x"},
            files={"file": ("secret.exe", b"hello", "application/octet-stream")})
        assert rejected.status_code == 422
        big = client.post(
            "/v1/labels/file", data={"name": "x"},
            files={"file": ("huge.txt", b"a" * (settings.max_file_bytes + 1))})
        assert big.status_code == 413


def test_http_cap_auth_batch():
    settings = Settings(provider="mock", max_request_bytes=1000, max_file_bytes=500, api_key="token123")
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/v1/labels", json=payload()).status_code == 401
        auth = {"Authorization": "Bearer token123"}
        assert client.post("/v1/labels", json=payload(), headers=auth).status_code == 200
        oversize = client.post("/v1/labels", content=b"X" * 2000, headers=auth)
        assert oversize.status_code == 413
        batch = client.post("/v1/labels/batch", json={"items": [payload(), payload()]}, headers=auth)
        assert batch.json()["success_count"] == 2


def test_http_provider_down_not_200(settings):
    class Down:
        name = "down"

        async def generate(self, prompt):
            raise RuntimeError("private")

    with TestClient(create_app(Labeler(Down(), settings), settings)) as client:
        response = client.post("/v1/labels", json=payload())
        assert response.status_code == 502
        assert "private" not in response.text


def test_http_rate_limit_and_invalid_file_form():
    cfg = Settings(provider="mock", rate_limit_rpm=1)
    with TestClient(create_app(settings=cfg)) as client:
        assert client.post("/v1/labels", json=payload()).status_code == 200
        assert client.post("/v1/labels", json=payload()).status_code == 429
    with TestClient(create_app(settings=Settings(provider="mock"))) as client:
        response = client.post(
            "/v1/labels/file", data={"name": "Test", "output_type": "not-valid"},
            files={"file": ("data.txt", b"sensitive", "text/plain")},
        )
        assert response.status_code == 422
        assert "sensitive" not in response.text
