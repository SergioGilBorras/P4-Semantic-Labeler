"""Contract tests: exercise the confirmed P4-Codex-Bridge 1.0 public surface.

These use a facade double so CI never invokes paid/external Codex inference.
"""
from __future__ import annotations

import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import ProviderFailure, ProviderTimeout
from p4_semantic_labeler.core.models import LabelRequest, Subject
from p4_semantic_labeler.core.service import Labeler


@pytest.fixture
def fake_bridge(monkeypatch):
    module = types.ModuleType("p4_codex_bridge")
    module.SandboxMode = SimpleNamespace(READ_ONLY="read-only")
    module.ApprovalPolicy = SimpleNamespace(NEVER="never")
    module.ProjectTrust = SimpleNamespace(TRUSTED="TRUSTED")
    module.CodexPermissions = lambda sandbox, approval_policy: SimpleNamespace(
        sandbox=sandbox, approval_policy=approval_policy
    )
    module.RunSecurityPolicy = lambda **kwargs: SimpleNamespace(**kwargs)
    module.BridgeTimeoutError = type("BridgeTimeoutError", (TimeoutError,), {})
    module.AuthenticationError = type("AuthenticationError", (RuntimeError,), {})
    module.CapabilityUnavailableError = type("CapabilityUnavailableError", (RuntimeError,), {})
    module.ServiceUnavailableError = type("ServiceUnavailableError", (RuntimeError,), {})
    module.RunSecurityRejectedError = type("RunSecurityRejectedError", (RuntimeError,), {})
    calls = []
    response = SimpleNamespace(ok=True, content="Validar pedidos pendientes", error=None)

    class Bridge:
        def __init__(self, *, allowed_roots):
            calls.append(("constructor", allowed_roots))

        def run(self, prompt, **kwargs):
            calls.append(("run", prompt, kwargs))
            if isinstance(response.error, BaseException):
                raise response.error
            return response

    module.CodexBridge = Bridge
    monkeypatch.setattr("p4_semantic_labeler.providers.codex_bridge.importlib.import_module",
                        lambda name: module)
    return calls, response


@pytest.mark.asyncio
async def test_codex_frozen_public_interface_with_accepted_mcp_risk(fake_bridge):
    calls, response = fake_bridge
    settings = Settings(provider="codex", provider_timeout_seconds=5)
    labeler = Labeler(settings=settings)
    request = LabelRequest(subject=Subject(name="process_pending_orders"),
                           context={"documentation": "Validate pending orders"},
                           max_chars=45, language="es")
    result = await labeler.agenerate(request)
    assert result.label == response.content and result.provider == "codex"
    assert [call[0] for call in calls] == ["constructor", "run"]
    assert len(calls[0][1]) == 1
    assert Path(calls[0][1][0]).is_dir()
    _, prompt, kwargs = calls[1]
    assert '"documentation"' in prompt
    assert "Validate pending orders" in prompt
    assert kwargs["profile"] == "analysis"
    assert kwargs["config_policy"] == "isolated"
    assert kwargs["capture_last_message"] is True
    assert kwargs["permissions"].sandbox == "read-only"
    assert kwargs["permissions"].approval_policy == "never"
    policy = kwargs["security_policy"]
    assert policy.project_trust == "TRUSTED"
    assert policy.allow_external_mcps
    assert policy.allow_side_effect_mcps
    assert policy.explicit_risk_acknowledgement
    assert kwargs["timeout_seconds"] == 5


@pytest.mark.asyncio
async def test_codex_error_results_are_not_false_success(fake_bridge):
    _, response = fake_bridge
    response.ok = False
    response.content = "secret provider text"
    response.error = {"code": "CODEX_PROCESS_FAILED", "message": "SECRET"}
    with pytest.raises(ProviderFailure):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="example")))


@pytest.mark.asyncio
async def test_codex_timeout_result(fake_bridge):
    _, response = fake_bridge
    response.ok = False
    response.error = {"code": "CODEX_TIMEOUT", "message": "SECRET"}
    with pytest.raises(ProviderTimeout):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="example")))


@pytest.mark.asyncio
async def test_codex_authentication_error(fake_bridge):
    _, response = fake_bridge
    response.error = RuntimeError("not authorized")
    with pytest.raises(ProviderFailure):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="example")))


@pytest.mark.asyncio
async def test_codex_uses_configured_existing_workspace(fake_bridge, tmp_path):
    calls, _ = fake_bridge
    config = Settings(provider="codex", codex_workspace=tmp_path)
    await Labeler(settings=config).agenerate(LabelRequest(subject=Subject(name="example")))
    assert calls[0] == ("constructor", [str(tmp_path)])
